let currentRegistry = null;
let currentRepo = null;
let loadedTags = new Set();

// Sidebar toggle
document.getElementById('sidebarToggle').addEventListener('click', function() {
    document.getElementById('sidebar').classList.toggle('collapsed');
});

// View switching
document.querySelectorAll('[data-view]').forEach(link => {
    link.addEventListener('click', function(e) {
        e.preventDefault();
        const view = this.dataset.view;
        
        // Update active state
        document.querySelectorAll('[data-view]').forEach(l => l.classList.remove('active'));
        this.classList.add('active');
        
        // Show/hide views
        document.getElementById('repositories-view').style.display = view === 'repositories' ? 'block' : 'none';
        document.getElementById('registries-view').style.display = view === 'registries' ? 'block' : 'none';
    });
});

// Registry selector
document.getElementById('registrySelector').addEventListener('change', function() {
    const registryName = this.value;
    if (!registryName) return;
    
    currentRegistry = registryName;
    loadRepositories(registryName);
});

// Auto-select default registry on page load
window.addEventListener('DOMContentLoaded', function() {
    const selector = document.getElementById('registrySelector');
    const defaultOption = Array.from(selector.options).find(opt => opt.dataset.default === 'true');
    
    if (defaultOption) {
        selector.value = defaultOption.value;
        currentRegistry = defaultOption.value;
        loadRepositories(currentRegistry);
    }
});

// Refresh repositories
document.getElementById('refreshRepos').addEventListener('click', function() {
    if (!currentRegistry) {
        showAlert('Please select a registry first', 'warning');
        return;
    }
    loadRepositories(currentRegistry);
});

// Search
document.getElementById('searchBox').addEventListener('keyup', function() {
    const q = this.value.toLowerCase();
    document.querySelectorAll('.repo-row').forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
});

function showAlert(message, type = 'success') {
    const alert = `<div class="alert alert-${type} alert-dismissible fade show" role="alert">
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    </div>`;
    document.getElementById('alert-container').innerHTML = alert;
    setTimeout(() => { document.getElementById('alert-container').innerHTML = ''; }, 5000);
}

function showLoading(elementId) {
    const el = document.getElementById(elementId);
    el.innerHTML = '<div class="text-center p-4"><div class="spinner-border text-primary" role="status"></div></div>';
}

function loadRepositories(registryName, force = false) {
    showLoading('repo-list');
    
    fetch(`/api/repositories/${encodeURIComponent(registryName)}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                document.getElementById('repo-list').innerHTML = 
                    `<div class="text-center p-4 text-danger">${data.error}</div>`;
                return;
            }
            
            const repos = data.repositories;
            if (repos.length === 0) {
                document.getElementById('repo-list').innerHTML = 
                    '<div class="text-center p-4 text-muted">No repositories found</div>';
                return;
            }
            
            let html = '';
            repos.forEach(repo => {
                html += `<div class="repo-row" data-repo="${repo}">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${repo}</strong>
                        </div>
                        <i class="bi bi-chevron-right"></i>
                    </div>
                </div>`;
            });
            
            document.getElementById('repo-list').innerHTML = html;
            
            // Update repository count
            document.getElementById('stat-repos').textContent = repos.length;
            
            // Attach click handlers
            document.querySelectorAll('.repo-row').forEach(row => {
                row.addEventListener('click', function() {
                    document.querySelectorAll('.repo-row').forEach(r => r.classList.remove('active'));
                    this.classList.add('active');
                    loadTags(currentRegistry, this.dataset.repo);
                });
            });
        })
        .catch(err => {
            document.getElementById('repo-list').innerHTML = 
                `<div class="text-center p-4 text-danger">Error loading repositories</div>`;
        });
}

function loadTags(registryName, repo) {
    currentRepo = repo;
    document.getElementById('repo-title').textContent = repo;
    const deleteBtn = document.getElementById('deleteRepoBtn');
    if (deleteBtn) {
        deleteBtn.style.display = (typeof readOnly !== 'undefined' && readOnly) ? 'none' : 'block';
    }
    
    // Hide tag count badge initially
    document.getElementById('stat-tags').style.display = 'none';
    
    showLoading('tags-container');
    
    fetch(`/api/tags/${encodeURIComponent(registryName)}/${encodeURIComponent(repo)}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                document.getElementById('tags-container').innerHTML = 
                    `<div class="text-center p-4 text-danger">${data.error}</div>`;
                return;
            }
            
            const tags = data.tags;
            
            // Update tag count badge
            const tagBadge = document.getElementById('stat-tags');
            tagBadge.textContent = tags.length;
            tagBadge.style.display = 'inline-block';
            
            if (tags.length === 0) {
                document.getElementById('tags-container').innerHTML = 
                    '<p class="text-muted text-center p-4">No tags found</p>';
                return;
            }
            
            let html = '';
            tags.forEach(tag => {
                html += `<div class="tag-item" data-tag="${tag}">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${tag}</strong>
                            <div class="tag-size text-muted small" data-registry="${registryName}" data-repo="${repo}" data-tag="${tag}">
                                <span class="spinner-border spinner-border-sm"></span> Loading size...
                            </div>
                        </div>
                        ${!readOnly ? `<button class="btn btn-sm btn-outline-danger" onclick="deleteTag('${registryName}', '${repo}', '${tag}')">
                            <i class="bi bi-trash"></i>
                        </button>` : ''}
                    </div>
                </div>`;
            });
            
            document.getElementById('tags-container').innerHTML = html;
            
            // Load tag sizes on-demand (lazy loading)
            loadTagSizes(registryName, repo, tags);
        });
}

