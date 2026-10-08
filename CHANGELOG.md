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

### Fixed

- **Deleting a tag stored as an OCI image manifest failed** with
  `No digest found`, because the Accept list did not include
  `application/vnd.oci.image.manifest.v1+json` and a registry answers 404 when
  the requested media type does not match what it has stored. This also made
  "delete repository" and bulk cleanup remove nothing while reporting success.
- Bulk operations now report a `failures` array instead of discarding failed
  deletions, so a cleanup that did not happen is no longer reported as one that
  did.

### Changed

- Image publishing runs on tags only. Pushing to `main` no longer publishes.

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
