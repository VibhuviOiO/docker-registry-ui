"""Exercise the Requests hook/redirect pipeline without external services."""

import io
import json
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from requests.adapters import BaseAdapter

from app.registry import get_auth, fetch_repository_tags, delete_tag
from app.registry_auth import RegistryAuth


REGISTRY = "https://registry.example"
REALM = "https://auth.example/token"
CHALLENGE = f'Bearer realm="{REALM}",service="registry",scope="repository:team/image:pull,push"'


class Transport(BaseAdapter):
    def __init__(self, respond):
        self.respond = respond
        self.calls = []

    def send(self, request, **kwargs):
        self.calls.append((request, kwargs))
        status, headers, body = self.respond(request)
        response = requests.Response()
        response.status_code = status
        response.headers.update(headers)
        response._content = json.dumps(body).encode()
        response.raw = io.BytesIO(response._content)
        response.request = request
        response.url = request.url
        response.connection = self
        return response

    def close(self):
        pass


@pytest.fixture
def transport(monkeypatch):
    def install(respond):
        adapter = Transport(respond)
        monkeypatch.setattr(requests.Session, "get_adapter", lambda self, url: adapter)
        return adapter
    return install


@pytest.mark.parametrize("field", ["token", "access_token"])
@pytest.mark.parametrize("credentials", [False, True])
def test_bearer_exchange_preserves_scope_and_request(transport, field, credentials):
    def respond(request):
        if request.url.startswith(REALM):
            assert parse_qs(urlsplit(request.url).query) == {
                "service": ["registry"], "scope": ["repository:team/image:pull,push"]
            }
            assert request.headers.get("Authorization") == (
                "Basic dXNlcjpwYXNz" if credentials else None
            )
            return 200, {}, {field: "issued-token"}
        if request.headers.get("Authorization") == "Bearer issued-token":
            assert request.method == "DELETE"
            assert request.headers["Accept"] == "application/example"
            return 202, {}, {}
        return 401, {"WWW-Authenticate": 'Basic realm="legacy", ' + CHALLENGE}, {}

    adapter = transport(respond)
    auth = RegistryAuth("user", "pass") if credentials else RegistryAuth()
    result = requests.delete(REGISTRY + "/v2/team/image/manifests/sha256:abc",
                             auth=auth, headers={"Accept": "application/example"}, timeout=7)
    assert result.status_code == 202
    assert result.history[0].status_code == 401
    assert len(adapter.calls) == 3
    assert adapter.calls[1][1]["verify"] is True
    assert adapter.calls[1][1]["timeout"] == 7


def test_basic_registry_still_receives_credentials(transport):
    adapter = transport(lambda request: (200, {}, {}))
    assert requests.get(REGISTRY, auth=RegistryAuth("user", "pass")).status_code == 200
    assert adapter.calls[0][0].headers["Authorization"] == "Basic dXNlcjpwYXNz"
    assert len(adapter.calls) == 1


def test_401_retry_is_bounded_and_new_requests_can_refresh(transport):
    count = 0

    def respond(request):
        nonlocal count
        if request.url.startswith(REALM):
            count += 1
            return 200, {}, {"token": f"token-{count}"}
        return 401, {"WWW-Authenticate": CHALLENGE}, {}

    adapter = transport(respond)
    auth = RegistryAuth()
    for _ in range(2):
        assert requests.get(REGISTRY, auth=auth).status_code == 401
    assert count == 2
    assert len(adapter.calls) == 6
    assert adapter.calls[2][0].headers["Authorization"] == "Bearer token-1"
    assert adapter.calls[5][0].headers["Authorization"] == "Bearer token-2"


@pytest.mark.parametrize("header", [
    "", 'Basic realm="registry"', 'Bearer service="registry"',
    'Bearer realm="http://auth.example/token"',
    'Bearer realm="https://user:pass@auth.example/token"',
    'Bearer realm="https://auth.example/token#fragment"',
])
def test_missing_unsupported_or_unsafe_challenges_do_not_retry(transport, header):
    adapter = transport(lambda request: (401, {"WWW-Authenticate": header}, {}))
    assert requests.get(REGISTRY, auth=RegistryAuth("user", "pass")).status_code == 401
    assert len(adapter.calls) == 1


