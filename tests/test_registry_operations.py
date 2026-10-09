"""Registry operations: deleting tags, and the scan path.

Both come from real failures -- deleting a tag stored as an OCI image
manifest failed with "No digest found", and scanning reported a raw errno
after three pointless retries. Same subject, so one file.
"""


# ---------------------------------------------------------------------------
# from test_scanning.py
# ---------------------------------------------------------------------------

import pytest

from app import routes


class _Jobs:
    """Captures what ``_run_scan_job`` records."""

    def __init__(self, monkeypatch):
        self.updates = []
        monkeypatch.setattr(routes, "update_scan_job", self._update)
        monkeypatch.setattr(routes, "store_scan_results", lambda *args: None)

    def _update(self, job_id, status=None, result=None, error=None):
        self.updates.append({"job_id": job_id, "status": status, "result": result, "error": error})
        return True

    @property
    def final(self):
        return self.updates[-1]


class _Scanner:
    def __init__(self, available=True, results=None, calls=None):
        self._available = available
        self._results = list(results) if results else None
        self._calls = calls if calls is not None else []

    @property
    def calls(self):
        return self._calls

    def health_check(self):
        return self._available

    def scan_image(self, *args):
        self._calls.append(args)
        if self._results is None:
            return {"scanner": "trivy", "summary": {}, "total": 0, "details": [], "layers": []}
        return self._results.pop(0) if len(self._results) > 1 else self._results[0]


def _registry(**vuln):
    registry = {"name": "r", "api": "http://registry:5000"}
    if vuln:
        registry["vulnerabilityScan"] = vuln
    return registry


def test_unavailable_scanner_fails_fast_and_explains_what_to_fix(monkeypatch):
    jobs = _Jobs(monkeypatch)
    scanner = _Scanner(available=False)
    monkeypatch.setattr("app.scanners.factory.get_scanner", lambda t, u: scanner)

    routes._run_scan_job("job-1", _registry(scanner="trivy", scannerUrl="builtin"), "demo/app", "v1")

    assert jobs.final["status"] == "failed"
    message = jobs.final["error"]
    assert "Trivy CLI is not available" in message
    # It must say what to do, not just that it broke.
    assert "install" in message.lower()
    assert "container image" in message
    assert scanner.calls == [], "the scanner must not be invoked when unavailable"


def test_a_remote_trivy_server_that_is_down_is_named_in_the_error(monkeypatch):
    jobs = _Jobs(monkeypatch)
    monkeypatch.setattr(
        "app.scanners.factory.get_scanner", lambda t, u: _Scanner(available=False)
    )

    routes._run_scan_job(
        "job-2", _registry(scanner="trivy", scannerUrl="http://trivy-server:8080"), "demo/app", "v1"
    )

    assert "http://trivy-server:8080" in jobs.final["error"]


def test_permanent_failures_are_not_retried(monkeypatch):
    jobs = _Jobs(monkeypatch)
    scanner = _Scanner(results=[{"error": "no trivy", "permanent": True}])
    monkeypatch.setattr("app.scanners.factory.get_scanner", lambda t, u: scanner)
    monkeypatch.setattr(routes, "SCAN_RETRY_DELAY", 0)
    monkeypatch.setattr(routes.time, "sleep", lambda seconds: scanner.calls.append("slept"))

    routes._run_scan_job("job-3", _registry(), "demo/app", "v1")

    assert jobs.final["status"] == "failed"
    assert len(scanner.calls) == 1, "a permanent failure must be attempted exactly once"


def test_transient_failures_still_retry(monkeypatch):
    """The retry policy exists for registry contention; it must still work."""
    jobs = _Jobs(monkeypatch)
    scanner = _Scanner(
        results=[
            {"error": "registry busy"},
            {"error": "registry busy"},
            {"scanner": "trivy", "summary": {}, "total": 0, "details": [], "layers": []},
        ]
    )
    monkeypatch.setattr("app.scanners.factory.get_scanner", lambda t, u: scanner)
    monkeypatch.setattr(routes, "SCAN_RETRIES", 3)
    monkeypatch.setattr(routes, "SCAN_RETRY_DELAY", 0)
    monkeypatch.setattr(routes.time, "sleep", lambda seconds: None)

    routes._run_scan_job("job-4", _registry(), "demo/app", "v1")

    assert len(scanner.calls) == 3
    assert jobs.final["status"] == "completed"


def test_the_configured_scanner_and_url_are_honoured(monkeypatch):
    """Regression: single scans were hardcoded to the built-in Trivy binary, so
    a configured remote Trivy server was silently ignored."""
    seen = {}

    def fake_get_scanner(scanner_type, scanner_url):
        seen["type"] = scanner_type
        seen["url"] = scanner_url
        return _Scanner()

    monkeypatch.setattr("app.scanners.factory.get_scanner", fake_get_scanner)
    _Jobs(monkeypatch)

    routes._run_scan_job(
        "job-5",
        _registry(scanner="trivy", scannerUrl="http://trivy-server:8080"),
        "demo/app",
        "v1",
    )

    assert seen == {"type": "trivy", "url": "http://trivy-server:8080"}


def test_scanner_status_endpoint_reports_why_it_is_unusable(monkeypatch):
    monkeypatch.setattr(routes, "get_registry_by_name", lambda name: {"name": name, "api": "http://r"})
    monkeypatch.setattr("app.scanners.factory.get_scanner", lambda t, u: _Scanner(available=False))

    result = routes.api_scanner_status("r")

    assert result["available"] is False
    assert result["scanner"] == "trivy"
    assert "Trivy CLI is not available" in result["reason"]


