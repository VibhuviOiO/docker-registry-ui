"""Request-level authentication and authorisation.

Mounted as ASGI middleware rather than as a dependency on each route, so the
existing route table in ``app/routes.py`` is not touched at all. That is what
guarantees "auth off" is byte-for-byte the previous behaviour, and it also means
this file is the single place to read for the access policy.

Access policy
-------------
* ``/health*``, ``/static/*``, ``/login`` and the login/logout endpoints stay
  open. The first two matter operationally: every shipped compose file probes
  ``/health/live``, and the login page needs its CSS and JS.
* Every other request requires a valid session.
* Admin-only operations are matched by path. ``READ_ONLY=true`` remains an
  independent upper bound, so an admin can still never delete when read-only.

HTML navigations are redirected to the login page; API calls get a 401 with an
``X-Auth-Required`` header, which the front-end turns into a redirect.
"""

import logging
import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse

from .config import AuthConfig
from .session import SessionManager
from .service import describe
from . import audit

logger = logging.getLogger(__name__)

EXEMPT_PATHS = {
    "/login",
    "/auth/login",
    "/auth/logout",
    "/favicon.ico",
    "/health",
    "/health/live",
    "/health/ready",
}
EXEMPT_PREFIXES = (
    "/static/",
    # The OIDC handshake has to be reachable before a session exists, otherwise
    # the redirect back from the identity provider would be bounced to /login.
    "/auth/oidc/",
)

# Destructive or configuration-changing endpoints. Everything else is available
# to any authenticated user. Matched by path so no route decorator changes are
# needed; adding a route under one of these prefixes inherits the restriction.
ADMIN_ONLY_RULES = (
    ("DELETE", re.compile(r"^/api/delete/")),
    ("POST", re.compile(r"^/api/bulk-operation/?$")),
    ("POST", re.compile(r"^/api/registry/")),
    # The audit trail names who did what, so it is itself privileged.
    ("GET", re.compile(r"^/api/audit/?$")),
)


def is_exempt(path: str, method: str) -> bool:
    """Paths that must stay reachable without a session.

    ``/auth/me`` is deliberately absent so the front-end can use it to detect
    whether the current session is still valid.
    """
    if path in EXEMPT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES)


def requires_admin(method: str, path: str) -> bool:
    return any(method == m and pattern.match(path) for m, pattern in ADMIN_ONLY_RULES)


def wants_json(request) -> bool:
    path = request.url.path
    # /auth/me is called by the front-end via fetch(); it must answer with a 401
    # rather than a redirect, otherwise an expired session looks like a success.
    if path.startswith("/api/") or path.startswith("/auth/"):
        return True
    accept = request.headers.get("accept", "")
    return "application/json" in accept and "text/html" not in accept


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, session_manager: SessionManager):
        super().__init__(app)
        self.sessions = session_manager
        self._logged_startup = False

    async def dispatch(self, request, call_next):
        if not AuthConfig.ENABLED:
            return await call_next(request)

        if not self._logged_startup:
            self._logged_startup = True
            logger.warning("Authentication is ENABLED: %s", describe())

        path = request.url.path
        method = request.method.upper()

        if is_exempt(path, method):
            return await call_next(request)

        user = self.sessions.read(request.cookies.get(self.sessions.cookie_name))
        if user is None:
            return self._unauthenticated(request)

        request.state.user = user

        if requires_admin(method, path) and not user.is_admin:
            logger.warning("Denied %s %s for %r (role=%s)", method, path, user.username, user.role)
            audit.record(
                "privileged_denied",
                actor=user.username,
                role=user.role,
                provider=user.provider,
                action=f"{method} {path}",
                target=path,
                status=403,
                ip=audit.client_ip(request),
            )
            if wants_json(request):
                return JSONResponse(
                    {"success": False, "error": "Administrator role required"},
                    status_code=403,
                )
            return JSONResponse({"error": "Administrator role required"}, status_code=403)

        response = await call_next(request)

        # Recorded after the fact so the real outcome (including a 404 or a
        # 500 from the registry itself) lands in the trail.
        if requires_admin(method, path):
            audit.record(
                "privileged_request",
                actor=user.username,
                role=user.role,
                provider=user.provider,
                action=f"{method} {path}",
                target=path,
                status=response.status_code,
                ip=audit.client_ip(request),
            )

        return response

    @staticmethod
    def _unauthenticated(request):
        if wants_json(request):
            return JSONResponse(
                {"error": "Authentication required"},
                status_code=401,
                headers={"X-Auth-Required": "1"},
            )
        target = request.url.path
        if request.url.query:
            target = f"{target}?{request.url.query}"
        return RedirectResponse(f"/login?next={target}", status_code=302)
