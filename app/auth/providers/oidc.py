"""OpenID Connect (SSO) authentication.

Implements the standard authorization-code flow with PKCE against any provider
that publishes a discovery document: Keycloak, Entra ID, Okta, Authentik,
Google, ...

Security decisions worth knowing about:

* **PKCE + state + nonce are all used.** State protects the callback from CSRF,
  nonce binds the id_token to this browser session, and PKCE protects the code
  exchange even for a confidential client.
* **The id_token signature is verified** against the provider's JWKS, and only
  asymmetric algorithms are accepted. Permitting HS256 would let anyone who
  knows the client secret mint a token; permitting ``none`` would disable
  verification entirely.
* **Handshake state is kept in a signed cookie**, not in memory, because the
  redirect back from the provider may land on a different uvicorn worker than
  the one that started the flow.
* ``jwt`` is imported lazily-guarded so an installation with authentication
  disabled never needs the dependency.
"""

import base64
import hashlib
import hmac
import logging
import secrets
import time
from urllib.parse import urlencode

import requests

from ..models import ROLE_ADMIN, ROLE_VIEWER, AuthError, User
from .base import AuthProvider
from .groups import as_group_list, matches_group, split_group_list

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised by the OIDC integration tests
    import jwt
    from jwt import PyJWKSet

    JWT_AVAILABLE = True
except ImportError:  # pragma: no cover
    JWT_AVAILABLE = False
    jwt = None
    PyJWKSet = None


# Asymmetric only. See the module docstring.
ALLOWED_ALGORITHMS = (
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
)

# How long a fetched JWKS may be reused before it is refreshed.
JWKS_TTL_SECONDS = 3600

REQUIRED_METADATA = ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri")


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def create_pkce_pair():
    """Return ``(code_verifier, code_challenge)`` for PKCE S256."""
    verifier = _b64url(secrets.token_bytes(48))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


