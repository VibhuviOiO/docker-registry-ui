# Docker Registry UI

Modern, lightweight web interface for managing Docker Registry with built-in vulnerability scanning.

[![Docker Pulls](https://img.shields.io/docker/pulls/vibhuvi/docker-registry-ui)](https://hub.docker.com/r/vibhuvi/docker-registry-ui)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## ✨ Features

- 📦 **Repository Management** - Browse, search, and manage Docker images and tags
- 🔒 **Read/Write Modes** - Toggle between read-only and read-write modes
- 🗑️ **Bulk Operations** - Delete multiple images based on patterns, age, and retention policies
- 🛡️ **Vulnerability Scanning** - Built-in Trivy integration with CVE details linked to NVD
- 🔗 **Multi-Registry Support** - Manage multiple Docker registries from a single interface
- 📊 **Analytics** - View storage usage, image statistics, and layer information
- 🎨 **Modern UI** - Clean, responsive interface with Jira/Bitbucket-inspired design

## 🚀 Quick Start

### Docker Run

```bash
docker run -d \
  --name registry-ui \
  -p 5000:5000 \
  -e CONFIG_FILE=/app/data/registries.config.json \
  -e READ_ONLY=false \
  -v $(pwd)/data:/app/data \
  vibhuvi/docker-registry-ui:latest
```

### Docker Compose

```yaml
version: '3.8'

services:
  registry:
    image: registry:2
    ports:
      - "5001:5000"
    environment:
      REGISTRY_STORAGE_DELETE_ENABLED: "true"
    volumes:
      - registry-data:/var/lib/registry

  registry-ui:
    image: vibhuvi/docker-registry-ui:latest
    ports:
      - "5000:5000"
    environment:
      - CONFIG_FILE=/app/data/registries.config.json
      - READ_ONLY=false
    volumes:
      - ./data:/app/data
    depends_on:
      - registry

volumes:
  registry-data:
```

Access the UI at `http://localhost:5000`

## 📖 Documentation

Full documentation is available at [vibhuvioio.com/docker-registry-ui](https://vibhuvioio.com/docker-registry-ui/)

- [Getting Started](https://vibhuvioio.com/docker-registry-ui/getting-started.html)
- [Configuration Guide](https://vibhuvioio.com/docker-registry-ui/configuration.html)
- [Features Overview](https://vibhuvioio.com/docker-registry-ui/features.html)
- [Security Scanning](https://vibhuvioio.com/docker-registry-ui/security.html)
- [API Reference](https://vibhuvioio.com/docker-registry-ui/api.html)
- [Development Guide](https://vibhuvioio.com/docker-registry-ui/development.html)

## 🛡️ Vulnerability Scanning

Built-in Trivy scanner provides:
- Per-tag vulnerability scanning
- CVE details with severity levels (Critical, High, Medium, Low)
- Direct links to National Vulnerability Database (NVD)
- Layer-by-layer vulnerability breakdown
- Persistent scan results

## 🗑️ Bulk Operations

Delete multiple images efficiently:
- Pattern-based deletion (wildcards supported)
- Age-based cleanup (older than X days)
- Retention policies (keep minimum N tags)
- Dry-run mode for safe testing

## 🔌 Docker Registry API

Integrates with Docker Registry v2 API:
- `/v2/_catalog` - List repositories
- `/v2/<name>/tags/list` - List tags
- `/v2/<name>/manifests/<tag>` - Get manifest
- `/v2/<name>/manifests/<digest>` - Delete image

## 💻 Development

```bash
# Clone repository
git clone https://github.com/vibhuvi/docker-registry-ui.git
cd docker-registry-ui

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run application
python app.py
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Developed by [Vibhuvi OiO](https://vibhuvioio.com) as part of giving back to the open source community.

This project exists because of the countless open source contributors who helped me learn and grow. I'm grateful to the community and hope this tool helps others manage their Docker registries more effectively.

## 🔗 Links

- [Documentation](https://vibhuvioio.com/docker-registry-ui/)
- [Docker Hub](https://hub.docker.com/r/vibhuvi/docker-registry-ui)
- [GitHub](https://github.com/vibhuvi/docker-registry-ui)
- [National Vulnerability Database](https://nvd.nist.gov/)
- [Trivy Scanner](https://aquasecurity.github.io/trivy/)
