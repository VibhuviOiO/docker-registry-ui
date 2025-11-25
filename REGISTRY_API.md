# Docker Registry API Reference

## Complete Flow: Pull to UI Display

### Example: nginx image

#### 1. Pull Image from Docker Hub
```bash
docker pull nginx:latest
```

#### 2. Tag for Local Registry
```bash
docker tag nginx:latest localhost:5001/nginx:latest
```

#### 3. Push to Local Registry
```bash
docker push localhost:5001/nginx:latest
```

#### 4. Registry API Calls (What the UI Does)

##### Step 1: List All Repositories
```bash
curl http://localhost:5001/v2/_catalog
```
**Response:**
```json
{"repositories":["nginx"]}
```

##### Step 2: List Tags for Repository
```bash
curl http://localhost:5001/v2/nginx/tags/list
```
**Response:**
```json
{"name":"nginx","tags":["latest"]}
```

##### Step 3: Get Manifest (Try OCI Index First)
```bash
curl -H "Accept: application/vnd.oci.image.index.v1+json" \
  http://localhost:5001/v2/nginx/manifests/latest
```

**Response (OCI Index - Multi-platform):**
```json
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.oci.image.index.v1+json",
  "manifests": [
    {
      "mediaType": "application/vnd.oci.image.manifest.v1+json",
      "digest": "sha256:abc123...",
      "size": 1234,
      "platform": {
        "architecture": "amd64",
        "os": "linux"
      }
    }
  ]
}
```

##### Step 4: Get Actual Manifest Using Digest
```bash
curl -H "Accept: application/vnd.oci.image.manifest.v1+json" \
  http://localhost:5001/v2/nginx/manifests/sha256:abc123...
```

**Response:**
```json
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.oci.image.manifest.v1+json",
  "config": {
    "mediaType": "application/vnd.oci.image.config.v1+json",
    "digest": "sha256:config123...",
    "size": 7234
  },
  "layers": [
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:layer1...",
      "size": 29123456
    },
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:layer2...",
      "size": 3456789
    }
  ]
}
```

##### Step 5: Calculate Total Size
```bash
# Sum all layer sizes + config size
curl -s -H "Accept: application/vnd.oci.image.manifest.v1+json" \
  http://localhost:5001/v2/nginx/manifests/sha256:abc123... \
  | jq '([.layers[].size] | add) + .config.size'
```

**Result:** `32587479` (bytes) = **31.08 MB** (compressed)

#### 5. What UI Shows

**Repository List:**
- Name: `nginx`
- Tags: `1 tag`
- Size: `31.08 MB`

**Tag Details (when clicked):**
- Tag: `latest`
- Size: `31.08 MB`
- Digest: `sha256:abc123...`

---

## API Endpoints Used by UI

### 1. List Repositories
```
GET /v2/_catalog
```

### 2. List Tags
```
GET /v2/{repository}/tags/list
```

### 3. Get Manifest (OCI Index)
```
GET /v2/{repository}/manifests/{tag}
Accept: application/vnd.oci.image.index.v1+json
```

### 4. Get Manifest (OCI Image)
```
GET /v2/{repository}/manifests/{digest}
Accept: application/vnd.oci.image.manifest.v1+json
```

### 5. Get Manifest (Docker v2)
```
GET /v2/{repository}/manifests/{tag}
Accept: application/vnd.docker.distribution.manifest.v2+json
```

### 6. Delete Tag (if READ_ONLY=false)
```
DELETE /v2/{repository}/manifests/{digest}
```

---

## Size Calculation Methods

### Method 1: OCI Index (Multi-platform)
```bash
# 1. Get index
INDEX=$(curl -s -H "Accept: application/vnd.oci.image.index.v1+json" \
  http://localhost:5001/v2/nginx/manifests/latest)

# 2. Extract first platform digest (skip attestations)
DIGEST=$(echo $INDEX | jq -r '.manifests[] | select(.annotations."vnd.docker.reference.type" != "attestation-manifest") | .digest' | head -1)

# 3. Get manifest and calculate size
curl -s -H "Accept: application/vnd.oci.image.manifest.v1+json" \
  http://localhost:5001/v2/nginx/manifests/$DIGEST \
  | jq '([.layers[].size] | add) + .config.size'
```

### Method 2: Docker v2 Manifest (Single platform)
```bash
curl -s -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
  http://localhost:5001/v2/nginx/manifests/latest \
  | jq '([.layers[].size] | add) + .config.size'
```

### Method 3: Convert to MB
```bash
curl -s -H "Accept: application/vnd.oci.image.manifest.v1+json" \
  http://localhost:5001/v2/nginx/manifests/$DIGEST \
  | jq '(([.layers[].size] | add) + .config.size) / 1024 / 1024'
```

---

## Complete Example with nginx

```bash
# Pull and push
docker pull nginx:latest
docker tag nginx:latest localhost:5001/nginx:latest
docker push localhost:5001/nginx:latest

# List repositories
curl http://localhost:5001/v2/_catalog
# {"repositories":["nginx"]}

# List tags
curl http://localhost:5001/v2/nginx/tags/list
# {"name":"nginx","tags":["latest"]}

# Get OCI index
curl -s -H "Accept: application/vnd.oci.image.index.v1+json" \
  http://localhost:5001/v2/nginx/manifests/latest | jq .

# Extract digest for amd64
DIGEST=$(curl -s -H "Accept: application/vnd.oci.image.index.v1+json" \
  http://localhost:5001/v2/nginx/manifests/latest \
  | jq -r '.manifests[] | select(.platform.architecture == "amd64" and .annotations."vnd.docker.reference.type" != "attestation-manifest") | .digest')

echo "Digest: $DIGEST"

# Get manifest and calculate size
SIZE=$(curl -s -H "Accept: application/vnd.oci.image.manifest.v1+json" \
  http://localhost:5001/v2/nginx/manifests/$DIGEST \
  | jq '([.layers[].size] | add) + .config.size')

echo "Size: $SIZE bytes"
echo "Size: $(echo "scale=2; $SIZE / 1024 / 1024" | bc) MB"
```

---

## UI Implementation

The UI follows this exact flow:

1. **On page load**: Fetch `/v2/_catalog` → Display repository list
2. **On repository click**: Fetch `/v2/{repo}/tags/list` → Display tags
3. **On tag display**: 
   - Try OCI index first
   - If OCI index, extract platform manifest digest
   - Fetch actual manifest
   - Sum layer sizes
   - Display formatted size

---

## Notes

- **Compressed vs Uncompressed**: Registry stores compressed layers, so sizes shown are compressed (smaller than `docker images` shows)
- **Multi-platform**: OCI indexes contain multiple platform manifests (amd64, arm64, etc.)
- **Attestations**: Skip manifests with `vnd.docker.reference.type: attestation-manifest`
- **Size Accuracy**: Sizes are exact bytes from registry, not estimates