class OidcAuthProvider(AuthProvider):
    name = "oidc"

    def __init__(self, cfg):
        self.cfg = cfg
        self._metadata = None
        self._jwks = None
        self._jwks_fetched_at = 0.0

    # ------------------------------------------------------------------ setup

    def available(self) -> bool:
        return bool(
            JWT_AVAILABLE
            and self.cfg.OIDC_ISSUER
            and self.cfg.OIDC_CLIENT_ID
            and self.cfg.OIDC_CLIENT_SECRET
            and self.cfg.AUTH_PUBLIC_URL
        )

    def describe(self) -> dict:
        return {
            "name": self.name,
            "available": self.available(),
            "issuer": self.cfg.OIDC_ISSUER or None,
            "redirectUri": self.redirect_uri() if self.cfg.AUTH_PUBLIC_URL else None,
        }

    def unavailable_reason(self) -> str:
        missing = [
            name
            for name, value in (
                ("OIDC_ISSUER", self.cfg.OIDC_ISSUER),
                ("OIDC_CLIENT_ID", self.cfg.OIDC_CLIENT_ID),
                ("OIDC_CLIENT_SECRET", self.cfg.OIDC_CLIENT_SECRET),
                ("AUTH_PUBLIC_URL", self.cfg.AUTH_PUBLIC_URL),
            )
            if not value
        ]
        if missing:
            return "Missing configuration: " + ", ".join(missing)
        if not JWT_AVAILABLE:
            return "PyJWT is not installed in this image"
        return "OIDC is not configured"

    def redirect_uri(self) -> str:
        return f"{(self.cfg.AUTH_PUBLIC_URL or '').rstrip('/')}/auth/oidc/callback"

    def authenticate(self, username: str, password: str):
        # There is no password to check: the identity provider owns it.
        raise AuthError(
            "This deployment signs in with single sign-on. Use the 'Sign in with SSO' button.",
            400,
        )

    # ------------------------------------------------------------------- http

    def _tls_verify(self):
        if self.cfg.OIDC_INSECURE:
            return False
        return self.cfg.OIDC_CA_CERT or True

    def _get_json(self, url: str) -> dict:
        try:
            response = requests.get(
                url, timeout=self.cfg.OIDC_TIMEOUT, verify=self._tls_verify()
            )
        except requests.RequestException as exc:
            logger.warning("OIDC GET %s failed: %s", url, exc)
            raise AuthError("Identity provider is unreachable", 503) from exc

        if response.status_code != 200:
            raise AuthError(f"Identity provider returned HTTP {response.status_code}", 503)
        try:
            return response.json()
        except ValueError as exc:
            raise AuthError("Identity provider returned invalid JSON", 503) from exc

    def metadata(self) -> dict:
        if self._metadata is None:
            document = self._get_json(
                f"{self.cfg.OIDC_ISSUER}/.well-known/openid-configuration"
            )
            missing = [key for key in REQUIRED_METADATA if not document.get(key)]
            if missing:
                raise AuthError(
                    "Identity provider discovery document is missing: " + ", ".join(missing),
                    503,
                )
            self._metadata = document
            logger.info("OIDC discovery loaded from %s", self.cfg.OIDC_ISSUER)
        return self._metadata

    def _fetch_jwks(self) -> dict:
        return self._get_json(self.metadata()["jwks_uri"])

    @staticmethod
    def _select_key(jwks: dict, kid):
        try:
            key_set = PyJWKSet.from_dict(jwks)
        except Exception as exc:
            raise AuthError(f"Identity provider signing keys are invalid: {exc}", 503) from exc

        if not key_set.keys:
            return None
        if kid is None:
            return key_set.keys[0].key
        for key in key_set.keys:
            if key.key_id == kid:
                return key.key
        return None

    def _signing_key(self, kid):
        now = time.time()
        if self._jwks is None or (now - self._jwks_fetched_at) > JWKS_TTL_SECONDS:
            self._jwks = self._fetch_jwks()
            self._jwks_fetched_at = now

        key = self._select_key(self._jwks, kid)
        if key is None:
            # The provider may have rotated its keys since we cached them.
            logger.info("OIDC signing key %r not in cached JWKS; refreshing", kid)
            self._jwks = self._fetch_jwks()
            self._jwks_fetched_at = time.time()
            key = self._select_key(self._jwks, kid)

        if key is None:
            raise AuthError("Identity provider signing key not found", 503)
        return key

    # ------------------------------------------------------------ the flow

    def authorization_url(self, state: str, nonce: str, code_challenge: str) -> str:
        metadata = self.metadata()
        params = {
            "response_type": "code",
            "client_id": self.cfg.OIDC_CLIENT_ID,
            "redirect_uri": self.redirect_uri(),
            "scope": self.cfg.OIDC_SCOPES,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if self.cfg.OIDC_PROMPT:
            params["prompt"] = self.cfg.OIDC_PROMPT
        return f"{metadata['authorization_endpoint']}?{urlencode(params)}"

    def exchange_code(self, code: str, code_verifier: str, expected_nonce: str) -> User:
        metadata = self.metadata()
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri(),
            "client_id": self.cfg.OIDC_CLIENT_ID,
            "client_secret": self.cfg.OIDC_CLIENT_SECRET,
            "code_verifier": code_verifier,
        }

        try:
            response = requests.post(
                metadata["token_endpoint"],
                data=payload,
                timeout=self.cfg.OIDC_TIMEOUT,
                verify=self._tls_verify(),
            )
        except requests.RequestException as exc:
            logger.warning("OIDC token exchange failed: %s", exc)
            raise AuthError("Identity provider is unreachable", 503) from exc

        if response.status_code != 200:
            logger.warning(
                "OIDC token endpoint returned HTTP %s: %s",
                response.status_code,
                response.text[:300],
            )
            raise AuthError(
                f"Sign-in could not be completed (token endpoint returned HTTP {response.status_code})",
                401,
            )

        try:
            tokens = response.json()
        except ValueError as exc:
            raise AuthError("Identity provider returned an invalid token response", 401) from exc

        id_token = tokens.get("id_token")
        if not id_token:
            raise AuthError("Identity provider did not return an id_token", 401)

        claims = self._verify_id_token(id_token, expected_nonce)
        return self._user_from_claims(claims)

    def _verify_id_token(self, id_token: str, expected_nonce: str) -> dict:
        try:
            header = jwt.get_unverified_header(id_token)
        except Exception as exc:
            raise AuthError("Identity provider returned a malformed id_token", 401) from exc

        algorithm = (header.get("alg") or "").upper()
        if algorithm not in ALLOWED_ALGORITHMS:
            raise AuthError(f"id_token uses an unsupported algorithm ({algorithm or 'none'})", 401)

        key = self._signing_key(header.get("kid"))

        try:
            claims = jwt.decode(
                id_token,
                key=key,
                algorithms=list(ALLOWED_ALGORITHMS),
                audience=self.cfg.OIDC_CLIENT_ID,
                issuer=self.metadata()["issuer"],
                options={"require": ["exp", "iat", "aud", "iss", "sub"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("Your sign-in took too long and expired; please try again", 401) from exc
        except jwt.InvalidTokenError as exc:
            logger.warning("id_token validation failed: %s", exc)
            raise AuthError(f"id_token validation failed: {exc}", 401) from exc

        # Binds the token to the browser session that started the flow, which
        # stops a token captured elsewhere from being replayed here.
        nonce = claims.get("nonce")
        if not expected_nonce or not nonce or not hmac.compare_digest(str(nonce), str(expected_nonce)):
            raise AuthError("id_token nonce does not match this sign-in attempt", 401)

        return claims

    # ------------------------------------------------------------- mapping

    def _user_from_claims(self, claims: dict) -> User:
        username = (
            self._claim(claims, self.cfg.OIDC_USERNAME_CLAIM)
            or self._claim(claims, self.cfg.OIDC_EMAIL_CLAIM)
            or claims.get("sub")
            or ""
        )
        if not username:
            raise AuthError("Identity provider did not supply a usable username", 401)

        groups = as_group_list(claims.get(self.cfg.OIDC_GROUPS_CLAIM))
        configured_admin = split_group_list(self.cfg.OIDC_ADMIN_GROUP)

        if configured_admin and not groups:
            logger.warning(
                "OIDC_ADMIN_GROUP is set but the %r claim is absent from the id_token; "
                "users will get the default role. Add the claim via a scope or mapper.",
                self.cfg.OIDC_GROUPS_CLAIM,
            )

        role = ROLE_ADMIN if matches_group(configured_admin, groups) else (
            self.cfg.DEFAULT_ROLE or ROLE_VIEWER
        )

        logger.info(
            "OIDC: authenticated %r groups=%s -> role=%s", username, groups or "[]", role
        )

        return User(
            username=str(username),
            role=role,
            display_name=self._claim(claims, self.cfg.OIDC_DISPLAY_CLAIM) or str(username),
            email=self._claim(claims, self.cfg.OIDC_EMAIL_CLAIM),
            provider=self.name,
            groups=groups,
        )

    @staticmethod
    def _claim(claims: dict, name: str) -> str:
        if not name:
            return ""
        value = claims.get(name)
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        return str(value).strip() if value is not None else ""
