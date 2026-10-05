/**
 * Shared delegated UI handlers (CSP-safe replacements for inline onclick/onsubmit).
 */

/**
 * Toast helper (redesign pages). No-ops when #rxToast is absent.
 */
window.rxShowToast = function (message) {
    var toast = document.getElementById('rxToast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(window.__rxToastTimer);
    window.__rxToastTimer = setTimeout(function () {
        toast.classList.remove('is-visible');
    }, 3500);
};

document.addEventListener('click', function (e) {
    var go = e.target && e.target.closest ? e.target.closest('[data-href]') : null;
    if (go) {
        e.preventDefault();
        window.location.href = go.getAttribute('data-href');
        return;
    }

    var printBtn = e.target && e.target.closest ? e.target.closest('[data-action="print"]') : null;
    if (printBtn) {
        e.preventDefault();
        window.print();
        return;
    }

    var shareBtn = e.target && e.target.closest ? e.target.closest('[data-action="share"]') : null;
    if (shareBtn) {
        e.preventDefault();
        // Resolve + validate the URL: navigator.share() has killed the
        // renderer (RESULT_CODE_KILLED_BAD_MESSAGE) on raw/relative URLs,
        // so never feed it anything but a verified absolute http(s) URL.
        var rawUrl = shareBtn.getAttribute('data-share-url') || window.location.href;
        var pageUrl = null;
        try {
            var resolved = new URL(rawUrl, window.location.href).href;
            if (/^https?:\/\//i.test(resolved)) pageUrl = resolved;
        } catch (err) { pageUrl = null; }
        var docTitle = shareBtn.getAttribute('data-share-title');
        if (!docTitle) {
            var titleEl = document.querySelector('h1.document-title');
            docTitle = titleEl ? titleEl.textContent.replace(/\s+/g, ' ').trim() : document.title;
        }
        docTitle = (docTitle || document.title || '').replace(/\s+/g, ' ').trim();
        var shareText = pageUrl ? (docTitle + '\n' + pageUrl) : docTitle;
        var toast = window.rxShowToast || function () {};
        var done = function (ok) {
            // Button label restore works for every label variant
            // (.btn-text classic, .r-label ruler, .rx-meta-label cards).
            var label = shareBtn.querySelector('.btn-text, .r-label, .rx-meta-label');
            if (label) {
                if (!label.getAttribute('data-orig')) {
                    label.setAttribute('data-orig', label.textContent);
                }
                label.textContent = ok ? 'تم النسخ ✓' : 'تعذر النسخ';
                clearTimeout(window.__shareTimer);
                window.__shareTimer = setTimeout(function () {
                    label.textContent = label.getAttribute('data-orig');
                }, 2000);
            }
            toast(ok ? 'تم نسخ الرابط ✓' : 'تعذر النسخ — انسخ الرابط يدويًا');
        };
        var legacyCopy = function () {
            try {
                var ta = document.createElement('textarea');
                ta.value = shareText;
                ta.setAttribute('readonly', '');
                ta.style.position = 'fixed';
                ta.style.opacity = '0';
                document.body.appendChild(ta);
                ta.select();
                var ok = false;
                try { ok = document.execCommand('copy'); } catch (err) { ok = false; }
                document.body.removeChild(ta);
                done(ok);
            } catch (err) { done(false); }
        };
        var copied = false;
        var fallbacksDone = function () {
            if (!copied) done(false);
        };
        if (navigator.share) {
            // Share sheet first; ANY failure (sync throw, async reject,
            // invalid payload) cascades to clipboard copy — never silent.
            var payload = { title: document.title, text: docTitle };
            if (pageUrl) payload.url = pageUrl;
            try {
                var p = navigator.share(payload);
                if (p && p.then) {
                    p.then(function () {
                        copied = true;
                        done(true);
                    }, function (err) {
                        // User-cancelled sheet (AbortError) is intentional:
                        // do nothing instead of surprising them with a copy.
                        if (err && err.name === 'AbortError') return;
                        copyViaClipboard();
                    });
                } else {
                    copied = true;
                    done(true);
                }
            } catch (err) {
                copyViaClipboard();
            }
        } else {
            copyViaClipboard();
        }
        var copyTimer = null;
        function copyViaClipboard() {
            if (copied) return;
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(shareText).then(function () {
                    copied = true;
                    done(true);
                }, function () {
                    legacyCopy();
                });
            } else {
                legacyCopy();
            }
            // Safety net: clipboard promises that never settle.
            clearTimeout(copyTimer);
            copyTimer = setTimeout(fallbacksDone, 4000);
        }
        return;
    }

    var copyBtn = e.target && e.target.closest ? e.target.closest('[data-action="copy-text"]') : null;
    if (copyBtn) {
        e.preventDefault();
        var art = document.querySelector('.document-layout > .document-content, article.document-content');
        var text = art ? (art.innerText || art.textContent || '') : '';
        text = text.replace(/\s+\n/g, '\n').trim();
        var mark = function (ok) {
            var prev = copyBtn.textContent;
            copyBtn.textContent = ok ? '✓ تم النسخ' : 'تعذر النسخ';
            clearTimeout(window.__copyTimer);
            window.__copyTimer = setTimeout(function () {
                copyBtn.textContent = prev;
            }, 2000);
        };
        if (!text) {
            mark(false);
            return;
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function () {
                mark(true);
            }, function () {
                mark(false);
            });
        } else {
            mark(false);
        }
        return;
    }

    var newsBtn = e.target && e.target.closest ? e.target.closest('[data-action="newsletter-focus"]') : null;
    if (newsBtn) {
        e.preventDefault();
        var form = document.getElementById('newsletterForm');
        if (form) {
            form.scrollIntoView({ behavior: 'smooth', block: 'center' });
            var input = form.querySelector('input[type=email]');
            if (input) input.focus();
        }
        return;
    }

    var header = e.target && e.target.closest ? e.target.closest('.category-header') : null;
    if (header) {
        var section = header.closest('.category-section');
        if (section) section.classList.toggle('open');
    }
});

