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
   REDESIGN extras (index-new) — every block is guarded, so the
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
        var p2 = document.createElement('p');
        p2.textContent = 'تتمتع هذه الترجمة بأسلوب شروحي يربط نصوص العهدين معاً لإيصال المقاصد الإلهية للقارئ والباحث.';
        modalBody.appendChild(p2);
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
