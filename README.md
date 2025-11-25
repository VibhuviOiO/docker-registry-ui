# Docker Registry UI

A modern web interface for Docker Registry with multi-registry support.

## Quick Start

### 1. Start Registry + UI

```bash
docker-compose -f docker/docker-compose-with-registry.yml up -d
```

**Access:**
- Registry: http://localhost:5001
- UI: http://localhost:8080

### 2. Push an Image

```bash
docker pull nginx
docker tag nginx localhost:5001/nginx:latest
docker push localhost:5001/nginx:latest
```

### 3. View in UI

Open http://localhost:8080 - nginx will appear automatically!

## Features

- ✅ Multi-registry support
- ✅ View repositories and tags
- ✅ Delete images (read-write mode)
- ✅ Real-time search
- ✅ Image size calculation
- ✅ Health checks
- ✅ Production-ready (Uvicorn)

## Configuration

### Single Registry (Environment)
```yaml
environment:
  - REGISTRIES=[{"name":"Local","api":"http://registry:5000","isAuthEnabled":false,"user":"","password":"","apiToken":"","default":true}]
  - READ_ONLY=false
```

### Multiple Registries (JSON File)

1. Copy example:
```bash
cp registries.json.example registries.json
```

2. Edit `registries.json`:
```json
[
  {
    "name": "Production",
    "api": "http://registry.example.com",
    "isAuthEnabled": false,
    "user": "",
    "password": "",
    "apiToken": "",
    "default": true
  }
]
```

3. Use in docker-compose:
```yaml
environment:
  - REGISTRIES=${REGISTRIES}
```

Then run:
```bash
export REGISTRIES=$(cat registries.json)
docker-compose up -d
```

## Development

### With Docker (Recommended)
```bash
docker-compose -f docker/docker-compose.dev.yml up
```

### With Python
```bash
pip install -r requirements.txt
export REGISTRIES='[{"name":"Local","api":"http://localhost:5001","isAuthEnabled":false,"user":"","password":"","apiToken":"","default":true}]'
python run.py
```

## API Reference

See [REGISTRY_API.md](REGISTRY_API.md) for complete Docker Registry API documentation.

## Version

Current version: **1.0.0** (defined in `app/version.py`)

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Built By

**Vibhuvi OiO** - [GitHub](https://github.com/vibhuvio)
