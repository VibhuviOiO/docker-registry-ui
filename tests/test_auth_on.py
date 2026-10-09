"""Behaviour with authentication enabled."""

import pytest
from fastapi.testclient import TestClient

BREAK_GLASS_USER = "emergency"
BREAK_GLASS_PASSWORD = "correct-horse-battery-staple"
SECRET = "test-secret-key-not-for-production"


@pytest.fixture
def app(monkeypatch, isolated_data_dir):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_MODE", "none")
    monkeypatch.setenv("AUTH_SECRET_KEY", SECRET)
    monkeypatch.setenv("BREAK_GLASS_USER", BREAK_GLASS_USER)
    monkeypatch.setenv("BREAK_GLASS_PASSWORD", BREAK_GLASS_PASSWORD)

    from app import create_app

    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)


def _sign_in(client):
    return client.post(
        "/auth/login",
        data={"username": BREAK_GLASS_USER, "password": BREAK_GLASS_PASSWORD, "next": "/"},
        follow_redirects=False,
    )


# --------------------------------------------------------------------- gating


def test_main_ui_redirects_to_login(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/login")


def test_api_returns_401_with_marker_header(client):
    response = client.get("/api/registries")
    assert response.status_code == 401
    assert response.headers.get("X-Auth-Required") == "1"


def test_health_and_static_stay_open(client):
    """Operational endpoints must not require a session.

    ``/health/ready`` legitimately answers 503 when no registry is configured --
    reaching that route at all is the point, because the alternative would be a
    401 or a redirect to the login page.
    """
    assert client.get("/health/live").status_code == 200
    assert client.get("/health").status_code == 200

    ready = client.get("/health/ready")
    assert ready.status_code in (200, 503)
    assert "registries" in ready.json() or "no registries" in ready.text

    assert client.get("/static/js/core.js").status_code == 200


def test_login_page_is_reachable(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "Sign in" in response.text


# ---------------------------------------------------------------------- login


def test_wrong_password_is_rejected_without_a_cookie(client):
    response = client.post(
        "/auth/login",
        data={"username": BREAK_GLASS_USER, "password": "wrong", "next": "/"},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert "drui_session" not in response.cookies


def test_successful_login_grants_access(client):
    response = _sign_in(client)
    assert response.status_code == 303
    assert "drui_session" in response.cookies

    whoami = client.get("/auth/me")
    assert whoami.status_code == 200
    assert whoami.json()["username"] == BREAK_GLASS_USER
    assert whoami.json()["isAdmin"] is True

    # The endpoint that 401'd earlier now works.
    assert client.get("/api/registries").status_code == 200


def test_logout_clears_the_session(client):
    _sign_in(client)
    assert client.get("/auth/me").status_code == 200

    response = client.get("/auth/logout", follow_redirects=False)
    assert response.status_code == 303

    # The cookie must be expired outright, not merely blanked.
    set_cookie = response.headers["set-cookie"]
    assert "Max-Age=0" in set_cookie
    assert "1970" in set_cookie

    assert client.get("/auth/me").status_code == 401


def test_session_validity_is_reported_as_json_not_a_redirect(client):
    """An expired session on a fetch() call must be a 401, not an HTML redirect."""
    response = client.get("/auth/me", follow_redirects=False)
    assert response.status_code == 401
    assert response.json()["error"] == "Authentication required"


def test_tampered_cookie_is_rejected(client):
    client.cookies.set("drui_session", "not-a-valid-signed-token")
    assert client.get("/auth/me").status_code == 401
    assert client.get("/api/registries").status_code == 401


def test_cookie_has_hardening_flags(client):
    response = _sign_in(client)
    header = response.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header


# ------------------------------------------------------------------ redirects


@pytest.mark.parametrize(
    "hostile",
    ["https://evil.example.com", "//evil.example.com", "/\\evil.example.com", ""],
)
def test_next_parameter_cannot_redirect_off_site(client, hostile):
    response = client.post(
        "/auth/login",
        data={"username": BREAK_GLASS_USER, "password": BREAK_GLASS_PASSWORD, "next": hostile},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_same_site_next_is_honoured(client):
    response = client.post(
        "/auth/login",
        data={"username": BREAK_GLASS_USER, "password": BREAK_GLASS_PASSWORD, "next": "/cleanup"},
        follow_redirects=False,
    )
    assert response.headers["location"] == "/cleanup"


# ----------------------------------------------------------------------- RBAC


def test_viewer_cannot_reach_admin_endpoints(app):
    from app.auth.models import User

    client = TestClient(app)
    manager = app.state.session_manager
    client.cookies.set(manager.cookie_name, manager.issue(User(username="v", role="viewer")))

    response = client.delete("/api/delete/tag/reg/repo/latest")
    assert response.status_code == 403
    assert response.json()["error"] == "Administrator role required"


def test_read_only_still_bounds_an_admin(app, monkeypatch):
    """READ_ONLY stays an independent upper bound: admin does not imply delete."""
    from app.auth.models import User
    from app.config import Config

    client = TestClient(app)
    manager = app.state.session_manager
    client.cookies.set(manager.cookie_name, manager.issue(User(username="a", role="admin")))

    monkeypatch.setattr(Config, "READ_ONLY", True)
    response = client.delete("/api/delete/tag/reg/repo/latest")
    assert response.status_code == 403
    assert response.json()["error"] == "Read-only mode"


def test_admin_passes_the_middleware_when_not_read_only(app, monkeypatch):
    from app.auth.models import User
    from app.config import Config

    monkeypatch.setattr(Config, "READ_ONLY", False)

    client = TestClient(app)
    manager = app.state.session_manager
    client.cookies.set(manager.cookie_name, manager.issue(User(username="a", role="admin")))

    # The registry does not exist, so the request reaches the route and 404s --
    # the important part is that it is no longer blocked by RBAC.
    response = client.delete("/api/delete/tag/reg/repo/latest")
    assert response.status_code == 404


def test_viewer_can_still_browse(app):
    from app.auth.models import User

    client = TestClient(app)
    manager = app.state.session_manager
    client.cookies.set(manager.cookie_name, manager.issue(User(username="v", role="viewer")))

    assert client.get("/api/registries").status_code == 200
    assert client.get("/").status_code == 200


# ------------------------------------------------------------------- failures


def test_no_provider_configured_reports_503(monkeypatch, isolated_data_dir):
    """A misconfiguration must not look like a wrong password."""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_MODE", "none")
    monkeypatch.setenv("AUTH_SECRET_KEY", SECRET)
    # No break-glass account.

    from app import create_app

    client = TestClient(create_app())
    response = client.post(
        "/auth/login",
        data={"username": "anyone", "password": "anything", "next": "/"},
        follow_redirects=False,
    )
    assert response.status_code == 503
