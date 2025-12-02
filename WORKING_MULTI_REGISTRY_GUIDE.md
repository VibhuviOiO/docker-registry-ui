# Docker Registry UI - Working Multi-Registry Setup Guide

## ✅ Tested and Working Setup

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

### 3. Start Multi-Registry UI (Environment Variables - WORKING)

```bash
docker run -d -p 5008:5000 \
  -e 'REGISTRIES=[{"name":"Development","url":"http://host.docker.internal:5001","auth":{"type":"none"}},{"name":"Staging","url":"http://host.docker.internal:5002","auth":{"type":"none"}},{"name":"Production","url":"http://host.docker.internal:5003","auth":{"type":"none"}}]' \
  -v $(pwd)/data:/app/data \
  --add-host=host.docker.internal:host-gateway \
  --name registry-ui \
  ghcr.io/vibhuvioio/docker-registry-ui:latest
```

### 4. Verify Setup

```bash
# Check logs - should show "Configured 3 registries"
docker logs registry-ui

# Access UI at http://localhost:5008
# You should see a dropdown to switch between registries
```

## Alternative: Development Environment (Single Registry)

```bash
# Build and start development environment
docker-compose -f docker/docker-compose.dev.yml build
docker-compose -f docker/docker-compose.dev.yml up -d

# Access at http://localhost:5003
# View logs
docker-compose -f docker/docker-compose.dev.yml logs -f registry-ui

# Stop
docker-compose -f docker/docker-compose.dev.yml down
```

## Configuration Formats

### Working: Environment Variable
```bash
REGISTRIES='[{"name":"Registry Name","url":"http://registry-url:port","auth":{"type":"none"}}]'
```

### Config File Format (Use with development build)
```json
{
  "registries": [
    {
      "name": "Local Registry",
      "url": "http://registry:5000",
      "auth": {
        "type": "none"
      }
    }
  ]
}
```

## Authentication Examples

```bash
# No Authentication
{"auth":{"type":"none"}}

# Basic Authentication  
{"auth":{"type":"basic","username":"admin","password":"secret"}}

# Bearer Token
{"auth":{"type":"bearer","token":"your-token-here"}}
```

## Troubleshooting

### Verify Registries Are Running
```bash
docker ps
curl http://localhost:5001/v2/_catalog
curl http://localhost:5002/v2/_catalog  
curl http://localhost:5003/v2/_catalog
```

### Check UI Logs
```bash
docker logs registry-ui
# Should show "Configured 3 registries"
```

### Test Registry Connectivity
```bash
# From inside the UI container
docker exec registry-ui curl http://host.docker.internal:5001/v2/_catalog
```

## Cleanup

```bash
# Stop and remove all containers
docker stop registry-ui registry1 registry2 registry3
docker rm registry-ui registry1 registry2 registry3

# Remove data
rm -rf data
```

## Key Points

1. ✅ **Environment variables work** for multi-registry setup
2. ✅ **Development environment works** for single registry
3. ⚠️ **Config files** may not work with published Docker image (use environment variables)
4. 🔑 **Use `host.docker.internal`** when UI runs in Docker to access host registries
5. 📝 **Logs show registry count** - look for "Configured X registries" message

## Complete Working Example

```bash
# Start registries
docker run -d --name registry1 -p 5001:5000 -e REGISTRY_STORAGE_DELETE_ENABLED=true registry:2
docker run -d --name registry2 -p 5002:5000 -e REGISTRY_STORAGE_DELETE_ENABLED=true registry:2
docker run -d --name registry3 -p 5003:5000 -e REGISTRY_STORAGE_DELETE_ENABLED=true registry:2

# Push test images
docker pull alpine:3.18 && docker tag alpine:3.18 localhost:5001/test/alpine:3.18 && docker push localhost:5001/test/alpine:3.18
docker pull nginx:alpine && docker tag nginx:alpine localhost:5002/test/nginx:alpine && docker push localhost:5002/test/nginx:alpine

# Start UI with multi-registry support
docker run -d -p 5008:5000 \
  -e 'REGISTRIES=[{"name":"Development","url":"http://host.docker.internal:5001","auth":{"type":"none"}},{"name":"Staging","url":"http://host.docker.internal:5002","auth":{"type":"none"}},{"name":"Production","url":"http://host.docker.internal:5003","auth":{"type":"none"}}]' \
  --add-host=host.docker.internal:host-gateway \
  --name registry-ui \
  ghcr.io/vibhuvioio/docker-registry-ui:latest

# Verify
docker logs registry-ui | grep "Configured"
# Should output: "Configured 3 registries"

# Access UI at http://localhost:5008
```