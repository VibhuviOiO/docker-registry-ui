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
    const date = new Date(dateString.replace('Z', ''));
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours ago`;
    if (seconds < 2592000) return `${Math.floor(seconds / 86400)} days ago`;
    if (seconds < 31536000) return `${Math.floor(seconds / 2592000)} months ago`;
    return `${Math.floor(seconds / 31536000)} years ago`;
}

// ---------------------------------------------------------------------------
// Authentication support
//
// The server only ever returns 401 when AUTH_ENABLED=true, so wrapping fetch
// here is a no-op on installations that do not use authentication. Doing it
// centrally means the ~10 existing API call sites need no changes: they redirect
// to the login page instead of silently rendering an empty table.
// ---------------------------------------------------------------------------
(function () {
    const originalFetch = window.fetch.bind(window);

    window.fetch = function (input, init) {
        return originalFetch(input, init).then(function (response) {
            if (response.status === 401 && response.headers.get('X-Auth-Required')) {
                const next = encodeURIComponent(window.location.pathname + window.location.search);
                window.location.href = '/login?next=' + next;
                throw new Error('Authentication required');
            }
            return response;
        });
    };
})();

function initAccountChip() {
    fetch('/auth/me', { headers: { 'Accept': 'application/json' } })
        .then(function (response) { return response.ok ? response.json() : null; })
        .then(function (user) {
            if (!user || !user.username) return;

            const host = document.querySelector('.navbar .ms-auto');
            if (!host) return;

            const wrap = document.createElement('div');
            wrap.className = 'd-flex align-items-center ms-2';

            // Values originate from the directory / identity provider, so they
            // are set as text rather than interpolated into HTML.
            const chip = document.createElement('span');
            chip.className = 'badge bg-light text-dark border me-1';
            chip.title = user.email || '';

            const icon = document.createElement('i');
            icon.className = 'bi bi-person-circle';
            chip.appendChild(icon);
            chip.appendChild(document.createTextNode(
                ' ' + user.displayName + (user.isAdmin ? ' · admin' : ' · viewer')
            ));

            const signOut = document.createElement('a');
            signOut.className = 'btn btn-sm btn-outline-secondary';
            signOut.href = '/auth/logout';
            signOut.innerHTML = '<i class="bi bi-box-arrow-right"></i>';

            wrap.appendChild(chip);
            wrap.appendChild(signOut);
            host.appendChild(wrap);
        })
        .catch(function () { /* authentication is not enabled */ });
}

window.addEventListener('DOMContentLoaded', initAccountChip);


