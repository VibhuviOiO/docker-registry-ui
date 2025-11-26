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
    
    document.getElementById('manifestJson').textContent = JSON.stringify(details.manifest || {}, null, 2);
    
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
    
    document.getElementById('configJson').textContent = JSON.stringify(details.config || {}, null, 2);
    
    manifestModal.show();
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
