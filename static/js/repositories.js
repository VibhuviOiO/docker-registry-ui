// Repository and tag management
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
                        <div><strong>${repo}</strong></div>
                        <i class="bi bi-chevron-right"></i>
                    </div>
                </div>`;
            });
            
            document.getElementById('repo-list').innerHTML = html;
            document.getElementById('stat-repos').textContent = repos.length;
            
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
            
            const tagBadge = document.getElementById('stat-tags');
            tagBadge.textContent = tags.length;
            tagBadge.style.display = 'inline-block';
            
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
    const registryUrl = registryUrlCache[currentRegistry] || '';
    let html = '';
    tags.forEach(tag => {
        const pullCmd = `docker pull ${registryUrl}/${currentRepo}:${tag}`;
        html += `<div class="tag-item" data-tag="${tag}">
            <div class="mb-2">
                <div class="d-flex justify-content-between align-items-center">
                    <div class="flex-grow-1">
                        <div class="d-flex align-items-center mb-1">
                            <strong class="me-2">${tag}</strong>
                            <span class="badge bg-light text-dark tag-digest" data-tag="${tag}"></span>
                        </div>
                        <div class="d-flex gap-3 text-muted small">
                            <span class="tag-size" data-tag="${tag}">
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
                        <button class="btn btn-outline-info scan-vuln-btn" onclick="scanVulnerabilities('${currentRegistry}', '${currentRepo}', '${tag}')" title="Scan vulnerabilities">
                            <i class="bi bi-shield-check"></i>
                        </button>
                        ${!readOnly ? `<button class="btn btn-outline-danger" onclick="deleteTag('${currentRegistry}', '${currentRepo}', '${tag}')">
                            <i class="bi bi-trash"></i>
                        </button>` : ''}
                    </div>
                </div>
            </div>
            <div class="input-group input-group-sm">
                <input type="text" class="form-control font-monospace bg-light" id="pull-${tag}" value="${pullCmd}" readonly style="font-size:0.8rem;">
                <button class="btn btn-outline-secondary" onclick="copyToClipboard('pull-${tag}')" title="Copy to clipboard">
                    <i class="bi bi-clipboard"></i>
                </button>
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
                    if (sizeEl) sizeEl.innerHTML = '<i class="bi bi-hdd"></i> N/A';
                    const createdEl = document.querySelector(`.tag-created[data-tag="${tag}"]`);
                    if (createdEl) createdEl.innerHTML = '<i class="bi bi-clock"></i> N/A';
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

function copyToClipboard(inputId) {
    const input = document.getElementById(inputId);
    input.select();
    navigator.clipboard.writeText(input.value).then(() => {
        const btn = input.nextElementSibling;
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check"></i>';
        setTimeout(() => {
            btn.innerHTML = originalHtml;
        }, 2000);
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

function switchToRegistryConfigOld() {
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
