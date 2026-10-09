"""Append-only audit log of authentication and privileged actions.

Deliberately a plain JSON-lines file rather than a database: it adds no
dependency, it survives restarts on the mounted data volume, and it is trivial
to ship to a log collector.

The container runs several uvicorn workers, so several processes append to the
same file. Writes take an advisory file lock -- the same technique the Trivy
scanner already uses for its shared cache -- so lines cannot interleave. The
file is rotated once past ``MAX_BYTES`` to stop it growing without bound.
"""

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

AUDIT_FILENAME = "audit.log"
MAX_BYTES = 5 * 1024 * 1024
READ_LIMIT_DEFAULT = 200
READ_LIMIT_MAX = 1000

try:
    import fcntl

    _HAS_FCNTL = True
except ImportError:  # pragma: no cover - Windows
    _HAS_FCNTL = False


def audit_path() -> str:
    from ..config import Config

    return os.path.join(Config.DATA_DIR, AUDIT_FILENAME)


def client_ip(request) -> str:
    """Best-effort client address.

    ``X-Forwarded-For`` is only trustworthy behind a reverse proxy that
    overwrites it; a client talking to the app directly can set it freely.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _lock(fd) -> None:
    if _HAS_FCNTL:
        fcntl.flock(fd, fcntl.LOCK_EX)


def _unlock(fd) -> None:
    if _HAS_FCNTL:
        fcntl.flock(fd, fcntl.LOCK_UN)


def _rotate_if_needed(path: str) -> None:
    try:
        if os.path.exists(path) and os.path.getsize(path) > MAX_BYTES:
            os.replace(path, path + ".1")
    except OSError:
        pass


def record(
    event: str,
    *,
    actor: str = "",
    role: str = "",
    provider: str = "",
    action: str = "",
    target: str = "",
    status=None,
    ip: str = "",
    detail=None,
) -> dict:
    """Append one audit entry. Never raises: auditing must not break a request."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "actor": actor or "anonymous",
        "role": role,
        "provider": provider,
        "action": action,
        "target": target,
        "status": status,
        "ip": ip,
        "detail": detail,
    }

    path = audit_path()
    line = json.dumps(entry, separators=(",", ":")) + "\n"

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _rotate_if_needed(path)
        fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
        try:
            _lock(fd)
            os.write(fd, line.encode("utf-8"))
        finally:
            _unlock(fd)
            os.close(fd)
    except OSError as exc:
        logger.error("Could not write audit entry: %s", exc)

    return entry


def read_recent(limit: int = READ_LIMIT_DEFAULT) -> list:
    """Return up to ``limit`` newest entries, most recent first."""
    try:
        limit = max(1, min(int(limit), READ_LIMIT_MAX))
    except (TypeError, ValueError):
        limit = READ_LIMIT_DEFAULT

    path = audit_path()
    if not os.path.exists(path):
        return []

    entries = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except ValueError:
                    continue
    except OSError as exc:
        logger.error("Could not read the audit log: %s", exc)
        return []

    return entries[-limit:][::-1]
