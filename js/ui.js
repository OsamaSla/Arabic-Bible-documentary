/**
 * Shared delegated UI handlers (CSP-safe replacements for inline onclick/onsubmit).
 */

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
    }
});
