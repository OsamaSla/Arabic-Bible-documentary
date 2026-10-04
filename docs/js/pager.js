/**
 * A4 page flipper for document pages (progressive enhancement).
 * Splits article top-level blocks into A4-ratio sheets with a pager bar,
 * prev/next buttons, keyboard navigation and footnote-jump support.
 * Without JS (or on failure) the article simply scrolls as before.
 * CSP-safe: no inline handlers; all listeners attached here.
 */
(function () {
    'use strict';

    var A4_RATIO = 297 / 210;
    var SHEET_PAD_Y = 64; /* top+bottom inner padding reserve (px) */
    var MIN_PAGE_H = 420;
    var RESIZE_DEBOUNCE = 200;
    /* Scroll gap below the sticky site header (measured in updateTocOffset). */
    var STICKY_GAP = 160;

    function assignPages(items, pageH) {
        // items: [{h:number, heading:boolean, anchor:boolean}]
        // returns array of pages, each a list of item indexes.
        // A chapter anchor always starts a fresh page (unless the page is
        // still empty), so jumping to a chapter shows the page that starts
        // with it — never the tail of the previous text.
        var pages = [[]];
        var curH = 0;
        for (var i = 0; i < items.length; i++) {
            var it = items[i];
            var h = it.h || 0;
            if (it.anchor && pages[pages.length - 1].length > 0) {
                pages.push([]);
                curH = 0;
            }
            if (pages[pages.length - 1].length > 0 && curH + h > pageH) {
                pages.push([]);
                curH = 0;
            }
            // Avoid leaving a heading alone at a page bottom.
            if (it.heading && pages[pages.length - 1].length > 0 &&
                    curH + h > pageH * 0.92) {
                pages.push([]);
                curH = 0;
            }
            pages[pages.length - 1].push(i);
            curH += h;
        }
        return pages.filter(function (pg) { return pg.length > 0; });
    }

    function Pager(article) {
        this.article = article;
        this.nodes = [];
        this.pages = [];
        this.sheets = [];
        this.current = 0;
        this.bar = null; /* single bottom bar (scroll reference) */
        this.bars = [];
        this.prevBtns = [];
        this.nextBtns = [];
        this.countEls = [];
        this.barHandlers = [];
        this.mini = null; /* tiny top button (scroll mode only) */
        this.miniHandler = null;
        this.mode = 'pages';
        this.resizeTimer = null;
        this.onResize = null;
        this.onKey = null;
        this.onNoteJump = null;
    }

    Pager.prototype.measure = function () {
        this.nodes = Array.prototype.slice.call(this.article.children);
        return this.nodes.map(function (el) {
            var tag = el.tagName;
            return {
                el: el,
                h: el.getBoundingClientRect().height,
                heading: tag === 'H1' || tag === 'H2' || tag === 'H3' || tag === 'H4',
                anchor: !!(el.classList && el.classList.contains('doc-chapter-anchor'))
            };
        });
    };

    Pager.prototype.pageHeight = function () {
        var w = this.article.clientWidth;
        if (!w) return 0;
        return Math.max(MIN_PAGE_H, Math.round(w * A4_RATIO) - SHEET_PAD_Y);
    };

    Pager.prototype.build = function () {
        this.restoreNodes();
        var items = this.measure();
        var pageH = this.pageHeight();
        if (!items.length || !pageH) return false;
        var plan = assignPages(items, pageH);
        var doc = this.article.ownerDocument;
        var self = this;

        this.removeBars();
        this.article.classList.add('paged');
        this.sheets = plan.map(function (idxs, pi) {
            var sheet = doc.createElement('div');
            sheet.className = 'doc-page';
            sheet.style.minHeight = pageH + 'px';
            sheet.setAttribute('data-page', String(pi + 1));
            idxs.forEach(function (i) { sheet.appendChild(items[i].el); });
            self.article.appendChild(sheet);
            return sheet;
        });
        this.pages = plan;
        this.buildBars();
        this.show(0, true);
        return true;
    };

    Pager.prototype.topAnchor = function () {
        // Narrow centered row above the article (mini button only).
        var layout = this.article.closest
            ? this.article.closest('.document-layout') : null;
        if (layout && layout.parentNode) {
            return { parent: layout.parentNode, before: layout };
        }
        return { parent: this.article.parentNode, before: this.article };
    };

    Pager.prototype.bottomAnchor = function () {
        // Full-width row directly under the article: right after it inside
        // the (now single-column) layout, so the related dropdown follows.
        var parent = this.article.parentNode;
        if (parent) {
            return { parent: parent, before: this.article.nextSibling };
        }
        return { parent: this.article.parentNode, before: null };
    };

    Pager.prototype.makeBar = function () {
        var doc = this.article.ownerDocument;
        var bar = doc.createElement('div');
        bar.className = 'pager-bar' + (this.mode === 'scroll' ? ' scroll-mode' : '');
        bar.setAttribute('role', 'navigation');
        bar.setAttribute('aria-label', 'التنقل بين الصفحات');

        var prev = doc.createElement('button');
        prev.type = 'button';
        prev.className = 'btn btn-print pager-btn';
        prev.setAttribute('data-pager', 'prev');
        prev.setAttribute('aria-label', 'الصفحة السابقة');
        prev.innerHTML = '<span aria-hidden="true">&#8594;</span><span class="btn-text">السابق</span>';

        var count = doc.createElement('span');
        count.className = 'pager-count';
        count.setAttribute('aria-live', 'polite');

        var view = doc.createElement('button');
        view.type = 'button';
        view.className = 'btn btn-print pager-btn pager-view';
        view.setAttribute('data-pager', 'view');
        view.innerHTML = '<span class="btn-text">' +
            (this.mode === 'scroll' ? 'عرض الصفحات' : 'عرض متصل') + '</span>';

        var next = doc.createElement('button');
        next.type = 'button';
        next.className = 'btn btn-print pager-btn';
        next.setAttribute('data-pager', 'next');
        next.setAttribute('aria-label', 'الصفحة التالية');
        next.innerHTML = '<span class="btn-text">التالي</span><span aria-hidden="true">&#8592;</span>';

        var edgeR = doc.createElement('span');
        edgeR.className = 'pager-edge pager-edge-r';
        edgeR.appendChild(prev);
        var center = doc.createElement('span');
        center.className = 'pager-center';
        center.appendChild(view);
        center.appendChild(count);
        var edgeL = doc.createElement('span');
        edgeL.className = 'pager-edge pager-edge-l';
        edgeL.appendChild(next);
        bar.appendChild(edgeR);
        bar.appendChild(center);
        bar.appendChild(edgeL);

        var self = this;
        var handler = function (e) {
            var btn = e.target && e.target.closest
                ? e.target.closest('[data-pager]') : null;
            if (!btn || !bar.contains(btn)) return;
            var action = btn.getAttribute('data-pager');
            if (action === 'prev') self.show(self.current - 1);
            else if (action === 'next') self.show(self.current + 1);
            else if (action === 'view') {
                self.setMode(self.mode === 'scroll' ? 'pages' : 'scroll');
            }
        };
        bar.addEventListener('click', handler);

        this.bars.push(bar);
        this.prevBtns.push(prev);
        this.nextBtns.push(next);
        this.countEls.push(count);
        this.barHandlers.push({ bar: bar, handler: handler });
        return bar;
    };

    Pager.prototype.makeMini = function () {
        // Tiny "back to pages" button above the article (scroll mode only).
        var doc = this.article.ownerDocument;
        var wrap = doc.createElement('div');
        wrap.className = 'pager-mini-wrap';
        var btn = doc.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-print pager-mini';
        btn.setAttribute('data-pager', 'view');
        btn.setAttribute('aria-label', 'العودة إلى عرض الصفحات');
        btn.innerHTML = '<span class="btn-text">عرض الصفحات</span>';
        wrap.appendChild(btn);
        var self = this;
        var handler = function (e) {
            e.preventDefault();
            self.setMode('pages');
        };
        btn.addEventListener('click', handler);
        this.mini = wrap;
        this.miniHandler = { btn: btn, handler: handler };
        return wrap;
    };

    Pager.prototype.buildBars = function () {
        // Single bottom bar below the article (no top bar above the text).
        var bottom = this.bottomAnchor();
        bottom.parent.insertBefore(this.makeBar(), bottom.before);
        this.bar = this.bars[0];
        // Scroll mode only: tiny button above the article to go back.
        if (this.mode === 'scroll') {
            var top = this.topAnchor();
            top.parent.insertBefore(this.makeMini(), top.before);
        }
    };

    Pager.prototype.show = function (n, silent) {
        if (!this.sheets.length) return;
        if (n < 0) n = 0;
        if (n > this.sheets.length - 1) n = this.sheets.length - 1;
        this.current = n;
        for (var i = 0; i < this.sheets.length; i++) {
            this.sheets[i].hidden = (i !== n);
        }
        var label = (n + 1) + ' / ' + this.sheets.length;
        var full = 'صفحة ' + (n + 1) + ' من ' + this.sheets.length;
        this.countEls.forEach(function (el) {
            el.textContent = label;
            el.setAttribute('aria-label', full);
        });
        var first = (n === 0);
        var last = (n === this.sheets.length - 1);
        this.prevBtns.forEach(function (btn) { btn.disabled = first; });
        this.nextBtns.forEach(function (btn) { btn.disabled = last; });
        if (!silent) {
            // Single bottom bar lives below the article: scroll back to the
            // article top (not to the bar) on page change, leaving room for
            // the sticky site header so no text hides behind it.
            var top = 0;
            try {
                var r = this.article.getBoundingClientRect();
                top = r.top + (window.scrollY || window.pageYOffset || 0);
            } catch (e) { top = 0; }
            try {
                window.scrollTo(0, Math.max(0, top - STICKY_GAP));
            } catch (e) { /* ignore */ }
        }
    };

    Pager.prototype.pageOf = function (el) {
        for (var i = 0; i < this.sheets.length; i++) {
            if (this.sheets[i].contains(el)) return i;
        }
        return -1;
    };

    Pager.prototype.jumpToId = function (id) {
        var doc = this.article.ownerDocument;
        var target = doc.getElementById(id);
        if (!target) return false;
        var pi = this.pageOf(target);
        if (pi >= 0 && pi !== this.current) this.show(pi, true);
        try {
            target.scrollIntoView({ block: 'start' });
        } catch (e) {
            target.scrollIntoView();
        }
        if (window.location.hash !== '#' + id) {
            window.location.hash = id;
        }
        return true;
    };

    Pager.prototype.removeBars = function () {
        this.barHandlers.forEach(function (entry) {
            if (entry.bar && entry.bar.parentNode) {
                entry.bar.removeEventListener('click', entry.handler);
                entry.bar.parentNode.removeChild(entry.bar);
            }
        });
        this.bars = [];
        this.prevBtns = [];
        this.nextBtns = [];
        this.countEls = [];
        this.barHandlers = [];
        this.bar = null;
        if (this.miniHandler) {
            try {
                this.miniHandler.btn.removeEventListener('click', this.miniHandler.handler);
            } catch (e) { /* ignore */ }
            this.miniHandler = null;
        }
        if (this.mini && this.mini.parentNode) {
            this.mini.parentNode.removeChild(this.mini);
        }
        this.mini = null;
    };

    Pager.prototype.restoreNodes = function () {
        if (!this.nodes.length && !this.sheets.length) return;
        var frag = this.article.ownerDocument.createDocumentFragment();
        this.nodes.forEach(function (el) {
            frag.appendChild(el);
        });
        var self = this;
        this.sheets.forEach(function (sheet) {
            if (sheet.parentNode) sheet.parentNode.removeChild(sheet);
        });
        this.article.appendChild(frag);
        this.article.classList.remove('paged');
        this.sheets = [];
        this.pages = [];
        this.current = 0;
    };

    Pager.prototype.setMode = function (mode) {
        if (mode === this.mode) return;
        if (mode === 'scroll') {
            this.restoreNodes();
            this.removeBars();
            this.mode = 'scroll';
            this.buildBars();
        } else {
            this.mode = 'pages';
            this.build();
        }
        try {
            window.localStorage.setItem('docPagerMode', this.mode);
        } catch (e) { /* ignore */ }
    };

    Pager.prototype.bindGlobal = function () {
        var self = this;
        this.onKey = function (e) {
            if (self.mode !== 'pages') return;
            var tag = (e.target && e.target.tagName) || '';
            if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
            if (e.key === 'ArrowLeft') { e.preventDefault(); self.show(self.current + 1); }
            else if (e.key === 'ArrowRight') { e.preventDefault(); self.show(self.current - 1); }
        };
        document.addEventListener('keydown', this.onKey);
        // Footnote / backlink jumps across pages (same-document anchors).
        this.onNoteJump = function (e) {
            if (self.mode !== 'pages') return;
            var a = e.target && e.target.closest ? e.target.closest('a[href^="#"]') : null;
            if (!a || !self.article.contains(a)) return;
            var id = a.getAttribute('href').slice(1);
            if (!id) return;
            var target = document.getElementById(id);
            if (target && self.pageOf(target) >= 0) {
                e.preventDefault();
                self.jumpToId(id);
            }
        };
        this.article.addEventListener('click', this.onNoteJump);
        // Chapter-index jumps across pages (TOC lives beside the article).
        // Works in both modes: flips to the target page, or plain-scrolls.
        this.onTocJump = function (e) {
            var a = e.target && e.target.closest
                ? e.target.closest('.doc-toc a[href^="#"]') : null;
            if (!a) return;
            var id = a.getAttribute('href').slice(1);
            if (!id) return;
            var target = document.getElementById(id);
            if (target && self.article.contains(target)) {
                e.preventDefault();
                self.jumpToId(id);
            }
        };
        document.addEventListener('click', this.onTocJump);
    };

    Pager.prototype.watchResize = function () {
        var self = this;
        this.onResize = function () {
            updateTocOffset();
            if (self.mode !== 'pages') return;
            clearTimeout(self.resizeTimer);
            self.resizeTimer = setTimeout(function () { self.build(); }, RESIZE_DEBOUNCE);
        };
        window.addEventListener('resize', this.onResize);
    };

    // Keep the sticky chapter index (and anchor jumps) clear of the tall
    // sticky site header: measure it and expose CSS vars. No-JS fallback
    // lives in css/document.css.
    function updateTocOffset() {
        try {
            var h = document.querySelector('.site-header');
            var hh = h ? h.getBoundingClientRect().height : 0;
            var top = Math.ceil(hh) + 12;
            STICKY_GAP = top + 16;
            var root = document.documentElement;
            if (root && root.style && root.style.setProperty) {
                root.style.setProperty('--toc-top', top + 'px');
                root.style.setProperty('--jump-top', STICKY_GAP + 'px');
            }
        } catch (e) { /* ignore */ }
    }

    function init() {
        var article = document.querySelector('.document-layout > .document-content');
        if (!article || !article.children.length) return;
        updateTocOffset();
        // Chapter index starts collapsed on small screens (progressive
        // enhancement; without JS it stays open).
        try {
            var tocBox = document.querySelector('.doc-toc-box');
            if (tocBox && window.matchMedia &&
                    window.matchMedia('(max-width: 900px)').matches) {
                tocBox.removeAttribute('open');
            }
        } catch (e) { /* ignore */ }
        var saved = null;
        try {
            saved = window.localStorage.getItem('docPagerMode');
        } catch (e) { /* ignore */ }
        var pager = new Pager(article);
        pager.bindGlobal();
        pager.watchResize();
        if (saved === 'scroll') {
            pager.setMode('scroll');
        } else if (!pager.build()) {
            return;
        }
        if (document.fonts && document.fonts.ready) {
            document.fonts.ready.then(function () {
                if (pager.mode === 'pages') pager.build();
            });
        }
        window.addEventListener('load', function () {
            if (pager.mode === 'pages') pager.build();
        });
    }

    if (typeof document !== 'undefined') {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
        } else {
            init();
        }
    }

    // Export pure planner for testing (harmless in browsers).
    try {
        if (typeof module !== 'undefined' && module.exports) {
            module.exports = { assignPages: assignPages, Pager: Pager };
        }
    } catch (e) { /* ignore */ }
    try {
        if (typeof window !== 'undefined') {
            window.__pagerAssign = assignPages;
        }
    } catch (e) { /* ignore */ }
})();
