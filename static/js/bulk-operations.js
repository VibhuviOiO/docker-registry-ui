// Bulk operations module
function switchToCleanupView() {
    document.querySelectorAll('[data-view]').forEach(l => l.classList.remove('active'));
    document.querySelector('[data-view="cleanup"]').classList.add('active');
    document.getElementById('repositories-view').style.display = 'none';
    document.getElementById('registries-view').style.display = 'none';
    document.getElementById('cleanup-view').style.display = 'block';
    document.getElementById('bulk-operations-view').style.display = 'none';
    document.getElementById('analytics-view').style.display = 'none';
}

function switchToRegistryConfig() {
    document.querySelectorAll('[data-view]').forEach(l => l.classList.remove('active'));
    document.querySelector('[data-view="registries"]').classList.add('active');
    document.getElementById('repositories-view').style.display = 'none';
    document.getElementById('registries-view').style.display = 'block';
    document.getElementById('cleanup-view').style.display = 'none';
    document.getElementById('bulk-operations-view').style.display = 'none';
    document.getElementById('analytics-view').style.display = 'none';
}

function checkBulkOpsEnabled() {
    populateBulkRepoDropdown();
}

function populateBulkRepoDropdown() {
    if (!currentRegistry) return;
    
    fetch(`/api/repositories/${encodeURIComponent(currentRegistry)}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) return;
            
            const select = document.getElementById('bulkRepoPattern');
            if (!select) return;
            
            select.innerHTML = '<option value="*">* (All repositories)</option>';
            
            data.repositories.forEach(repo => {
                const option = document.createElement('option');
                option.value = repo;
                option.textContent = repo;
                select.appendChild(option);
            });
            
            const prefixes = new Set();
            data.repositories.forEach(repo => {
                const parts = repo.split('/');
                if (parts.length > 1) {
                    prefixes.add(parts[0] + '/*');
                }
            });
            
            if (prefixes.size > 0) {
                const optgroup = document.createElement('optgroup');
                optgroup.label = 'Wildcard Patterns';
                prefixes.forEach(pattern => {
                    const option = document.createElement('option');
                    option.value = pattern;
                    option.textContent = pattern;
                    optgroup.appendChild(option);
                });
                select.appendChild(optgroup);
            }
        });
}

function initBulkOperations() {
    const bulkConfirm = document.getElementById('bulkConfirm');
    const bulkKeepMin = document.getElementById('bulkKeepMin');
    const bulkOlderThan = document.getElementById('bulkOlderThan');
    const bulkRepoPattern = document.getElementById('bulkRepoPattern');
    const bulkTagPattern = document.getElementById('bulkTagPattern');
    const bulkDryRun = document.getElementById('bulkDryRun');
    const runBulkBtn = document.getElementById('runBulkOperation');
    
    if (!bulkConfirm || !runBulkBtn) return;
    
    bulkConfirm.addEventListener('change', function() {
        runBulkBtn.disabled = !this.checked;
    });
    
    function updateBulkSummary() {
        const repoPattern = bulkRepoPattern.value || '*';
        const tagPattern = bulkTagPattern.value || '*';
        const olderThan = bulkOlderThan.value;
        const keepMin = bulkKeepMin.value || '0';
        const isDryRun = bulkDryRun.checked;
        
        let summary = '<div class="alert alert-info mb-0">';
        summary += '<h6 class="alert-heading"><i class="bi bi-list-check"></i> What You Selected:</h6>';
        summary += '<ul class="mb-2">';
        summary += `<li><strong>Registry:</strong> ${currentRegistry || 'Not selected'}</li>`;
        summary += `<li><strong>Repository Pattern:</strong> <code>${repoPattern}</code></li>`;
        summary += `<li><strong>Tag Pattern:</strong> <code>${tagPattern}</code></li>`;
        summary += `<li><strong>Age Filter:</strong> ${olderThan ? `Tags older than ${olderThan} days` : 'No age filter'}</li>`;
        summary += `<li><strong>Keep Minimum:</strong> ${keepMin} tags per repository</li>`;
        summary += `<li><strong>Mode:</strong> <span class="badge ${isDryRun ? 'bg-success' : 'bg-danger'}">${isDryRun ? 'DRY RUN (Preview Only)' : 'LIVE DELETION'}</span></li>`;
        summary += '</ul><hr>';
        summary += '<h6 class="alert-heading"><i class="bi bi-gear"></i> What Will Happen:</h6>';
        summary += '<ol class="mb-0">';
        summary += `<li>Search for repositories matching pattern: <code>${repoPattern}</code></li>`;
        summary += `<li>In each repository, find tags matching: <code>${tagPattern}</code></li>`;
        
        if (olderThan) {
            summary += `<li>Filter tags that are <strong>older than ${olderThan} days</strong></li>`;
        }
        
        if (parseInt(keepMin) > 0) {
            summary += `<li><strong class="text-success">Protect the ${keepMin} most recent tags</strong> (will NOT be deleted)</li>`;
        } else if (olderThan) {
            summary += `<li><strong class="text-danger">WARNING: No minimum tags set - ALL old tags may be deleted!</strong></li>`;
        }
        
        if (isDryRun) {
            summary += '<li><strong class="text-success">Preview results only</strong> - no actual deletion</li>';
        } else {
            summary += '<li><strong class="text-danger">DELETE matching tags permanently</strong></li>';
            summary += '<li>Manifest references removed (garbage collection required to free disk space)</li>';
        }
        
        summary += '</ol>';
        
        if (!isDryRun) {
            summary += '<hr><div class="text-danger"><strong><i class="bi bi-exclamation-triangle-fill"></i> FINAL WARNING:</strong></div>';
            summary += '<ul class="text-danger mb-0">';
            summary += '<li>Deleted tags <strong>CANNOT be recovered</strong></li>';
            summary += '<li>Images must be <strong>rebuilt and re-pushed</strong> if needed again</li>';
            summary += '<li>This operation has <strong>NO knowledge of active deployments</strong></li>';
            summary += '</ul>';
        }
        
        summary += '</div>';
        document.getElementById('bulkSummary').innerHTML = summary;
    }
    
    if (bulkOlderThan && bulkKeepMin) {
        bulkOlderThan.addEventListener('input', function() {
            if (this.value && parseInt(this.value) > 0) {
                bulkKeepMin.classList.add('border-danger');
                if (!bulkKeepMin.value || parseInt(bulkKeepMin.value) < 1) {
                    bulkKeepMin.value = '5';
                }
            } else {
                bulkKeepMin.classList.remove('border-danger');
            }
            updateBulkSummary();
        });
        
        bulkKeepMin.addEventListener('input', function() {
            if (this.value && parseInt(this.value) >= 1) {
                this.classList.remove('border-danger');
            }
            updateBulkSummary();
        });
    }
    
    [bulkRepoPattern, bulkTagPattern, bulkOlderThan, bulkKeepMin, bulkDryRun].forEach(el => {
        if (el) {
            el.addEventListener('input', updateBulkSummary);
            el.addEventListener('change', updateBulkSummary);
        }
    });
    
    updateBulkSummary();
}





function downloadConfig() {
    fetch('/api/registries')
        .then(r => r.json())
        .then(data => {
            const json = JSON.stringify(data.registries, null, 2);
            const blob = new Blob([json], {type: 'application/json'});
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `registries.config.${new Date().toISOString().split('T')[0]}.json`;
            a.click();
            window.URL.revokeObjectURL(url);
        });
}
