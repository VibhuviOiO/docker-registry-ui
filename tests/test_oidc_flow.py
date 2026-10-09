"""The OIDC login flow as the browser drives it, against the fake provider."""

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(oidc_env):
    from app import create_app

    return TestClient(create_app())


def start_login(client, target="/"):
    """Begin the flow and return the (state, nonce) the provider would see."""
    response = client.get(f"/auth/oidc/login?next={target}", follow_redirects=False)
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    return query["state"][0], query["nonce"][0], response


def identity(nonce, groups=("registry-admins",), username="alice"):
    return {
        "sub": "subject-1",
        "preferred_username": username,
        "name": f"{username.title()} Example",
        "email": f"{username}@example.com",
        "groups": list(groups),
        "nonce": nonce,
    }


# ------------------------------------------------------------- start of flow


def test_login_redirects_to_the_provider(client, idp):
    state, nonce, response = start_login(client)
    location = response.headers["location"]

    assert location.startswith(f"{idp.issuer}/authorize?")
    assert "code_challenge_method=S256" in location
    assert "state=" in location
    assert "nonce=" in location


def test_handshake_cookie_is_scoped_to_the_oidc_paths(client):
    _, _, response = start_login(client)
    set_cookie = response.headers["set-cookie"].lower()

    assert "drui_oidc=" in set_cookie
    assert "path=/auth/oidc" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie


def test_login_page_offers_sso_and_hides_the_password_form(client):
    page = client.get("/login")
    assert page.status_code == 200
    assert "Sign in with SSO" in page.text
    # No break-glass account is configured for this fixture.
    assert 'name="password"' not in page.text


# ------------------------------------------------------------------ callback


