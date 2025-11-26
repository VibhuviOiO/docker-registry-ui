#!/bin/bash

# Script to populate test registries with popular Docker images
# This creates a realistic test environment with multiple images and tags

set -e

REGISTRY1="localhost:5001"
REGISTRY2="localhost:5002"

echo "=========================================="
echo "Populating Test Registries with Images"
echo "Registry 1: $REGISTRY1"
echo "Registry 2: $REGISTRY2"
echo "=========================================="

# Popular small images with multiple versions
IMAGES=(
    "alpine:3.18 alpine:3.17 alpine:3.16 alpine:latest"
    "nginx:1.25 nginx:1.24 nginx:1.23 nginx:alpine nginx:latest"
    "redis:7.2 redis:7.0 redis:6.2 redis:alpine redis:latest"
    "postgres:16 postgres:15 postgres:14 postgres:13 postgres:alpine"
    "node:20 node:18 node:16 node:20-alpine node:18-alpine"
    "python:3.11 python:3.10 python:3.9 python:3.11-slim python:3.10-alpine"
    "busybox:1.36 busybox:1.35 busybox:latest busybox:musl"
    "ubuntu:22.04 ubuntu:20.04 ubuntu:18.04 ubuntu:latest"
    "mysql:8.0 mysql:5.7 mysql:latest"
    "mongo:7.0 mongo:6.0 mongo:5.0 mongo:latest"
)

pull_tag_push() {
    local source=$1
    local target_registry=$2
    local target_repo=$3
    local target_tag=$4
    
    echo "  → Pulling $source..."
    docker pull $source --quiet
    
    echo "  → Tagging as $target_registry/$target_repo:$target_tag..."
    docker tag $source $target_registry/$target_repo:$target_tag
    
    echo "  → Pushing to $target_registry/$target_repo:$target_tag..."
    docker push $target_registry/$target_repo:$target_tag --quiet
    
    echo "  ✓ Completed $target_repo:$target_tag"
}

# Populate Registry 1
echo ""
echo "Populating Registry 1 ($REGISTRY1)..."
echo "=========================================="

for image_set in "${IMAGES[@]}"; do
    read -ra tags <<< "$image_set"
    base_image=$(echo ${tags[0]} | cut -d: -f1)
    
    echo ""
    echo "Processing $base_image..."
    
    for tag in "${tags[@]}"; do
        version=$(echo $tag | cut -d: -f2)
        pull_tag_push "$tag" "$REGISTRY1" "$base_image" "$version"
    done
done

# Populate Registry 2 with subset
echo ""
echo "Populating Registry 2 ($REGISTRY2)..."
echo "=========================================="

REGISTRY2_IMAGES=(
    "alpine:3.18 alpine:latest"
    "nginx:1.25 nginx:alpine"
    "redis:7.2 redis:alpine"
    "postgres:16 postgres:alpine"
    "node:20 node:20-alpine"
)

for image_set in "${REGISTRY2_IMAGES[@]}"; do
    read -ra tags <<< "$image_set"
    base_image=$(echo ${tags[0]} | cut -d: -f1)
    
    echo ""
    echo "Processing $base_image..."
    
    for tag in "${tags[@]}"; do
        version=$(echo $tag | cut -d: -f2)
        pull_tag_push "$tag" "$REGISTRY2" "$base_image" "$version"
    done
done

# Create some custom namespaced images
echo ""
echo "Creating namespaced test images..."
echo "=========================================="

for i in {1..3}; do
    echo ""
    echo "Creating myapp/service-$i..."
    docker tag alpine:latest $REGISTRY1/myapp/service-$i:v1.0.0
    docker tag alpine:latest $REGISTRY1/myapp/service-$i:v1.1.0
    docker tag alpine:latest $REGISTRY1/myapp/service-$i:latest
    docker push $REGISTRY1/myapp/service-$i:v1.0.0 --quiet
    docker push $REGISTRY1/myapp/service-$i:v1.1.0 --quiet
    docker push $REGISTRY1/myapp/service-$i:latest --quiet
    echo "  ✓ Completed myapp/service-$i"
done

echo ""
echo "=========================================="
echo "✓ Test registries populated successfully!"
echo "=========================================="
echo ""
echo "Registry 1 ($REGISTRY1): ~40+ images"
echo "Registry 2 ($REGISTRY2): ~10+ images"
echo ""
echo "You can now test:"
echo "  - Browse repositories and tags"
echo "  - Filter and sort tags"
echo "  - Bulk operations with age filters"
echo "  - Delete operations"
echo "  - Analytics and statistics"
echo ""
