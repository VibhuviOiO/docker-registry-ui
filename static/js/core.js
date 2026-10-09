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

// Notifications stack in the corner instead of overwriting each other.
//
// showAlert used to replace the contents of a single #alert-container and clear
// it after 5 seconds, so a second message destroyed the first and a scan result
// or a failed delete could vanish before it was read. showToast keeps its own
// element per message, and showAlert keeps the old signature -- including
// accepting HTML, because call sites pass markup like <strong>...</strong>.
function showToast(message, type = 'success', timeoutMs = 8000) {
    const host = document.getElementById('toast-container');
    if (!host) {
        // Never let a missing container swallow the message.
        console.warn('toast container missing:', message);
        return null;
    }

    const el = document.createElement('div');
    el.className = `alert alert-${type} alert-dismissible fade show shadow-sm mb-2`;
    // Errors are interruptive; everything else is informational.
    el.setAttribute('role', type === 'danger' ? 'alert' : 'status');
    el.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>`;
    host.appendChild(el);

    setTimeout(() => {
        if (!el.parentNode) return;
        el.classList.remove('show');
        setTimeout(() => el.remove(), 300);
    }, timeoutMs);

    return el;
}

function showAlert(message, type = 'success') {
    // Give errors longer: they usually need reading or acting on.
    showToast(message, type, type === 'danger' ? 15000 : 8000);
}

function showLoading(elementId, message = 'Loading…') {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.innerHTML = `<div class="text-center text-muted p-4">
        <div class="spinner-border spinner-border-sm text-primary mb-2" role="status"></div>
        <div class="small">${message}</div>
    </div>`;
}

function showEmptyState(elementId, message) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.innerHTML = `<p class="text-muted text-center py-4 mb-0">${message}</p>`;
}

function showErrorState(elementId, message) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.innerHTML = `<p class="text-danger text-center py-4 mb-0">
        <i class="bi bi-exclamation-triangle"></i> ${message}
    </p>`;
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