def test_scanner_status_endpoint_reports_availability(monkeypatch):
    monkeypatch.setattr(routes, "get_registry_by_name", lambda name: {"name": name, "api": "http://r"})
    monkeypatch.setattr("app.scanners.factory.get_scanner", lambda t, u: _Scanner(available=True))

    result = routes.api_scanner_status("r")

    assert result["available"] is True
    assert result["reason"] is None


def test_scanner_status_endpoint_404s_for_an_unknown_registry(monkeypatch):
    monkeypatch.setattr(routes, "get_registry_by_name", lambda name: None)

    response = routes.api_scanner_status("nope")

    assert response.status_code == 404


def test_a_missing_trivy_binary_is_reported_as_permanent(monkeypatch, isolated_data_dir):
    from app.scanners import trivy as trivy_module

    def fake_run(cmd, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "trivy")

    monkeypatch.setattr("subprocess.run", fake_run)

    result = trivy_module.TrivyScanner("builtin", 300).scan_image(
        "http://registry:5000", "demo/app", "v1"
    )

    assert result["permanent"] is True
    assert "Trivy CLI is not available" in result["error"]


# ---------------------------------------------------------------------------
# from test_deletion.py
# ---------------------------------------------------------------------------

from app import registry

OCI_IMAGE_MANIFEST = "application/vnd.oci.image.manifest.v1+json"
DOCKER_V2_MANIFEST = "application/vnd.docker.distribution.manifest.v2+json"
OCI_INDEX = "application/vnd.oci.image.index.v1+json"
DOCKER_LIST = "application/vnd.docker.distribution.manifest.list.v2+json"


class _Response:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = ""


def _fake_registry(monkeypatch, stored_type):
    """A registry that only serves manifests of ``stored_type``."""
    seen = []

    def fake_get(url, headers=None, auth=None, timeout=None):
        accept = (headers or {}).get("Accept")
        seen.append(accept)
        if accept == stored_type:
            return _Response(200, {"Docker-Content-Digest": "sha256:deadbeef"})
        return _Response(404)

    def fake_delete(url, headers=None, auth=None, timeout=None):
        seen.append("DELETE")
        return _Response(202)

    monkeypatch.setattr(registry.requests, "get", fake_get)
    monkeypatch.setattr(registry.requests, "delete", fake_delete)
    return seen


@pytest.mark.parametrize(
    "stored_type",
    [OCI_IMAGE_MANIFEST, DOCKER_V2_MANIFEST, OCI_INDEX, DOCKER_LIST],
)
def test_delete_tag_handles_every_stored_manifest_type(monkeypatch, stored_type):
    _fake_registry(monkeypatch, stored_type)

    success, error = registry.delete_tag("http://registry:5000", "demo/app", "v1")

    assert success is True, f"could not delete a {stored_type} tag: {error}"


def test_delete_tag_requests_the_oci_image_manifest_type(monkeypatch):
    seen = _fake_registry(monkeypatch, OCI_IMAGE_MANIFEST)

    registry.delete_tag("http://registry:5000", "demo/app", "v1")

    assert OCI_IMAGE_MANIFEST in seen


def test_delete_tag_reports_an_unmatched_manifest(monkeypatch):
    _fake_registry(monkeypatch, "application/vnd.example.unknown+json")

    success, error = registry.delete_tag("http://registry:5000", "demo/app", "v1")

    assert success is False
    assert error == "No digest found"


def test_bulk_operation_reports_failed_deletions(monkeypatch):
    """A deletion that fails must not be reported as a successful cleanup."""
    from app import routes
    from app.config import Config

    monkeypatch.setattr(Config, "READ_ONLY", False)

    monkeypatch.setattr(routes, "get_registry_by_name", lambda name: {"name": "x", "api": "http://r"})
    monkeypatch.setattr(routes, "get_auth", lambda reg: None)
    monkeypatch.setattr(routes, "fetch_repositories", lambda api, auth: (["demo/app"], None))
    monkeypatch.setattr(routes, "fetch_repository_tags", lambda api, repo, auth: ["v1"])
    monkeypatch.setattr(routes, "fetch_tag_details", lambda api, repo, tag, auth: {"created": None})
    monkeypatch.setattr(routes, "delete_tag", lambda api, repo, tag, auth: (False, "No digest found"))

    result = routes.api_bulk_operation({"registry": "x", "dryRun": False})

    assert result["failures"] == [
        {"repo": "demo/app", "tag": "v1", "error": "No digest found"}
    ]


def test_bulk_operation_reports_no_failures_when_deletion_works(monkeypatch):
    from app import routes
    from app.config import Config

    monkeypatch.setattr(Config, "READ_ONLY", False)

    monkeypatch.setattr(routes, "get_registry_by_name", lambda name: {"name": "x", "api": "http://r"})
    monkeypatch.setattr(routes, "get_auth", lambda reg: None)
    monkeypatch.setattr(routes, "fetch_repositories", lambda api, auth: (["demo/app"], None))
    monkeypatch.setattr(routes, "fetch_repository_tags", lambda api, repo, auth: ["v1"])
    monkeypatch.setattr(routes, "fetch_tag_details", lambda api, repo, tag, auth: {"created": None})
    monkeypatch.setattr(routes, "delete_tag", lambda api, repo, tag, auth: (True, None))

    result = routes.api_bulk_operation({"registry": "x", "dryRun": False})

    assert result["failures"] == []
    assert result["results"] == [{"repo": "demo/app", "tags": ["v1"], "count": 1}]
