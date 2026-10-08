#!/usr/bin/env python3
"""Full-stack validation: exercise every feature against a real registry and a
real OpenLDAP, with real HTTP calls.

Unlike the pytest suite (which uses TestClient and a real-but-in-process fake
identity provider), this runs the actual uvicorn app against the containers from
``docker/ldap-auth`` and drives it over the network.

Prerequisites:
    cd docker/ldap-auth
    docker compose up -d --no-build openldap ldap-bootstrap registry

Then:
    python tests/validate_full_stack.py

Exit code 0 means every check passed.
"""

import gzip
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

REGISTRY = "http://127.0.0.1:5007"
LDAP_URL = "ldap://127.0.0.1:3389"
LDAP_BASE = "dc=example,dc=com"
LDAP_BIND_DN = f"cn=registry-ui,ou=Services,{LDAP_BASE}"
LDAP_BIND_PASSWORD = "ui-bind-password"
APP_PORT = 5099
APP = f"http://127.0.0.1:{APP_PORT}"
DATA_DIR = Path("/tmp/drui-validate")
SECRET = "validation-shared-secret"


class Results:
    def __init__(self):
        self.rows = []

    def check(self, group, name, ok, detail=""):
        self.rows.append((group, name, bool(ok), detail))
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f"  ({detail})" if detail and not ok else ""))
        return ok

    def expect(self, group, name, response, status):
        return self.check(
            group,
            name,
            response.status_code == status,
            f"expected {status}, got {response.status_code}: {response.text[:120]}",
        )

    def report(self):
        groups = {}
        for group, name, ok, _ in self.rows:
            groups.setdefault(group, []).append(ok)
        print("\n" + "=" * 68)
        total = failed = 0
        for group, oks in groups.items():
            passed = sum(oks)
            total += len(oks)
            failed += len(oks) - passed
            print(f"  {group:<28} {passed}/{len(oks)}")
        print("=" * 68)
        print(f"  TOTAL: {total - failed}/{total} checks passed")
        return failed == 0


# --------------------------------------------------------------------- app


