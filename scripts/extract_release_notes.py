#!/usr/bin/env python3
"""Print the CHANGELOG.md section for a version.

Used as the body of the GitHub release, and by CI to refuse a tag whose release
notes were never written.

    ./scripts/extract_release_notes.py 2.2.0

Exit codes: 0 section found, 1 no section for that version, 2 bad usage.
"""

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"


def extract(text: str, version: str):
    """Return the section body for ``version``, or None if it is not present."""
    heading = re.compile(rf"^##\s+\[?{re.escape(version)}\]?(?:\s|$)", re.MULTILINE)
    match = heading.search(text)
    if not match:
        return None

    # Skip the rest of the heading line, so a trailing "- Unreleased" or a date
    # does not leak into the release body.
    first_newline = text.find("\n", match.end())
    remainder = text[first_newline + 1:] if first_newline != -1 else ""

    next_heading = re.search(r"^##\s", remainder, re.MULTILINE)
    section = remainder[: next_heading.start()] if next_heading else remainder
    return section.strip()


def main(argv):
    if len(argv) != 2:
        print("usage: extract_release_notes.py <version>", file=sys.stderr)
        return 2

    version = argv[1].lstrip("v")
    if not CHANGELOG.exists():
        print(f"CHANGELOG.md not found at {CHANGELOG}", file=sys.stderr)
        return 1

    section = extract(CHANGELOG.read_text(encoding="utf-8"), version)
    if not section:
        print(
            f"CHANGELOG.md has no '## [{version}]' section. "
            f"Write the release notes before tagging.",
            file=sys.stderr,
        )
        return 1

    print(section)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
