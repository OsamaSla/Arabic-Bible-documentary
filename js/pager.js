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

    function isFiller(it) {
        // Anchors, zero-height nodes and empty paragraphs must never own
        // a page alone — they attach to the next real content block.
        // Otherwise page 1 renders as a blank A4 sheet (empty-page bug).
        return !!(it.anchor || it.empty);
    }

    function pageHasContent(pg, items) {
        for (var k = 0; k < pg.length; k++) {
            if (!isFiller(items[pg[k]])) return true;
        }
        return false;
    }

    function assignPages(items, pageH) {
        // items: [{h:number, heading:boolean, anchor:boolean, empty:boolean}]
        // returns array of pages, each a list of item indexes.
        // A chapter anchor starts a fresh page only when the current page
        // already holds real content; leading/consecutive anchors and empty
        // paragraphs are glued to the following content — never alone.
        var pages = [[]];
        var curH = 0;
        var curReal = 0;
        // Don't strand 1-2 short opener lines (e.g. title + author) alone
        // on page 1: while the page is still mostly empty, keep flowing
        // instead of breaking before an oversized block. The sheet simply
        // grows past min-height — far better than a near-blank first page.
        var MIN_FILL = pageH * 0.4;
        for (var i = 0; i < items.length; i++) {
            var it = items[i];
            var h = it.h || 0;
            var filler = isFiller(it);
            var barelyStarted = curReal > 0 && curH < MIN_FILL;
            if (it.anchor && curReal > 0 && !barelyStarted) {
                pages.push([]);
                curH = 0;
                curReal = 0;
            }
            if (!filler && curReal > 0 && curH + h > pageH && !barelyStarted) {
                pages.push([]);
                curH = 0;
                curReal = 0;
            }
            // Avoid leaving a heading alone at a page bottom.
            if (!filler && it.heading && curReal > 0 &&
                    curH + h > pageH * 0.92 && !barelyStarted) {
                pages.push([]);
                curH = 0;
                curReal = 0;
            }
            pages[pages.length - 1].push(i);
            if (!filler) {
                curH += h;
                curReal++;
            }
        }
        // Merge filler-only pages into the next page with content (or the
        // previous one for trailing fillers), so no blank sheet survives.
        var merged = [];
        var carry = [];
        for (var p = 0; p < pages.length; p++) {
            var pg = pages[p];
            if (!pg.length) continue;
            if (!pageHasContent(pg, items)) {
                carry = carry.concat(pg);
                continue;
            }
            merged.push(carry.concat(pg));
            carry = [];
        }
        if (carry.length) {
            if (merged.length) {
                merged[merged.length - 1] = merged[merged.length - 1].concat(carry);
            } else {
                merged.push(carry);
            }
        }
        return merged.filter(function (pg) { return pg.length > 0; });
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
        this.floats = null; /* fixed side-edge arrows (pages mode only) */
        this.floatPrev = null;
        this.floatNext = null;
        this.floatHandler = null;
        this.touchX = null;
        this.touchY = null;
        this.onTouchStart = null;
        this.onTouchEnd = null;
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
            var isAnchor = !!(el.classList && el.classList.contains('doc-chapter-anchor'));
            var h = 0;
            try { h = el.getBoundingClientRect().height; } catch (e) { h = 0; }
            var empty = false;
            if (!isAnchor) {
                var text = '';
                try { text = (el.textContent || '').replace(/ /g, ' ').trim(); } catch (e) { text = ''; }
                var hasMedia = false;
                try {
                    hasMedia = !!(el.querySelector &&
                        el.querySelector('img, table, iframe, video, figure, object, embed'));
                } catch (e) { hasMedia = false; }
                empty = (!text && !hasMedia) || h < 2;
            }
            return {
                el: el,
                h: h,
                heading: tag === 'H1' || tag === 'H2' || tag === 'H3' || tag === 'H4',
                anchor: isAnchor,
                empty: empty
            };
        });
    };

    Pager.prototype.pageHeight = function () {
        var w = this.article.clientWidth;
        if (!w) return 0;
        return Math.max(MIN_PAGE_H, Math.round(w * A4_RATIO) - SHEET_PAD_Y);
    };

    Pager.prototype.build = function () {
        // Remember where the reader was: rebuilds happen on resize/font
        // load, and must never throw the reader back to page 1.
        var keep = this.current || 0;
        this.restoreNodes();
        var items = this.measure();
        var pageH = this.pageHeight();
        if (!items.length || !pageH) return false;
        this.lastW = this.article.clientWidth || 0;
        var plan = assignPages(items, pageH);
        if (!plan.length) return false;
        // If the document has no measurable content (e.g. failed render),
        // stay in plain scroll mode instead of showing a blank sheet.
        var hasReal = plan.some(function (pg) {
            return pg.some(function (i) { return items[i] && !items[i].anchor && !items[i].empty; });
        });
        if (!hasReal) return false;
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
        // Restore the reader's page (clamped — a narrower screen can add
        // pages, a wider one can remove them).
        var at = Math.max(0, Math.min(keep, plan.length - 1));
        this.show(at, true);
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

    Pager.prototype.makeFloats = function () {
        // Fixed side-edge flip arrows for touch screens (CSS shows them
        // only on small viewports; hidden on desktop and in scroll mode).
        // RTL: previous sits at inline-start (right), next at inline-end.
        var doc = this.article.ownerDocument;
        var wrap = doc.createElement('div');
        wrap.className = 'pager-floats';
        wrap.setAttribute('aria-hidden', 'false');

        var prev = doc.createElement('button');
        prev.type = 'button';
        prev.className = 'pager-float pager-float-prev';
        prev.setAttribute('data-pager', 'prev');
        prev.setAttribute('aria-label', 'الصفحة السابقة');
        prev.setAttribute('tabindex', '0');
        prev.innerHTML = '<span aria-hidden="true">&#8594;</span>';

        var next = doc.createElement('button');
        next.type = 'button';
        next.className = 'pager-float pager-float-next';
        next.setAttribute('data-pager', 'next');
        next.setAttribute('aria-label', 'الصفحة التالية');
        next.setAttribute('tabindex', '0');
        next.innerHTML = '<span aria-hidden="true">&#8592;</span>';

        wrap.appendChild(prev);
        wrap.appendChild(next);

        var self = this;
        var handler = function (e) {
            var btn = e.target && e.target.closest
                ? e.target.closest('[data-pager]') : null;
            if (!btn || !wrap.contains(btn)) return;
            e.preventDefault();
            var action = btn.getAttribute('data-pager');
            if (action === 'prev') self.show(self.current - 1);
            else if (action === 'next') self.show(self.current + 1);
        };
        wrap.addEventListener('click', handler);

        this.floats = wrap;
        this.floatPrev = prev;
        this.floatNext = next;
        this.floatHandler = { wrap: wrap, handler: handler };
        return wrap;
    };

    Pager.prototype.buildBars = function () {
        // Single bottom bar below the article (no top bar above the text).
        var bottom = this.bottomAnchor();
        bottom.parent.insertBefore(this.makeBar(), bottom.before);
        this.bar = this.bars[0];
        // Pages mode: fixed side-edge arrows for quick flipping.
        if (this.mode === 'pages') {
            var floats = this.makeFloats();
            try {
                this.article.ownerDocument.body.appendChild(floats);
            } catch (e) { /* ignore */ }
        }
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
        // Keep the floating side arrows in sync; hide them entirely for
        // single-page articles where there is nothing to flip.
        try {
            if (this.floatPrev) this.floatPrev.disabled = first;
            if (this.floatNext) this.floatNext.disabled = last;
            if (this.floats) {
                if (this.sheets.length < 2) this.floats.setAttribute('hidden', '');
                else this.floats.removeAttribute('hidden');
            }
        } catch (e) { /* ignore */ }
        if (!silent) {
            // Single bottom bar lives below the article: scroll back to the
            // article top (not to the bar) on page change, leaving room for
            // the sticky site header so no text hides behind it. The header
            // is much taller on mobile (stacked layout), so measure it live
            // instead of trusting the desktop STICKY_GAP constant.
            var gap = STICKY_GAP;
            try {
                var hdr = document.querySelector('.site-header, .rx-header');
                if (hdr) gap = Math.ceil(hdr.getBoundingClientRect().height) + 16;
            } catch (e) { /* keep default */ }
            var top = 0;
            try {
                var r = this.article.getBoundingClientRect();
                top = r.top + (window.scrollY || window.pageYOffset || 0);
            } catch (e) { top = 0; }
            try {
                window.scrollTo(0, Math.max(0, top - gap));
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
        if (this.floatHandler) {
            try {
                this.floatHandler.wrap.removeEventListener('click', this.floatHandler.handler);
            } catch (e) { /* ignore */ }
            this.floatHandler = null;
        }
        if (this.floats && this.floats.parentNode) {
            this.floats.parentNode.removeChild(this.floats);
        }
        this.floats = null;
        this.floatPrev = null;
        this.floatNext = null;
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
        // Swipe to flip on touch screens (RTL: swipe left = next page,
        // mirroring ArrowLeft; ignored when vertical scroll dominates).
        this.onTouchStart = function (e) {
            if (self.mode !== 'pages') return;
            try {
                var t = e.changedTouches && e.changedTouches[0];
                if (!t) return;
                self.touchX = t.clientX;
                self.touchY = t.clientY;
            } catch (err) { self.touchX = null; }
        };
        this.onTouchEnd = function (e) {
            if (self.mode !== 'pages') return;
            try {
                var t = e.changedTouches && e.changedTouches[0];
                if (!t || self.touchX === null || self.touchX === undefined) return;
                var dx = t.clientX - self.touchX;
                var dy = t.clientY - (self.touchY || 0);
                self.touchX = null;
                self.touchY = null;
                if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
                if (dx < 0) self.show(self.current + 1);
                else self.show(self.current - 1);
            } catch (err) { /* ignore */ }
        };
        try {
            this.article.addEventListener('touchstart', this.onTouchStart, { passive: true });
            this.article.addEventListener('touchend', this.onTouchEnd, { passive: true });
        } catch (err) {
            this.article.addEventListener('touchstart', this.onTouchStart);
            this.article.addEventListener('touchend', this.onTouchEnd);
        }
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
            self.resizeTimer = setTimeout(function () {
                // Mobile browsers fire resize when the URL bar shows/hides
                // while scrolling (width unchanged). Rebuilding then is both
                // wasteful and disruptive — only rebuild on real width change.
                var w = 0;
                try { w = self.article.clientWidth || 0; } catch (e) { w = 0; }
                if (self.lastW && w && Math.abs(w - self.lastW) < 2) return;
                self.build();
            }, RESIZE_DEBOUNCE);
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
