let currentRegistry = null;
let currentRepo = null;
let loadedTags = new Set();
let allTags = [];
let tagDetailsCache = {};
let deleteModal = null;
let copyModal = null;
let manifestModal = null;
let pendingDelete = null;

// Initialize modals and dark mode on page load
window.addEventListener('DOMContentLoaded', function() {
    deleteModal = new bootstrap.Modal(document.getElementById('deleteModal'));
    copyModal = new bootstrap.Modal(document.getElementById('copyModal'));
    manifestModal = new bootstrap.Modal(document.getElementById('manifestModal'));
    
    document.getElementById('confirmDeleteBtn').addEventListener('click', function() {
        if (pendingDelete) {
            pendingDelete();
            deleteModal.hide();
            pendingDelete = null;
        }
    });
    
    // Initialize dark mode
    initDarkMode();
    
    // Copy command button
    document.getElementById('copyCommandBtn').addEventListener('click', function() {
        const input = document.getElementById('copyCommandInput');
        input.select();
        navigator.clipboard.writeText(input.value).then(() => {
            this.innerHTML = '<i class="bi bi-check"></i> Copied!';
            setTimeout(() => {
                this.innerHTML = '<i class="bi bi-clipboard"></i> Copy';
            }, 2000);
        });
    });
    
    // Tag sorting
    document.getElementById('sortTags').addEventListener('change', function() {
        sortAndFilterTags();
    });
    
    // Tag filtering
    document.getElementById('filterTags').addEventListener('keyup', function() {
        sortAndFilterTags();
    });
});

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
        document.getElementById('cleanup-view').style.display = view === 'cleanup' ? 'block' : 'none';
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
    
    // Check registry health status
    checkRegistryHealth();
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
    tagDetailsCache = {};
    document.getElementById('repo-title').textContent = repo;
    document.getElementById('image-name-section').style.display = 'block';
    
    const deleteBtn = document.getElementById('deleteRepoBtn');
    if (deleteBtn) {
        deleteBtn.style.display = (typeof readOnly !== 'undefined' && readOnly) ? 'none' : 'block';
    }
    
    document.getElementById('stat-tags').style.display = 'none';
    document.getElementById('tag-controls').style.display = 'none';
    showLoading('tags-list');
    
    fetch(`/api/tags/${encodeURIComponent(registryName)}/${encodeURIComponent(repo)}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                document.getElementById('tags-container').innerHTML = 
                    `<div class="text-center p-4 text-danger">${data.error}</div>`;
                return;
            }
            
            const tags = data.tags;
            allTags = tags;
            
            // Update tag count badge
            const tagBadge = document.getElementById('stat-tags');
            tagBadge.textContent = tags.length;
            tagBadge.style.display = 'inline-block';
            
            // Show tag controls
            document.getElementById('tag-controls').style.display = tags.length > 0 ? 'flex' : 'none';
            
            if (tags.length === 0) {
                document.getElementById('tags-list').innerHTML = 
                    '<p class="text-muted text-center p-4">No tags found</p>';
                return;
            }
            
            renderTags(tags);
            loadTagSizes(registryName, repo, tags);
        });
}

function renderTags(tags) {
    let html = '';
    tags.forEach(tag => {
        html += `<div class="tag-item" data-tag="${tag}">
            <div class="d-flex justify-content-between align-items-center">
                <div class="flex-grow-1">
                    <div class="d-flex align-items-center mb-1">
                        <strong class="me-2">${tag}</strong>
                        <span class="badge bg-light text-dark tag-digest" data-tag="${tag}"></span>
                    </div>
                    <div class="d-flex gap-3 text-muted small">
                        <span class="tag-size" data-registry="${currentRegistry}" data-repo="${currentRepo}" data-tag="${tag}">
                            <i class="bi bi-hdd"></i> <span class="spinner-border spinner-border-sm"></span>
                        </span>
                        <span class="tag-created" data-tag="${tag}">
                            <i class="bi bi-clock"></i> <span class="spinner-border spinner-border-sm"></span>
                        </span>
                    </div>
                </div>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-secondary" onclick="viewManifest('${currentRegistry}', '${currentRepo}', '${tag}')" title="View manifest">
                        <i class="bi bi-file-code"></i>
                    </button>
                    <button class="btn btn-outline-secondary" onclick="copyPullCommand('${currentRegistry}', '${currentRepo}', '${tag}')" title="Copy pull command">
                        <i class="bi bi-clipboard"></i>
                    </button>
                    ${!readOnly ? `<button class="btn btn-outline-danger" onclick="deleteTag('${currentRegistry}', '${currentRepo}', '${tag}')">
                        <i class="bi bi-trash"></i>
                    </button>` : ''}
                </div>
            </div>
        </div>`;
    });
    
    document.getElementById('tags-list').innerHTML = html;
}

function loadTagSizes(registryName, repo, tags) {
    const batchSize = 5;
    let index = 0;
    
    function loadBatch() {
        const batch = tags.slice(index, index + batchSize);
        
        batch.forEach(tag => {
            fetch(`/api/tag-details/${encodeURIComponent(registryName)}/${encodeURIComponent(repo)}/${encodeURIComponent(tag)}`)
                .then(r => r.json())
                .then(data => {
                    tagDetailsCache[tag] = data;
                    
                    const sizeEl = document.querySelector(`.tag-size[data-tag="${tag}"]`);
                    if (sizeEl) {
                        sizeEl.innerHTML = `<i class="bi bi-hdd"></i> ${formatSize(data.size)}`;
                        sizeEl.dataset.sizeBytes = data.size;
                    }
                    
                    const createdEl = document.querySelector(`.tag-created[data-tag="${tag}"]`);
                    if (createdEl && data.created) {
                        createdEl.innerHTML = `<i class="bi bi-clock"></i> ${formatTimeAgo(data.created)}`;
                        createdEl.dataset.timestamp = new Date(data.created).getTime();
                    } else if (createdEl) {
                        createdEl.innerHTML = `<i class="bi bi-clock"></i> Unknown`;
                    }
                    
                    const digestEl = document.querySelector(`.tag-digest[data-tag="${tag}"]`);
                    if (digestEl && data.digest) {
                        digestEl.textContent = data.digest.substring(7, 19);
                    }
                })
                .catch(() => {
                    const sizeEl = document.querySelector(`.tag-size[data-tag="${tag}"]`);
                    if (sizeEl) {
                        sizeEl.innerHTML = '<i class="bi bi-hdd"></i> N/A';
                    }
                    const createdEl = document.querySelector(`.tag-created[data-tag="${tag}"]`);
                    if (createdEl) {
                        createdEl.innerHTML = '<i class="bi bi-clock"></i> N/A';
                    }
                });
        });
        
        index += batchSize;
        if (index < tags.length) {
            setTimeout(loadBatch, 500);
        }
    }
    
    loadBatch();
}

function sortAndFilterTags() {
    const sortBy = document.getElementById('sortTags').value;
    const filterText = document.getElementById('filterTags').value.toLowerCase();
    
    let filteredTags = allTags.filter(tag => tag.toLowerCase().includes(filterText));
    
    const tagItems = Array.from(document.querySelectorAll('.tag-item'));
    
    tagItems.sort((a, b) => {
        const tagA = a.dataset.tag;
        const tagB = b.dataset.tag;
        
        if (sortBy === 'name') {
            return tagA.localeCompare(tagB);
        } else if (sortBy === 'size') {
            const sizeA = parseInt(a.querySelector('.tag-size').dataset.sizeBytes || 0);
            const sizeB = parseInt(b.querySelector('.tag-size').dataset.sizeBytes || 0);
            return sizeB - sizeA;
        } else if (sortBy === 'date') {
            const dateA = parseInt(a.querySelector('.tag-created').dataset.timestamp || 0);
            const dateB = parseInt(b.querySelector('.tag-created').dataset.timestamp || 0);
            return dateB - dateA;
        }
        return 0;
    });
    
    const tagsList = document.getElementById('tags-list');
    tagsList.innerHTML = '';
    
    tagItems.forEach(item => {
        if (filteredTags.includes(item.dataset.tag)) {
            tagsList.appendChild(item);
        }
    });
}

function deleteTag(registryName, repo, tag) {
    document.getElementById('deleteModalMessage').innerHTML = 
        `Are you sure you want to delete tag <strong>${tag}</strong> from <strong>${repo}</strong>?`;
    
    pendingDelete = function() {
        fetch(`/api/delete/tag/${encodeURIComponent(registryName)}/${encodeURIComponent(repo)}/${encodeURIComponent(tag)}`, { method: 'DELETE' })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    showAlert(`Tag <strong>${tag}</strong> deleted successfully. <a href="#" onclick="switchToRegistryConfig(); return false;" class="alert-link">Run garbage collection</a> to free disk space.`, 'warning');
                    loadTags(registryName, repo);
                } else {
                    showAlert(data.error || 'Failed to delete tag', 'danger');
                }
            });
    };
    
    deleteModal.show();
}

document.getElementById('deleteRepoBtn').addEventListener('click', function() {
    if (!currentRepo || !currentRegistry) return;
    
    document.getElementById('deleteModalMessage').innerHTML = 
        `Are you sure you want to delete the entire repository <strong>${currentRepo}</strong>?<br><br>This will delete all tags in this repository.`;
    
    pendingDelete = function() {
        fetch(`/api/delete/repo/${encodeURIComponent(currentRegistry)}/${encodeURIComponent(currentRepo)}`, { method: 'DELETE' })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    showAlert(`Repository <strong>${currentRepo}</strong> deleted (${data.deleted}/${data.total} tags). <a href="#" onclick="switchToRegistryConfig(); return false;" class="alert-link">Run garbage collection</a> to free disk space.`, 'warning');
                    loadRepositories(currentRegistry, true);
                    document.getElementById('image-name-section').style.display = 'none';
                    document.getElementById('tags-list').innerHTML = 
                        '<p class="text-muted text-center">Select a repository to view tags</p>';
                } else {
                    showAlert(data.error || 'Failed to delete repository', 'danger');
                }
            });
    };
    
    deleteModal.show();
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

function formatTimeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours ago`;
    if (seconds < 2592000) return `${Math.floor(seconds / 86400)} days ago`;
    if (seconds < 31536000) return `${Math.floor(seconds / 2592000)} months ago`;
    return `${Math.floor(seconds / 31536000)} years ago`;
}

