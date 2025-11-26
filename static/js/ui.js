// UI and theme management
function initDarkMode() {
    const themeToggle = document.getElementById('themeToggle');
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

function viewManifest(registryName, repo, tag) {
    const details = tagDetailsCache[tag];
    if (!details) {
        showAlert('Loading tag details...', 'info');
        return;
    }
    
    let html = `
        <div class="modal fade" id="manifestOnlyModal" tabindex="-1">
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Manifest: ${repo}:${tag}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <pre><code>${JSON.stringify(details.manifest || {}, null, 2)}</code></pre>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>`;
    
    const existingModal = document.getElementById('manifestOnlyModal');
    if (existingModal) existingModal.remove();
    
    document.body.insertAdjacentHTML('beforeend', html);
    const modal = new bootstrap.Modal(document.getElementById('manifestOnlyModal'));
    modal.show();
}

function viewLayers(repo, tag) {
    fetch(`/api/vulnerabilities/${encodeURIComponent(currentRegistry)}`)
        .then(r => r.json())
        .then(data => {
            const results = data.results || {};
            const key = `${repo}:${tag}`;
            const result = results[key];
            const details = tagDetailsCache[tag];
            const manifestLayers = details?.manifest?.layers || [];
            
            let html = `
                <div class="modal fade" id="layersModal" tabindex="-1">
                    <div class="modal-dialog modal-xl">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">Layers: ${repo}:${tag}</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">`;
            
            manifestLayers.forEach((layer, idx) => {
                const layerDigest = layer.digest.substring(7, 19);
                let vulnLayer = null;
                
                if (result && result.layers) {
                    vulnLayer = result.layers[idx];
                }
                
                html += `<div class="card mb-2">
                    <div class="card-header">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <strong>Layer ${idx + 1}</strong> <code>${layerDigest}</code>
                                <span class="badge bg-secondary ms-2">${formatSize(layer.size)}</span>
                            </div>
                            <div>`;
                
                if (vulnLayer && vulnLayer.total > 0) {
                    html += `<span class="badge bg-danger">${vulnLayer.summary.CRITICAL || 0} C</span>
                            <span class="badge bg-warning">${vulnLayer.summary.HIGH || 0} H</span>
                            <span class="badge bg-info">${vulnLayer.summary.MEDIUM || 0} M</span>
                            <span class="badge bg-secondary">${vulnLayer.summary.LOW || 0} L</span>`;
                } else {
                    html += `<span class="text-muted">No vulnerabilities</span>`;
                }
                
                html += `</div>
                        </div>
                    </div>
                </div>`;
            });
            
            html += `</div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            </div>
                        </div>
                    </div>
                </div>`;
            
            const existingModal = document.getElementById('layersModal');
            if (existingModal) existingModal.remove();
            
            document.body.insertAdjacentHTML('beforeend', html);
            const modal = new bootstrap.Modal(document.getElementById('layersModal'));
            modal.show();
        });
}

function viewConfig(registryName, repo, tag) {
    const details = tagDetailsCache[tag];
    if (!details) {
        showAlert('Loading tag details...', 'info');
        return;
    }
    
    let html = `
        <div class="modal fade" id="configModal" tabindex="-1">
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Config: ${repo}:${tag}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <pre><code>${JSON.stringify(details.config || {}, null, 2)}</code></pre>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>`;
    
    const existingModal = document.getElementById('configModal');
    if (existingModal) existingModal.remove();
    
    document.body.insertAdjacentHTML('beforeend', html);
    const modal = new bootstrap.Modal(document.getElementById('configModal'));
    modal.show();
}

function scanVulnerabilities(registryName, repo, tag) {
    const btn = event.target.closest('button');
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    btn.disabled = true;
    
    fetch(`/api/scan/${encodeURIComponent(registryName)}/${encodeURIComponent(repo)}/${encodeURIComponent(tag)}`)
        .then(r => r.json())
        .then(data => {
            btn.innerHTML = originalHtml;
            btn.disabled = false;
            
            if (data.error) {
                showAlert(data.error, 'danger');
                return;
            }
            
            showVulnerabilityReport(repo, tag, data);
        })
        .catch(err => {
            btn.innerHTML = originalHtml;
            btn.disabled = false;
            showAlert('Scan failed: ' + err.message, 'danger');
        });
}

function showVulnerabilityReport(repo, tag, report) {
    const summary = report.summary || {};
    const total = report.total || 0;
    
    let html = `<div class="modal fade" id="vulnModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="bi bi-shield-exclamation"></i> Vulnerability Report</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <h6>${repo}:${tag}</h6>
                    <div class="alert alert-${total === 0 ? 'success' : 'warning'}">
                        <strong>Total Vulnerabilities: ${total}</strong>
                    </div>
                    <div class="row mb-3">
                        <div class="col"><span class="badge bg-danger">CRITICAL: ${summary.CRITICAL || 0}</span></div>
                        <div class="col"><span class="badge bg-warning">HIGH: ${summary.HIGH || 0}</span></div>
                        <div class="col"><span class="badge bg-info">MEDIUM: ${summary.MEDIUM || 0}</span></div>
                        <div class="col"><span class="badge bg-secondary">LOW: ${summary.LOW || 0}</span></div>
                    </div>`;
    
    if (report.details && report.details.length > 0) {
        html += '<h6>Details:</h6><div class="table-responsive" style="max-height: 400px; overflow-y: auto;">';
        html += '<table class="table table-sm"><thead><tr><th>ID</th><th>Severity</th><th>Package</th><th>Version</th><th>Fixed</th></tr></thead><tbody>';
        report.details.forEach(v => {
            const severityClass = v.severity === 'CRITICAL' ? 'danger' : v.severity === 'HIGH' ? 'warning' : 'info';
            html += `<tr><td><small>${v.id}</small></td><td><span class="badge bg-${severityClass}">${v.severity}</span></td><td>${v.package}</td><td>${v.version}</td><td>${v.fixedVersion || 'N/A'}</td></tr>`;
        });
        html += '</tbody></table></div>';
    }
    
    html += '</div></div></div></div>';
    
    const existing = document.getElementById('vulnModal');
    if (existing) existing.remove();
    
    document.body.insertAdjacentHTML('beforeend', html);
    const modal = new bootstrap.Modal(document.getElementById('vulnModal'));
    modal.show();
}
