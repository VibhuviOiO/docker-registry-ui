// Audit log view.
//
// The endpoint is admin-only, so the navigation entry is revealed only after a
// probe succeeds. That keeps the view invisible to viewers without needing the
// server to pass an extra flag into every template.

function initAuditView() {
    fetch('/api/audit?limit=1', { headers: { 'Accept': 'application/json' } })
        .then(function (response) { return response.ok ? response.json() : null; })
        .then(function (data) {
            if (!data) return;
            const nav = document.getElementById('audit-nav');
            if (nav) nav.style.display = '';
        })
        .catch(function () { /* authentication disabled, or not an admin */ });
}

function loadAuditLog() {
    const target = document.getElementById('audit-results');
    if (!target) return;

    target.innerHTML = '';
    const spinner = document.createElement('div');
    spinner.className = 'text-center p-4';
    spinner.innerHTML = '<div class="spinner-border text-primary" role="status"></div>';
    target.appendChild(spinner);

    fetch('/api/audit?limit=200', { headers: { 'Accept': 'application/json' } })
        .then(function (response) {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.json();
        })
        .then(function (data) {
            const entries = (data && data.entries) || [];
            target.innerHTML = '';
            if (!entries.length) {
                const empty = document.createElement('p');
                empty.className = 'text-muted text-center py-4 mb-0';
                empty.textContent = 'No audit entries yet.';
                target.appendChild(empty);
                return;
            }
            target.appendChild(renderAuditTable(entries));
        })
        .catch(function () {
            target.innerHTML = '';
            const failed = document.createElement('p');
            failed.className = 'text-danger text-center py-4 mb-0';
            failed.textContent = 'Could not load the audit log.';
            target.appendChild(failed);
        });
}

const AUDIT_EVENT_STYLES = {
    login_success: 'success',
    login_failed: 'danger',
    logout: 'light',
    privileged_denied: 'warning',
    privileged_request: 'secondary'
};

function renderAuditTable(entries) {
    const table = document.createElement('table');
    table.className = 'table table-sm table-striped align-middle mb-0';

    const head = document.createElement('thead');
    const headRow = document.createElement('tr');
    ['Time', 'Event', 'Actor', 'Role', 'Action', 'Status', 'IP'].forEach(function (label) {
        const th = document.createElement('th');
        th.textContent = label;
        th.className = 'small text-muted text-uppercase';
        headRow.appendChild(th);
    });
    head.appendChild(headRow);
    table.appendChild(head);

    const body = document.createElement('tbody');

    entries.forEach(function (entry) {
        const row = document.createElement('tr');

        // Every value here originates from the audit file, so it is set as text
        // rather than interpolated into HTML.
        const time = document.createElement('td');
        time.className = 'small text-nowrap';
        time.textContent = formatAuditTime(entry.timestamp);
        row.appendChild(time);

        const event = document.createElement('td');
        const badge = document.createElement('span');
        const style = AUDIT_EVENT_STYLES[entry.event] || 'secondary';
        // Bootstrap's .badge sets white text, which is invisible on a light
        // background -- the logout row rendered as an empty pill.
        badge.className = 'badge bg-' + style + (style === 'light' ? ' text-dark border' : '');
        badge.textContent = entry.event || '';
        if (entry.detail) badge.title = entry.detail;
        event.appendChild(badge);
        row.appendChild(event);

        [entry.actor, entry.role, entry.action].forEach(function (value) {
            const cell = document.createElement('td');
            cell.className = 'small';
            cell.textContent = value || '—';
            row.appendChild(cell);
        });

        const status = document.createElement('td');
        status.className = 'small';
        status.textContent = entry.status === null || entry.status === undefined ? '—' : entry.status;
        row.appendChild(status);

        const ip = document.createElement('td');
        ip.className = 'small text-muted';
        ip.textContent = entry.ip || '—';
        row.appendChild(ip);

        body.appendChild(row);
    });

    table.appendChild(body);
    return table;
}

function formatAuditTime(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (isNaN(date.getTime())) return value;
    return date.toLocaleString();
}
