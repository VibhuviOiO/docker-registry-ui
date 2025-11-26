#!/usr/bin/env python3
"""
Docker Registry UI - Web interface for Docker Registry with read/write modes

Usage:
  READ_ONLY=true python registry_ui.py
  READ_ONLY=false python registry_ui.py
"""

import os
import requests
import threading
import time
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

# ---------------- Config ----------------
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry.vibhuvioio.com")
READ_ONLY = os.getenv("READ_ONLY", "true").lower() == "true"
CHECK_INTERVAL = 300
TIMEOUT = 10

# ---------------- Shared Data ----------------
registry_data = {
    "repositories": [],
    "last_run": None,
    "error": None,
    "total_size": 0
}

def format_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} PB"

def get_manifest_digest(repo, tag):
    try:
        r = requests.get(
            f"{REGISTRY_URL}/v2/{repo}/manifests/{tag}",
            headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
            timeout=TIMEOUT
        )
        return r.headers.get("Docker-Content-Digest") if r.status_code == 200 else None
    except:
        return None

def get_image_details(repo):
    try:
        r = requests.get(f"{REGISTRY_URL}/v2/{repo}/tags/list", timeout=TIMEOUT)
        if r.status_code != 200:
            return {"tags": [], "total_size": 0}
        
        tags = r.json().get("tags", []) or []
        total_size = 0
        tag_details = []
        
        for tag in tags[:10]:
            try:
                manifest_r = requests.get(
                    f"{REGISTRY_URL}/v2/{repo}/manifests/{tag}",
                    headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
                    timeout=TIMEOUT
                )
                if manifest_r.status_code == 200:
                    manifest = manifest_r.json()
                    digest = manifest_r.headers.get("Docker-Content-Digest", "")
                    size = manifest.get("config", {}).get("size", 0)
                    for layer in manifest.get("layers", []):
                        size += layer.get("size", 0)
                    total_size += size
                    tag_details.append({"tag": tag, "size": size, "digest": digest})
            except:
                pass
        
        return {"tags": tag_details, "total_size": total_size, "tag_count": len(tags)}
    except:
        return {"tags": [], "total_size": 0, "tag_count": 0}

# ---------------- Fetch Registry Data ----------------
def fetch_registry_data():
    global registry_data
    while True:
        try:
            r = requests.get(f"{REGISTRY_URL}/v2/_catalog", timeout=TIMEOUT)
            if r.status_code == 200:
                repos = r.json().get("repositories", [])
                repo_details = []
                total_size = 0
                
                for repo in sorted(repos):
                    details = get_image_details(repo)
                    total_size += details["total_size"]
                    repo_details.append({
                        "name": repo,
                        "tags": details["tags"],
                        "tag_count": details["tag_count"],
                        "size": details["total_size"]
                    })
                
                registry_data.update({
                    "repositories": repo_details,
                    "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "total_size": total_size,
                    "error": None
                })
            else:
                registry_data["error"] = f"HTTP {r.status_code}"
        except Exception as e:
            registry_data["error"] = str(e)
        
        time.sleep(CHECK_INTERVAL)

# ---------------- Flask App ----------------
app = Flask("registry_ui")

TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Docker Registry UI</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css" rel="stylesheet">
<style>
body { padding: 1rem; font-size: 0.9rem; background: #f4f6f8; }
.repo-row { cursor: pointer; }
.repo-row:hover { background-color: #e9ecef; }
.tag-item { padding: 0.5rem; border-bottom: 1px solid #dee2e6; }
.tag-item:hover { background-color: #f8f9fa; }
.mode-badge { position: fixed; top: 10px; right: 10px; z-index: 1000; }
</style>
</head>
<body>
<span class="badge {{mode_class}} mode-badge">{{mode_text}}</span>

<div class="text-center mb-3">
  <h2>🐳 Docker Registry UI</h2>
</div>

<div class="mb-3 text-center">
  Registry: <b>{{registry_url}}</b> |
  Repositories: <b>{{data.repositories|length}}</b> |
  Total Size: <b>{{format_size(data.total_size)}}</b> |
  Last Updated: {{data.last_run}}
</div>

<div id="alert-container"></div>

<div class="mb-3">
  <input type="text" id="searchBox" class="form-control" placeholder="Search repositories...">
</div>

<div class="row">
  <div class="col-md-4">
    <div class="card">
      <div class="card-header"><strong>Repositories</strong></div>
      <div class="card-body p-0" style="max-height: 70vh; overflow-y: auto;">
        <div class="list-group list-group-flush">
          {% for repo in data.repositories %}
          <a href="#" class="list-group-item list-group-item-action repo-row" data-repo="{{repo.name}}">
            <div class="d-flex justify-content-between align-items-center">
              <div>
                <strong>{{repo.name}}</strong><br>
                <small class="text-muted">{{repo.tag_count}} tags · {{format_size(repo.size)}}</small>
              </div>
              <i class="bi bi-chevron-right"></i>
            </div>
          </a>
          {% endfor %}
        </div>
      </div>
    </div>
  </div>
  
  <div class="col-md-8">
    <div class="card">
      <div class="card-header d-flex justify-content-between align-items-center">
        <strong id="repo-title">Select a repository</strong>
        {% if not read_only %}
        <button class="btn btn-sm btn-danger" id="deleteRepoBtn" style="display:none;" onclick="deleteRepository()">
          <i class="bi bi-trash"></i> Delete Repository
        </button>
        {% endif %}
      </div>
      <div class="card-body" id="tags-container" style="max-height: 70vh; overflow-y: auto;">
        <p class="text-muted text-center">Select a repository to view tags</p>
      </div>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
const readOnly = {{read_only|tojson}};
let currentRepo = null;
let repoData = {{data.repositories|tojson}};

function showAlert(message, type = 'success') {
  const alert = `<div class="alert alert-${type} alert-dismissible fade show" role="alert">
    ${message}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
  </div>`;
  document.getElementById('alert-container').innerHTML = alert;
  setTimeout(() => { document.getElementById('alert-container').innerHTML = ''; }, 5000);
}

document.querySelectorAll('.repo-row').forEach(row => {
  row.addEventListener('click', function(e) {
    e.preventDefault();
    const repo = this.dataset.repo;
    loadTags(repo);
  });
});

function loadTags(repo) {
  currentRepo = repo;
  document.getElementById('repo-title').textContent = repo;
  document.getElementById('deleteRepoBtn').style.display = readOnly ? 'none' : 'block';
  
  fetch(`/api/tags/${repo}`)
    .then(r => r.json())
    .then(data => {
      let html = '';
      if (data.tags.length === 0) {
        html = '<p class="text-muted text-center">No tags found</p>';
      } else {
        data.tags.forEach(tag => {
          html += `<div class="tag-item d-flex justify-content-between align-items-center">
            <div>
              <strong>${tag.tag}</strong><br>
              <small class="text-muted">${formatSize(tag.size)}</small>
            </div>
            ${!readOnly ? `<button class="btn btn-sm btn-outline-danger" onclick="deleteTag('${repo}', '${tag.tag}')">
              <i class="bi bi-trash"></i>
            </button>` : ''}
          </div>`;
        });
      }
      document.getElementById('tags-container').innerHTML = html;
    });
}

function deleteTag(repo, tag) {
  if (!confirm(`Delete tag ${tag} from ${repo}?`)) return;
  
  fetch(`/api/delete/tag/${repo}/${tag}`, { method: 'DELETE' })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showAlert(`Tag ${tag} deleted successfully`);
        loadTags(repo);
        setTimeout(() => location.reload(), 2000);
      } else {
        showAlert(data.error || 'Failed to delete tag', 'danger');
      }
    });
}

function deleteRepository() {
  if (!currentRepo || !confirm(`Delete entire repository ${currentRepo}?`)) return;
  
  fetch(`/api/delete/repo/${currentRepo}`, { method: 'DELETE' })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showAlert(`Repository ${currentRepo} deleted successfully`);
        setTimeout(() => location.reload(), 2000);
      } else {
        showAlert(data.error || 'Failed to delete repository', 'danger');
      }
    });
}