(function () {
    // Card "PDF" buttons link to <article>?print=1 : open print-ready so the
    // user can Save-as-PDF. Waits for full render (pager + fonts).
    var params = null;
    try {
        params = new URLSearchParams(window.location.search || '');
    } catch (e) {
        return;
    }
    if (!params || params.get('print') !== '1') return;
    var fired = false;
    var fire = function () {
        if (fired) return;
        fired = true;
        try {
            window.print();
        } catch (e) { /* ignore */ }
    };
    // Print only after full render AND embedded fonts: early printing
    // is what produced blurry fallback-glyph PDFs.
    var ready = function () {
        setTimeout(fire, 400);
    };
    var onLoad = function () {
        try {
            if (document.fonts && document.fonts.ready) {
                document.fonts.ready.then(ready, ready);
            } else {
                ready();
            }
        } catch (e) {
            ready();
        }
    };
    window.addEventListener('load', onLoad);
    setTimeout(fire, 8000);
})();

document.addEventListener('submit', function (e) {
    if (e.target && e.target.id === 'newsletterForm') {
        e.preventDefault();
        // Toast + reset only exist on the redesign page (originals untouched)
        if (document.getElementById('rxToast')) {
            e.target.reset();
            window.rxShowToast('شكراً لاشتراكك في النشرة البريدية بنجاح!');
        }
    }
});

/* ============================================================
   REDESIGN extras (homepage) — every block is guarded, so the
   original pages are completely unaffected.
   ============================================================ */

