/**
 * Search results page (search.html): full-text + metadata search over all
 * documents. Query from ?q=. Snippets are extracted client-side by fetching
 * matched pages (cached). Links carry ?hl= for in-article highlighting.
 * CSP-safe: no inline JS (this external file only).
 */
(function () {
    'use strict';

    var SNIPPET_RADIUS = 70;
    var SNIPPET_FETCH_POOL = 6;
    var MAX_RESULTS_RENDER = 500;

    function esc(s) {
        return window.escapeHtml ? window.escapeHtml(s) : String(s == null ? '' : s)
            .replace(/[&<>"']/g, function (c) {
                return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
            });
    }

    function root() {
        if (typeof SEARCH_SITE_ROOT !== 'undefined' && SEARCH_SITE_ROOT) return SEARCH_SITE_ROOT;
        return '';
    }

    function docUrl(doc, q) {
        var base = doc.html_path || '#';
        if (!/^(https?:)?\/\//i.test(base)) base = root() + String(base).replace(/^\/+/, '');
        var url = (window.safePath ? window.safePath(base) : base);
        return url + '?hl=' + encodeURIComponent(q);
    }

    function scoreDoc(doc, words, contentHit) {
        var norm = window.ArSearch.normalize;
        var title = norm(doc.title).toLowerCase();
        var author = norm(doc.author).toLowerCase();
        var desc = norm(doc.description).toLowerCase();
        var score = 0;
        if (words.length && words.every(function (w) { return title.indexOf(w) !== -1; })) score += 100;
        else if (words.some(function (w) { return title.indexOf(w) !== -1; })) score += 40;
        if (words.some(function (w) { return author.indexOf(w) !== -1; })) score += 50;
        if (words.some(function (w) { return desc.indexOf(w) !== -1; })) score += 20;
        if (contentHit) score += 10;
        return score;
    }

    var textCache = {};
    function docText(doc) {
        var key = doc.html_path || doc.id;
        if (!textCache[key]) {
            var url = doc.html_path || '#';
            if (!/^(https?:)?\/\//i.test(url)) url = root() + String(url).replace(/^\/+/, '');
            textCache[key] = fetch(url).then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.text();
            }).then(function (html) {
                var d = new DOMParser().parseFromString(html, 'text/html');
                var a = d.querySelector('.document-content');
                var t = a ? (a.textContent || '') : '';
                return t.replace(/\s+/g, ' ').trim();
            }).catch(function () { return ''; });
        }
        return textCache[key];
    }

    function snippetHtml(text, words) {
        if (!text) return '';
        var ranges = window.ArSearch.findRanges(text, words);
        if (!ranges.length) return '';
        var r0 = ranges[0];
        var start = Math.max(0, r0[0] - SNIPPET_RADIUS);
        var end = Math.min(text.length, r0[1] + SNIPPET_RADIUS);
        while (start > 0 && !/\s/.test(text[start - 1])) start--;
        while (end < text.length && !/\s/.test(text[end])) end++;
        var slice = text.slice(start, end);
        var inner = window.ArSearch.findRanges(slice, words);
        var out = '', pos = 0;
        inner.forEach(function (r) {
            out += esc(slice.slice(pos, r[0])) + '<mark>' + esc(slice.slice(r[0], r[1])) + '</mark>';
            pos = r[1];
        });
        out += esc(slice.slice(pos));
        return (start > 0 ? '…' : '') + out + (end < text.length ? '…' : '');
    }

    function renderMeta(el, text) {
        el.textContent = text;
    }

    function run() {
        var params = new URLSearchParams(window.location.search);
        var q = (params.get('q') || '').trim();
        var input = document.getElementById('pageSearchInput');
        var list = document.getElementById('resultsList');
        var meta = document.getElementById('searchMeta');
        if (!list || !meta) return;
        if (input && q) input.value = q;
        if (q.length < 2) {
            renderMeta(meta, 'اكتب كلمتين على الأقل للبحث.');
            list.innerHTML = '';
            return;
        }
        var words = window.ArSearch.tokenize(q);
        if (!words.length) {
            renderMeta(meta, 'تعذر فهم كلمات البحث.');
            return;
        }
        renderMeta(meta, 'جاري البحث…');
        list.innerHTML = '';

        Promise.all([window.ArSearch.loadMeta(), window.ArSearch.loadFullIndex().catch(function () { return null; })])
            .then(function (pair) {
                var docs = pair[0] || [];
                var full = pair[1];
                var contentIdx = new Set(full ? window.ArSearch.matchContent(q, full) : []);
                var scored = [];
                docs.forEach(function (doc, i) {
                    var s = scoreDoc(doc, words, contentIdx.has(i));
                    if (s > 0) scored.push({ doc: doc, score: s, idx: i });
                });
                scored.sort(function (a, b) {
                    return (b.score - a.score) || String(a.doc.title).localeCompare(String(b.doc.title));
                });
                var total = scored.length;
                var shown = scored.slice(0, MAX_RESULTS_RENDER);
                renderMeta(meta, total === 0 ? 'لا توجد نتائج عن: ' + q : total + ' نتيجة عن: ' + q +
                    ' (العناوين والمؤلفون والنصوص الكاملة)');
                if (!shown.length) return;
                shown.forEach(function (entry, n) { entry.n = n; });
                list.innerHTML = shown.map(function (entry) {
                    var doc = entry.doc;
                    var title = esc(doc.title || 'بدون عنوان');
                    var author = esc(doc.author || '');
                    return '<article class="result-item" data-n="' + entry.n + '">' +
                        '<a class="result-title" href="' + esc(docUrl(doc, q)) + '">' + title + '</a>' +
                        (author ? '<div class="result-meta">' + author + '</div>' : '') +
                        '<p class="search-snippet" data-snippet>جاري استخراج المقتطف…</p>' +
                        '</article>';
                }).join('');
                // Fill snippets with a small fetch pool, in rank order.
                var queue = shown.slice();
                var active = 0;
                function pump() {
                    while (active < SNIPPET_FETCH_POOL && queue.length) {
                        (function (entry) {
                            active++;
                            docText(entry.doc).then(function (text) {
                                active--;
                                var html = snippetHtml(text, words);
                                var sel = '.result-item[data-n="' + entry.n + '"] [data-snippet]';
                                var p = list.querySelector(sel);
                                if (p) {
                                    if (html) p.innerHTML = html;
                                    else p.remove();
                                }
                                pump();
                            });
                        })(queue.shift());
                    }
                }
                pump();
            })
            .catch(function () {
                renderMeta(meta, 'تعذر تحميل فهرس البحث. تحقق من الاتصال ثم أعد المحاولة.');
            });
    }

    if (document.readyState !== 'loading') run();
    else document.addEventListener('DOMContentLoaded', run);
})();
