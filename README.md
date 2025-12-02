# Docker Registry UI

Modern web interface for managing Docker Registry with vulnerability scanning, bulk operations, and multi-registry support.

[![Docker Pulls](https://img.shields.io/docker/pulls/vibhuvi/docker-registry-ui)](https://github.com/VibhuviOiO/docker-registry-ui/pkgs/container/docker-registry-ui)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[![Docker Registry UI](https://vibhuvioio.com/docker-registry-ui/img/repositories.png)](https://vibhuvioio.com/docker-registry-ui/)

## 🚀 Try It Now (2 Minutes)

```bash
# Download test environment
wget https://raw.githubusercontent.com/VibhuviOiO/docker-registry-ui/main/docker/docker-compose-multi-registry.yml
wget https://raw.githubusercontent.com/VibhuviOiO/docker-registry-ui/main/docker/populate-test-images.sh
chmod +x populate-test-images.sh

# Start registries and UI
docker-compose -f docker-compose-multi-registry.yml up -d

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

```bash
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  ghcr.io/vibhuvioio/docker-registry-ui:latest
```

Access at `http://localhost:5000` - Setup wizard will guide you.

## 🧭 Run Locally (Developer)

If you want to run the Python application locally (outside the official container) use one of the following:

```bash
# Run with the Flask factory entrypoint
python run.py

# Or run the ASGI app (matches production image)
uvicorn asgi:app --host 0.0.0.0 --port 5000
```

Note: The official Docker image includes the `trivy` binary so vulnerability scanning works out-of-the-box. If you run locally (not using the container) install the `trivy` CLI separately to enable scanning.

## 📖 Documentation

**Full docs:** [vibhuvioio.com/docker-registry-ui](https://vibhuvioio.com/docker-registry-ui/)

- [Getting Started](https://vibhuvioio.com/docker-registry-ui/getting-started.html) - Installation & setup
- [Testing Guide](https://vibhuvioio.com/docker-registry-ui/testing.html) - Full feature testing
- [Configuration](https://vibhuvioio.com/docker-registry-ui/configuration.html) - Multi-registry setup
- [Features](https://vibhuvioio.com/docker-registry-ui/features.html) - Complete feature list
- [Development](https://vibhuvioio.com/docker-registry-ui/development.html) - Contributing guide

## 📦 Versions

[View all versions](https://github.com/VibhuviOiO/docker-registry-ui/pkgs/container/docker-registry-ui) | Use specific version: `ghcr.io/vibhuvioio/docker-registry-ui:v1.0.0`

---

**Developed by [Vibhuvi OiO](https://vibhuvioio.com)** | [GitHub](https://github.com/vibhuvi/docker-registry-ui) | [Docs](https://vibhuvioio.com/docker-registry-ui/) | MIT License
