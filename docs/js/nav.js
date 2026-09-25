document.addEventListener('DOMContentLoaded', function() {
    // Mobile nav toggle
    var toggle = document.getElementById('navToggle');
    var navBar = document.getElementById('navBar');
    if (toggle && navBar) {
        toggle.addEventListener('click', function() {
            navBar.classList.toggle('open');
            toggle.classList.toggle('open');
        });
    }

    // Mobile search toggle
    var searchToggle = document.getElementById('searchToggle');
    var headerSearch = document.querySelector('.header-search');
    if (searchToggle && headerSearch) {
        searchToggle.addEventListener('click', function() {
            var isOpen = headerSearch.classList.toggle('mobile-open');
            this.classList.toggle('open');
            if (isOpen) {
                headerSearch.querySelector('input').focus();
            }
        });
    }

    // Close nav when clicking a nav link on mobile
    var navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(function(link) {
        link.addEventListener('click', function() {
            if (window.innerWidth <= 768 && navBar) {
                navBar.classList.remove('open');
                toggle.classList.remove('open');
            }
        });
    });

    // Mega-menu book grid expand/collapse ([+] / [-])
    document.querySelectorAll('.nav-dropdown-toggle').forEach(function(toggleEl) {
        toggleEl.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            var section = this.closest('.nav-dropdown-section');
            if (!section) return;
            var grid = section.querySelector('.nav-book-grid');
            if (!grid) return;
            var mark = this.querySelector('.toggle-mark');
            var expanded = grid.classList.toggle('expanded');
            section.classList.toggle('expanded', expanded);
            this.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            if (mark) mark.textContent = expanded ? '[-]' : '[+]';
        });
    });

    // Escape closes a focus-opened mega menu (hover menus close on mouseleave)
    document.addEventListener('keydown', function(e) {
        if (e.key !== 'Escape') return;
        var el = document.activeElement;
        if (el && el.closest && el.closest('.has-mega')) {
            el.blur();
        }
    });
});
