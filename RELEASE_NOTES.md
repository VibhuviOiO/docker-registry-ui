# Release Notes

## v2.0.0 (2024-01-20)

### Features
- Modular template architecture with reusable components
- Dark mode with localStorage persistence and system theme detection
- Docker Hub-style inline copy-to-clipboard for pull commands
- Tag sorting by name, size, and date
- Real-time tag filtering
- Manifest viewer with tabs for manifest, layers, and config JSON
- Bulk operations with cleanup rules (age-based, pattern-based, keep minimum)
- Dry-run mode for bulk operations
- Usage analytics with Chart.js visualizations
- Top 10 repositories by size and tag count charts
- CSV export for analytics data
- Performance improvements with tag details caching

### UI Improvements
- Restructured templates into components and views
- Added bulk operations view with rule configuration
- Added analytics dashboard with statistics and charts
- Improved tag display with inline pull commands
- Enhanced dark mode support across all components

### API Additions
- POST /api/bulk-operation - Execute bulk cleanup operations
- GET /api/analytics/<registry> - Get registry analytics

### Technical
- Chart.js 4.4.0 for data visualization
- Modular JavaScript with feature separation
- Enhanced caching for better performance

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