@pytest.mark.parametrize("status,payload", [
    (403, {}), (200, {}), (200, []), (200, {"token": 123}),
    (200, {"token": "unsafe\r\nvalue"}),
])
def test_failed_or_invalid_token_responses_leave_401(transport, status, payload):
    def respond(request):
        if request.url.startswith(REALM):
            return status, {}, payload
        return 401, {"WWW-Authenticate": CHALLENGE}, {}

    adapter = transport(respond)
    assert requests.get(REGISTRY, auth=RegistryAuth()).status_code == 401
    assert len(adapter.calls) == 2


def test_token_redirect_is_not_followed(transport):
    def respond(request):
        if request.url.startswith(REALM):
            return 302, {"Location": "https://other.example/token"}, {}
        return 401, {"WWW-Authenticate": CHALLENGE}, {}

    adapter = transport(respond)
    assert requests.get(REGISTRY, auth=RegistryAuth("user", "pass")).status_code == 401
    assert len(adapter.calls) == 2


def test_redirected_registry_cannot_trigger_credential_exchange(transport):
    def respond(request):
        if request.url.startswith(REGISTRY):
            return 302, {"Location": "https://other.example/v2/"}, {}
        assert "Authorization" not in request.headers
        return 401, {"WWW-Authenticate": CHALLENGE}, {}

    adapter = transport(respond)
    assert requests.get(REGISTRY, auth=RegistryAuth("user", "pass")).status_code == 401
    assert len(adapter.calls) == 2


@pytest.mark.parametrize("url,verify", [("http://registry.example", True), (REGISTRY, False)])
def test_unverified_registry_cannot_delegate_credentials(transport, url, verify):
    adapter = transport(lambda request: (401, {"WWW-Authenticate": CHALLENGE}, {}))
    assert requests.get(url, auth=RegistryAuth("user", "pass"), verify=verify).status_code == 401
    assert len(adapter.calls) == 1


def test_auth_configuration_contracts():
    assert get_auth({"auth": {"type": "bearer", "token": "fixed"}}) == {
        "Authorization": "Bearer fixed"
    }
    assert get_auth({"isAuthEnabled": True, "apiToken": "legacy"}) == {
        "Authorization": "Bearer legacy"
    }
    for config in (
        {"user": "user", "password": "pass", "isAuthEnabled": False},
        {"auth": {"type": "none", "username": "user", "password": "pass"},
         "isAuthEnabled": True, "user": "user", "password": "pass"},
    ):
        assert get_auth(config).basic is None
    for config in (
        {"auth": {"type": "basic", "username": "user", "password": "pass"}},
        {"isAuthEnabled": True, "user": "user", "password": "pass"},
    ):
        assert get_auth(config).basic.username == "user"


def test_registry_operations_and_connection_test_use_challenge_auth(transport):
    from app.routes import api_test_registry

    def respond(request):
        if request.url.startswith(REALM):
            return 200, {}, {"token": "issued-token"}
        if request.headers.get("Authorization") != "Bearer issued-token":
            return 401, {"WWW-Authenticate": CHALLENGE}, {}
        if request.method == "DELETE":
            return 202, {}, {}
        return 200, {"Docker-Content-Digest": "sha256:abc"}, {"tags": ["latest"]}

    transport(respond)
    config = {"api": REGISTRY, "isAuthEnabled": True, "user": "user", "password": "pass"}
    assert fetch_repository_tags(REGISTRY, "team/image", get_auth(config)) == ["latest"]
    assert delete_tag(REGISTRY, "team/image", "latest", get_auth(config)) == (True, None)
    assert api_test_registry(config) == {"success": True}


def test_http_token_service_requires_explicit_opt_in(transport):
    realm = "http://auth.example/token"

    def respond(request):
        if request.url.startswith(realm):
            assert request.headers["Authorization"] == "Basic dXNlcjpwYXNz"
            return 200, {}, {"token": "issued-token"}
        if request.headers.get("Authorization") == "Bearer issued-token":
            return 200, {}, {"tags": ["latest"]}
        return 401, {"WWW-Authenticate": f'Bearer realm="{realm}"'}, {}

    adapter = transport(respond)
    config = {"isAuthEnabled": True, "user": "user", "password": "pass"}
    assert fetch_repository_tags("http://registry.example", "team/image", get_auth(config)) == []
    assert len(adapter.calls) == 1
    config["allowHttp"] = True
    assert fetch_repository_tags("http://registry.example", "team/image", get_auth(config)) == ["latest"]
    assert len(adapter.calls) == 4
    assert all(kwargs["verify"] is True for _, kwargs in adapter.calls)


