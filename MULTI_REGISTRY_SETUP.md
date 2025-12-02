# Docker Registry UI - Multi-Registry Setup Guide

This guide provides working examples for setting up Docker Registry UI with multiple registries.

## Quick Start (Single Registry Development)

### 1. Development Environment Setup

```bash
# Clone or navigate to the project
cd docker-registry-ui

# Build the development environment
docker-compose -f docker/docker-compose.dev.yml build

# Start registry and UI in development mode
docker-compose -f docker/docker-compose.dev.yml up -d

# View logs
docker-compose -f docker/docker-compose.dev.yml logs -f registry-ui

# Access UI at http://localhost:5003
```

### 2. Stop Development Environment

```bash
# Stop services
docker-compose -f docker/docker-compose.dev.yml down
```

## Multi-Registry Setup (Production)

### 1. Start Multiple Registries

```bash
# Development Registry (port 5001)
docker run -d --name registry1 -p 5001:5000 \
  -e REGISTRY_STORAGE_DELETE_ENABLED=true \
  registry:2

# Staging Registry (port 5002)  
docker run -d --name registry2 -p 5002:5000 \
  -e REGISTRY_STORAGE_DELETE_ENABLED=true \
  registry:2

# Production Registry (port 5003)
docker run -d --name registry3 -p 5003:5000 \
  -e REGISTRY_STORAGE_DELETE_ENABLED=true \
  registry:2
```

### 2. Push Test Images

```bash
# Push to Development Registry
docker pull alpine:3.18
docker tag alpine:3.18 localhost:5001/test/alpine:3.18
docker push localhost:5001/test/alpine:3.18

docker pull nginx:alpine
docker tag nginx:alpine localhost:5001/test/nginx:alpine
docker push localhost:5001/test/nginx:alpine

# Push to Staging Registry
docker tag alpine:3.18 localhost:5002/test/alpine:3.18
docker push localhost:5002/test/alpine:3.18

# Push to Production Registry
docker tag nginx:alpine localhost:5003/prod/nginx:alpine
docker push localhost:5003/prod/nginx:alpine
```

### 3. Create Registry Configuration

**Note**: There appears to be a configuration parsing issue in the current version. Use environment variables instead of config file for now.

```bash
# Method 1: Using Environment Variables (Recommended)
docker run -d -p 5008:5000 \
  -e 'REGISTRIES=[{"name":"Development","url":"http://host.docker.internal:5001","auth":{"type":"none"}},{"name":"Staging","url":"http://host.docker.internal:5002","auth":{"type":"none"}},{"name":"Production","url":"http://host.docker.internal:5003","auth":{"type":"none"}}]' \
  -v $(pwd)/data:/app/data \
  --add-host=host.docker.internal:host-gateway \
  --name registry-ui \
  ghcr.io/vibhuvioio/docker-registry-ui:latest
```

### 4. Alternative: Single Registry with Config File

If you want to use a config file for a single registry:

```bash
# Create configuration file
cat <<'EOF' > registries.config.json
{
  "registries": [
    {
      "name": "Local Registry",
      "url": "http://host.docker.internal:5001",
      "auth": {
        "type": "none"
      }
    }
  ]
}
EOF

# Start UI with config file
docker run -d -p 5008:5000 \
  -v $(pwd)/registries.config.json:/app/registries.config.json \
  -v $(pwd)/data:/app/data \
  --add-host=host.docker.internal:host-gateway \
  --name registry-ui \
  ghcr.io/vibhuvioio/docker-registry-ui:latest
```

## Configuration Formats

### Environment Variable Format
```bash
REGISTRIES='[{"name":"Registry Name","url":"http://registry-url:port","auth":{"type":"none"}}]'
```

### Config File Format
```json
{
  "registries": [
    {
      "name": "Local Registry",
      "url": "http://localhost:5001",
      "auth": {
        "type": "none"
      }
    },
    {
      "name": "Production Registry", 
      "url": "https://registry.example.com",
      "auth": {
        "type": "basic",
        "username": "admin",
        "password": "secret"
      }
    },
    {
      "name": "Private Registry with Token",
      "url": "https://registry-private.example.com", 
      "auth": {
        "type": "bearer",
        "token": "your-bearer-token-here"
      }
    }
  ]
}
```

## Authentication Types

- **None**: `{"type": "none"}`
- **Basic Auth**: `{"type": "basic", "username": "user", "password": "pass"}`
- **Bearer Token**: `{"type": "bearer", "token": "your-token"}`

## Troubleshooting

### UI Can't Connect to Registries
```bash
# Check containers are running
docker ps

# Check UI logs
docker logs registry-ui

# Verify registries respond
curl http://localhost:5001/v2/_catalog
curl http://localhost:5002/v2/_catalog  
curl http://localhost:5003/v2/_catalog
```

### Images Not Showing
```bash
# Verify images were pushed
curl http://localhost:5001/v2/_catalog

# Check registry logs
docker logs registry1

# Restart UI
docker restart registry-ui
```

### Configuration Issues
- Use environment variables instead of config file if parsing fails
- Ensure JSON is valid
- Check that registry URLs are accessible from the UI container
- Use `host.docker.internal` for localhost registries when running UI in Docker

## Cleanup

```bash
# Stop and remove all containers
docker stop registry-ui registry1 registry2 registry3
docker rm registry-ui registry1 registry2 registry3

# Remove configuration and data
rm -f registries.config.json
rm -rf data
```

## Known Issues

1. **Configuration Parsing**: There's currently an issue with multi-registry config file parsing. Use environment variables as a workaround.
2. **Network Access**: When running UI in Docker, use `host.docker.internal` instead of `localhost` to access host registries.
3. **Read-Only Mode**: The UI may start in read-only mode by default. Set `READ_ONLY=false` environment variable if needed.

## Working Examples

### Development (Tested)
```bash
docker-compose -f docker/docker-compose.dev.yml up -d
```

### Single Registry (Tested)
```bash
docker run -d -p 5008:5000 \
  -e 'REGISTRIES=[{"name":"Local","url":"http://host.docker.internal:5001","auth":{"type":"none"}}]' \
  --add-host=host.docker.internal:host-gateway \
  --name registry-ui \
  ghcr.io/vibhuvioio/docker-registry-ui:latest
```