// Main initialization
window.addEventListener('DOMContentLoaded', function() {
    deleteModal = new bootstrap.Modal(document.getElementById('deleteModal'));
    manifestModal = new bootstrap.Modal(document.getElementById('manifestModal'));
    
    document.getElementById('confirmDeleteBtn').addEventListener('click', function() {
        if (pendingDelete) {
            pendingDelete();
            deleteModal.hide();
            pendingDelete = null;
        }
    });
    

    
    document.getElementById('sortTags').addEventListener('change', sortAndFilterTags);
    document.getElementById('filterTags').addEventListener('keyup', sortAndFilterTags);
    
    document.getElementById('sidebarToggle').addEventListener('click', function() {
        document.getElementById('sidebar').classList.toggle('collapsed');
    });
    
    document.querySelectorAll('[data-view]').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const view = this.dataset.view;
            
            document.querySelectorAll('[data-view]').forEach(l => l.classList.remove('active'));
            this.classList.add('active');
            
            document.getElementById('repositories-view').style.display = view === 'repositories' ? 'block' : 'none';
            document.getElementById('registries-view').style.display = view === 'registries' ? 'block' : 'none';
            document.getElementById('cleanup-view').style.display = view === 'cleanup' ? 'block' : 'none';
            document.getElementById('bulk-operations-view').style.display = view === 'bulk' ? 'block' : 'none';
            document.getElementById('analytics-view').style.display = view === 'analytics' ? 'block' : 'none';
            document.getElementById('vulnerabilities-view').style.display = view === 'vulnerabilities' ? 'block' : 'none';
            
            if (view === 'analytics' && currentRegistry) {
                loadAnalytics(currentRegistry);
            }
            if (view === 'bulk' && currentRegistry) {
                checkBulkOpsEnabled();
            }
            if (view === 'vulnerabilities' && currentRegistry) {
                loadVulnerabilities();
            }
        });
    });
    
    document.getElementById('registrySelector').addEventListener('change', function() {
        const registryName = this.value;
        if (!registryName) return;
        currentRegistry = registryName;
        loadRepositories(registryName);
    });
    
    document.getElementById('refreshRepos').addEventListener('click', function() {
        if (!currentRegistry) {
            showAlert('Please select a registry first', 'warning');
            return;
        }
        loadRepositories(currentRegistry);
    });
    
    document.getElementById('searchBox').addEventListener('keyup', function() {
        const q = this.value.toLowerCase();
        document.querySelectorAll('.repo-row').forEach(row => {
            row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
        });
    });
    
    const deleteRepoBtn = document.getElementById('deleteRepoBtn');
    if (deleteRepoBtn) {
        deleteRepoBtn.addEventListener('click', function() {
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
                            document.getElementById('tags-list').innerHTML = '<p class="text-muted text-center">Select a repository to view tags</p>';
                        } else {
                            showAlert(data.error || 'Failed to delete repository', 'danger');
                        }
                    });
            };
            
            deleteModal.show();
        });
    }
    
    const bulkOpBtn = document.getElementById('runBulkOperation');
    if (bulkOpBtn) {
        bulkOpBtn.addEventListener('click', function() {
            if (!currentRegistry) {
                showAlert('Please select a registry first', 'warning');
                return;
            }
            
            const olderThan = parseInt(document.getElementById('bulkOlderThan').value) || null;
            const keepMin = parseInt(document.getElementById('bulkKeepMin').value) || 0;
            
            if (olderThan && keepMin < 1) {
                showAlert('ERROR: "Keep minimum tags" is REQUIRED when using age-based deletion to prevent losing all images. Set it to at least 5.', 'danger');
                document.getElementById('bulkKeepMin').classList.add('border-danger');
                document.getElementById('bulkKeepMin').focus();
                return;
            }
            
            const data = {
                registry: currentRegistry,
                repoPattern: document.getElementById('bulkRepoPattern').value,
                olderThanDays: olderThan,
                keepMin: keepMin,
                tagPattern: document.getElementById('bulkTagPattern').value,
                dryRun: document.getElementById('bulkDryRun').checked
            };
            
            document.getElementById('bulkResults').innerHTML = '<div class="spinner-border"></div> Processing...';
            
            fetch('/api/bulk-operation', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            })
            .then(r => r.json())
            .then(result => {
                if (result.success) {
                    let html = `<div class="alert alert-${result.dryRun ? 'info' : 'success'}">`;
                    html += result.dryRun ? '<strong>Dry Run Results:</strong>' : '<strong>Deleted:</strong>';
                    html += `</div>`;
                    
                    if (result.results.length === 0) {
                        html += '<p class="text-muted">No tags match the criteria</p>';
                    } else {
                        html += '<div class="list-group">';
                        result.results.forEach(r => {
                            html += `<div class="list-group-item">
                                <strong>${r.repo}</strong>: ${r.count} tags
                                <div class="small text-muted">${r.tags.join(', ')}</div>
                            </div>`;
                        });
                        html += '</div>';
                    }
                    
                    document.getElementById('bulkResults').innerHTML = html;
                } else {
                    showAlert(result.error, 'danger');
                }
            });
        });
    }
    
    const exportBtn = document.getElementById('exportAnalytics');
    if (exportBtn) {
        exportBtn.addEventListener('click', function() {
            if (!currentRegistry) return;
            
            fetch(`/api/analytics/${encodeURIComponent(currentRegistry)}`)
                .then(r => r.json())
                .then(data => {
                    let csv = 'Repository,Tags,Total Size (MB),Avg Size (MB)\n';
                    data.analytics.forEach(a => {
                        csv += `${a.repo},${a.tags},${(a.size / 1024 / 1024).toFixed(2)},${(a.avgSize / 1024 / 1024).toFixed(2)}\n`;
                    });
                    
                    const blob = new Blob([csv], {type: 'text/csv'});
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `registry-analytics-${currentRegistry}-${new Date().toISOString().split('T')[0]}.csv`;
                    a.click();
                });
        });
    }
    
    fetch('/api/registries')
        .then(r => r.json())
        .then(data => {
            data.registries.forEach(reg => {
                registryUrlCache[reg.name] = reg.url || reg.api.replace(/^https?:\/\//, '');
            });
        });
    
    const selector = document.getElementById('registrySelector');
    const defaultOption = Array.from(selector.options).find(opt => opt.dataset.default === 'true');
    
    if (defaultOption) {
        selector.value = defaultOption.value;
        currentRegistry = defaultOption.value;
        loadRepositories(currentRegistry);
    }
    
    checkRegistryHealth();
    initBulkOperations();
    initSetupWizard();
    checkFirstRun();
    
    const scanAllBtn = document.getElementById('scanAllBtn');
    if (scanAllBtn) {
        scanAllBtn.addEventListener('click', scanAllImages);
    }
    
    const refreshVulnBtn = document.getElementById('refreshVulnBtn');
    if (refreshVulnBtn) {
        refreshVulnBtn.addEventListener('click', loadVulnerabilities);
    }
    
    document.querySelectorAll('.bulk-ops-toggle').forEach(toggle => {
        toggle.addEventListener('change', function() {
            toggleBulkOperations(this.dataset.registry, this.checked);
        });
    });
    
    document.querySelectorAll('.config-details-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            showRegistryConfig(this.dataset.registry);
        });
    });
    
    const vulnEnabled = document.getElementById('config-vuln-enabled');
    if (vulnEnabled) {
        vulnEnabled.addEventListener('change', function() {
            document.getElementById('vuln-scan-config').style.display = this.checked ? 'block' : 'none';
        });
    }
    
    const saveConfigBtn = document.getElementById('save-registry-config');
    if (saveConfigBtn) {
        saveConfigBtn.addEventListener('click', saveRegistryConfig);
    }
    
    const downloadConfigBtn = document.getElementById('download-config-btn');
    if (downloadConfigBtn) {
        downloadConfigBtn.addEventListener('click', downloadConfig);
    }
    
    document.querySelectorAll('.vuln-scan-toggle').forEach(toggle => {
        toggle.addEventListener('change', function() {
            toggleVulnScan(this.dataset.registry, this.checked);
        });
    });
});