function formatSize(bytes) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return `${size.toFixed(2)} ${units[unitIndex]}`;
}

document.getElementById('searchBox').addEventListener('keyup', function() {
  const q = this.value.toLowerCase();
  document.querySelectorAll('.repo-row').forEach(row => {
    row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
});
</script>
</body>
</html>
"""

@app.route("/")
def index():
    mode_text = "READ ONLY" if READ_ONLY else "READ/WRITE"
    mode_class = "bg-info" if READ_ONLY else "bg-warning text-dark"
    return render_template_string(TEMPLATE, 
                                  registry_url=REGISTRY_URL,
                                  data=registry_data,
                                  format_size=format_size,
                                  read_only=READ_ONLY,
                                  mode_text=mode_text,
                                  mode_class=mode_class)

@app.route("/api/repositories")
def api_repositories():
    return jsonify(registry_data)

@app.route("/api/tags/<path:repo>")
def api_tags(repo):
    try:
        r = requests.get(f"{REGISTRY_URL}/v2/{repo}/tags/list", timeout=TIMEOUT)
        if r.status_code != 200:
            return jsonify({"tags": []})
        
        tags = r.json().get("tags", []) or []
        tag_details = []
        
        for tag in tags:
            try:
                manifest_r = requests.get(
                    f"{REGISTRY_URL}/v2/{repo}/manifests/{tag}",
                    headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
                    timeout=TIMEOUT
                )
                if manifest_r.status_code == 200:
                    manifest = manifest_r.json()
                    size = manifest.get("config", {}).get("size", 0)
                    for layer in manifest.get("layers", []):
                        size += layer.get("size", 0)
                    tag_details.append({"tag": tag, "size": size})
            except:
                tag_details.append({"tag": tag, "size": 0})
        
        return jsonify({"tags": tag_details})
    except Exception as e:
        return jsonify({"tags": [], "error": str(e)})

@app.route("/api/delete/tag/<path:repo>/<tag>", methods=["DELETE"])
def delete_tag(repo, tag):
    if READ_ONLY:
        return jsonify({"success": False, "error": "Read-only mode"}), 403
    
    try:
        manifest_r = requests.get(
            f"{REGISTRY_URL}/v2/{repo}/manifests/{tag}",
            headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
            timeout=TIMEOUT
        )
        
        if manifest_r.status_code != 200:
            return jsonify({"success": False, "error": "Tag not found"})
        
        digest = manifest_r.headers.get("Docker-Content-Digest")
        if not digest:
            return jsonify({"success": False, "error": "No digest found"})
        
        delete_r = requests.delete(
            f"{REGISTRY_URL}/v2/{repo}/manifests/{digest}",
            timeout=TIMEOUT
        )
        
        if delete_r.status_code in [200, 202]:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": f"HTTP {delete_r.status_code}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/delete/repo/<path:repo>", methods=["DELETE"])
def delete_repo(repo):
    if READ_ONLY:
        return jsonify({"success": False, "error": "Read-only mode"}), 403
    
    try:
        r = requests.get(f"{REGISTRY_URL}/v2/{repo}/tags/list", timeout=TIMEOUT)
        if r.status_code != 200:
            return jsonify({"success": False, "error": "Repository not found"})
        
        tags = r.json().get("tags", []) or []
        deleted = 0
        
        for tag in tags:
            try:
                manifest_r = requests.get(
                    f"{REGISTRY_URL}/v2/{repo}/manifests/{tag}",
                    headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
                    timeout=TIMEOUT
                )
                
                if manifest_r.status_code == 200:
                    digest = manifest_r.headers.get("Docker-Content-Digest")
                    if digest:
                        delete_r = requests.delete(
                            f"{REGISTRY_URL}/v2/{repo}/manifests/{digest}",
                            timeout=TIMEOUT
                        )
                        if delete_r.status_code in [200, 202]:
                            deleted += 1
            except:
                pass
        
        return jsonify({"success": True, "deleted": deleted, "total": len(tags)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    threading.Thread(target=fetch_registry_data, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
