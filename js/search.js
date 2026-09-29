/**
 * Arabic Christian Translations - Search Functionality
 * Instant search across all documents
 */

// Site root derived from this script's own URL (…/js/search.js) so the
// index is fetched with ONE request at any page depth (bible/<slug>/<n>.html
// included) instead of blind relative probes.
var SEARCH_SITE_ROOT = (function () {
    var src = (document.currentScript && document.currentScript.src) || '';
    return src.replace(/js\/[^/]*$/, '');
})();

/* Shared Arabic full-text engine (mirrors scripts/build.py tokenization):
   strip diacritics/tatweel, normalize alef/hamza forms, words of 2+ letters. */
window.ArSearch = (function () {
    'use strict';
    var DIACRITICS_RE = /[\u064B-\u0652\u0670\u0640]/g;
    var WORD_SRC = '[\\p{L}]{2,}';
    var ALEF_MAP = {'\u0623': '\u0627', '\u0625': '\u0627', '\u0622': '\u0627',
                    '\u0671': '\u0627', '\u0624': '\u0648', '\u0626': '\u064A'};

    function normalize(str) {
        var t = String(str == null ? '' : str).replace(DIACRITICS_RE, '');
        var out = '';
        for (var i = 0; i < t.length; i++) {
            out += ALEF_MAP[t[i]] || t[i];
        }
        return out;
    }

    function tokenize(str) {
        var t = normalize(str).toLowerCase();
        var re = new RegExp(WORD_SRC, 'gu');
        var out = [], m;
        while ((m = re.exec(t)) !== null) out.push(m[0]);
        return out;
    }

    /* Normalized text + map[normIdx] = origIdx (diacritics dropped). */
    function normWithMap(str) {
        var orig = String(str == null ? '' : str);
        var chars = [], map = [];
        for (var i = 0; i < orig.length; i++) {
            var ch = orig[i];
            if (/[\u064B-\u0652\u0670\u0640]/.test(ch)) continue;
            chars.push(ALEF_MAP[ch] || ch);
            map.push(i);
        }
        return { text: chars.join('').toLowerCase(), map: map };
    }

    /* Find [start,end) ranges (original coords) of any word in text. */
    function findRanges(text, words) {
        var nm = normWithMap(String(text).toLowerCase());
        var ranges = [];
        (words || []).forEach(function (w) {
            if (!w) return;
            var from = 0, at;
            while ((at = nm.text.indexOf(w, from)) !== -1) {
                ranges.push([nm.map[at], nm.map[at + w.length - 1] + 1]);
                from = at + Math.max(1, w.length);
            }
        });
        ranges.sort(function (a, b) { return a[0] - b[0]; });
        var merged = [];
        ranges.forEach(function (r) {
            var last = merged[merged.length - 1];
            if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
            else merged.push([r[0], r[1]]);
        });
        return merged;
    }

    var metaCache = null, fullCache = null, fullFailed = false;
    function root() { return SEARCH_SITE_ROOT || ''; }
    function fetchJson(url) {
        return fetch(url).then(function (r) {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        });
    }
    function loadMeta() {
        if (metaCache) return Promise.resolve(metaCache);
        if (window.__DOCUMENTS_DATA__) {
            metaCache = window.__DOCUMENTS_DATA__;
            return Promise.resolve(metaCache);
        }
        return fetchJson(root() + 'documents/index.json').then(function (d) {
            metaCache = d.documents || [];
            return metaCache;
        });
    }
    function loadFullIndex() {
        if (fullCache) return Promise.resolve(fullCache);
        if (fullFailed) return Promise.reject(new Error('unavailable'));
        return fetchJson(root() + 'search-index.json').then(function (d) {
            fullCache = d;
            return d;
        }).catch(function (e) {
            fullFailed = true;
            throw e;
        });
    }

    /* AND over tokens (rarest posting first). Returns [docIdx...]. */
    function matchContent(query, full) {
        var words = [];
        tokenize(query).forEach(function (w) {
            if (words.indexOf(w) === -1) words.push(w);
        });
        if (!words.length || !full || !full.index) return [];
        var lists = [];
        for (var i = 0; i < words.length; i++) {
            var l = full.index[words[i]];
            if (!l || !l.length) return [];
            lists.push(l);
        }
        lists.sort(function (a, b) { return a.length - b.length; });
        var set = new Set(lists[0]);
        for (var k = 1; k < lists.length; k++) {
            var next = new Set();
            lists[k].forEach(function (id) { if (set.has(id)) next.add(id); });
            set = next;
            if (!set.size) return [];
        }
        return Array.from(set);
    }

    return {
        normalize: normalize, tokenize: tokenize,
        normWithMap: normWithMap, findRanges: findRanges,
        loadMeta: loadMeta, loadFullIndex: loadFullIndex,
        matchContent: matchContent
    };
})();

