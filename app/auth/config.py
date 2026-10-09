"""Authentication configuration.

Deliberately kept separate from ``app/config.py`` so the pre-existing
configuration surface is untouched: enabling auth must not change any existing
env var, default or code path.

Every setting here defaults to "off", and ``load()`` is called at application
startup rather than at import time so the values can be exercised by tests.
"""

import os

from ..config import Config


def _flag(name: str, default: bool = False) -> bool:
    """Parse a boolean env var, accepting the spellings operators actually use."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class AuthConfig:
    """Runtime authentication settings, populated by :meth:`load`."""

    ENABLED = False
    MODE = "none"

    SECRET_KEY = ""
    SECRET_FILE = ""
    SESSION_HOURS = 12
    COOKIE_NAME = "drui_session"
    COOKIE_SECURE = False
    COOKIE_DOMAIN = None
    DEFAULT_ROLE = "viewer"
    ADMIN_GROUP = ""

    # Emergency local account. Works with any MODE, so a misconfigured IdP or an
    # unreachable directory cannot lock every administrator out permanently.
    BREAK_GLASS_USER = ""
    BREAK_GLASS_PASSWORD = ""

    # LDAP / Active Directory
    LDAP_URL = ""
    LDAP_BIND_DN = ""
    LDAP_BIND_PASSWORD = ""
    LDAP_BASE_DN = ""
    LDAP_USER_BASE = ""
    LDAP_USER_FILTER = "(&(objectClass=inetOrgPerson)(uid={username}))"
    LDAP_GROUP_BASE = ""
    LDAP_GROUP_FILTER = ""
    LDAP_ADMIN_GROUP = ""
    LDAP_STARTTLS = False
    LDAP_CA_CERT = ""
    LDAP_INSECURE = False
    LDAP_TIMEOUT = 10
    LDAP_ATTR_USERNAME = "uid"
    LDAP_ATTR_MAIL = "mail"
    LDAP_ATTR_DISPLAY = "cn"

    # SSO / OIDC
    # AUTH_PUBLIC_URL is the external base URL of this UI. The identity provider
    # redirects the browser back to it, so it must match what the browser sees,
    # not what the container sees (a reverse proxy usually differs).
    AUTH_PUBLIC_URL = ""
    OIDC_ISSUER = ""
    OIDC_CLIENT_ID = ""
    OIDC_CLIENT_SECRET = ""
    OIDC_SCOPES = "openid profile email"
    OIDC_USERNAME_CLAIM = "preferred_username"
    OIDC_DISPLAY_CLAIM = "name"
    OIDC_EMAIL_CLAIM = "email"
    OIDC_GROUPS_CLAIM = "groups"
    OIDC_ADMIN_GROUP = ""
    OIDC_PROMPT = ""
    OIDC_CA_CERT = ""
    OIDC_INSECURE = False
    OIDC_TIMEOUT = 10

    # Login page
    LOGIN_TITLE = "Docker Registry UI"
    LOGIN_SUBTITLE = "Sign in to continue"

    @classmethod
    def load(cls) -> "AuthConfig":
        """(Re)read every setting from the environment."""
        cls.ENABLED = _flag("AUTH_ENABLED", False)
        cls.MODE = (os.getenv("AUTH_MODE", "none") or "none").strip().lower()

        cls.SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "")
        cls.SECRET_FILE = os.getenv("AUTH_SECRET_FILE", "")
        cls.SESSION_HOURS = _int("AUTH_SESSION_HOURS", 12)
        cls.COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "drui_session")
        cls.COOKIE_SECURE = _flag("AUTH_COOKIE_SECURE", False)
        cls.COOKIE_DOMAIN = os.getenv("AUTH_COOKIE_DOMAIN", "") or None
        cls.DEFAULT_ROLE = (os.getenv("AUTH_DEFAULT_ROLE", "viewer") or "viewer").strip().lower()
        cls.ADMIN_GROUP = os.getenv("AUTH_ADMIN_GROUP", "")

        cls.BREAK_GLASS_USER = os.getenv("BREAK_GLASS_USER", "")
        cls.BREAK_GLASS_PASSWORD = os.getenv("BREAK_GLASS_PASSWORD", "")

        cls.LDAP_URL = os.getenv("LDAP_URL", "")
        cls.LDAP_BIND_DN = os.getenv("LDAP_BIND_DN", "")
        cls.LDAP_BIND_PASSWORD = cls._secret("LDAP_BIND_PASSWORD")
        cls.LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "")
        cls.LDAP_USER_BASE = os.getenv("LDAP_USER_BASE", "") or cls.LDAP_BASE_DN
        cls.LDAP_USER_FILTER = os.getenv(
            "LDAP_USER_FILTER", "(&(objectClass=inetOrgPerson)(uid={username}))"
        )
        cls.LDAP_GROUP_BASE = os.getenv("LDAP_GROUP_BASE", "") or cls.LDAP_BASE_DN
        cls.LDAP_GROUP_FILTER = os.getenv("LDAP_GROUP_FILTER", "")
        cls.LDAP_ADMIN_GROUP = cls.ADMIN_GROUP or os.getenv("LDAP_ADMIN_GROUP", "")
        cls.LDAP_STARTTLS = _flag("LDAP_STARTTLS", False)
        cls.LDAP_CA_CERT = os.getenv("LDAP_CA_CERT", "")
        cls.LDAP_INSECURE = _flag("LDAP_INSECURE", False)
        cls.LDAP_TIMEOUT = _int("LDAP_TIMEOUT", 10)
        cls.LDAP_ATTR_USERNAME = os.getenv("LDAP_ATTR_USERNAME", "uid")
        cls.LDAP_ATTR_MAIL = os.getenv("LDAP_ATTR_MAIL", "mail")
        cls.LDAP_ATTR_DISPLAY = os.getenv("LDAP_ATTR_DISPLAY", "cn")

        cls.OIDC_ISSUER = os.getenv("OIDC_ISSUER", "").rstrip("/")
        cls.OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "")
        cls.OIDC_CLIENT_SECRET = cls._secret("OIDC_CLIENT_SECRET")
        cls.OIDC_SCOPES = os.getenv("OIDC_SCOPES", "openid profile email")
        cls.OIDC_USERNAME_CLAIM = os.getenv("OIDC_USERNAME_CLAIM", "preferred_username")
        cls.OIDC_DISPLAY_CLAIM = os.getenv("OIDC_DISPLAY_CLAIM", "name")
        cls.OIDC_EMAIL_CLAIM = os.getenv("OIDC_EMAIL_CLAIM", "email")
        cls.OIDC_GROUPS_CLAIM = os.getenv("OIDC_GROUPS_CLAIM", "groups")
        cls.OIDC_ADMIN_GROUP = cls.ADMIN_GROUP or os.getenv("OIDC_ADMIN_GROUP", "")
        cls.OIDC_PROMPT = os.getenv("OIDC_PROMPT", "")
        cls.OIDC_CA_CERT = os.getenv("OIDC_CA_CERT", "")
        cls.OIDC_INSECURE = _flag("OIDC_INSECURE", False)
        cls.OIDC_TIMEOUT = _int("OIDC_TIMEOUT", 10)
        cls.AUTH_PUBLIC_URL = os.getenv("AUTH_PUBLIC_URL", "").rstrip("/")

        cls.LOGIN_TITLE = os.getenv("LOGIN_TITLE", "Docker Registry UI")
        cls.LOGIN_SUBTITLE = os.getenv("LOGIN_SUBTITLE", "Sign in to continue")

        return cls

    @staticmethod
    def _secret(env_name: str) -> str:
        """Read a secret from ``<VAR>`` or, preferred, ``<VAR>_FILE``.

        The ``_FILE`` form is what Docker and Kubernetes secrets mount, and it
        keeps passwords out of ``docker inspect`` output.
        """
        file_path = os.getenv(f"{env_name}_FILE", "")
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as handle:
                    return handle.read().strip()
            except OSError:
                return ""
        return os.getenv(env_name, "")

    @classmethod
    def data_dir(cls) -> str:
        return Config.DATA_DIR
