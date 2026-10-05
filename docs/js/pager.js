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

    function pageStoreKey() {
        // Per-article key so a reload (pull-to-refresh, browser refresh,
        // process kill) can restore the reader's page instead of page 1.
        try {
            return 'docPagerPage:' + window.location.pathname;
        } catch (e) {
            return null;
        }
    }

    function readSavedPage() {
        var k = pageStoreKey();
        if (!k) return 0;
        try {
            return parseInt(window.sessionStorage.getItem(k), 10) || 0;
        } catch (e) {
            return 0;
        }
    }

    function savePage(n) {
        var k = pageStoreKey();
        if (!k) return;
        try {
            window.sessionStorage.setItem(k, String(n));
        } catch (e) { /* ignore */ }
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
        // Restore the reader's page (clamped — a narrower screen can add
        // pages, a wider one can remove them).
        var at = Math.max(0, Math.min(keep, plan.length - 1));
        this.show(at, true);
        return true;
    };

    // Navigation UI moved to the study ruler (js/ruler.js).

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
            this.mode = 'scroll';
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
        try {
            window.__docPager = pager;
        } catch (e) { /* ignore */ }
        pager.bindGlobal();
        pager.watchResize();
        if (saved === 'scroll') {
            pager.setMode('scroll');
        } else {
            // Restore the page the reader was on before a reload (browser
            // refresh, pull-to-refresh, process kill — sessionStorage
            // survives all of them within the tab session). build()
            // clamps it to the actual page count.
            var savedPage = readSavedPage();
            if (savedPage > 0) pager.current = savedPage;
            if (!pager.build()) {
                return;
            }
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
