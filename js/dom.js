/**
 * Shared DOM safety helpers.
 */

function escapeHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function safePath(path) {
    var p = String(path == null ? '' : path).trim();
    if (!p) return '#';
    if (p.charAt(0) === '#') return p;
    var lower = p.toLowerCase();
    if (lower.indexOf('javascript:') === 0 ||
        lower.indexOf('data:') === 0 ||
        lower.indexOf('vbscript:') === 0) {
        return '#';
    }
    if (/^[a-z][a-z0-9+.\-]*:/i.test(p)) {
        return (/^https?:/i.test(p)) ? p : '#';
    }
    return p;
}