function switchToRegistryConfig() {
    document.querySelectorAll('[data-view]').forEach(l => l.classList.remove('active'));
    document.querySelector('[data-view="cleanup"]').classList.add('active');
    document.getElementById('repositories-view').style.display = 'none';
    document.getElementById('registries-view').style.display = 'none';
    document.getElementById('cleanup-view').style.display = 'block';
}

function checkRegistryHealth() {
    fetch('/api/registries')
        .then(r => r.json())
        .then(data => {
            data.registries.forEach((registry, index) => {
                const statusCell = document.querySelector(`#registry-status-${index}`);
                if (!statusCell) return;
                
                statusCell.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Checking...';
                
                fetch(`/api/repositories/${encodeURIComponent(registry.name)}`)
                    .then(r => {
                        if (r.ok) {
                            statusCell.innerHTML = '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Online</span>';
                        } else {
                            statusCell.innerHTML = '<span class="badge bg-danger"><i class="bi bi-x-circle"></i> Error</span>';
                        }
                    })
                    .catch(() => {
                        statusCell.innerHTML = '<span class="badge bg-danger"><i class="bi bi-x-circle"></i> Offline</span>';
                    });
            });
        });
}

// Dark mode functionality
function initDarkMode() {
    const themeToggle = document.getElementById('themeToggle');
    const themeIcon = document.getElementById('themeIcon');
    const html = document.documentElement;
    
    const savedTheme = localStorage.getItem('theme');
    const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    const currentTheme = savedTheme || systemTheme;
    
    html.setAttribute('data-bs-theme', currentTheme);
    updateThemeIcon(currentTheme);
    
    themeToggle.addEventListener('click', function() {
        const current = html.getAttribute('data-bs-theme');
        const newTheme = current === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-bs-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateThemeIcon(newTheme);
    });
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('themeIcon');
    icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
}