class Search {
    constructor() {
        this.documents = [];
        this.searchInput = null;
        this.searchResults = null;
        this.isOpen = false;
        this.activeIndex = -1;
        this.debounceTimer = null;
        this.loadError = false;
        this.isLoading = false;

        this.init();
    }

    async init() {
        this.searchInput = document.getElementById('searchInput');
        this.searchResults = document.getElementById('searchResults');

        if (!this.searchInput || !this.searchResults) return;

        if (!this.searchResults.id) {
            this.searchResults.id = 'searchResults';
        }
        this.searchResults.setAttribute('role', 'listbox');
        this.searchResults.setAttribute('aria-label', 'نتائج البحث');

        this.setupEventListeners();
        this.isLoading = true;
        await this.loadDocuments();
        this.isLoading = false;
    }

    async loadDocuments() {
        if (window.__DOCUMENTS_DATA__) {
            this.documents = window.__DOCUMENTS_DATA__;
            return;
        }

        const paths = [];
        if (SEARCH_SITE_ROOT) {
            paths.push(SEARCH_SITE_ROOT + 'documents/index.json');
        }
        paths.push(
            'documents/index.json',
            '../documents/index.json',
            '../../documents/index.json',
            '../../../documents/index.json'
        );
        for (const path of paths) {
            try {
                const response = await fetch(path);
                if (response.ok) {
                    const data = await response.json();
                    this.documents = data.documents || [];
                    return;
                }
            } catch (error) {
                console.error('Search load failed:', error);
            }
        }
        this.loadError = true;
    }

    setupEventListeners() {
        this.searchInput.setAttribute('role', 'combobox');
        this.searchInput.setAttribute('aria-expanded', 'false');
        this.searchInput.setAttribute('aria-controls', 'searchResults');
        this.searchInput.setAttribute('aria-autocomplete', 'list');

        this.searchInput.addEventListener('input', () => {
            clearTimeout(this.debounceTimer);
            this.debounceTimer = setTimeout(() => {
                this.handleSearch(this.searchInput.value);
            }, 150);
        });

        this.searchInput.addEventListener('focus', () => {
            if (this.searchInput.value.trim().length >= 2) {
                this.showResults();
            }
        });

        this.searchInput.addEventListener('keydown', (e) => {
            const items = this.getResultItems();

            if (e.key === 'Escape') {
                this.hideResults();
                this.clearActive();
                return;
            }

            if (e.key === 'ArrowDown' && items.length) {
                e.preventDefault();
                this.moveActive(1, items);
            } else if (e.key === 'ArrowUp' && items.length) {
                e.preventDefault();
                this.moveActive(-1, items);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (this.activeIndex >= 0 && items[this.activeIndex]) {
                    items[this.activeIndex].click();
                } else {
                    this.goToResultsPage(this.searchInput.value);
                }
            }
        });

        document.addEventListener('click', (e) => {
            if (!this.searchInput.contains(e.target) &&
                !this.searchResults.contains(e.target)) {
                this.hideResults();
                this.clearActive();
            }
        });
    }

