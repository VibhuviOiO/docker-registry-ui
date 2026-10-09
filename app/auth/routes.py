"""Login, logout and current-user endpoints.

The login page is deliberately a standalone template rather than an extension of
``base.html``: the base layout loads the registry scripts, which immediately call
``/api/...`` on load and would fight the very authentication they are meant to
pass through.
"""

import hmac
import logging
import os
import secrets

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import audit
from .config import AuthConfig
from .models import AuthError
from .providers.oidc import create_pkce_pair
from .service import authenticate, get_provider

logger = logging.getLogger(__name__)

auth_router = APIRouter()

templates_dir = os.path.join(os.path.dirname(__file__), "..", "..", "templates")
templates = Jinja2Templates(directory=templates_dir)


def safe_next(target: str) -> str:
    """Allow only same-site relative redirects, so ``?next=`` is not an open redirect."""
    if not target or not target.startswith("/") or target.startswith("//"):
        return "/"
    # A backslash is normalised to a slash by some browsers and can be used to
    # smuggle an absolute URL past a naive prefix check.
    if "\\" in target:
        return "/"
    return target


def _sso_info() -> dict:
    """What the login page should offer.

    In OIDC mode the password form is hidden, but an explicitly configured
    break-glass account keeps it visible so the UI is still reachable when the
    identity provider is down.
    """
    mode = (AuthConfig.MODE or "none").strip().lower()
    break_glass = bool(AuthConfig.BREAK_GLASS_USER and AuthConfig.BREAK_GLASS_PASSWORD)
    return {
        "sso_enabled": mode == "oidc",
        "password_enabled": mode != "oidc" or break_glass,
        "mode": mode,
    }


def _page(request: Request, target: str, error: str = None, status_code: int = 200):
    context = {
        "request": request,
        "next": target,
        "error": error,
        "title": AuthConfig.LOGIN_TITLE,
        "subtitle": AuthConfig.LOGIN_SUBTITLE,
    }
    context.update(_sso_info())
    return templates.TemplateResponse("login.html", context, status_code=status_code)


def _sessions(request: Request):
    manager = getattr(request.app.state, "session_manager", None)
    if manager is None:
        logger.error("Login attempted but no session manager is configured")
    return manager


def _set_session_cookie(response, manager, user) -> None:
    response.set_cookie(
        key=manager.cookie_name,
        value=manager.issue(user),
        max_age=manager.max_age,
        httponly=True,
        samesite="lax",
        secure=AuthConfig.COOKIE_SECURE,
        domain=AuthConfig.COOKIE_DOMAIN,
        path="/",
    )


@auth_router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/"):
    return _page(request, safe_next(next))


@auth_router.post("/auth/login")
async def login_submit(request: Request):
    form = await request.form()
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""
    target = safe_next(form.get("next") or "/")

    manager = _sessions(request)
    if manager is None:
        return _page(request, target, "Authentication is not configured", status_code=503)

    try:
        user = authenticate(username, password)
    except AuthError as exc:
        logger.info("Rejected login for %r: %s", username, exc.message)
        audit.record(
            "login_failed",
            actor=username,
            action="password login",
            status=exc.status_code,
            ip=audit.client_ip(request),
            detail=exc.message,
        )
        return _page(request, target, exc.message, status_code=exc.status_code)
    except Exception:
        logger.exception("Unexpected error while authenticating %r", username)
        return _page(request, target, "Authentication service error", status_code=500)

    response = RedirectResponse(target, status_code=303)
    _set_session_cookie(response, manager, user)
    audit.record(
        "login_success",
        actor=user.username,
        role=user.role,
        provider=user.provider,
        action="password login",
        status=303,
        ip=audit.client_ip(request),
    )
    logger.info("User %r signed in via %s (role=%s)", user.username, user.provider, user.role)
    return response


@auth_router.get("/auth/logout")
def logout(request: Request):
    manager = _sessions(request)
    user = getattr(request.state, "user", None)
    if user is None and manager is not None:
        # /auth/logout is exempt from the authentication middleware -- it has to
        # work with an already-expired session -- so middleware never populated
        # state.user. Identify the actor from the cookie directly, otherwise
        # logouts would be the one action missing from the audit trail.
        user = manager.read(request.cookies.get(manager.cookie_name))

    response = RedirectResponse("/login", status_code=303)
    if manager is not None:
        # An explicit epoch expiry rather than Response.delete_cookie, which
        # emits `expires=<now>` and therefore depends on the client honouring
        # Max-Age to actually drop the session.
        response.set_cookie(
            key=manager.cookie_name,
            value="",
            max_age=0,
            expires="Thu, 01 Jan 1970 00:00:00 GMT",
            path="/",
            domain=AuthConfig.COOKIE_DOMAIN,
            secure=AuthConfig.COOKIE_SECURE,
            httponly=True,
            samesite="lax",
        )
    if user is not None:
        audit.record(
            "logout",
            actor=user.username,
            role=user.role,
            provider=user.provider,
            action="logout",
            status=303,
            ip=audit.client_ip(request),
        )
    return response