def test_successful_callback_creates_a_session(client, idp):
    state, nonce = start_login(client, "/cleanup")[:2]
    idp.issue_code("code-1", identity(nonce))

    response = client.get(
        f"/auth/oidc/callback?code=code-1&state={state}", follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/cleanup"

    whoami = client.get("/auth/me")
    assert whoami.status_code == 200
    assert whoami.json()["username"] == "alice"
    assert whoami.json()["isAdmin"] is True
    assert whoami.json()["provider"] == "oidc"


def test_callback_clears_the_handshake_cookie(client, idp):
    state, nonce = start_login(client)[:2]
    idp.issue_code("code-1", identity(nonce))

    response = client.get(f"/auth/oidc/callback?code=code-1&state={state}", follow_redirects=False)
    assert "drui_oidc=" in response.headers["set-cookie"]


def test_handshake_cannot_be_replayed(client, idp):
    """The callback must not be reusable once it has been consumed."""
    state, nonce = start_login(client)[:2]
    idp.issue_code("code-1", identity(nonce))

    first = client.get(f"/auth/oidc/callback?code=code-1&state={state}", follow_redirects=False)
    assert first.status_code == 303

    client.cookies.clear()
    replay = client.get(f"/auth/oidc/callback?code=code-1&state={state}", follow_redirects=False)
    assert replay.status_code == 401


def test_state_mismatch_is_rejected(client, idp):
    _, nonce = start_login(client)[:2]
    idp.issue_code("code-1", identity(nonce))

    response = client.get(
        "/auth/oidc/callback?code=code-1&state=not-the-right-state", follow_redirects=False
    )
    assert response.status_code == 401
    assert "state" in response.text.lower()


def test_callback_without_a_handshake_cookie_is_rejected(client, idp):
    idp.issue_code("code-1", identity("whatever"))
    response = client.get("/auth/oidc/callback?code=code-1&state=abc", follow_redirects=False)
    assert response.status_code == 401


def test_provider_reported_error_is_shown_as_a_failed_login(client):
    start_login(client)
    response = client.get(
        "/auth/oidc/callback?error=access_denied&error_description=user+cancelled",
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert "access_denied" in response.text


def test_callback_without_a_code_is_rejected(client):
    state, _ = start_login(client)[:2]
    response = client.get(f"/auth/oidc/callback?state={state}", follow_redirects=False)
    assert response.status_code == 401


def test_forged_token_cannot_create_a_session(client, idp):
    """A token the provider did not sign must not become a session."""
    state, nonce = start_login(client)[:2]
    idp.issue_code("code-1", identity(nonce))
    idp.mint = lambda form: idp.mint_id_token(identity(nonce), key=idp.other_key, kid=idp.kid)

    response = client.get(f"/auth/oidc/callback?code=code-1&state={state}", follow_redirects=False)
    assert response.status_code == 401
    assert client.get("/auth/me").status_code == 401


# ---------------------------------------------------------------------- RBAC


def sign_in(client, idp, groups, username="alice"):
    state, nonce = start_login(client)[:2]
    code = f"code-{username}-{'-'.join(groups) or 'none'}"
    idp.issue_code(code, identity(nonce, groups=groups, username=username))
    response = client.get(f"/auth/oidc/callback?code={code}&state={state}", follow_redirects=False)
    assert response.status_code == 303
    return response


def test_group_membership_grants_admin_through_the_flow(client, idp, monkeypatch):
    """An admin from the groups claim passes RBAC.

    READ_ONLY is turned on explicitly so the request is stopped by read-only mode
    rather than by RBAC -- a viewer would get "Administrator role required"
    instead, which is what distinguishes the two layers.
    """
    from app.config import Config

    monkeypatch.setattr(Config, "READ_ONLY", True)
    sign_in(client, idp, ["registry-admins"])

    response = client.delete("/api/delete/tag/nope/repo/latest")
    assert response.status_code == 403
    assert response.json()["error"] == "Read-only mode"


def test_admin_reaches_the_route_when_not_read_only(client, idp, monkeypatch):
    from app.config import Config

    monkeypatch.setattr(Config, "READ_ONLY", False)
    sign_in(client, idp, ["registry-admins"])

    # 404 because the registry does not exist: the request reached the route.
    response = client.delete("/api/delete/tag/nope/repo/latest")
    assert response.status_code == 404
    assert response.json()["error"] == "Registry not found"


def test_non_member_is_a_viewer_and_cannot_delete(client, idp):
    sign_in(client, idp, ["developers"], username="bob")

    assert client.get("/auth/me").json()["isAdmin"] is False
    response = client.delete("/api/delete/tag/nope/repo/latest")
    assert response.status_code == 403
    assert response.json()["error"] == "Administrator role required"


def test_sso_user_can_browse(client, idp):
    sign_in(client, idp, ["developers"], username="bob")
    assert client.get("/").status_code == 200
    assert client.get("/api/registries").status_code == 200


def test_logout_after_sso(client, idp):
    sign_in(client, idp, ["registry-admins"])
    assert client.get("/auth/me").status_code == 200

    client.get("/auth/logout", follow_redirects=False)
    assert client.get("/auth/me").status_code == 401


def _complete_chain(client, idp):
    """Run the three hops a browser makes, end to end.

    Hop 1 and hop 3 go through TestClient (the app). Hop 2 must be a real HTTP
    call: TestClient routes *every* URL to the ASGI app, so following the
    redirect to the provider would otherwise hit the app's own /authorize.
    """
    import requests

    session = requests.Session()
    session.trust_env = False  # ignore any ambient proxy configuration

    start = client.get("/auth/oidc/login?next=/", follow_redirects=False)
    assert start.status_code == 302

    provider_response = session.get(start.headers["location"], allow_redirects=False, timeout=10)
    assert provider_response.status_code == 302

    callback = provider_response.headers["location"]
    parsed = urlparse(callback)
    assert parsed.path == "/auth/oidc/callback"

    return client.get(f"{parsed.path}?{parsed.query}", follow_redirects=False)


def test_entire_browser_redirect_chain(client, idp):
    """app -> provider /authorize -> app /auth/oidc/callback -> app.

    Nothing is injected by hand: the provider issues the code and redirects back.
    """
    callback = _complete_chain(client, idp)
    assert callback.status_code == 303

    whoami = client.get("/auth/me")
    assert whoami.status_code == 200
    assert whoami.json()["username"] == "alice"
    assert whoami.json()["isAdmin"] is True


def test_entire_chain_as_a_non_admin(client, idp):
    idp.authorize_claims = lambda: {
        "sub": "subject-bob",
        "preferred_username": "bob",
        "name": "Bob Example",
        "email": "bob@example.com",
        "groups": ["developers"],
    }

    callback = _complete_chain(client, idp)
    assert callback.status_code == 303

    whoami = client.get("/auth/me").json()
    assert whoami["username"] == "bob"
    assert whoami["isAdmin"] is False

    denied = client.delete("/api/delete/tag/nope/repo/latest")
    assert denied.status_code == 403
    assert denied.json()["error"] == "Administrator role required"


# ------------------------------------------------------- break-glass fallback


def test_password_form_stays_available_with_break_glass(monkeypatch, isolated_data_dir, idp):
    """An IdP outage must not lock administrators out entirely."""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key-not-for-production")
    monkeypatch.setenv("AUTH_PUBLIC_URL", "http://testserver")
    monkeypatch.setenv("OIDC_ISSUER", idp.issuer)
    monkeypatch.setenv("OIDC_CLIENT_ID", idp.CLIENT_ID)
    monkeypatch.setenv("OIDC_CLIENT_SECRET", idp.CLIENT_SECRET)
    monkeypatch.setenv("BREAK_GLASS_USER", "emergency")
    monkeypatch.setenv("BREAK_GLASS_PASSWORD", "letmein")

    from app import create_app

    client = TestClient(create_app())
    page = client.get("/login")
    assert "Sign in with SSO" in page.text
    assert 'name="password"' in page.text

    response = client.post(
        "/auth/login",
        data={"username": "emergency", "password": "letmein", "next": "/"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert client.get("/auth/me").json()["isAdmin"] is True