    getResultItems() {
        return Array.from(this.searchResults.querySelectorAll('a.search-result-item'));
    }

    moveActive(delta, items) {
        if (this.activeIndex >= 0 && items[this.activeIndex]) {
            items[this.activeIndex].classList.remove('is-active');
            items[this.activeIndex].removeAttribute('aria-selected');
        }
        this.activeIndex += delta;
        if (this.activeIndex < 0) this.activeIndex = items.length - 1;
        if (this.activeIndex >= items.length) this.activeIndex = 0;
        const el = items[this.activeIndex];
        el.classList.add('is-active');
        el.setAttribute('aria-selected', 'true');
        el.scrollIntoView({ block: 'nearest' });
        this.searchInput.setAttribute('aria-activedescendant', el.id || '');
        if (!el.id) {
            el.id = 'search-result-' + this.activeIndex;
            this.searchInput.setAttribute('aria-activedescendant', el.id);
        }
    }

    clearActive() {
        this.activeIndex = -1;
        this.searchResults.querySelectorAll('.is-active').forEach(el => {
            el.classList.remove('is-active');
            el.removeAttribute('aria-selected');
        });
        this.searchInput.removeAttribute('aria-activedescendant');
    }

    handleSearch(query) {
        query = (query || '').trim();

        if (query.length < 2) {
            this.hideResults();
            this.announce('');
            return;
        }

        if (this.loadError) {
            this.searchResults.innerHTML = `
                <div class="search-result-item" role="presentation">
                    <div class="search-result-title">تعذر تحميل نتائج البحث</div>
                    <div class="search-result-category">حاول تحديث الصفحة</div>
                </div>
            `;
            this.showResults();
            this.announce('خطأ في تحميل البحث');
            return;
        }

        if (this.isLoading) {
            this.searchResults.innerHTML = `
                <div class="search-result-item" role="presentation">
                    <div class="search-result-title">جاري التحميل...</div>
                </div>
            `;
            this.showResults();
            return;
        }

        try {
            const results = this.searchDocuments(query);
            this.displayResults(results, query);
        } catch (error) {
            console.error('Search error:', error);
            this.searchResults.innerHTML = `
                <div class="search-result-item" role="presentation">
                    <div class="search-result-title">حدث خطأ في البحث</div>
                </div>
            `;
            this.showResults();
        }
    }

    searchDocuments(query) {
        const words = window.ArSearch ? window.ArSearch.tokenize(query) : [query.toLowerCase()];
        const norm = window.ArSearch
            ? (t) => window.ArSearch.normalize(t).toLowerCase()
            : (t) => String(t || '').toLowerCase();
        const matched = this.documents.filter(doc => {
            const hay = norm(doc.title) + ' ' + norm(doc.description) + ' ' +
                        norm(doc.author) + ' ' +
                        (Array.isArray(doc.categories)
                            ? doc.categories.join(' ')
                            : String(doc.category || ''));
            const hayN = norm(hay);
            return words.length > 0 && words.every(w => hayN.includes(w));
        });
        return { all: matched, shown: matched.slice(0, 20) };
    }

    resultsPageUrl(query) {
        return (SEARCH_SITE_ROOT || '') + 'search.html?q=' + encodeURIComponent((query || '').trim());
    }

    goToResultsPage(query) {
        window.location.href = this.resultsPageUrl(query);
    }

