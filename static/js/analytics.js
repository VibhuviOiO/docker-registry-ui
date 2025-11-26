// Analytics module
function loadAnalytics(registryName) {
    document.getElementById('analyticsTableBody').innerHTML = '<tr><td colspan="4" class="text-center"><div class="spinner-border spinner-border-sm"></div> Loading...</td></tr>';
    
    fetch(`/api/analytics/${encodeURIComponent(registryName)}`)
        .then(r => r.json())
        .then(data => {
            document.getElementById('stat-total-repos').textContent = data.totalRepos;
            document.getElementById('stat-total-tags').textContent = data.totalTags;
            document.getElementById('stat-total-storage').textContent = formatSize(data.totalSize);
            document.getElementById('stat-avg-size').textContent = formatSize(data.avgSize);
            
            let tableHtml = '';
            data.analytics.forEach(a => {
                tableHtml += `<tr>
                    <td>${a.repo}</td>
                    <td>${a.tags}</td>
                    <td>${formatSize(a.size)}</td>
                    <td>${formatSize(a.avgSize)}</td>
                </tr>`;
            });
            document.getElementById('analyticsTableBody').innerHTML = tableHtml;
            
            const top10Size = data.analytics.sort((a, b) => b.size - a.size).slice(0, 10);
            const top10Tags = data.analytics.sort((a, b) => b.tags - a.tags).slice(0, 10);
            
            if (repoSizeChart) repoSizeChart.destroy();
            if (repoTagChart) repoTagChart.destroy();
            
            const ctx1 = document.getElementById('repoSizeChart').getContext('2d');
            repoSizeChart = new Chart(ctx1, {
                type: 'bar',
                data: {
                    labels: top10Size.map(a => a.repo),
                    datasets: [{
                        label: 'Size (MB)',
                        data: top10Size.map(a => (a.size / 1024 / 1024).toFixed(2)),
                        backgroundColor: 'rgba(13, 110, 253, 0.5)',
                        borderColor: 'rgba(13, 110, 253, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: {y: {beginAtZero: true}}
                }
            });
            
            const ctx2 = document.getElementById('repoTagChart').getContext('2d');
            repoTagChart = new Chart(ctx2, {
                type: 'bar',
                data: {
                    labels: top10Tags.map(a => a.repo),
                    datasets: [{
                        label: 'Tag Count',
                        data: top10Tags.map(a => a.tags),
                        backgroundColor: 'rgba(25, 135, 84, 0.5)',
                        borderColor: 'rgba(25, 135, 84, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: {y: {beginAtZero: true}}
                }
            });
        });
}
