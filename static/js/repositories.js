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
                        <div class="d-flex align-items-start">
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
                            <div class="tag-vuln" data-tag="${tag}" style="min-width: 250px;"></div>
                        </div>
                    </div>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-secondary" onclick="viewManifest('${currentRegistry}', '${currentRepo}', '${tag}')" title="View manifest">
                            Manifest
                        </button>
                        <button class="btn btn-outline-secondary" onclick="viewLayers('${currentRepo}', '${tag}')" title="View layers">
                            Layers
                        </button>
                        <button class="btn btn-outline-secondary" onclick="viewConfig('${currentRegistry}', '${currentRepo}', '${tag}')" title="View config">
                            Config
                        </button>
                        <button class="btn btn-outline-primary tag-scan-btn" data-tag="${tag}" onclick="scanTagVulnerabilities('${currentRegistry}', '${currentRepo}', '${tag}', this)" title="Scan vulnerabilities">
                            Scan
                        </button>
                        <button class="btn btn-outline-secondary tag-cve-btn d-none" data-tag="${tag}" onclick="viewCVEDetails('${currentRepo}', '${tag}')" title="View CVEs">
                            CVEs
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
    loadTagVulnerabilities(tags);
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

function loadTagVulnerabilities(tags) {
    fetch(`/api/vulnerabilities/${encodeURIComponent(currentRegistry)}`)
        .then(r => r.json())
        .then(data => {
            const results = data.results || {};
            tags.forEach(tag => {
                const key = `${currentRepo}:${tag}`;
                const result = results[key];
                const vulnEl = document.querySelector(`.tag-vuln[data-tag="${tag}"]`);
                const btnEl = document.querySelector(`.tag-scan-btn[data-tag="${tag}"]`);
                
                if (result && vulnEl && btnEl) {
                    const summary = result.summary || {};
                    const total = result.total || 0;
                    
                    let badges = '<div><small class="text-muted">Vulnerabilities:</small></div>';
                    badges += '<div class="d-flex gap-2 mt-1">';
                    badges += `<span class="badge bg-danger">${summary.CRITICAL || 0} C</span>`;
                    badges += `<span class="badge bg-warning">${summary.HIGH || 0} H</span>`;
                    badges += `<span class="badge bg-info">${summary.MEDIUM || 0} M</span>`;
                    badges += `<span class="badge bg-secondary">${summary.LOW || 0} L</span>`;
                    badges += '</div>';
                    vulnEl.innerHTML = badges;
                    
                    btnEl.textContent = 'Rescan';
                    btnEl.classList.remove('btn-outline-primary');
                    btnEl.classList.add('btn-outline-secondary');
                    
                    const cveBtn = document.querySelector(`.tag-cve-btn[data-tag="${tag}"]`);
                    if (cveBtn && total > 0) {
                        cveBtn.classList.remove('d-none');
                    }
                }
            });
        });
}

function scanTagVulnerabilities(registryName, repo, tag, btn) {
    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    
    fetch(`/api/scan/${encodeURIComponent(registryName)}/${encodeURIComponent(repo)}/${encodeURIComponent(tag)}`)
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
            
            if (data.error) {
                showAlert(`Scan failed: ${data.error}`, 'danger');
            } else {
                const total = data.total || 0;
                const critical = data.summary?.CRITICAL || 0;
                const high = data.summary?.HIGH || 0;
                
                const vulnEl = document.querySelector(`.tag-vuln[data-tag="${tag}"]`);
                if (vulnEl) {
                    let badges = '<div><small class="text-muted">Vulnerabilities:</small></div>';
                    badges += '<div class="d-flex gap-2 mt-1">';
                    badges += `<span class="badge bg-danger">${critical} C</span>`;
                    badges += `<span class="badge bg-warning">${high} H</span>`;
                    badges += `<span class="badge bg-info">${data.summary?.MEDIUM || 0} M</span>`;
                    badges += `<span class="badge bg-secondary">${data.summary?.LOW || 0} L</span>`;
                    badges += '</div>';
                    vulnEl.innerHTML = badges;
                }
                
                const cveBtn = document.querySelector(`.tag-cve-btn[data-tag="${tag}"]`);
                if (cveBtn) {
                    if (total > 0) {
                        cveBtn.classList.remove('d-none');
                    } else {
                        cveBtn.classList.add('d-none');
                    }
                }
                
                btn.textContent = 'Rescan';
                btn.classList.remove('btn-outline-primary');
                btn.classList.add('btn-outline-secondary');
                
                if (total === 0) {
                    showAlert(`✓ No vulnerabilities found in ${repo}:${tag}`, 'success');
                } else {
                    showAlert(`Found ${total} vulnerabilities (Critical: ${critical}, High: ${high}) in ${repo}:${tag}`, 'warning');
                }
            }
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
            showAlert('Scan failed: ' + err.message, 'danger');
        });
}

