"""Stateless, signed-cookie sessions.

The container runs ``uvicorn --workers 4`` (see Dockerfile). A server-side
session store would therefore live in four separate processes and users would be
logged out at random as requests bounce between workers. Sessions are instead
self-contained signed cookies, so any worker can validate any request.

That makes the signing key shared state: it must be identical in every worker.
It is resolved once at startup from ``AUTH_SECRET_KEY``, ``AUTH_SECRET_FILE`` or
a generated file inside the persistent data directory. Generating a key per
process is the classic failure mode here (login appears to work, then loops), so
if no key can be established the application refuses to start rather than
falling back to a random one.
"""

import logging
import os
import secrets
import time

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .models import User

logger = logging.getLogger(__name__)

SECRET_FILENAME = ".auth_secret"
_SECRET_BYTES = 32

# Another worker may have created the file a moment ago but not finished
# writing it. Bounded retry rather than a single read.
_READ_ATTEMPTS = 50
_READ_DELAY_SECONDS = 0.02


def _read_secret(path: str) -> str:
    for _ in range(_READ_ATTEMPTS):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                value = handle.read().strip()
            if value:
                return value
        except OSError:
            pass
        time.sleep(_READ_DELAY_SECONDS)
    return ""


def _load_or_create_secret(data_dir: str) -> str:
    """Return a stable secret, creating it on first boot.

    ``O_CREAT | O_EXCL`` makes the winner of a multi-worker startup race
    unambiguous; the losers re-read the winner's file.
    """
    path = os.path.join(data_dir, SECRET_FILENAME)

    existing = _read_secret(path)
    if existing:
        return existing

    try:
        os.makedirs(data_dir, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"AUTH_ENABLED is set but the data directory {data_dir!r} is not writable "
            f"({exc}). Set AUTH_SECRET_KEY or AUTH_SECRET_FILE instead."
        ) from exc

    candidate = secrets.token_urlsafe(_SECRET_BYTES)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        # Lost the race: another worker is creating it.
        value = _read_secret(path)
        if not value:
            raise RuntimeError(f"Could not read the session secret at {path!r}")
        return value
    except OSError as exc:
        raise RuntimeError(
            f"AUTH_ENABLED is set but the session secret file {path!r} could not be created "
            f"({exc}). Set AUTH_SECRET_KEY or AUTH_SECRET_FILE instead."
        ) from exc

    try:
        os.write(fd, candidate.encode("utf-8"))
    finally:
        os.close(fd)
    return candidate


def resolve_secret(cfg) -> str:
    """Resolve the cookie signing key, in order of operator preference."""
    if cfg.SECRET_KEY:
        return cfg.SECRET_KEY

    if cfg.SECRET_FILE:
        if not os.path.exists(cfg.SECRET_FILE):
            raise RuntimeError(f"AUTH_SECRET_FILE {cfg.SECRET_FILE!r} does not exist")
        value = _read_secret(cfg.SECRET_FILE)
        if not value:
            raise RuntimeError(f"AUTH_SECRET_FILE {cfg.SECRET_FILE!r} is empty")
        return value

    return _load_or_create_secret(cfg.data_dir())


class SessionManager:
    """Issues and validates session cookies."""

    SALT = "drui.auth.session"

    # The OIDC login handshake (state, nonce, PKCE verifier) is held in a short
    # lived signed cookie rather than in memory. In-memory state would break
    # across uvicorn workers: the redirect back from the identity provider can
    # land on a different worker than the one that started the flow.
    HANDSHAKE_SALT = "drui.auth.handshake"
    HANDSHAKE_COOKIE = "drui_oidc"
    HANDSHAKE_MAX_AGE = 600

    def __init__(self, secret: str, cookie_name: str = "drui_session", max_age: int = 43200):
        self._serializer = URLSafeTimedSerializer(secret, salt=self.SALT)
        self._handshake = URLSafeTimedSerializer(secret, salt=self.HANDSHAKE_SALT)
        self.cookie_name = cookie_name
        self.max_age = max_age

    @classmethod
    def from_config(cls, cfg) -> "SessionManager":
        return cls(
            secret=resolve_secret(cfg),
            cookie_name=cfg.COOKIE_NAME,
            max_age=max(60, cfg.SESSION_HOURS * 3600),
        )

    def issue_handshake(self, data: dict) -> str:
        return self._handshake.dumps(data)

    def read_handshake(self, token: str):
        """Return the pending login state, or ``None`` if it is missing/expired."""
        if not token:
            return None
        try:
            payload = self._handshake.loads(token, max_age=self.HANDSHAKE_MAX_AGE)
        except (SignatureExpired, BadSignature):
            logger.info("OIDC handshake cookie was missing, expired or tampered with")
            return None
        except Exception:
            logger.info("OIDC handshake cookie could not be decoded")
            return None
        return payload if isinstance(payload, dict) else None

    def issue(self, user: User) -> str:
        return self._serializer.dumps(user.to_session())

    def read(self, token: str):
        """Return the :class:`User` for a token, or ``None`` if it is not valid."""
        if not token:
            return None
        try:
            payload = self._serializer.loads(token, max_age=self.max_age)
        except SignatureExpired:
            logger.debug("Session cookie expired")
            return None
        except BadSignature:
            logger.debug("Session cookie failed signature verification")
            return None
        except Exception:
            logger.debug("Session cookie could not be decoded")
            return None

        if not isinstance(payload, dict) or not payload.get("u"):
            return None
        return User.from_session(payload)