@pytest.mark.parametrize("auth_config", [
    {}, {"isAuthEnabled": True, "user": "user", "password": "pass"},
    {"auth": {"type": "bearer", "token": "fixed"}},
    {"isAuthEnabled": True, "apiToken": "fixed"},
])
def test_skip_tls_verification_reaches_registry_and_token_service(transport, auth_config):
    def respond(request):
        if request.url.startswith(REALM):
            return 200, {}, {"token": "issued-token"}
        if request.headers.get("Authorization") in ("Bearer fixed", "Bearer issued-token"):
            return 200, {}, {"tags": ["latest"]}
        return 401, {"WWW-Authenticate": CHALLENGE}, {}

    adapter = transport(respond)
    config = {**auth_config, "skipTlsVerify": True}
    assert fetch_repository_tags(REGISTRY, "team/image", get_auth(config)) == ["latest"]
    assert all(kwargs["verify"] is False for _, kwargs in adapter.calls)


def test_connection_test_applies_tls_setting(transport):
    from app.routes import api_test_registry

    adapter = transport(lambda request: (200, {}, {}))
    assert api_test_registry({"api": REGISTRY, "skipTlsVerify": True}) == {"success": True}
    assert adapter.calls[0][1]["verify"] is False


def test_connection_options_persist_and_are_returned(monkeypatch, isolated_data_dir):
    from app.config import Config
    from app.data_store import update_registry_config
    from app.routes import api_registries

    monkeypatch.setattr(Config, "REGISTRIES", [{"name": "test", "api": REGISTRY}])
    monkeypatch.setattr(Config, "USE_ENV_CONFIG", False)
    monkeypatch.setattr(Config, "CONFIG_FILE", str(isolated_data_dir / "registries.config.json"))
    assert update_registry_config("test", {"allowHttp": True, "skipTlsVerify": True})
    persisted = json.loads((isolated_data_dir / "registries.config.json").read_text())
    assert persisted[0]["allowHttp"] is True
    assert persisted[0]["skipTlsVerify"] is True
    assert api_registries()["registries"][0]["allowHttp"] is True
    assert api_registries()["registries"][0]["skipTlsVerify"] is True
    assert update_registry_config("test", {"skipTlsVerify": False})
    assert Config.REGISTRIES[0]["allowHttp"] is True
    assert Config.REGISTRIES[0]["skipTlsVerify"] is False


@pytest.mark.parametrize("value", [False, "false", "true", 1, None])
def test_connection_options_require_boolean_true(value):
    auth = get_auth({"allowHttp": value, "skipTlsVerify": value})
    assert auth.allow_http is False
    assert auth.skip_tls_verify is False


@pytest.mark.parametrize("spacing", [" = ", "\t=\t", "= ", " ="])
def test_challenge_parameters_allow_whitespace_around_equals(transport, spacing):
    challenge = (
        f'Basic realm="legacy", bEaReR realm{spacing}"{REALM}", '
        f'Service{spacing}"registry", Scope{spacing}"repository:team/image:pull,push", '
        'Basic realm="other"'
    )

    def respond(request):
        if request.url.startswith(REALM):
            assert parse_qs(urlsplit(request.url).query) == {
                "service": ["registry"], "scope": ["repository:team/image:pull,push"]
            }
            return 200, {}, {"token": "issued-token"}
        if request.headers.get("Authorization") == "Bearer issued-token":
            return 200, {}, {}
        return 401, {"WWW-Authenticate": challenge}, {}

    adapter = transport(respond)
    assert requests.get(REGISTRY, auth=RegistryAuth()).status_code == 200
    assert len(adapter.calls) == 3


@pytest.mark.parametrize("bypass_host", ["auth.example", "registry.example"])
def test_token_service_resolves_its_own_environment_proxy(transport, monkeypatch, bypass_host):
    for name in ("http_proxy", "https_proxy", "all_proxy", "no_proxy",
                 "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)
    proxy = "http://proxy.example:3128"
    monkeypatch.setenv("HTTPS_PROXY", proxy)
    monkeypatch.setenv("NO_PROXY", bypass_host)

    def respond(request):
        if request.url.startswith(REALM):
            return 200, {}, {"token": "issued-token"}
        if request.headers.get("Authorization") == "Bearer issued-token":
            return 200, {}, {}
        return 401, {"WWW-Authenticate": CHALLENGE}, {}

    adapter = transport(respond)
    assert requests.get(REGISTRY, auth=RegistryAuth()).status_code == 200
    assert len(adapter.calls) == 3
    for request, options in adapter.calls:
        expected = None if urlsplit(request.url).hostname == bypass_host else proxy
        assert options["proxies"].get("https") == expected
