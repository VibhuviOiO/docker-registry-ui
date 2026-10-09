"""Packaging and release correctness.

Where the configuration is persisted, which defaults a fresh install gets,
and the release-note extraction that gates a publish.
"""


# ---------------------------------------------------------------------------
# from test_config_and_defaults.py
# ---------------------------------------------------------------------------

import json
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.config import Config


@pytest.fixture
def clean_env(monkeypatch, isolated_data_dir):
    """No config env vars, and no legacy file lying around to be picked up."""
    monkeypatch.delenv("CONFIG_FILE", raising=False)
    monkeypatch.delenv("REGISTRIES", raising=False)
    monkeypatch.setattr(Config, "CONFIG_FILE", "")
    monkeypatch.setattr(Config, "LEGACY_CONFIG_FILE", "/nonexistent/registries.config.json")
    return monkeypatch


# ------------------------------------------------------- configuration location


def test_config_file_defaults_inside_the_data_directory(clean_env, isolated_data_dir):
    assert Config.config_file() == str(isolated_data_dir / "registries.config.json")


def test_an_explicit_config_file_wins(clean_env, tmp_path):
    explicit = tmp_path / "elsewhere" / "registries.json"
    clean_env.setattr(Config, "CONFIG_FILE", str(explicit))

    assert Config.config_file() == str(explicit)


def test_the_legacy_path_is_still_read_when_present(clean_env, tmp_path):
    """Deployments mounting /app/registries.config.json keep working."""
    legacy = tmp_path / "legacy-registries.config.json"
    legacy.write_text("[]")
    clean_env.setattr(Config, "LEGACY_CONFIG_FILE", str(legacy))

    assert Config.config_file() == str(legacy)


def test_the_new_default_beats_the_legacy_path(clean_env, isolated_data_dir, tmp_path):
    legacy = tmp_path / "legacy-registries.config.json"
    legacy.write_text("[]")
    clean_env.setattr(Config, "LEGACY_CONFIG_FILE", str(legacy))
    (isolated_data_dir / "registries.config.json").write_text("[]")

    assert Config.config_file() == str(isolated_data_dir / "registries.config.json")


def test_registries_save_and_reload_round_trip(clean_env, isolated_data_dir):
    expected = [{"name": "Saved", "api": "http://registry:5000"}]
    clean_env.setattr(Config, "USE_ENV_CONFIG", False)
    clean_env.setattr(Config, "REGISTRIES", expected)

    assert Config.save_registries() is True
    assert json.loads((isolated_data_dir / "registries.config.json").read_text()) == expected

    clean_env.setattr(Config, "REGISTRIES", [])
    Config.load_registries()
    assert Config.REGISTRIES == expected


def test_saving_creates_the_data_directory_if_missing(clean_env, isolated_data_dir):
    fresh = isolated_data_dir / "nested" / "deeper"
    clean_env.setattr(Config, "DATA_DIR", str(fresh))
    clean_env.setattr(Config, "USE_ENV_CONFIG", False)
    clean_env.setattr(Config, "REGISTRIES", [])

    assert Config.save_registries() is True
    assert (fresh / "registries.config.json").exists()


# --------------------------------------------------------------- first run


