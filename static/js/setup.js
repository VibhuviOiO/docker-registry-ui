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
    
    const formInputs = ['setup-name', 'setup-api', 'setup-user', 'setup-password', 'setup-bulk-ops', 'setup-scanner', 'setup-scanner-url'];
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
        default: true,
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
            showAlert('Registry created successfully! Reloading...', 'success');
            setTimeout(() => location.reload(), 1500);
        } else {
            showAlert(data.error || 'Failed to create registry', 'danger');
        }
    });
}

function checkFirstRun() {
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
        default: true,
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
