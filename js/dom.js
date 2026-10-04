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

/**
 * Shorten text to <= limit chars, preferably ending with punctuation
 * (mirrors cut_at_sentence in scripts/convert.py).
 */
function cutAtSentence(text, limit) {
    var s = String(text == null ? '' : text).replace(/^\s+|\s+$/g, '');
    if (s.length <= limit) return s;
    var head = s.substring(0, limit);
    var marks = ['.', '؟', '!', '…'];
    var idx = -1;
    for (var k = 0; k < marks.length; k++) {
        var at = head.lastIndexOf(marks[k]);
        if (at > idx) idx = at;
    }
    if (idx >= 40) return head.substring(0, idx + 1).replace(/\s+$/g, '');
    var cut = head.lastIndexOf(' ');
    return (cut > 0 ? head.substring(0, cut) : head).replace(/[\s,،;:]+$/g, '') + '...';
}
