// Vulnerability scanning module
let scanResults = {};

function loadVulnerabilities() {
    if (!currentRegistry) return;
    
    fetch('/api/registries')
        .then(r => r.json())
        .then(data => {
            const registry = data.registries.find(r => r.name === currentRegistry);
            const vulnScan = registry?.vulnerabilityScan || {};
            
            if (!vulnScan.enabled) {
                showVulnDisabledMessage();
                return;
            }
            
            document.getElementById('vuln-results-table').innerHTML = '<tr><td colspan="9" class="text-center"><div class="spinner-border spinner-border-sm"></div> Loading...</td></tr>';
            
            fetch(`/api/vulnerabilities/${encodeURIComponent(currentRegistry)}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('vuln-results-table').innerHTML = `<tr><td colspan="9" class="text-center text-muted">${data.error}</td></tr>`;
                        return;
                    }
                    
                    scanResults = data.results || {};
                    renderVulnerabilityResults();
                });
        });
}

function showVulnDisabledMessage() {
    const vulnView = document.getElementById('vulnerabilities-view');
    vulnView.innerHTML = `
        <div class="bg-success bg-opacity-10 border border-success rounded p-4">
            <h5 class="text-success"><i class="bi bi-shield-check"></i> Vulnerability Scanning Setup</h5>
            <p class="text-dark">Vulnerability scanning is currently disabled for <strong>${currentRegistry}</strong> registry.</p>
            <hr>
            <h6 class="text-success">Two Ways to Enable:</h6>
            
            <div class="row mt-3">
                <div class="col-md-6">
                    <div class="card h-100">
                        <div class="card-header bg-success text-white">
                            <strong>Option 1: Via UI (Recommended)</strong>
                        </div>
                        <div class="card-body">
                            <ol class="mb-0">
                                <li>Go to <a href="#" onclick="switchToRegistryConfig(); return false;" class="fw-bold">Registry Configuration</a></li>
                                <li>Click the gear icon next to your registry</li>
                                <li>Enable "Vulnerability Scanning"</li>
                                <li>Select scanner (Trivy or Clair)</li>
                                <li>Enter scanner URL</li>
                                <li>Click "Save Configuration"</li>
                                <li>Restart the application</li>
                            </ol>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="card h-100">
                        <div class="card-header bg-info text-white">
                            <strong>Option 2: Via Configuration File</strong>
                        </div>
                        <div class="card-body">
                            <p><strong>Update REGISTRIES environment variable:</strong></p>
                            <pre class="bg-dark text-light p-2" style="font-size: 0.8rem;">REGISTRIES='[{
  "name": "${currentRegistry}",
  "api": "...",
  "vulnerabilityScan": {
    "enabled": true,
    "scanner": "trivy",
    "scannerUrl": "http://trivy-server:8080"
  }
}]'</pre>
                            <p class="mb-0"><strong>Then restart:</strong></p>
                            <pre class="bg-dark text-light p-2" style="font-size: 0.8rem;">docker-compose restart registry-ui</pre>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="alert alert-info mt-3 mb-0">
                <strong><i class="bi bi-info-circle"></i> Need a Scanner?</strong><br>
                Run Trivy server: <code>docker run -d -p 8080:8080 aquasec/trivy:latest server --listen 0.0.0.0:8080</code><br>
                See <a href="https://github.com/aquasecurity/trivy" target="_blank" class="alert-link">Trivy Documentation</a> for more details.
            </div>
        </div>
    `;
}

function renderVulnerabilityResults() {
    const results = Object.values(scanResults);
    
    if (results.length === 0) {
        document.getElementById('vuln-results-table').innerHTML = '<tr><td colspan="9" class="text-center text-muted">No scan results available. Click "Scan All Images" to start.</td></tr>';
        return;
    }
    
    let totalCritical = 0, totalHigh = 0, totalMedium = 0;
    
    let html = '';
    results.forEach(r => {
        const summary = r.summary || {};
        totalCritical += summary.CRITICAL || 0;
        totalHigh += summary.HIGH || 0;
        totalMedium += summary.MEDIUM || 0;
        
        const total = r.total || 0;
        const rowClass = total > 0 ? (summary.CRITICAL > 0 ? 'table-danger' : summary.HIGH > 0 ? 'table-warning' : '') : '';
        
        html += `<tr class="${rowClass}">
            <td>${r.repo}</td>
            <td><code>${r.tag}</code></td>
            <td><span class="badge bg-danger">${summary.CRITICAL || 0}</span></td>
            <td><span class="badge bg-warning">${summary.HIGH || 0}</span></td>
            <td><span class="badge bg-info">${summary.MEDIUM || 0}</span></td>
            <td><span class="badge bg-secondary">${summary.LOW || 0}</span></td>
            <td><strong>${total}</strong></td>
            <td><small class="text-muted">${formatTimeAgo(r.scannedAt)}</small></td>
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="viewVulnDetails('${r.repo}', '${r.tag}')">
                    <i class="bi bi-eye"></i>
                </button>
                <button class="btn btn-sm btn-outline-secondary" onclick="rescanImage('${r.repo}', '${r.tag}')">
                    <i class="bi bi-arrow-clockwise"></i>
                </button>
            </td>
        </tr>`;
    });
    
    document.getElementById('vuln-results-table').innerHTML = html;
    document.getElementById('vuln-total-scanned').textContent = results.length;
    document.getElementById('vuln-critical').textContent = totalCritical;
    document.getElementById('vuln-high').textContent = totalHigh;
    document.getElementById('vuln-medium').textContent = totalMedium;
}

function scanAllImages() {
    if (!currentRegistry) {
        showAlert('Please select a registry first', 'warning');
        return;
    }
    
    const btn = document.getElementById('scanAllBtn');
    if (!btn) return;
    
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Scanning...';
    
    fetch(`/api/scan-all/${encodeURIComponent(currentRegistry)}`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-shield-check"></i> Scan Latest Tags';
            
            if (data.success) {
                showAlert(`Scanned ${data.scanned} images`, 'success');
                loadVulnerabilities();
            } else {
                showAlert(data.error || 'Scan failed', 'danger');
            }
        });
}

function rescanImage(repo, tag) {
    scanVulnerabilities(currentRegistry, repo, tag);
    setTimeout(() => loadVulnerabilities(), 2000);
}

function viewVulnDetails(repo, tag) {
    const key = `${repo}:${tag}`;
    const result = scanResults[key];
    if (result) {
        showVulnerabilityReport(repo, tag, result);
    }
}
