# Docker Registry UI

Modern web interface for managing Docker Registry with vulnerability scanning, bulk operations, and multi-registry support.

[![Docker Pulls](https://img.shields.io/docker/pulls/vibhuvi/docker-registry-ui)](https://github.com/VibhuviOiO/docker-registry-ui/pkgs/container/docker-registry-ui)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Open in Gitpod](https://img.shields.io/badge/Gitpod-Ready%20to%20Code-purple?logo=gitpod)](https://gitpod.io/#https://github.com/VibhuviOiO/docker-registry-ui)

[![Docker Registry UI](https://vibhuvioio.com/docker-registry-ui/img/repositories.png)](https://vibhuvioio.com/docker-registry-ui/)

## 🚀 Try It Now (2 Minutes)

### ☁️ Play with Docker (Browser)

Click the button below to try Docker Registry UI instantly in your browser using [Play with Docker](https://labs.play-with-docker.com/):

[![Try in PWD](https://raw.githubusercontent.com/play-with-docker/stacks/master/assets/images/button.png)](https://labs.play-with-docker.com/?stack=https://raw.githubusercontent.com/VibhuviOiO/docker-registry-ui/main/docker/single-registry/docker-compose.yml)

**Note:** This launches a single-registry setup. The UI will be available on port **5000** and the registry on port **5001**.

### 🖥️ Local Quick Start

```bash
# Download test environment
wget https://raw.githubusercontent.com/VibhuviOiO/docker-registry-ui/main/docker/multi-registry/docker-compose.yml
wget https://raw.githubusercontent.com/VibhuviOiO/docker-registry-ui/main/docker/multi-registry/populate-test-images.sh
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
- 🗑️ Bulk operations with safety features
- 🔗 Multi-registry support
- 📊 Storage analytics
- 🎨 Modern, responsive UI

## 📦 Quick Start (Production)

```bash
# Simple setup (setup wizard will guide you)
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  ghcr.io/vibhuvioio/docker-registry-ui:latest

# With test registry (using Docker network)
docker network create registry-net
docker run -d --name test-registry --network registry-net -p 5001:5000 \
  -e REGISTRY_STORAGE_DELETE_ENABLED=true registry:2
docker run -d --name registry-ui --network registry-net -p 5000:5000 \
  -e 'REGISTRIES=[{"name":"Local Registry","api":"http://test-registry:5000"}]' \
  -v $(pwd)/data:/app/data \
  ghcr.io/vibhuvioio/docker-registry-ui:latest
```

Access at `http://localhost:5000` - Setup wizard will guide you.

## 🧭 Run Locally (Developer)

### Docker Development
```bash
# Clone repository
git clone https://github.com/vibhuvi/docker-registry-ui.git
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

[View all versions](https://github.com/VibhuviOiO/docker-registry-ui/pkgs/container/docker-registry-ui) | Use specific version: `ghcr.io/vibhuvioio/docker-registry-ui:v1.0.0`

---

**Developed by [Vibhuvi OiO](https://vibhuvioio.com)** | [GitHub](https://github.com/vibhuvi/docker-registry-ui) | [Docs](https://vibhuvioio.com/docker-registry-ui/) | MIT License
