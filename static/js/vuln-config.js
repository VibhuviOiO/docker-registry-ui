// Vulnerability scanning configuration
function toggleVulnScan(registryName, enabled) {
    if (enabled) {
        showVulnScanSetup(registryName);
    } else {
        if (confirm(`Disable vulnerability scanning for ${registryName}?`)) {
            updateVulnScanConfig(registryName, {enabled: false});
        } else {
            document.querySelector(`.vuln-scan-toggle[data-registry="${registryName}"]`).checked = true;
        }
    }
}

function showVulnScanSetup(registryName) {
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header bg-info text-white">
                    <h5 class="modal-title"><i class="bi bi-shield-check"></i> Configure Vulnerability Scanning</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="alert alert-info">
                        <strong>Scanner Service Required:</strong><br>
                        Run Trivy or Clair scanner service separately and provide connection details below.
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Scanner Type</label>
                        <select class="form-select" id="vuln-modal-scanner">
                            <option value="trivy">Trivy</option>
                            <option value="clair">Clair</option>
                        </select>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Scanner URL <span class="text-danger">*</span></label>
                        <input type="text" class="form-control" id="vuln-modal-url" placeholder="http://trivy-server:8080" required>
                        <small class="text-muted">Example: <code>http://trivy-server:8080</code></small>
                    </div>
                    
                    <div class="mb-3">
                        <button type="button" class="btn btn-sm btn-outline-secondary" id="test-scanner-btn">
                            <i class="bi bi-plug"></i> Test Connection
                        </button>
                        <span id="scanner-test-result" class="ms-2"></span>
                    </div>
                    
                    <hr>
                    <h6>Scanning Options</h6>
                    
                    <div class="alert alert-info mb-3">
                        <strong>How Scanning Works:</strong><br>
                        • <strong>Manual:</strong> Click shield icon (<i class="bi bi-shield-check"></i>) on any tag to scan<br>
                        • <strong>Auto-Scan:</strong> Automatically scan latest tag per repo when enabled
                    </div>
                    
                    <div class="form-check form-switch mb-3">
                        <input class="form-check-input" type="checkbox" id="vuln-modal-autoscan">
                        <label class="form-check-label" for="vuln-modal-autoscan">
                            <strong>Enable Auto-Scan</strong><br>
                            <small class="text-muted">Automatically scan latest tag for each repository</small>
                        </label>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="save-vuln-config-btn">
                        <i class="bi bi-save"></i> Save & Enable
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    modal.querySelector('#test-scanner-btn').addEventListener('click', function() {
        const url = document.getElementById('vuln-modal-url').value;
        if (!url) {
            showAlert('Please enter scanner URL', 'warning');
            return;
        }
        
        const btn = this;
        const result = document.getElementById('scanner-test-result');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Testing...';
        
        fetch('/api/test-scanner', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url: url, scanner: document.getElementById('vuln-modal-scanner').value})
        })
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-plug"></i> Test Connection';
            if (data.success) {
                result.innerHTML = '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Connected</span>';
            } else {
                result.innerHTML = `<span class="badge bg-danger"><i class="bi bi-x-circle"></i> ${data.error}</span>`;
            }
        });
    });
    
    modal.querySelector('#save-vuln-config-btn').addEventListener('click', function() {
        const url = document.getElementById('vuln-modal-url').value;
        if (!url) {
            showAlert('Scanner URL is required', 'warning');
            return;
        }
        
        const config = {
            enabled: true,
            scanner: document.getElementById('vuln-modal-scanner').value,
            scannerUrl: url,
            autoScan: document.getElementById('vuln-modal-autoscan').checked
        };
        
        updateVulnScanConfig(registryName, config);
        bsModal.hide();
    });
    
    modal.addEventListener('hidden.bs.modal', function() {
        modal.remove();
    });
}

function updateVulnScanConfig(registryName, vulnConfig) {
    fetch('/api/registry/vuln-scan', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({registry: registryName, vulnerabilityScan: vulnConfig})
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            const msg = `Vulnerability scanning ${vulnConfig.enabled ? 'enabled' : 'disabled'} for ${registryName}. <button class="btn btn-sm btn-success ms-2" onclick="downloadConfig()"><i class="bi bi-download"></i> Download Backup</button>`;
            showAlert(msg, 'success');
            setTimeout(() => location.reload(), 2000);
        } else {
            showAlert(data.error || 'Failed to update setting', 'danger');
        }
    });
}
