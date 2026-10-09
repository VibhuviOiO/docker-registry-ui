# Docker Registry UI - [Docs](https://vibhuvioio.com/docker-registry-ui/)

Modern web interface for managing Docker Registry with vulnerability scanning, bulk operations, and multi-registry support.

[![Docker Hub Pulls](https://img.shields.io/docker/pulls/vibhuvioio/docker-registry-ui)](https://hub.docker.com/r/vibhuvioio/docker-registry-ui)
[![GHCR Pulls](https://img.shields.io/badge/GHCR%20Pulls-15.5K-blue?logo=github)](https://github.com/VibhuviOiO/docker-registry-ui/pkgs/container/docker-registry-ui)
[![Release](https://img.shields.io/badge/release-v2.1.0-blue.svg)](https://github.com/VibhuviOiO/docker-registry-ui/releases/tag/v2.1.0)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[![Open in Gitpod](https://img.shields.io/badge/Gitpod-Ready%20to%20Code-purple?logo=gitpod)](https://gitpod.io/#https://github.com/VibhuviOiO/docker-registry-ui)

[![Docker Registry UI](https://vibhuvioio.com/img/docker-registry-ui/repositories.png)](https://vibhuvioio.com/docker-registry-ui/)

## 🚀 Try It Now (2 Minutes)

### ☁️ Play with Docker (Browser)

Click the button below to try Docker Registry UI instantly in your browser using [Play with Docker](https://labs.play-with-docker.com/):

[![Try in PWD](https://raw.githubusercontent.com/play-with-docker/stacks/master/assets/images/button.png)](https://labs.play-with-docker.com/?stack=https://raw.githubusercontent.com/VibhuviOiO/docker-registry-ui/main/docker/built-in-trivy/docker-compose.yml)

**Note:** This launches a single-registry setup. The UI will be available on port **5000** and the registry on port **5001**.

### 🖥️ Local Quick Start

```bash
# Download test environment
wget https://raw.githubusercontent.com/VibhuviOiO/docker-registry-ui/main/docker/multi-registry/docker-compose.yml
wget https://raw.githubusercontent.com/VibhuviOiO/docker-registry-ui/main/docker/multi-registry/registries.config.json
wget https://raw.githubusercontent.com/VibhuviOiO/docker-registry-ui/main/docker/multi-registry/populate-test-images.sh

chmod +x populate-test-images.sh

# Start registries, Trivy server, and UI
docker compose -f docker-compose.yml up -d

# Populate with test images (optional, takes 5-10 min)
./populate-test-images.sh

# Open http://localhost:5003
```

## ✨ Features

- 📦 Repository & tag management
- 🛡️ Vulnerability scanning (Trivy)
- 🗑️ Bulk operations with safety features
- 🔗 Multi-registry support
- 📊 Storage analytics
- 🎨 Modern, responsive UI

## 📦 Quick Start (Production)

### Built-in Trivy (simplest)

```bash
# Simple setup (setup wizard will guide you)
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/trivy-data:/root/.cache/trivy \
  vibhuvioio/docker-registry-ui:latest

# With test registry (using Docker network)
docker network create registry-net
docker run -d --name test-registry --network registry-net -p 5001:5000 \
  -e REGISTRY_STORAGE_DELETE_ENABLED=true registry:2
docker run -d --name registry-ui --network registry-net -p 5000:5000 \
  -e 'REGISTRIES=[{"name":"Local Registry","api":"http://test-registry:5000","vulnerabilityScan":{"enabled":true,"scanner":"trivy","scannerUrl":"builtin"}}]' \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/trivy-data:/root/.cache/trivy \
  vibhuvioio/docker-registry-ui:latest
```

> **Tip:** Mount `/root/.cache/trivy` to persist the Trivy vulnerability database across container restarts.

### Single-Registry Compose Examples

- [`docker/remote-trivy`](docker/remote-trivy/docker-compose.yml) — recommended; uses a dedicated Trivy server for concurrent scans
- [`docker/built-in-trivy`](docker/built-in-trivy/docker-compose.yml) — uses the Trivy binary inside the UI container
- [`docker/ldap-auth`](docker/ldap-auth/docker-compose.yml) — LDAP login against a bundled OpenLDAP, with admin and viewer demo accounts

## 🔧 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CONFIG_FILE` | `<DATA_DIR>/registries.config.json` | Path to registries configuration file |
| `DATA_DIR` | `/app/data` | Directory where the registries configuration, scan results and scan job state are persisted |
| `TRIVY_CACHE_DIR` | `/root/.cache/trivy` | Directory where the built-in Trivy scanner stores its vulnerability database |
| `READ_ONLY` | `false` | Disable delete operations (deleting tags and repositories, bulk cleanup). Set `true` when exposing the UI publicly |
| `LOG_LEVEL` | `WARNING` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `UVICORN_WORKERS` | `4` | Number of Uvicorn worker processes |
| `SCAN_WORKERS` | `2` | Concurrent background scans per Uvicorn worker |
| `SCAN_RETRIES` | `3` | Retry attempts for transient scan failures |
| `SCAN_RETRY_DELAY` | `2` | Base delay in seconds between scan retries |

The registries configuration now lives inside `DATA_DIR`, so the single volume in
the quick start below persists the setup wizard's configuration across restarts.
An existing deployment that mounts `/app/registries.config.json` keeps working —
that path is still read when it is present — or set `CONFIG_FILE` explicitly.

Access at `http://localhost:5000` - Setup wizard will guide you.

## 🔐 Authentication (optional)

Authentication is **opt-in and off by default**. With `AUTH_ENABLED` unset the UI
behaves exactly as before: no login page, no extra endpoints, and none of the
authentication dependencies are even loaded.

Set `AUTH_ENABLED=true` and choose a mode with `AUTH_MODE` (`ldap`, `oidc`, or
`none` for break-glass only).

| Variable | Default | Description |
|---|---|---|
| `AUTH_ENABLED` | `false` | Turn authentication on |
| `AUTH_MODE` | `none` | `ldap` or `oidc` |
| `AUTH_SECRET_KEY` | generated into `DATA_DIR` | Session signing key — **must be identical in every worker** |
| `AUTH_SESSION_HOURS` | `12` | Session lifetime |
| `AUTH_COOKIE_SECURE` | `false` | Set `true` when serving over HTTPS |
| `AUTH_DEFAULT_ROLE` | `viewer` | Role for a user matching no group or claim |
| `BREAK_GLASS_USER` / `BREAK_GLASS_PASSWORD` | — | Emergency admin that still works when the IdP or directory is down |

### LDAP / Active Directory

| Variable | Default | Description |
|---|---|---|
| `LDAP_URL` | — | `ldap://host:389` or `ldaps://host:636` |
| `LDAP_BASE_DN` | — | e.g. `dc=example,dc=com` |
| `LDAP_BIND_DN` / `LDAP_BIND_PASSWORD` | — | Search account; `LDAP_BIND_PASSWORD_FILE` is also supported for Docker/Kubernetes secrets |
| `LDAP_USER_FILTER` | `(&(objectClass=inetOrgPerson)(uid={username}))` | Must match exactly one entry |
| `LDAP_ADMIN_GROUP` | — | Group(s) granting the admin role. Separate several with `;` — **not** `,`, because commas are part of a DN |
| `LDAP_GROUP_FILTER` | — | Optional group search for directories without the memberOf overlay (e.g. `(&(objectClass=groupOfNames)(member={user_dn}))`) |
| `LDAP_STARTTLS` / `LDAP_CA_CERT` / `LDAP_INSECURE` | `false` / — / `false` | Transport security |

```yaml
environment:
  AUTH_ENABLED: "true"
  AUTH_MODE: "ldap"
  AUTH_SECRET_KEY: "${AUTH_SECRET_KEY}"          # shared by all workers
  BREAK_GLASS_USER: "emergency"                   # recovery path
  BREAK_GLASS_PASSWORD: "${BREAK_GLASS_PASSWORD}"
  LDAP_URL: "ldaps://ldap.example.com:636"
  LDAP_BASE_DN: "dc=example,dc=com"
  LDAP_BIND_DN: "cn=registry-ui,ou=Services,dc=example,dc=com"
  LDAP_BIND_PASSWORD_FILE: "/run/secrets/ldap_bind_password"
  LDAP_ADMIN_GROUP: "registry-admins"
```

A runnable example, including a bundled OpenLDAP with an admin and a viewer
account, is in [`docker/ldap-auth`](docker/ldap-auth/docker-compose.yml).

### Single sign-on (OIDC)

Works with any provider that publishes a discovery document: Keycloak, Entra ID,
Okta, Authentik, Google, ... The UI uses the authorization-code flow with PKCE,
verifies the `id_token` signature against the provider's JWKS, and checks the
issuer, audience, expiry and nonce.

| Variable | Default | Description |
|---|---|---|
| `OIDC_ISSUER` | — | Issuer URL, e.g. `https://keycloak.example.com/realms/main` |
| `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` | — | Confidential client credentials; `OIDC_CLIENT_SECRET_FILE` is also supported |
| `AUTH_PUBLIC_URL` | — | The URL **the browser** uses to reach this UI. The redirect URI is `<AUTH_PUBLIC_URL>/auth/oidc/callback` and must be registered with the provider |
| `OIDC_SCOPES` | `openid profile email` | Requested scopes; add whatever exposes your groups claim |
| `OIDC_USERNAME_CLAIM` | `preferred_username` | Falls back to email, then `sub` |
| `OIDC_GROUPS_CLAIM` | `groups` | Claim holding group membership |
| `OIDC_ADMIN_GROUP` | — | Group(s) granting admin; separate several with `;` |
| `OIDC_CA_CERT` / `OIDC_INSECURE` | — / `false` | For a self-signed or internal provider |

```yaml
environment:
  AUTH_ENABLED: "true"
  AUTH_MODE: "oidc"
  AUTH_PUBLIC_URL: "https://registry-ui.example.com"
  OIDC_ISSUER: "https://keycloak.example.com/realms/main"
  OIDC_CLIENT_ID: "docker-registry-ui"
  OIDC_CLIENT_SECRET_FILE: "/run/secrets/oidc_client_secret"
  OIDC_ADMIN_GROUP: "registry-admins"
  BREAK_GLASS_USER: "emergency"          # stays available if the IdP is down
  BREAK_GLASS_PASSWORD: "${BREAK_GLASS_PASSWORD}"
```

> If `OIDC_ADMIN_GROUP` is set but the groups claim is missing from the
> `id_token`, everyone silently gets the default role. The application logs a
> warning when that happens; otherwise configure a protocol mapper (Keycloak) or
> a groups claim (Entra/Okta) so the claim is actually present.

### Roles

Two roles are enforced:

| Role | Can do |
|---|---|
| `viewer` | Browse repositories and tags, view manifests and layers, run and read vulnerability scans, view analytics and export CSV |
| `admin` | Everything a viewer can, plus delete tags/repositories, bulk cleanup, changing registry configuration, and reading the audit log |

`READ_ONLY=true` still applies on top of the role, so an admin cannot delete
anything in read-only mode. Roles are derived from directory group membership or
an SSO claim; an unmatched user gets `AUTH_DEFAULT_ROLE`.

### Audit log

When authentication is enabled, every sign-in, failed sign-in, sign-out and
privileged action is appended to `audit.log` in the data directory — a JSON-lines
file, one object per event:

```json
{"timestamp":"2026-10-08T08:14:02+00:00","event":"privileged_request","actor":"alice",
 "role":"admin","provider":"ldap","action":"DELETE /api/delete/tag/prod/api/latest",
 "target":"/api/delete/tag/prod/api/latest","status":202,"ip":"203.0.113.9","detail":null}
```

Events are `login_success`, `login_failed`, `logout`, `privileged_request` and
`privileged_denied`. Writes are serialised with a file lock, so several uvicorn
workers can append safely, and the file rotates at 5 MB to `audit.log.1`.

Administrators can read the trail in the **Audit Log** view, or via
`GET /api/audit?limit=200` (admin-only; the entry for reading it is itself
audited). The application never edits or deletes entries — ship the file to your
log collector if you need retention beyond the on-disk rotation.


## 🧭 Run Locally (Developer)

### Docker Development
```bash
# Clone repository
git clone https://github.com/vibhuvi/docker-registry-ui.git
cd docker-registry-ui

# Start development environment
docker compose -f docker-compose.dev.yml up -d

# Access UI at http://localhost:5005
```

### Python Development
If you want to run the Python application locally (outside Docker):

```bash
# Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run application
python run.py
# Or: uvicorn asgi:app --host 0.0.0.0 --port 5000
```

Vulnerability scanning needs a scanner. Pick one:

| Setup | Command |
|---|---|
| Container image (bundles Trivy) | `docker run -v $(pwd)/data:/app/data vibhuvioio/docker-registry-ui:latest` |
| Remote Trivy server | set `vulnerabilityScan.scannerUrl` — see [`docker/remote-trivy`](docker/remote-trivy/docker-compose.yml) |
| Local Python | install the Trivy CLI, or scanning will fail |

Running from source without Trivy is detected, not guessed: the scan fails
immediately and `GET /api/scanner-status/<registry>` reports why.

```bash
curl -s localhost:5000/api/scanner-status/Local%20Registry
# {"enabled":true,"scanner":"trivy","scannerUrl":"builtin","available":false,
#  "reason":"The Trivy CLI is not available in this environment. ..."}
```

## 📖 Documentation

**Full docs:** [vibhuvioio.com/docker-registry-ui](https://vibhuvioio.com/docker-registry-ui/)

- [Getting Started](https://vibhuvioio.com/docker-registry-ui/getting-started.html) - Installation & setup
- [Testing Guide](https://vibhuvioio.com/docker-registry-ui/testing.html) - Full feature testing
- [Configuration](https://vibhuvioio.com/docker-registry-ui/configuration.html) - Multi-registry setup
- [Features](https://vibhuvioio.com/docker-registry-ui/features.html) - Complete feature list
- [Development](https://vibhuvioio.com/docker-registry-ui/development.html) - Contributing guide

## 📦 Versions

Images are published to both [Docker Hub](https://hub.docker.com/r/vibhuvioio/docker-registry-ui) and [GitHub Container Registry](https://github.com/VibhuviOiO/docker-registry-ui/pkgs/container/docker-registry-ui).

```bash
# Latest
docker pull vibhuvioio/docker-registry-ui:latest

# Specific version (recommended for production)
docker pull vibhuvioio/docker-registry-ui:v2.1.0
```

> **Latest release:** [v2.1.0](https://github.com/VibhuviOiO/docker-registry-ui/releases/tag/v2.1.0) — FastAPI backend, async scanning, and remote Trivy support.

---

**Developed by [Vibhuvi OiO](https://vibhuvioio.com)** | [GitHub](https://github.com/vibhuvi/docker-registry-ui) | [Docs](https://vibhuvioio.com/docker-registry-ui/) | MIT License
