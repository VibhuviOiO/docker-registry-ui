// Setup wizard module
function initSetupWizard() {
    const authEnabled = document.getElementById('setup-auth-enabled');
    const vulnEnabled = document.getElementById('setup-vuln-enabled');
    
    if (authEnabled) {
        authEnabled.addEventListener('change', function() {
            document.getElementById('auth-fields').style.display = this.checked ? 'block' : 'none';
            updateConfigPreview();
        });
    }
    
    if (vulnEnabled) {
        vulnEnabled.addEventListener('change', function() {
            document.getElementById('vuln-fields').style.display = this.checked ? 'block' : 'none';
            updateConfigPreview();
        });
    }
    
    const formInputs = ['setup-name', 'setup-api', 'setup-user', 'setup-password', 'setup-default', 'setup-bulk-ops', 'setup-scanner', 'setup-scanner-url'];
    formInputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', updateConfigPreview);
            el.addEventListener('change', updateConfigPreview);
        }
    });
    
    const testBtn = document.getElementById('test-connection-btn');
    if (testBtn) {
        testBtn.addEventListener('click', testRegistryConnection);
    }
    
    const setupForm = document.getElementById('setup-form');
    if (setupForm) {
        setupForm.addEventListener('submit', createRegistry);
    }
}

function testRegistryConnection() {
    const api = document.getElementById('setup-api').value;
    if (!api) {
        showAlert('Please enter Registry API URL', 'warning');
        return;
    }
    
    const btn = document.getElementById('test-connection-btn');
    const result = document.getElementById('test-result');
    
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Testing...';
    result.innerHTML = '';
    
    fetch('/api/test-registry', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            api: api,
            isAuthEnabled: document.getElementById('setup-auth-enabled').checked,
            user: document.getElementById('setup-user').value,
            password: document.getElementById('setup-password').value
        })
    })
    .then(r => r.json())
    .then(data => {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-plug"></i> Test Connection';
        
        if (data.success) {
            result.innerHTML = '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Connected</span>';
        } else {
            result.innerHTML = `<span class="badge bg-danger"><i class="bi bi-x-circle"></i> Failed: ${data.error}</span>`;
        }
    })
    .catch(err => {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-plug"></i> Test Connection';
        result.innerHTML = `<span class="badge bg-danger"><i class="bi bi-x-circle"></i> Error</span>`;
    });
}

function createRegistry(e) {
    e.preventDefault();
    
    const registry = {
        name: document.getElementById('setup-name').value,
        api: document.getElementById('setup-api').value,
        isAuthEnabled: document.getElementById('setup-auth-enabled').checked,
        user: document.getElementById('setup-user').value || '',
        password: document.getElementById('setup-password').value || '',
        apiToken: '',
        default: document.getElementById('setup-default').checked,
        bulkOperationsEnabled: document.getElementById('setup-bulk-ops').checked,
        vulnerabilityScan: {
            enabled: document.getElementById('setup-vuln-enabled').checked,
            scanner: document.getElementById('setup-scanner').value,
            scannerUrl: document.getElementById('setup-scanner-url').value || '',
            autoScanRules: [],
            scanLatestOnly: 1
        }
    };
    
    fetch('/api/registry/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(registry)
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            showSetupSuccess(registry);
        } else {
            showAlert(data.error || 'Failed to create registry', 'danger');
        }
    });
}

function showSetupSuccess(registry) {
    const wizardView = document.getElementById('setup-wizard-view');
    wizardView.innerHTML = `
        <div class="row justify-content-center">
            <div class="col-lg-8">
                <div class="card shadow">
                    <div class="card-header bg-success text-white">
                        <h4 class="mb-0"><i class="bi bi-check-circle"></i> Registry Created Successfully!</h4>
                    </div>
                    <div class="card-body">
                        <div class="alert alert-success">
                            <strong>Configuration Saved!</strong><br>
                            Your registry has been saved to <code>registries.config.json</code>
                        </div>
                        
                        <h5 class="mb-3">Next Steps:</h5>
                        
                        <div class="list-group mb-3">
                            <div class="list-group-item">
                                <div class="d-flex justify-content-between align-items-center">
                                    <div>
                                        <h6 class="mb-1"><i class="bi bi-download"></i> Download Backup</h6>
                                        <small class="text-muted">Save a copy of your configuration</small>
                                    </div>
                                    <button class="btn btn-primary" onclick="downloadSetupConfig()">
                                        <i class="bi bi-download"></i> Download
                                    </button>
                                </div>
                            </div>
                            

                            
                            <div class="list-group-item">
                                <div class="d-flex justify-content-between align-items-center">
                                    <div>
                                        <h6 class="mb-1"><i class="bi bi-box-seam"></i> Start Using Registry UI</h6>
                                        <small class="text-muted">Browse repositories and manage images</small>
                                    </div>
                                    <button class="btn btn-success" onclick="window.location.href='/?skipSetup=true'">
                                        <i class="bi bi-arrow-right"></i> Continue
                                    </button>
                                </div>
                            </div>
                        </div>
                        
                        <div class="alert alert-info mb-0">
                            <strong><i class="bi bi-info-circle"></i> Configuration Persisted:</strong><br>
                            • File saved to <code>data/registries.config.json</code> (volume-mounted)<br>
                            • Survives container restarts<br>
                            • Download backup for extra safety
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function downloadSetupConfig() {
    fetch('/api/registries')
        .then(r => r.json())
        .then(data => {
            const json = JSON.stringify(data.registries, null, 2);
            const blob = new Blob([json], {type: 'application/json'});
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'registries.config.json';
            a.click();
            window.URL.revokeObjectURL(url);
            showAlert('Configuration downloaded! You can now continue to the UI.', 'success');
        });
}

function checkFirstRun() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('skipSetup') === 'true') {
        return;
    }
    
    fetch('/api/registries')
        .then(r => r.json())
        .then(data => {
            if (!data.registries || data.registries.length === 0) {
                showSetupWizard();
            }
        });
}

function showSetupWizard() {
    document.getElementById('setup-wizard-view').style.display = 'block';
    document.getElementById('repositories-view').style.display = 'none';
    document.querySelector('.sidebar').style.display = 'none';
    updateConfigPreview();
}

function updateConfigPreview() {
    const config = {
        name: document.getElementById('setup-name')?.value || 'Your Registry Name',
        api: document.getElementById('setup-api')?.value || 'http://registry.example.com:5000',
        isAuthEnabled: document.getElementById('setup-auth-enabled')?.checked || false,
        user: '',
        password: '',
        apiToken: '',
        default: document.getElementById('setup-default')?.checked !== false,
        bulkOperationsEnabled: document.getElementById('setup-bulk-ops')?.checked || false,
        vulnerabilityScan: {
            enabled: document.getElementById('setup-vuln-enabled')?.checked || false,
            scanner: document.getElementById('setup-scanner')?.value || 'trivy',
            scannerUrl: document.getElementById('setup-scanner-url')?.value || '',
            autoScanRules: [],
            scanLatestOnly: 1
        }
    };
    
    if (config.isAuthEnabled) {
        config.user = document.getElementById('setup-user')?.value || 'username';
        config.password = '***hidden***';
    }
    
    const preview = document.getElementById('config-preview');
    if (preview) {
        preview.innerHTML = `<code class="language-json">${JSON.stringify([config], null, 2)}</code>`;
    }
}