// Copy commands functionality
function copyPullCommand(registryName, repo, tag) {
    fetch('/api/registries')
        .then(r => r.json())
        .then(data => {
            const registry = data.registries.find(r => r.name === registryName);
            if (!registry) return;
            
            const registryUrl = registry.url.replace(/^https?:\/\//, '');
            const pullCommand = `docker pull ${registryUrl}/${repo}:${tag}`;
            
            document.getElementById('copyCommandInput').value = pullCommand;
            copyModal.show();
        });
}

// Manifest viewer functionality
function viewManifest(registryName, repo, tag) {
    const details = tagDetailsCache[tag];
    if (!details) {
        showAlert('Loading tag details...', 'info');
        return;
    }
    
    // Display manifest JSON
    document.getElementById('manifestJson').textContent = JSON.stringify(details.manifest || {}, null, 2);
    
    // Display layers
    const layers = details.manifest?.layers || [];
    let layersHtml = '<div class="list-group">';
    layers.forEach((layer, idx) => {
        layersHtml += `<div class="list-group-item">
            <div class="d-flex justify-content-between">
                <strong>Layer ${idx + 1}</strong>
                <span class="badge bg-secondary">${formatSize(layer.size)}</span>
            </div>
            <small class="text-muted">${layer.digest}</small>
        </div>`;
    });
    layersHtml += '</div>';
    document.getElementById('layersList').innerHTML = layersHtml;
    
    // Display config
    document.getElementById('configJson').textContent = JSON.stringify(details.config || {}, null, 2);
    
    manifestModal.show();
}