@auth_router.get("/auth/me")
def whoami(request: Request):
    """Used by the front-end to render the account chip, and to detect expiry."""
    user = getattr(request.state, "user", None)
    if user is None:
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    return user.to_dict()


# --------------------------------------------------------------------- SSO


@auth_router.get("/auth/oidc/login")
def oidc_login(request: Request, next: str = "/"):
    """Start the authorization-code flow with PKCE."""
    manager = _sessions(request)
    target = safe_next(next)
    provider = get_provider()

    if manager is None:
        return _page(request, target, "Authentication is not configured", status_code=503)
    if provider is None or getattr(provider, "name", "") != "oidc":
        return _page(request, target, "Single sign-on is not configured", status_code=503)
    if not provider.available():
        return _page(request, target, provider.unavailable_reason(), status_code=503)

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier, challenge = create_pkce_pair()

    try:
        authorization_url = provider.authorization_url(state, nonce, challenge)
    except AuthError as exc:
        logger.warning("Could not start the OIDC flow: %s", exc.message)
        return _page(request, target, exc.message, status_code=exc.status_code)

    # Scoped to /auth/oidc so the transient handshake is never sent with normal
    # application requests.
    response = RedirectResponse(authorization_url, status_code=302)
    response.set_cookie(
        key=manager.HANDSHAKE_COOKIE,
        value=manager.issue_handshake(
            {"state": state, "nonce": nonce, "verifier": verifier, "next": target}
        ),
        max_age=manager.HANDSHAKE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=AuthConfig.COOKIE_SECURE,
        path="/auth/oidc",
    )
    return response


@auth_router.get("/auth/oidc/callback")
def oidc_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    error_description: str = "",
):
    """Complete the flow: verify state, exchange the code, start a session."""
    manager = _sessions(request)
    if manager is None:
        return _page(request, "/", "Authentication is not configured", status_code=503)

    handshake = manager.read_handshake(request.cookies.get(manager.HANDSHAKE_COOKIE))
    target = safe_next((handshake or {}).get("next") or "/")

    if error:
        logger.info("OIDC provider returned an error: %s (%s)", error, error_description)
        audit.record(
            "login_failed",
            provider="oidc",
            target=target,
            status=401,
            ip=audit.client_ip(request),
            detail=f"{error}: {error_description}".strip(": "),
        )
        return _page(request, target, f"Sign-in was refused by the identity provider ({error})", status_code=401)

    if not handshake:
        return _page(request, target, "Your sign-in session expired. Please try again.", status_code=401)

    # CSRF: the state must be the one issued to this browser, and nothing else.
    if not state or not hmac.compare_digest(str(state), str(handshake.get("state", ""))):
        audit.record(
            "login_failed",
            provider="oidc",
            status=401,
            ip=audit.client_ip(request),
            detail="state mismatch",
        )
        return _page(request, target, "Sign-in could not be verified (state mismatch). Please try again.", status_code=401)

    if not code:
        return _page(request, target, "The identity provider did not return an authorization code", status_code=401)

    provider = get_provider()
    if provider is None or getattr(provider, "name", "") != "oidc":
        return _page(request, target, "Single sign-on is not configured", status_code=503)

    try:
        user = provider.exchange_code(code, handshake.get("verifier", ""), handshake.get("nonce", ""))
    except AuthError as exc:
        logger.info("OIDC sign-in failed: %s", exc.message)
        audit.record(
            "login_failed",
            provider="oidc",
            status=exc.status_code,
            ip=audit.client_ip(request),
            detail=exc.message,
        )
        return _page(request, target, exc.message, status_code=exc.status_code)

    response = RedirectResponse(target, status_code=303)
    _set_session_cookie(response, manager, user)
    response.delete_cookie(manager.HANDSHAKE_COOKIE, path="/auth/oidc")
    audit.record(
        "login_success",
        actor=user.username,
        role=user.role,
        provider=user.provider,
        action="oidc login",
        status=303,
        ip=audit.client_ip(request),
    )
    logger.info("User %r signed in via %s (role=%s)", user.username, user.provider, user.role)
    return response


# ------------------------------------------------------------------- audit


@auth_router.get("/api/audit")
def audit_entries(limit: int = audit.READ_LIMIT_DEFAULT):
    """Recent audit entries, newest first.

    Admin-only: the path is listed in ``ADMIN_ONLY_RULES`` in the middleware.
    """
    return {"entries": audit.read_recent(limit)}
