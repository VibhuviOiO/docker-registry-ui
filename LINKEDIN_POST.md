🐳 **Built a Modern Web UI for Docker Registry - Now Open Source!**

Managing Docker images across multiple registries shouldn't require complex CLI commands or third-party tools. That's why I created **Docker Registry UI** - a production-ready web interface that brings Docker Hub-like experience to your private registries.

**🎯 The Problem:**
Most teams struggle with:
- No visibility into what images exist across registries
- Risk of accidental deletions without proper controls
- Managing multiple registries separately
- No easy way to see image sizes, tags, and metadata

**✨ The Solution - Key Features:**

🔹 **Multi-Registry Management** - Connect unlimited registries, switch between them seamlessly
🔹 **Dual Access Modes** - Read-only for safe browsing, read-write for full control
🔹 **Docker Hub-Style UI** - View tags with size, digest, creation time ("2 days ago")
🔹 **Smart Search** - Real-time filtering across 350+ repositories
🔹 **Live Statistics** - Repository count, total tags, image sizes at a glance
🔹 **Production Ready** - Health checks, JSON logging, Uvicorn with 4 workers, resource limits
🔹 **Security First** - Supports Basic Auth & Bearer tokens, no credential storage

**🚀 Get Started in 2 Minutes:**
```bash
docker-compose -f docker/docker-compose-with-registry.yml up -d
```
That's it! Access at http://localhost:8080

**🛠️ Tech Stack:**
Python Flask + Uvicorn (ASGI) | Bootstrap 5 | Docker Registry API V2 | Docker Compose

**📊 Real-World Use Case:**
Managing 352 repositories with 1000+ tags across dev, staging, and production registries - all from one clean interface. No more `docker images` commands or registry API curl requests!

**🔒 Enterprise-Ready:**
- Authentication support (Basic Auth & Bearer Tokens)
- Read-only mode prevents accidental deletions
- Environment-based configuration
- Customizable branding ("Built by" footer)
- Health endpoints for Kubernetes/monitoring

**🌟 Open Source (MIT License)**
Fully customizable, deploy anywhere (Docker, K8s, bare metal), contributions welcome!

📸 **Screenshots attached:**
- Image 1: Read-only mode - Safe browsing
- Image 2: Read-write mode - Full management

🔗 **GitHub:** https://github.com/VibhuviOiO/docker-registry-ui

⭐ Star the repo if you find it useful!
💬 What's your biggest pain point managing Docker registries? Let's discuss!

---

#Docker #DevOps #OpenSource #Containers #CloudNative #Python #Flask #ContainerManagement #DockerRegistry #Kubernetes #SoftwareEngineering #WebDevelopment
