"""Regression guard: with authentication off, nothing changes.

These tests encode the "never disturb existing features" contract. If a future
change makes authentication mandatory, requires a new dependency, or alters the
behaviour of an existing endpoint, one of these fails.
"""

import subprocess
import sys

from fastapi.testclient import TestClient


def _client():
    from app import create_app

    app = create_app()
    return app, TestClient(app)


def test_auth_off_adds_no_middleware_and_no_routes():
    app, _ = _client()

    assert app.state.auth_enabled is False

    # No authentication middleware in the stack.
    from app.auth.middleware import AuthMiddleware

    stack = [m.cls for m in app.user_middleware]
    assert AuthMiddleware not in stack

    # None of the auth endpoints exist, so an unauthenticated request cannot be
    # redirected to a login page that is not there.
    paths = {route.path for route in app.routes}
    for path in ("/login", "/auth/login", "/auth/logout", "/auth/me"):
        assert path not in paths


def test_existing_endpoints_unchanged():
    _, client = _client()

    # Health probes: every shipped compose file depends on these being open.
    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.json() == {"status": "alive"}

    assert client.get("/health").status_code == 200

    # Main UI renders without a session.
    index = client.get("/")
    assert index.status_code == 200
    assert "text/html" in index.headers["content-type"]

    # Registry listing keeps its exact response shape.
    registries = client.get("/api/registries")
    assert registries.status_code == 200
    assert "registries" in registries.json()

    # Unknown registry: unchanged 404 semantics.
    assert client.get("/api/repositories/nope").status_code == 404
    assert client.get("/api/tags/nope/some-repo").status_code == 404
    assert client.get("/api/tag-details/nope/some-repo/latest").status_code == 404

    # Static assets are served.
    assert client.get("/static/js/core.js").status_code == 200


def test_delete_is_gated_by_read_only_not_by_auth(monkeypatch):
    """With READ_ONLY on, the refusal must come from read-only mode.

    Not from an authentication layer that does not exist while auth is off.
    READ_ONLY is set explicitly rather than taken from its default: relying on
    the default is exactly how the code and the documentation drifted apart.
    """
    from app.config import Config

    monkeypatch.setattr(Config, "READ_ONLY", True)

    _, client = _client()
    response = client.delete("/api/delete/tag/reg/repo/latest")
    assert response.status_code == 403
    assert response.json()["error"] == "Read-only mode"


def test_auth_off_does_not_require_optional_dependencies(repo_root):
    """An existing image must keep working without the auth dependencies.

    none of itsdangerous, ldap3, PyJWT or cryptography may be imported when
    authentication is off. Run in a subprocess so an earlier test cannot have
    imported them already.
    """
    script = (
        "import sys\n"
        "from app import create_app\n"
        "app = create_app()\n"
        "assert app.state.auth_enabled is False\n"
        "watched = ('ldap3', 'itsdangerous', 'jwt', 'cryptography')\n"
        "leaked = [m for m in watched if m in sys.modules]\n"
        "assert not leaked, f'auth is off but these were imported: {leaked}'\n"
        "print('clean')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "clean" in result.stdout
