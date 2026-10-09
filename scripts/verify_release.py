#!/usr/bin/env python3
"""Verify a *published* image, after the release.

The unit suite and the full-stack harness both run from source, so neither can
catch the failures that actually reach users:

* the tag points at an image built from a different commit
* a default inside the image differs from the source that was tested
* the setup wizard's configuration is not persisted by the published image

This pulls the published artefact and exercises it the way a new user does: no
environment variables at all, one mounted volume, then the first run.

Usage:
    python scripts/verify_release.py                # version from app/version.py
    python scripts/verify_release.py 2.2.0
    python scripts/verify_release.py 2.2.0 --image ghcr.io/vibhuvioio/docker-registry-ui

Exit code 0 means every check passed.
"""

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
# Scratch stays inside the repository (gitignored), never the system temp area.
WORK = ROOT / ".e2e-tmp" / "release-check"
CONTAINER = "drui-release-check"
PORT = 5055
BASE = f"http://127.0.0.1:{PORT}"


class Checks:
    def __init__(self):
        self.rows = []

    def check(self, name, ok, detail=""):
        ok = bool(ok)
        self.rows.append((name, ok))
        line = f"  [{'PASS' if ok else 'FAIL'}] {name}"
        if not ok and detail:
            line += f"\n         -> {detail}"
        print(line, flush=True)
        return ok

    def report(self):
        passed = sum(1 for _, ok in self.rows if ok)
        total = len(self.rows)
        print()
        print("=" * 70)
        print(f"  {passed}/{total} checks passed")
        print("=" * 70)
        return total > 0 and passed == total


def docker(*args, check=True):
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=check)


def cleanup():
    docker("rm", "-f", CONTAINER, check=False)
    shutil.rmtree(WORK, ignore_errors=True)


def version_from_source() -> str:
    match = re.search(r'__version__ = "([^"]+)"', (ROOT / "app" / "version.py").read_text())
    if not match:
        raise SystemExit("could not read __version__ from app/version.py")
    return match.group(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("version", nargs="?", default=None)
    parser.add_argument("--image", default="vibhuvioio/docker-registry-ui")
    parser.add_argument("--keep", action="store_true", help="leave the container running")
    parser.add_argument(
        "--no-pull",
        action="store_true",
        help="verify a local image instead of pulling the published one (pre-release check)",
    )
    args = parser.parse_args()

    version = args.version or version_from_source()
    reference = f"{args.image}:{version}"

    print(f"Image under test: {reference}")
    print(f"Scratch: {WORK}\n")

    cleanup()
    WORK.mkdir(parents=True, exist_ok=True)
    checks = Checks()

    print("=== obtain the artefact ===")
    if args.no_pull:
        local = docker("image", "inspect", reference, check=False)
        if not checks.check(
            f"local image {reference} exists",
            local.returncode == 0,
            "not present locally; build it first or drop --no-pull",
        ):
            return checks.report()
    else:
        pulled = docker("pull", reference, check=False)
        if not checks.check(
            f"docker pull {reference} succeeds",
            pulled.returncode == 0,
            (pulled.stderr or pulled.stdout or "").strip()[:200],
        ):
            return checks.report()

    print("\n=== start it exactly as the README says: one volume, no env vars ===")
    started = docker(
        "run", "-d", "--name", CONTAINER,
        "-p", f"{PORT}:5000",
        "-v", f"{WORK}:/app/data",
        reference,
        check=False,
    )
    if not checks.check("container starts", started.returncode == 0, (started.stderr or "")[:200]):
        return checks.report()

    ready = False
    for _ in range(60):
        try:
            if requests.get(f"{BASE}/health/live", timeout=2).status_code == 200:
                ready = True
                break
        except requests.RequestException:
            time.sleep(2)

    checks.check("answers /health/live with no configuration at all", ready)
    if not ready:
        print(docker("logs", CONTAINER, check=False).stdout[-1500:])
        cleanup()
        return checks.report()

    try:
        health = requests.get(f"{BASE}/health", timeout=10).json()
        checks.check("/health reports healthy", health.get("status") == "healthy", str(health))

        index = requests.get(f"{BASE}/", timeout=30)
        checks.check("serves the UI", index.status_code == 200, f"HTTP {index.status_code}")

        # This is the check that catches a tag pointing at the wrong build.
        checks.check(
            f"the UI reports version {version} (tag matches the artefact)",
            f"v{version}" in index.text,
            f"the rendered page never mentions v{version}",
        )

        checks.check(
            "static assets are served",
            requests.get(f"{BASE}/static/js/core.js", timeout=10).status_code == 200,
        )

        # Authentication is opt-in: it must not be reachable on a default install.
        checks.check(
            "authentication is off by default (/login is absent)",
            requests.get(f"{BASE}/login", timeout=10).status_code == 404,
        )
        checks.check(
            "no login wall on the API",
            requests.get(f"{BASE}/api/registries", timeout=10).status_code == 200,
        )

        # The first-run path: this is what the READ_ONLY default broke.
        created = requests.post(
            f"{BASE}/api/registry/create",
            json={"name": "Release Check", "api": "http://registry:5000"},
            timeout=20,
        )
        checks.check(
            "first run can create a registry (READ_ONLY defaults to writable)",
            created.status_code == 200 and created.json().get("success") is True,
            f"HTTP {created.status_code}: {created.text[:140]}",
        )

        persisted = WORK / "registries.config.json"
        checks.check(
            "the configuration is written inside the mounted volume",
            persisted.exists(),
            f"{persisted} was never created, so the wizard's config is lost on restart",
        )
    finally:
        if not args.keep:
            cleanup()

    return checks.report()


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
