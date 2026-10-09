# Changelog

All notable changes to this image are recorded here. The section for a version
is used verbatim as the body of the GitHub release, and CI refuses to publish a
tag that has no section — so write the notes before tagging.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] - Unreleased

### Added

- Optional authentication, off by default. With `AUTH_ENABLED` unset the UI
  behaves exactly as before: no login page, no new endpoints, and none of the
  authentication dependencies are imported.
- LDAP / Active Directory sign-in: service-account search, bind-to-verify
  password check, `memberOf` or group-search role mapping, StartTLS and LDAPS.
- Single sign-on (OIDC) with PKCE, JWKS signature verification and nonce
  validation. Works with Keycloak, Entra ID, Okta, Authentik and Google.
- Two roles, `viewer` and `admin`, derived from directory groups or an SSO
  claim. `READ_ONLY` remains an independent upper bound.
- Audit log: every sign-in, failed sign-in, sign-out and privileged action is
  appended to `audit.log`, readable by administrators in the new Audit Log view
  and at `GET /api/audit`.
- `BREAK_GLASS_USER` / `BREAK_GLASS_PASSWORD` emergency administrator, so an
  identity-provider outage cannot lock everyone out.
- `docker/ldap-auth` example stack: the UI against a bundled OpenLDAP with demo
  admin and viewer accounts.
- `tests/validate_full_stack.py`, an end-to-end check against a real OpenLDAP
  and a real registry, run in CI on every branch push.
- `scripts/demo_local.sh`, a one-command local demo with LDAP sign-in.
- `scripts/verify_release.py`, which checks a *published* image the way a new
  user meets it: pull it, run it with no environment variables and one volume,
  and confirm the first run actually works.

### Fixed

- **A fresh install could not be configured at all.** `READ_ONLY` defaulted to
  `true` while the README documented `false`, and read-only refuses
  `/api/registry/create` — so the first-run setup wizard's "add registry"
  returned `403 Read-only mode`. `READ_ONLY` now defaults to `false`, matching
  the documentation; set `READ_ONLY=true` when exposing the UI publicly.
- **The setup wizard's configuration was lost on restart.** `CONFIG_FILE`
  defaulted to `/app/registries.config.json`, outside the `DATA_DIR` volume that
  the quick start mounts, so a registry added through the wizard was written
  into the container filesystem and disappeared on restart. It now defaults to
  `<DATA_DIR>/registries.config.json`; an existing `/app/registries.config.json`
  mount is still read, and an explicit `CONFIG_FILE` still wins.
- **Deleting a tag stored as an OCI image manifest failed** with
  `No digest found`, because the Accept list did not include
  `application/vnd.oci.image.manifest.v1+json` and a registry answers 404 when
  the requested media type does not match what it has stored. This also made
  "delete repository" and bulk cleanup remove nothing while reporting success.
- Bulk operations now report a `failures` array instead of discarding failed
  deletions, so a cleanup that did not happen is no longer reported as one that
  did.
- `TRIVY_CACHE_DIR` was documented but never passed to Trivy, so pointing it
  anywhere had no effect; it is now passed as `--cache-dir`. The scan lock file
  likewise follows `DATA_DIR` instead of the environment at import time.
- `SCAN_WORKERS` was a no-op — the executor it configures was built and never
  used, leaving scans on Starlette's much larger thread pool.
- **A missing scanner produced a raw `[Errno 2] No such file or directory:
  'trivy'` after three pointless retries.** A scan now fails immediately, naming
  the three supported setups, and `GET /api/scanner-status/{registry}` reports
  whether the configured scanner is usable before anything is queued. Only
  transient failures are retried.
- **Single-image scans ignored the registry's configured `scannerUrl`** and
  always used the built-in binary, so a remote Trivy server only worked for
  "scan all". The configured scanner is now used for both.

### Removed

- `REGISTRY_URL` and `CHECK_INTERVAL`, which were parsed and never used.

### Changed

- Image publishing runs on tags only. Pushing to `main` no longer publishes.
- `SCAN_WORKERS` documented as concurrent scans *per* Uvicorn worker.

## [2.1.0] - 2026-06-16

### Added

- FastAPI backend replacing the legacy Flask application.
- Asynchronous vulnerability scanning with scan job state persisted to disk.
- Remote Trivy server support alongside the built-in scanner.
- Multi-registry configuration, storage analytics and bulk cleanup.

### Changed

- Multi-stage Alpine image that bakes in the Trivy binary and vulnerability
  database.
- Multi-architecture publishing (linux/amd64, linux/arm64) to Docker Hub and
  GHCR.

## [2.0.0] - 2025-11-27

### Added

- Multi-registry support, bulk operations, Trivy vulnerability scanning and
  storage analytics.
