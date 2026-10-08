"""Release-note extraction.

The release cannot be published without notes for the tagged version, so the
extraction is what decides whether a tag is releasable.
"""

import subprocess
import sys
from pathlib import Path

import pytest

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
