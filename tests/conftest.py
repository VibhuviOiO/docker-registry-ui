"""Shared test setup.

The application mounts static files with the relative path ``static``
(``app/__init__.py``), so tests must run with the repository root as the working
directory. That mirrors how the container runs (``WORKDIR /app``).
"""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# tests/ itself, so "from fake_idp import FakeIdP" works regardless of import mode.
TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

# Every environment variable the authentication subsystem reads. Cleared before
# each test so one test's configuration cannot leak into another.
AUTH_ENV_VARS = (
    "AUTH_ENABLED",
    "AUTH_MODE",
    "AUTH_SECRET_KEY",
    "AUTH_SECRET_FILE",
    "AUTH_SESSION_HOURS",
    "AUTH_COOKIE_NAME",
    "AUTH_COOKIE_SECURE",
    "AUTH_COOKIE_DOMAIN",
    "AUTH_DEFAULT_ROLE",
    "AUTH_ADMIN_GROUP",
    "BREAK_GLASS_USER",
    "BREAK_GLASS_PASSWORD",
    "LDAP_URL",
    "LDAP_BIND_DN",
    "LDAP_BIND_PASSWORD",
    "LDAP_BIND_PASSWORD_FILE",
    "LDAP_BASE_DN",
    "LDAP_USER_BASE",
    "LDAP_USER_FILTER",
    "LDAP_GROUP_BASE",
    "LDAP_GROUP_FILTER",
    "LDAP_ADMIN_GROUP",
    "LDAP_STARTTLS",
    "LDAP_CA_CERT",
    "LDAP_INSECURE",
    "LDAP_TIMEOUT",
    "LDAP_ATTR_USERNAME",
    "LDAP_ATTR_MAIL",
    "LDAP_ATTR_DISPLAY",
    "AUTH_PUBLIC_URL",
    "OIDC_ISSUER",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "OIDC_CLIENT_SECRET_FILE",
    "OIDC_SCOPES",
    "OIDC_USERNAME_CLAIM",
    "OIDC_DISPLAY_CLAIM",
    "OIDC_EMAIL_CLAIM",
    "OIDC_GROUPS_CLAIM",
    "OIDC_ADMIN_GROUP",
    "OIDC_PROMPT",
    "OIDC_CA_CERT",
    "OIDC_INSECURE",
    "OIDC_TIMEOUT",
    "LOGIN_TITLE",
    "LOGIN_SUBTITLE",
)


@pytest.fixture(autouse=True)
def hermetic_environment(monkeypatch):
    """Run each test from the repo root with a clean auth environment."""
    monkeypatch.chdir(ROOT)
    for name in AUTH_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    yield


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    """Point the data directory at a temp dir.

    ``Config.DATA_DIR`` is captured at import time, so patching the attribute is
    what actually takes effect.
    """
    from app.config import Config

    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def repo_root():
    return ROOT


@pytest.fixture
def idp():
    """A real OpenID Connect provider listening on 127.0.0.1."""
    from fake_idp import FakeIdP

    server = FakeIdP().start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def oidc_env(monkeypatch, isolated_data_dir, idp):
    """Configure the app to use the fake provider, and return the provider."""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-not-for-production")
    monkeypatch.setenv("AUTH_PUBLIC_URL", "http://testserver")
    monkeypatch.setenv("OIDC_ISSUER", idp.issuer)
    monkeypatch.setenv("OIDC_CLIENT_ID", idp.CLIENT_ID)
    monkeypatch.setenv("OIDC_CLIENT_SECRET", idp.CLIENT_SECRET)
    monkeypatch.setenv("OIDC_ADMIN_GROUP", "registry-admins")
    monkeypatch.setenv("AUTH_DEFAULT_ROLE", "viewer")
    return idp


def pytest_report_header(config):
    return f"docker-registry-ui tests: repo root {ROOT} (cwd={os.getcwd()})"