(function () {
    // --- Preview modal ---
    var modal = document.getElementById('rxModal');
    if (!modal) return;

    var modalTitle = document.getElementById('rxModalTitle');
    var modalAuthor = document.getElementById('rxModalAuthor');
    var modalBody = document.getElementById('rxModalBody');
    var modalOpen = document.getElementById('rxModalOpen');
    var lastOpener = null;

    function openModal(btn) {
        modalTitle.textContent = btn.getAttribute('data-rx-title') || '';
        modalAuthor.textContent = btn.getAttribute('data-rx-author') || '';
        modalBody.innerHTML = '';
        var desc = (btn.getAttribute('data-rx-desc') || '').trim();
        var p = document.createElement('p');
        p.textContent = desc || 'افتح المقال لقراءة النص الكامل من المكتبة.';
        modalBody.appendChild(p);
        modalOpen.setAttribute('href', safePath(btn.getAttribute('data-rx-path') || '#'));
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
        lastOpener = btn;
        var closeBtn = modal.querySelector('.rx-modal-close');
        if (closeBtn) closeBtn.focus();
    }

    function closeModal() {
        modal.classList.remove('is-open');
        modal.setAttribute('aria-hidden', 'true');
        if (lastOpener && document.contains(lastOpener)) {
            lastOpener.focus();
        }
        lastOpener = null;
    }

    document.addEventListener('click', function (e) {
        if (!e.target || !e.target.closest) return;
        var opener = e.target.closest('[data-rx-preview]');
        if (opener) {
            e.preventDefault();
            openModal(opener);
            return;
        }
        if (e.target.closest('[data-rx-close]') || e.target === modal) {
            closeModal();
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modal.classList.contains('is-open')) {
            closeModal();
        }
    });
})();

(function () {
    // --- Mobile search dropdown toggle (redesign header) ---
    var searchToggle = document.getElementById('searchToggle');
    var searchWrap = document.querySelector('[data-rx-search]');
    if (!searchToggle || !searchWrap) return;

    searchToggle.addEventListener('click', function () {
        var isOpen = searchWrap.classList.toggle('mobile-open');
        searchToggle.classList.toggle('open', isOpen);
        searchToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        if (isOpen) {
            var input = searchWrap.querySelector('input');
            if (input) input.focus();
        }
    });
})();

document.addEventListener('DOMContentLoaded', function () {
    // --- Deep link: #book-<slug> (quick-lookup, mega tiles, legacy links) ---
    if (!document.querySelector('.translations-page')) return;
    var match = /^#book-(.+)$/.exec(window.location.hash || '');
    if (!match) return;

    var slug = decodeURIComponent(match[1]);
    var selector = '.book-item[data-book="' + slug + '"]';
    var tries = 0;

    function redirectToCategory() {
        var data = window.__CATEGORIES_DATA__;
        var cats = (data && data.categories) ? data.categories : data;
        if (!cats) return;
        var pages = {
            old_testament: 'translations-ot.html',
            new_testament: 'translations-nt.html',
            topics: 'translations-subjects.html'
        };
        for (var group in pages) {
            var books = (cats[group] && cats[group].books) || [];
            for (var i = 0; i < books.length; i++) {
                if (books[i].slug === slug) {
                    window.location.replace(
                        pages[group] + '#book-' + encodeURIComponent(slug));
                    return;
                }
            }
        }
    }

    function findItem() {
        var item = null;
        try {
            item = document.querySelector(selector);
        } catch (err) {
            item = null;
        }
        if (item) {
            setTimeout(function () {
                item.scrollIntoView({ behavior: 'smooth', block: 'center' });
                if (typeof window.toggleBook === 'function') {
                    window.toggleBook(slug);
                }
            }, 150);
            return;
        }
        // Book lists are JS-injected - retry briefly before giving up
        if (++tries < 20) {
            setTimeout(findItem, 50);
            return;
        }
        // Landing page: legacy translations.html#book-<slug> -> category page
        if (document.querySelector('.translations-cards')) {
            redirectToCategory();
        }
    }

    findItem();
});

// (Floating back-to-top button removed: the ruler Stage-A الأعلى button covers it.)