def start_app(env_overrides):
    env = dict(os.environ)
    env.update(env_overrides)
    env["DATA_DIR"] = str(DATA_DIR)
    env["LOG_LEVEL"] = "WARNING"
    env["READ_ONLY"] = "false"
    env["REGISTRIES"] = json.dumps(
        [{"name": "Local", "api": REGISTRY, "vulnerabilityScan": {"enabled": False}}]
    )

    process = subprocess.Popen(
        [
            # sys.executable, not a hardcoded venv path: this runs in CI too,
            # where the interpreter is not inside ./venv.
            sys.executable,
            "-m",
            "uvicorn",
            "asgi:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(APP_PORT),
            "--log-level",
            "warning",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(60):
        try:
            if requests.get(f"{APP}/health/live", timeout=1).status_code == 200:
                return process
        except requests.RequestException:
            time.sleep(0.5)

    process.terminate()
    raise RuntimeError("the application did not start")


def stop_app(process):
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def start_provider():
    from fake_idp import FakeIdP

    return FakeIdP().start()


# ---------------------------------------------------------------- seeding


def _digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _push_blob(repo, data):
    digest = _digest(data)
    if requests.head(f"{REGISTRY}/v2/{repo}/blobs/{digest}", timeout=10).status_code == 200:
        return digest
    start = requests.post(f"{REGISTRY}/v2/{repo}/blobs/uploads/", timeout=10)
    location = start.headers["Location"]
    if location.startswith("/"):
        location = REGISTRY + location
    separator = "&" if "?" in location else "?"
    requests.put(
        f"{location}{separator}digest={digest}", data=data,
        headers={"Content-Type": "application/octet-stream"}, timeout=30,
    ).raise_for_status()
    return digest


def seed_registry():
    plan = [
        ("demo/app", "v1", "2024-01-01T00:00:00Z"),
        ("demo/app", "v2", "2024-06-01T00:00:00Z"),
        ("demo/app", "latest", "2024-06-01T00:00:00Z"),
        ("demo/tool", "1.0", "2024-03-01T00:00:00Z"),
        ("team/service", "2024.01", "2024-01-15T00:00:00Z"),
        ("team/service", "2024.02", "2024-02-15T00:00:00Z"),
    ]
    manifest_type = "application/vnd.oci.image.manifest.v1+json"

    for repo, tag, created in plan:
        buffer = io.BytesIO()
        content = f"{repo}:{tag}\n".encode()
        with tarfile.open(fileobj=buffer, mode="w") as tar:
            info = tarfile.TarInfo("hello.txt")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        layer = gzip.compress(buffer.getvalue())
        layer_digest = _push_blob(repo, layer)

        config = json.dumps({
            "architecture": "amd64", "os": "linux", "created": created, "config": {},
            "rootfs": {"type": "layers", "diff_ids": [layer_digest]},
        }).encode()
        config_digest = _push_blob(repo, config)

        requests.put(
            f"{REGISTRY}/v2/{repo}/manifests/{tag}",
            data=json.dumps({
                "schemaVersion": 2, "mediaType": manifest_type,
                "config": {"mediaType": "application/vnd.oci.image.config.v1+json",
                           "digest": config_digest, "size": len(config)},
                "layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                            "digest": layer_digest, "size": len(layer)}],
            }).encode(),
            headers={"Content-Type": manifest_type},
            timeout=30,
        ).raise_for_status()


# ------------------------------------------------------------------- auth


def sign_in(username, password):
    session = requests.Session()
    session.trust_env = False
    response = session.post(
        f"{APP}/auth/login",
        data={"username": username, "password": password, "next": "/"},
        headers={"X-Forwarded-For": "203.0.113.9"},
        allow_redirects=False,
        timeout=10,
    )
    return session, response


def audit_events():
    path = DATA_DIR / "audit.log"
    if not path.exists():
        return []
    entries = []
    for line in path.read_text().splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


# ------------------------------------------------------------- validation


def phase_existing_features(results):
    """The features that existed before authentication was added."""
    print("\n[1] Existing features (unauthenticated health, plus authenticated browsing)")
    results.expect("health", "GET /health/live -> 200",
                   requests.get(f"{APP}/health/live", timeout=5), 200)
    results.expect("health", "GET /health -> 200",
                   requests.get(f"{APP}/health", timeout=5), 200)
    results.expect("health", "GET /static/js/core.js -> 200",
                   requests.get(f"{APP}/static/js/core.js", timeout=5), 200)

    session, response = sign_in("alice", "alicepassword")
    results.expect("auth/ldap", "alice signs in via LDAP -> 303", response, 303)

    # A rejected sign-in must be recorded too.
    _, bad = sign_in("alice", "definitely-the-wrong-password")
    results.expect("auth/ldap", "wrong password is refused -> 401", bad, 401)

    me = session.get(f"{APP}/auth/me", timeout=10).json()
    results.check("auth/ldap", "alice is admin", me.get("isAdmin") is True, str(me))
    results.check("auth/ldap", "alice profile from the directory",
                  me.get("displayName") == "Alice Example" and me.get("email") == "alice@example.com",
                  str(me))

    results.expect("features", "GET / (index) -> 200",
                   session.get(f"{APP}/", timeout=10), 200)
    results.expect("features", "GET /api/registries -> 200",
                   session.get(f"{APP}/api/registries", timeout=10), 200)
    results.expect("features", "GET /api/repositories/Local -> 200",
                   session.get(f"{APP}/api/repositories/Local", timeout=30), 200)

    repos = session.get(f"{APP}/api/repositories/Local", timeout=30).json()
    results.check("features", "registry lists the seeded repositories",
                  set(repos.get("repositories", [])) == {"demo/app", "demo/tool", "team/service"},
                  str(repos.get("repositories")))

    tags = session.get(f"{APP}/api/tags/Local/demo/app", timeout=15).json()
    results.check("features", "tags for demo/app",
                  set(tags.get("tags", [])) == {"v1", "v2", "latest"}, str(tags))

    details = session.get(f"{APP}/api/tag-details/Local/demo/app/v1", timeout=15).json()
    results.check("features", "tag details include size, digest and created date",
                  details.get("size", 0) > 0 and details.get("digest") and details.get("created"),
                  str(details)[:160])

    analytics = session.get(f"{APP}/api/analytics/Local", timeout=60).json()
    results.check("features", "analytics reports 3 repos and 6 tags",
                  analytics.get("totalRepos") == 3 and analytics.get("totalTags") == 6,
                  f"repos={analytics.get('totalRepos')} tags={analytics.get('totalTags')}")
    results.check("features", "analytics reports a non-zero total size",
                  analytics.get("totalSize", 0) > 0, str(analytics.get("totalSize")))

    vulns = session.get(f"{APP}/api/vulnerabilities/Local", timeout=15).json()
    results.check("features", "vulnerability results endpoint works",
                  isinstance(vulns.get("results"), dict), str(vulns)[:120])

    return session


def phase_rbac(results):
    print("\n[2] RBAC: viewer vs admin")
    viewer, response = sign_in("bob", "bobpassword")
    results.expect("rbac", "bob signs in via LDAP -> 303", response, 303)
    bob = viewer.get(f"{APP}/auth/me", timeout=10).json()
    results.check("rbac", "bob is a viewer", bob.get("isAdmin") is False, str(bob))

    results.expect("rbac", "viewer can browse repositories",
                   viewer.get(f"{APP}/api/repositories/Local", timeout=30), 200)
    results.expect("rbac", "viewer can read analytics",
                   viewer.get(f"{APP}/api/analytics/Local", timeout=60), 200)

    denied = viewer.delete(f"{APP}/api/delete/repo/demo/tool", timeout=15)
    results.check("rbac", "viewer cannot delete a repository",
                  denied.status_code == 403
                  and denied.json().get("error") == "Administrator role required",
                  f"{denied.status_code} {denied.text[:80]}")

    denied = viewer.post(f"{APP}/api/bulk-operation",
                         json={"registry": "Local", "dryRun": True}, timeout=30)
    results.check("rbac", "viewer cannot run bulk operations", denied.status_code == 403,
                  str(denied.status_code))

    results.expect("rbac", "viewer cannot read the audit log",
                   viewer.get(f"{APP}/api/audit", timeout=10), 403)


def phase_mutations(results, admin):
    print("\n[3] Admin mutations against the real registry")
    dry = admin.post(f"{APP}/api/bulk-operation",
                     json={"registry": "Local", "repoPattern": "team/*",
                           "dryRun": True, "keepMin": 0}, timeout=60).json()
    results.check("mutations", "bulk dry run matches team/service tags",
                  any(r["repo"] == "team/service" for r in dry.get("results", [])), str(dry)[:160])

    delete = admin.delete(f"{APP}/api/delete/tag/Local/demo/app/v1", timeout=30)
    results.check("mutations", "admin deletes a tag",
                  delete.status_code == 200 and delete.json().get("success") is True,
                  f"{delete.status_code} {delete.text[:100]}")

    remaining = admin.get(f"{APP}/api/tags/Local/demo/app", timeout=15).json().get("tags", [])
    results.check("mutations", "the deleted tag is gone",
                  "v1" not in remaining, str(remaining))

    real = admin.post(f"{APP}/api/bulk-operation",
                      json={"registry": "Local", "repoPattern": "team/*",
                            "tagPattern": "2024.01", "dryRun": False}, timeout=60)
    results.check("mutations", "bulk delete runs", real.status_code == 200, real.text[:120])
    left = admin.get(f"{APP}/api/tags/Local/team/service", timeout=15).json().get("tags", [])
    results.check("mutations", "the bulk-deleted tag is gone", "2024.01" not in left, str(left))

    toggle = admin.post(f"{APP}/api/registry/bulk-operations",
                        json={"registry": "Local", "enabled": True}, timeout=15)
    results.check("mutations", "registry configuration is writable",
                  toggle.status_code == 200, f"{toggle.status_code} {toggle.text[:80]}")

    missing = admin.get(f"{APP}/api/repositories/NoSuchRegistry", timeout=15)
    results.check("mutations", "unknown registry still 404s", missing.status_code == 404,
                  str(missing.status_code))


def phase_audit(results):
    print("\n[4] Audit trail")
    events = [e["event"] for e in audit_events()]
    for expected in ("login_success", "login_failed", "privileged_denied",
                     "privileged_request", "logout"):
        results.check("audit", f"records {expected}", expected in events)

    admin_events = [e for e in audit_events() if e["event"] == "privileged_request"]
    results.check("audit", "privileged entries name the actor",
                  all(e["actor"] for e in admin_events) and bool(admin_events))
    results.check("audit", "entries carry the forwarded client IP",
                  any(e["ip"] == "203.0.113.9" for e in audit_events()))
    results.check("audit", "entries are timestamped",
                  all(e["timestamp"] for e in audit_events()))


def phase_oidc(results):
    print("\n[5] SSO (OIDC): the live redirect chain")
    provider = start_provider()
    try:
        process = start_app({
            "AUTH_ENABLED": "true",
            "AUTH_MODE": "oidc",
            "AUTH_SECRET_KEY": SECRET,
            "AUTH_PUBLIC_URL": APP,
            "OIDC_ISSUER": provider.issuer,
            "OIDC_CLIENT_ID": provider.CLIENT_ID,
            "OIDC_CLIENT_SECRET": provider.CLIENT_SECRET,
            "OIDC_ADMIN_GROUP": "registry-admins",
            "AUTH_DEFAULT_ROLE": "viewer",
        })
        try:
            session = requests.Session()
            session.trust_env = False

            start = session.get(f"{APP}/auth/oidc/login?next=/",
                                allow_redirects=False, timeout=10)
            results.expect("sso", "app redirects to the provider -> 302", start, 302)
            results.check("sso", "authorization URL carries PKCE",
                          "code_challenge_method=S256" in start.headers.get("location", ""))
            results.check("sso", "handshake cookie is scoped to /auth/oidc",
                          "Path=/auth/oidc" in start.headers.get("set-cookie", ""))

            hop2 = session.get(start.headers["location"], allow_redirects=False, timeout=10)
            results.expect("sso", "provider redirects back -> 302", hop2, 302)

            parsed = urlparse(hop2.headers["location"])
            results.check("sso", "callback target is the app", parsed.path == "/auth/oidc/callback",
                          parsed.path)

            hop3 = session.get(f"{APP}{parsed.path}?{parsed.query}",
                               allow_redirects=False, timeout=10)
            results.expect("sso", "callback completes the sign-in -> 303", hop3, 303)

            me = session.get(f"{APP}/auth/me", timeout=10)
            results.check("sso", "session is established", me.status_code == 200, str(me.status_code))
            results.check("sso", "groups claim granted admin",
                          me.json().get("isAdmin") is True, str(me.text)[:120])
            results.check("sso", "identity came from the provider",
                          me.json().get("provider") == "oidc", str(me.text)[:120])

            results.expect("sso", "signed-in user can browse",
                           session.get(f"{APP}/api/repositories/Local", timeout=30), 200)

            session.get(f"{APP}/auth/logout", timeout=10, allow_redirects=False)
            results.check("sso", "logout ends the session",
                          session.get(f"{APP}/auth/me", timeout=10).status_code == 401)
        finally:
            stop_app(process)
    finally:
        provider.stop()


def main():
    if requests.get(f"{REGISTRY}/v2/", timeout=5).status_code != 200:
        print(f"registry is not reachable at {REGISTRY}.", file=sys.stderr)
        print("Start it with: cd docker/ldap-auth && "
              "docker compose up -d --no-build openldap ldap-bootstrap registry", file=sys.stderr)
        return 2

    shutil.rmtree(DATA_DIR, ignore_errors=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Seeding the registry...")
    seed_registry()

    results = Results()
    process = start_app({
        "AUTH_ENABLED": "true",
        "AUTH_MODE": "ldap",
        "AUTH_SECRET_KEY": SECRET,
        "AUTH_DEFAULT_ROLE": "viewer",
        "BREAK_GLASS_USER": "emergency",
        "BREAK_GLASS_PASSWORD": "letmein-validation",
        "LDAP_URL": LDAP_URL,
        "LDAP_BASE_DN": LDAP_BASE,
        "LDAP_BIND_DN": LDAP_BIND_DN,
        "LDAP_BIND_PASSWORD": LDAP_BIND_PASSWORD,
        "LDAP_USER_FILTER": "(&(objectClass=inetOrgPerson)(uid={username}))",
        "LDAP_ADMIN_GROUP": "registry-admins",
    })
    try:
        admin = phase_existing_features(results)
        phase_rbac(results)
        phase_mutations(results, admin)
        admin.get(f"{APP}/auth/logout", timeout=10, allow_redirects=False)
        phase_audit(results)
    finally:
        stop_app(process)

    phase_oidc(results)

    return 0 if results.report() else 1


if __name__ == "__main__":
    sys.exit(main())
