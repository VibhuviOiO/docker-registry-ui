# Release Notes

## v1.0.0 (2024-01-15)

### Features
- Multi-registry support with JSON configuration
- Read-only and read-write modes
- Tag deletion with Bootstrap modal confirmation
- Repository and tag search functionality
- Lazy loading for tag sizes (batched in groups of 5)
- Registry health status indicators (Online/Error/Offline)
- OCI index and multi-platform manifest support
- Health check endpoints (/health/live, /health/ready)
- Garbage collection instructions for Docker/Podman/K8s/Nexus
- Customizable footer branding via BUILT_BY env var
- Production-ready Uvicorn deployment with 4 workers

### Bug Fixes
- Fixed OCI index handling for multi-platform images
- Fixed URL encoding for registry names with spaces
- Fixed readOnly variable check preventing tag display
- Fixed tag deletion digest retrieval with multiple accept headers
- Fixed size calculation to skip attestation manifests

### Technical
- Python 3.11, Flask 3.0, Uvicorn ASGI server
- Bootstrap 5 UI with responsive design
- JSON structured logging
- Docker Compose with health checks and resource limits