    displayResults(resultObj, query) {
        const results = resultObj.shown || [];
        const total = resultObj.all ? resultObj.all.length : results.length;
        this.activeIndex = -1;

        if (results.length === 0) {
            this.searchResults.innerHTML = `
                <div class="search-result-item" role="presentation">
                    <div class="search-result-title">لا توجد نتائج</div>
                    <div class="search-result-category">جرّب كلمات بحث مختلفة</div>
                </div>
            <a href="${escapeHtml(this.resultsPageUrl(query))}" class="search-result-item search-result-all" role="option" aria-selected="false">
                <div class="search-result-title">البحث في نصوص التعليقات &larr;</div>
            </a>
            `;
            this.announce('لا توجد نتائج');
        } else {
            const moreNote = total > results.length
                ? `<div class="search-result-more">عرض ${results.length} من ${total} نتيجة</div>`
                : '';
            this.searchResults.innerHTML = results.map((doc, i) => {
                const path = safePath(doc.html_path || '#');
                const author = escapeHtml(doc.author || '');
                const title = doc.title || 'بدون عنوان';
                return `
                <a href="${escapeHtml(path)}" class="search-result-item" role="option" id="search-result-${i}" aria-selected="false">
                    <div class="search-result-title">${this.highlightText(title, query)}</div>
                    <div class="search-result-category">${author}</div>
                </a>
                `;
            }).join('') + moreNote +
            `<a href="${escapeHtml(this.resultsPageUrl(query))}" class="search-result-item search-result-all" role="option" aria-selected="false">`
            + `<div class="search-result-title">عرض كل النتائج &larr;</div></a>`;
            this.announce(`${total} نتيجة`);
        }

        this.showResults();
    }

    escapeRegex(str) {
        return String(str).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    highlightText(text, query) {
        const safe = escapeHtml(String(text || 'بدون عنوان'));
        if (!query) return safe;
        try {
            const regex = new RegExp(`(${this.escapeRegex(escapeHtml(query))})`, 'gi');
            return safe.replace(regex, '<strong>$1</strong>');
        } catch (e) {
            return safe;
        }
    }

    announce(message) {
        let live = document.getElementById('searchLive');
        if (!live) {
            live = document.createElement('div');
            live.id = 'searchLive';
            live.setAttribute('aria-live', 'polite');
            live.className = 'visually-hidden';
            document.body.appendChild(live);
        }
        live.textContent = message;
    }

    showResults() {
        this.searchResults.classList.add('active');
        this.searchInput.setAttribute('aria-expanded', 'true');
        this.isOpen = true;
    }

    hideResults() {
        this.searchResults.classList.remove('active');
        this.searchInput.setAttribute('aria-expanded', 'false');
        this.isOpen = false;
    }
}

/* Highlight search words inside article text (?hl=...), then jump to first hit. */
function highlightQueryInArticle() {
    var article = document.querySelector('.document-content');
    if (!article || !window.ArSearch) return;
    var raw = '';
    try {
        raw = (new URLSearchParams(window.location.search).get('hl') || '').trim();
    } catch (e) { return; }
    if (raw.length < 2) return;
    var words = [];
    window.ArSearch.tokenize(raw).forEach(function (w) {
        if (words.indexOf(w) === -1) words.push(w);
    });
    if (!words.length) return;
    var MAX_MARKS = 300, marks = 0, first = null;
    var walker = document.createTreeWalker(article, NodeFilter.SHOW_TEXT, null);
    var nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(function (node) {
        if (marks >= MAX_MARKS) return;
        var parent = node.parentNode;
        if (!parent || parent.closest('mark,script,style')) return;
        var ranges = window.ArSearch.findRanges(node.nodeValue, words);
        if (!ranges.length) return;
        var frag = document.createDocumentFragment();
        var pos = 0, text = node.nodeValue;
        ranges.forEach(function (r) {
            if (marks >= MAX_MARKS) return;
            if (r[0] > pos) frag.appendChild(document.createTextNode(text.slice(pos, r[0])));
            var mark = document.createElement('mark');
            mark.className = 'hl';
            mark.textContent = text.slice(r[0], r[1]);
            frag.appendChild(mark);
            marks++;
            if (!first) first = mark;
            pos = r[1];
        });
        if (pos < text.length) frag.appendChild(document.createTextNode(text.slice(pos)));
        parent.replaceChild(frag, node);
    });
    if (first && first.scrollIntoView) {
        try { first.scrollIntoView({ block: 'center' }); } catch (e) {}
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.search = new Search();
    highlightQueryInArticle();
});
