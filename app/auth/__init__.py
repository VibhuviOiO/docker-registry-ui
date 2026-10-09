"""Optional authentication: SSO (OIDC) and LDAP / Active Directory.

The whole subsystem is opt-in. With ``AUTH_ENABLED`` unset or false, importing
this package and calling :func:`install_auth` changes nothing about how the
application behaves: no middleware is added, no routes are registered, and no
authentication dependency is imported.

That contract is what makes it safe to ship in a patch release, and it is
asserted by ``tests/test_auth_off_regression.py``.
"""

import logging

from .config import AuthConfig
from .service import reset_provider

logger = logging.getLogger(__name__)


def install_auth(app):
    """Attach authentication to ``app`` when enabled. Never raises when disabled."""
    AuthConfig.load()
    reset_provider()

    if not AuthConfig.ENABLED:
        app.state.auth_enabled = False
        logger.info("Authentication disabled (AUTH_ENABLED is not set)")
        return app

    # Fail fast: a per-process signing key would log users out at random as
    # requests hit different uvicorn workers.
    from .session import SessionManager

    sessions = SessionManager.from_config(AuthConfig)

    from .middleware import AuthMiddleware
    from .routes import auth_router

    app.state.auth_enabled = True
    app.state.session_manager = sessions

    app.add_middleware(AuthMiddleware, session_manager=sessions)
    app.include_router(auth_router)

    logger.warning(
        "Authentication enabled (mode=%s, break_glass=%s, secure_cookie=%s)",
        AuthConfig.MODE or "none",
        bool(AuthConfig.BREAK_GLASS_USER and AuthConfig.BREAK_GLASS_PASSWORD),
        AuthConfig.COOKIE_SECURE,
    )
    if (AuthConfig.MODE or "none") == "none" and not AuthConfig.BREAK_GLASS_USER:
        logger.error(
            "AUTH_ENABLED=true but no provider is configured and no break-glass "
            "account is set: no user will be able to sign in."
        )
    elif (AuthConfig.MODE or "none") != "none":
        # Surface a bad AUTH_MODE at startup rather than at the first login.
        from .service import get_provider

        provider = get_provider()
        if provider is None:
            logger.error(
                "AUTH_MODE=%s did not produce a provider: nobody can sign in.",
                AuthConfig.MODE,
            )
        elif not provider.available():
            reason = ""
            if hasattr(provider, "unavailable_reason"):
                reason = f" ({provider.unavailable_reason()})"
            logger.error(
                "AUTH_MODE=%s is configured but unusable%s: sign-in will fail.",
                AuthConfig.MODE,
                reason,
            )
    return app


__all__ = ["AuthConfig", "install_auth"]