def test_first_run_can_create_a_registry_with_default_settings(clean_env, isolated_data_dir):
    """Regression: this is what the READ_ONLY default used to break.

    ``/api/registry/create`` is refused while read-only, so a default of true
    left a fresh install unable to be configured through the setup wizard at all.
    """
    from app import create_app

    client = TestClient(create_app())
    response = client.post(
        "/api/registry/create", json={"name": "First", "api": "http://registry:5000"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    # And it landed somewhere that survives a restart.
    assert (isolated_data_dir / "registries.config.json").exists()


def test_default_read_only_is_false(repo_root):
    """Checked in a subprocess so the real default is seen, not a patched one."""
    env = {k: v for k, v in os.environ.items() if k not in ("READ_ONLY", "REGISTRIES")}
    result = subprocess.run(
        [sys.executable, "-c", "from app.config import Config; print(Config.READ_ONLY)"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


def test_read_only_can_still_be_enabled(monkeypatch, isolated_data_dir):
    from app import create_app

    monkeypatch.setenv("READ_ONLY", "true")
    monkeypatch.setattr(Config, "READ_ONLY", True)

    client = TestClient(create_app())
    response = client.post(
        "/api/registry/create", json={"name": "Nope", "api": "http://registry:5000"}
    )
    assert response.status_code == 403
    assert response.json()["error"] == "Read-only mode"


# ------------------------------------------------------------ dead settings


def test_removed_settings_are_really_gone():
    assert not hasattr(Config, "REGISTRY_URL"), "REGISTRY_URL was parsed and never used"
    assert not hasattr(Config, "CHECK_INTERVAL"), "CHECK_INTERVAL was parsed and never used"


# ----------------------------------------------------------------- Trivy


def test_trivy_receives_the_configured_cache_dir(monkeypatch, isolated_data_dir):
    from app.scanners import trivy as trivy_module

    captured = {}

    class _Result:
        returncode = 0
        stdout = '{"Results": []}'
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _Result()

    # trivy.py imports subprocess inside the method, so patch the stdlib module
    # rather than an attribute of the scanner module.
    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setenv("TRIVY_CACHE_DIR", "/var/cache/trivy-under-test")

    trivy_module.TrivyScanner("builtin", 300).scan_image(
        "http://registry:5000", "demo/app", "v1"
    )

    command = captured["cmd"]
    assert "--cache-dir" in command
    assert command[command.index("--cache-dir") + 1] == "/var/cache/trivy-under-test"


def test_trivy_cache_dir_is_left_alone_when_not_configured(monkeypatch, isolated_data_dir):
    """Regression: passing Config's default unconditionally forced
    /root/.cache/trivy, which broke scanning outside the container, where that
    path is neither writable nor wanted."""
    from app.scanners import trivy as trivy_module

    captured = {}

    class _Result:
        returncode = 0
        stdout = '{"Results": []}'
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _Result()

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.delenv("TRIVY_CACHE_DIR", raising=False)

    trivy_module.TrivyScanner("builtin", 300).scan_image(
        "http://registry:5000", "demo/app", "v1"
    )

    assert "--cache-dir" not in captured["cmd"], "Trivy should use its own default"


def test_the_trivy_lock_lives_under_the_configured_data_dir(isolated_data_dir):
    """The lock path must follow DATA_DIR, not the environment at import time."""
    from app.scanners import trivy as trivy_module

    assert trivy_module.trivy_lock_file() == str(isolated_data_dir / ".trivy_scan.lock")


# -------------------------------------------------------- scan concurrency


def test_scan_jobs_are_queued_on_the_bounded_pool(monkeypatch):
    """SCAN_WORKERS was a no-op while scans ran on Starlette's own thread pool."""
    from fastapi import BackgroundTasks

    from app import routes

    class _Executor:
        def submit(self, *args, **kwargs):  # pragma: no cover - never invoked here
            raise AssertionError("submit should be recorded, not called")

    executor = _Executor()
    monkeypatch.setattr(routes, "scan_executor", executor)
    monkeypatch.setattr(
        routes, "get_registry_by_name", lambda name: {"name": "r", "api": "http://r"}
    )
    monkeypatch.setattr(routes, "create_scan_job", lambda *args: "job-42")

    background = BackgroundTasks()
    result = routes.api_scan_image("r", "demo/app", "v1", background)

    assert result == {"scanId": "job-42", "status": "queued"}
    assert len(background.tasks) == 1

    task = background.tasks[0]
    # The queued callable must be the bounded pool's submit; anything else means
    # SCAN_WORKERS does not limit anything.
    assert task.func == executor.submit
    # args are (_run_scan_job, job_id, registry, repo, tag)
    assert task.args[1] == "job-42"


# ---------------------------------------------------------------------------
# from test_release_notes.py
# ---------------------------------------------------------------------------

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from extract_release_notes import extract  # noqa: E402

SAMPLE = """# Changelog

Preamble text.

## [2.2.0] - Unreleased

### Added

- A thing.

## [2.1.0] - 2026-06-16

### Added

- An older thing.
"""


def test_extracts_the_requested_section_only():
    section = extract(SAMPLE, "2.2.0")
    assert "A thing." in section
    assert "An older thing." not in section


def test_heading_line_is_not_part_of_the_body():
    """A trailing '- Unreleased' or a date must not leak into the release body."""
    section = extract(SAMPLE, "2.2.0")
    assert section.startswith("### Added")
    assert "Unreleased" not in section


def test_extracts_a_historical_section():
    section = extract(SAMPLE, "2.1.0")
    assert "An older thing." in section
    assert "A thing." not in section


def test_missing_version_returns_none():
    assert extract(SAMPLE, "9.9.9") is None


def test_does_not_match_a_version_by_prefix():
    """2.1 must not be satisfied by a 2.1.0 section."""
    assert extract(SAMPLE, "2.1") is None


def test_cli_prints_the_section():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "extract_release_notes.py"), "2.1.0"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "FastAPI backend" in result.stdout


def test_cli_fails_for_an_unreleased_version():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "extract_release_notes.py"), "9.9.9"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "no '## [9.9.9]' section" in result.stderr


def test_the_repository_changelog_has_the_next_version():
    """The version in app/version.py must have notes, so it is always taggable."""
    version_file = (ROOT / "app" / "version.py").read_text()
    version = version_file.split('"')[1]

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "extract_release_notes.py"), version],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"app/version.py is {version} but CHANGELOG.md has no section for it: {result.stderr}"
    )
