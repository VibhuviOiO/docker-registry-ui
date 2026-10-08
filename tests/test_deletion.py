"""Deletion paths: registry client and bulk operations.

Regression guard. A registry answers 404 -- not the manifest -- when the
requested Accept type does not match what it has stored. ``delete_tag``'s list
of accepted types was missing the OCI image manifest (what modern builds
produce), so every deletion of such a tag failed with "No digest found", and
``delete_repository`` / bulk cleanup silently removed nothing.
"""

import pytest

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