function loadTagSizes(registryName, repo, tags) {
    // Load sizes in batches to avoid overwhelming the API
    const batchSize = 5;
    let index = 0;
    
    function loadBatch() {
        const batch = tags.slice(index, index + batchSize);
        
        batch.forEach(tag => {
            fetch(`/api/tag-details/${encodeURIComponent(registryName)}/${encodeURIComponent(repo)}/${encodeURIComponent(tag)}`)
                .then(r => r.json())
                .then(data => {
                    const sizeEl = document.querySelector(`.tag-size[data-tag="${tag}"]`);
                    if (sizeEl) {
                        sizeEl.innerHTML = formatSize(data.size);
                    }
                })
                .catch(() => {
                    const sizeEl = document.querySelector(`.tag-size[data-tag="${tag}"]`);
                    if (sizeEl) {
                        sizeEl.innerHTML = '<span class="text-muted">Size unavailable</span>';
                    }
                });
        });
        
        index += batchSize;
        if (index < tags.length) {
            setTimeout(loadBatch, 500); // Delay between batches
        }
    }
    
    loadBatch();
}

function deleteTag(registryName, repo, tag) {
    if (!confirm(`Delete tag ${tag} from ${repo}?`)) return;
    
    fetch(`/api/delete/tag/${encodeURIComponent(registryName)}/${encodeURIComponent(repo)}/${encodeURIComponent(tag)}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showAlert(`Tag ${tag} deleted successfully`);
                loadTags(registryName, repo);
            } else {
                showAlert(data.error || 'Failed to delete tag', 'danger');
            }
        });
}

document.getElementById('deleteRepoBtn').addEventListener('click', function() {
    if (!currentRepo || !currentRegistry) return;
    
    if (!confirm(`Delete entire repository ${currentRepo}? This will delete all tags.`)) return;
    
    fetch(`/api/delete/repo/${encodeURIComponent(currentRegistry)}/${encodeURIComponent(currentRepo)}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showAlert(`Repository ${currentRepo} deleted (${data.deleted}/${data.total} tags)`);
                loadRepositories(currentRegistry, true);
                document.getElementById('tags-container').innerHTML = 
                    '<p class="text-muted text-center">Select a repository to view tags</p>';
            } else {
                showAlert(data.error || 'Failed to delete repository', 'danger');
            }
        });
});

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
