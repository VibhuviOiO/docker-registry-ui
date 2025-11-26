// Core variables and utilities
let currentRegistry = null;
let currentRepo = null;
let loadedTags = new Set();
let allTags = [];
let tagDetailsCache = {};
let registryUrlCache = {};
let deleteModal = null;
let manifestModal = null;
let pendingDelete = null;
let repoSizeChart = null;
let repoTagChart = null;

function showAlert(message, type = 'success') {
    const alert = `<div class="alert alert-${type} alert-dismissible fade show" role="alert">
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    </div>`;
    document.getElementById('alert-container').innerHTML = alert;
    setTimeout(() => { document.getElementById('alert-container').innerHTML = ''; }, 5000);
}

function showLoading(elementId) {
    const el = document.getElementById(elementId);
    el.innerHTML = '<div class="text-center p-4"><div class="spinner-border text-primary" role="status"></div></div>';
}

function formatSize(bytes) {
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    return `${size.toFixed(2)} ${units[unitIndex]}`;
}

function formatTimeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours ago`;
    if (seconds < 2592000) return `${Math.floor(seconds / 86400)} days ago`;
    if (seconds < 31536000) return `${Math.floor(seconds / 2592000)} months ago`;
    return `${Math.floor(seconds / 31536000)} years ago`;
}
