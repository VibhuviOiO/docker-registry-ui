"""Authentication orchestration: break-glass first, then the configured provider."""

import logging

from .config import AuthConfig
from .models import AuthError
from .providers.local import BreakGlassProvider

logger = logging.getLogger(__name__)

_provider = None
_provider_mode = None


def get_provider():
    """Build (once) the provider for ``AUTH_MODE``.

    The provider module is imported lazily so that a deployment running with
    ``AUTH_ENABLED=false`` never needs ``ldap3`` installed.
    """
    global _provider, _provider_mode

    if _provider_mode == AuthConfig.MODE:
        return _provider

    mode = (AuthConfig.MODE or "none").strip().lower()
    provider = None

    if mode == "ldap":
        from .providers.ldap import LdapAuthProvider

        provider = LdapAuthProvider(AuthConfig)
    elif mode == "oidc":
        try:
            from .providers.oidc import OidcAuthProvider

            provider = OidcAuthProvider(AuthConfig)
        except ImportError:
            logger.error(
                "AUTH_MODE=oidc but this build has no OIDC provider; "
                "falling back to break-glass only"
            )
            provider = None
    elif mode not in ("none", ""):
        logger.error("Unknown AUTH_MODE %r; no provider will be used", mode)

    _provider = provider
    _provider_mode = AuthConfig.MODE
    return provider


def reset_provider() -> None:
    """Drop the cached provider (used by tests and after a config reload)."""
    global _provider, _provider_mode
    _provider = None
    _provider_mode = None


def break_glass_provider() -> BreakGlassProvider:
    return BreakGlassProvider(AuthConfig.BREAK_GLASS_USER, AuthConfig.BREAK_GLASS_PASSWORD)


def authenticate(username: str, password: str):
    """Return an authenticated :class:`User` or raise :class:`AuthError`."""
    emergency = break_glass_provider()
    provider = get_provider()

    if emergency.available():
        user = emergency.authenticate(username, password)
        if user is not None:
            return user

    if provider is None:
        # Distinguish "nothing is configured" from "these credentials are wrong".
        # Blaming the configuration for a typo sends operators down the wrong path.
        if emergency.available():
            raise AuthError("Invalid username or password", 401)
        raise AuthError("No authentication provider is configured", 503)

    user = provider.authenticate(username, password)
    if user is None:
        raise AuthError("Invalid username or password", 401)
    return user


def describe() -> dict:
    """Non-secret summary for logs and the login page."""
    provider = get_provider()
    return {
        "enabled": AuthConfig.ENABLED,
        "mode": AuthConfig.MODE,
        "breakGlass": break_glass_provider().available(),
        "provider": provider.describe() if provider else None,
    }