function viewCVEDetails(repo, tag) {
    fetch(`/api/vulnerabilities/${encodeURIComponent(currentRegistry)}`)
        .then(r => r.json())
        .then(data => {
            const results = data.results || {};
            const key = `${repo}:${tag}`;
            const result = results[key];
            
            if (!result || !result.details) {
                showAlert('No CVE details available', 'warning');
                return;
            }
            
            const details = result.details || [];
            let html = `
                <div class="modal fade" id="cveModal" tabindex="-1">
                    <div class="modal-dialog modal-xl">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">CVE Details: ${repo}:${tag}</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <div class="mb-3">
                                    <label class="form-label">Filter by Severity:</label>
                                    <div class="btn-group" role="group">
                                        <input type="checkbox" class="btn-check" id="filter-critical" checked>
                                        <label class="btn btn-outline-danger btn-sm" for="filter-critical">CRITICAL</label>
                                        
                                        <input type="checkbox" class="btn-check" id="filter-high" checked>
                                        <label class="btn btn-outline-warning btn-sm" for="filter-high">HIGH</label>
                                        
                                        <input type="checkbox" class="btn-check" id="filter-medium" checked>
                                        <label class="btn btn-outline-info btn-sm" for="filter-medium">MEDIUM</label>
                                        
                                        <input type="checkbox" class="btn-check" id="filter-low" checked>
                                        <label class="btn btn-outline-secondary btn-sm" for="filter-low">LOW</label>
                                        
                                        <input type="checkbox" class="btn-check" id="filter-unknown" checked>
                                        <label class="btn btn-outline-secondary btn-sm" for="filter-unknown">UNKNOWN</label>
                                    </div>
                                </div>
                                <div class="table-responsive">
                                    <table class="table table-sm table-hover" id="cve-table">
                                        <thead>
                                            <tr>
                                                <th>CVE ID</th>
                                                <th>Severity</th>
                                                <th>Package</th>
                                                <th>Installed</th>
                                                <th>Fixed</th>
                                                <th>Title</th>
                                            </tr>
                                        </thead>
                                        <tbody>`;
            
            details.forEach(vuln => {
                const severityClass = vuln.severity === 'CRITICAL' ? 'danger' : 
                                     vuln.severity === 'HIGH' ? 'warning' : 
                                     vuln.severity === 'MEDIUM' ? 'info' : 'secondary';
                const cveId = vuln.id || 'N/A';
                const cveLink = cveId !== 'N/A' ? `https://nvd.nist.gov/vuln/detail/${cveId}` : '#';
                html += `<tr data-severity="${vuln.severity}">
                    <td><a href="${cveLink}" target="_blank" rel="noopener"><code>${cveId}</code></a></td>
                    <td><span class="badge bg-${severityClass}">${vuln.severity}</span></td>
                    <td>${vuln.package || 'N/A'}</td>
                    <td><code>${vuln.version || 'N/A'}</code></td>
                    <td><code>${vuln.fixedVersion || 'N/A'}</code></td>
                    <td><small>${vuln.title || 'N/A'}</small></td>
                </tr>`;
            });
            
            html += `</tbody></table></div>`;
            
            if (result.layers && result.layers.length > 0) {
                html += `<h6 class="mt-4">Vulnerabilities by Layer</h6>`;
                result.layers.forEach((layer, idx) => {
                    html += `<div class="card mb-2">
                        <div class="card-header" style="font-size:0.875rem;">
                            <strong>Layer ${idx + 1}</strong> <code>${layer.digest}</code>
                            <span class="float-end">
                                <span class="badge bg-danger">${layer.summary.CRITICAL || 0}</span>
                                <span class="badge bg-warning">${layer.summary.HIGH || 0}</span>
                                <span class="badge bg-info">${layer.summary.MEDIUM || 0}</span>
                                <span class="badge bg-secondary">${layer.summary.LOW || 0}</span>
                            </span>
                        </div>
                    </div>`;
                });
            }
            
            html += `</div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            </div>
                        </div>
                    </div>
                </div>`;
            
            const existingModal = document.getElementById('cveModal');
            if (existingModal) existingModal.remove();
            
            document.body.insertAdjacentHTML('beforeend', html);
            const modal = new bootstrap.Modal(document.getElementById('cveModal'));
            modal.show();
            
            // Add filter event listeners
            ['critical', 'high', 'medium', 'low', 'unknown'].forEach(severity => {
                document.getElementById(`filter-${severity}`).addEventListener('change', function() {
                    const rows = document.querySelectorAll(`#cve-table tbody tr[data-severity="${severity.toUpperCase()}"]`);
                    rows.forEach(row => {
                        row.style.display = this.checked ? '' : 'none';
                    });
                });
            });
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
