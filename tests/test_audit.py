"""Audit trail tests.

The audit log is the control that answers "who deleted that?", so it is tested
for content, ordering, access control, and for the failure mode of not being
writable at all.
"""

import json
import os

import pytest
from fastapi.testclient import TestClient

from app.auth import audit
from app.auth.models import User

BREAK_GLASS_USER = "emergency"
BREAK_GLASS_PASSWORD = "letmein"


@pytest.fixture
def app(monkeypatch, isolated_data_dir):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_MODE", "none")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-not-for-production")
    monkeypatch.setenv("BREAK_GLASS_USER", BREAK_GLASS_USER)
    monkeypatch.setenv("BREAK_GLASS_PASSWORD", BREAK_GLASS_PASSWORD)

    from app import create_app

    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)


def sign_in(client, forwarded_for="203.0.113.9"):
    return client.post(
        "/auth/login",
        data={"username": BREAK_GLASS_USER, "password": BREAK_GLASS_PASSWORD, "next": "/"},
        headers={"X-Forwarded-For": forwarded_for},
        follow_redirects=False,
    )


def events():
    return [entry["event"] for entry in audit.read_recent(200)]


# ------------------------------------------------------------------- content


def test_successful_login_is_recorded(client):
    sign_in(client)

    entries = audit.read_recent(50)
    assert "login_success" in [e["event"] for e in entries]

    login = next(e for e in entries if e["event"] == "login_success")
    assert login["actor"] == BREAK_GLASS_USER
    assert login["role"] == "admin"
    assert login["provider"] == "break-glass"
    assert login["ip"] == "203.0.113.9"
    assert login["timestamp"]


def test_failed_login_is_recorded(client):
    client.post(
        "/auth/login",
        data={"username": BREAK_GLASS_USER, "password": "wrong", "next": "/"},
        follow_redirects=False,
    )

    failed = [e for e in audit.read_recent(50) if e["event"] == "login_failed"]
    assert failed, "a rejected login must be auditable"
    assert failed[0]["actor"] == BREAK_GLASS_USER
    assert failed[0]["status"] == 401


def test_logout_is_recorded(client):
    sign_in(client)
    client.get("/auth/logout", follow_redirects=False)
    assert "logout" in events()


def test_privileged_actions_name_the_actor(client):
    sign_in(client)
    client.delete("/api/delete/tag/nope/repo/latest")

    privileged = [e for e in audit.read_recent(50) if e["event"] == "privileged_request"]
    assert privileged
    assert privileged[0]["actor"] == BREAK_GLASS_USER
    assert privileged[0]["action"] == "DELETE /api/delete/tag/nope/repo/latest"


def test_denied_privileged_action_is_recorded(app):
    client = TestClient(app)
    manager = app.state.session_manager
    client.cookies.set(manager.cookie_name, manager.issue(User(username="v", role="viewer")))

    client.delete("/api/delete/tag/nope/repo/latest")

    denied = [e for e in audit.read_recent(50) if e["event"] == "privileged_denied"]
    assert denied
    assert denied[0]["actor"] == "v"
    assert denied[0]["role"] == "viewer"
    assert denied[0]["status"] == 403


# ------------------------------------------------------------------ ordering


def test_entries_are_returned_newest_first(client):
    sign_in(client)
    client.get("/auth/logout", follow_redirects=False)
    client.get("/auth/logout", follow_redirects=False)

    entries = audit.read_recent(50)
    timestamps = [e["timestamp"] for e in entries]
    assert timestamps == sorted(timestamps, reverse=True)


def test_limit_is_applied(client):
    sign_in(client)
    for _ in range(5):
        client.get("/auth/logout", follow_redirects=False)

    assert len(audit.read_recent(2)) == 2


# ------------------------------------------------------------ access control


def test_audit_endpoint_requires_authentication(client):
    response = client.get("/api/audit")
    assert response.status_code == 401


def test_audit_endpoint_is_admin_only(app):
    client = TestClient(app)
    manager = app.state.session_manager
    client.cookies.set(manager.cookie_name, manager.issue(User(username="v", role="viewer")))

    response = client.get("/api/audit")
    assert response.status_code == 403
    assert response.json()["error"] == "Administrator role required"


def test_admin_can_read_the_audit_endpoint(client):
    sign_in(client)
    response = client.get("/api/audit?limit=10")

    assert response.status_code == 200
    entries = response.json()["entries"]
    assert isinstance(entries, list)
    assert any(e["event"] == "login_success" for e in entries)


def test_audit_read_is_itself_audited(client):
    """Reading the trail is a privileged action and must appear in it."""
    sign_in(client)
    client.get("/api/audit")

    actions = [e.get("action", "") for e in audit.read_recent(50)]
    assert "GET /api/audit" in actions


# -------------------------------------------------------------------- storage


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    """Starlette's TestClient leaves scope['client'] unset, so the address
    resolution is tested directly rather than through an HTTP call."""

    def __init__(self, headers=None, client=None):
        self.headers = headers or {}
        self.client = client


def test_client_ip_prefers_the_forwarded_header():
    request = _FakeRequest(
        headers={"x-forwarded-for": "203.0.113.9, 10.0.0.1"}, client=_FakeClient("10.0.0.5")
    )
    assert audit.client_ip(request) == "203.0.113.9"


def test_client_ip_falls_back_to_the_socket_address():
    assert audit.client_ip(_FakeRequest(client=_FakeClient("10.0.0.5"))) == "10.0.0.5"


def test_client_ip_is_blank_when_there_is_no_client():
    assert audit.client_ip(_FakeRequest()) == ""


def test_entries_are_one_json_object_per_line(client):
    sign_in(client)

    with open(audit.audit_path(), "r", encoding="utf-8") as handle:
        lines = [line for line in handle if line.strip()]

    assert lines
    for line in lines:
        assert json.loads(line)["event"]


def test_audit_file_is_not_world_readable(client):
    sign_in(client)
    mode = os.stat(audit.audit_path()).st_mode & 0o777
    assert mode & 0o077 == 0, f"audit log is too permissive: {oct(mode)}"


def test_auditing_never_breaks_a_request(monkeypatch, isolated_data_dir, tmp_path):
    """An unwritable audit location must degrade, not fail the login."""
    from app.config import Config

    # A regular file where the data directory should be: any write fails.
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x")
    monkeypatch.setattr(Config, "DATA_DIR", str(blocker))

    # record() must swallow the error rather than propagating it.
    entry = audit.record("test", actor="someone")
    assert entry["actor"] == "someone"
    assert audit.read_recent() == []


# ------------------------------------------------------------------- the view


def test_audit_view_is_wired_into_the_index_page(client):
    sign_in(client)
    page = client.get("/")

    assert page.status_code == 200
    assert 'id="audit-view"' in page.text
    # Hidden until the probe in audit.js succeeds.
    assert 'id="audit-nav"' in page.text
    assert "js/audit.js" in page.text


# ------------------------------------------------- auth disabled means no audit


def test_no_audit_when_authentication_is_disabled(monkeypatch, isolated_data_dir):
    from app import create_app

    # AUTH_ENABLED is cleared by the hermetic fixture.
    client = TestClient(create_app())

    assert client.get("/").status_code == 200
    assert client.get("/api/audit").status_code == 404
    assert not os.path.exists(audit.audit_path()), "auth off must not create an audit log"
