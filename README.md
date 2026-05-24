# Docker Registry UI

Modern web interface for managing Docker Registry with vulnerability scanning, bulk operations, and multi-registry support.

[![Docker Pulls](https://img.shields.io/docker/pulls/molpie/docker-registry-ui)](https://hub.docker.com/r/molpie/docker-registry-ui)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[![Open in Gitpod](https://img.shields.io/badge/Gitpod-Ready%20to%20Code-purple?logo=gitpod)](https://gitpod.io/#https://github.com/molpie/docker-registry-ui)

### 🖥️ Local Quick Start

```bash
# Download test environment
wget https://raw.githubusercontent.com/molpie/docker-registry-ui/main/docker/multi-registry/docker-compose.yml
wget https://raw.githubusercontent.com/molpie/docker-registry-ui/main/docker/multi-registry/populate-test-images.sh
chmod +x populate-test-images.sh

# Start registries and UI
docker-compose -f docker-compose.yml up -d

# Populate with test images (optional, takes 5-10 min)
./populate-test-images.sh

# Open http://localhost:5003
```

## ✨ Features

- 📦 Repository & tag management
- 🛡️ Vulnerability scanning (Trivy)
- 📥 Download JSON report from image/tag detail
- 🧱 Layer-level vulnerability view with BASE/APP origin highlighting
- 🗑️ Bulk operations with safety features
- 📡 Massive scan API with advanced filters (all/older/unscanned/never-scanned)
- 🕒 Daily scheduled massive scan (supports cron expression)
- ✉️ Massive scan recap notifications (Email + Telegram)
- 🩺 System Status view (scheduler/notifications/storage)
- 💾 SQLite persistence for vulnerability scan results
- 🔗 Multi-registry support
- 📊 Storage analytics
- 🎨 Modern, responsive UI

## ⚙️ Configuration Model

This project now uses a clear split between registry configuration and runtime settings:

- `registries.config.json`: only registry definitions and per-registry options
- `.env` (from `.env.example`): application/runtime settings

Important rule:

- No registry definitions in `.env`.
- The only registry-related environment variable is `CONFIG_FILE` (path to `registries.config.json`).

Example `registries.config.json`:

```json
{
  "registries": [
    {
      "name": "Local Registry",
      "api": "http://registry:5000",
      "default": true
    }
  ]
}
```

Example setup:

```bash
cp .env.example .env
# Edit .env runtime settings
# Edit registries.config.json for registry definitions
```

## 📦 Quick Start (Production)

```bash
# Simple setup (setup wizard will guide you)
docker run -d \
  -p 5000:5000 \
  --env-file .env \
  -v $(pwd)/registries.config.json:/app/registries.config.json:ro \
  -v $(pwd)/data:/app/data \
  ghcr.io/molpie/docker-registry-ui:latest

# With test registry (using Docker network)
docker network create registry-net
docker run -d --name test-registry --network registry-net -p 5001:5000 \
  -e REGISTRY_STORAGE_DELETE_ENABLED=true registry:2
docker run -d --name registry-ui --network registry-net -p 5000:5000 \
  --env-file .env \
  -v $(pwd)/registries.config.json:/app/registries.config.json:ro \
  -v $(pwd)/data:/app/data \
  ghcr.io/molpie/docker-registry-ui:latest
```

Access at `http://localhost:5000` - Setup wizard will guide you.

## 🧭 Run Locally (Developer)

### Docker Development

```bash
# Clone repository
git clone https://github.com/molpie/docker-registry-ui.git
cd docker-registry-ui

# Start development environment
docker-compose -f docker-compose.dev.yml up -d

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

Note: The Docker development environment includes the `trivy` binary for vulnerability scanning. For local Python development, install `trivy` CLI separately.

## 📖 Documentation

**Full docs:** [vibhuvioio.com/docker-registry-ui](https://vibhuvioio.com/docker-registry-ui/)

- [Getting Started](https://vibhuvioio.com/docker-registry-ui/getting-started.html) - Installation & setup
- [Testing Guide](https://vibhuvioio.com/docker-registry-ui/testing.html) - Full feature testing
- [Configuration](https://vibhuvioio.com/docker-registry-ui/configuration.html) - Multi-registry setup
- [Features](https://vibhuvioio.com/docker-registry-ui/features.html) - Complete feature list
- [Development](https://vibhuvioio.com/docker-registry-ui/development.html) - Contributing guide

## 📦 Versions

[View all versions](https://hub.docker.com/r/molpie/docker-registry-ui) | Use specific version: `docker pull molpie/docker-registry-ui:2.2.0`

---

**Developed by [Vibhuvi OiO](https://vibhuvioio.com)** and **molpie** | [GitHub](https://github.com/molpie/docker-registry-ui) | [Docs](https://vibhuvioio.com/docker-registry-ui/) | MIT License
