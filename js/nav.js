/* Navigation: mobile drawer (shared by .nav-bar and .rx-nav), mega menus. */
document.addEventListener('DOMContentLoaded', function () {
    var toggle = document.getElementById('navToggle');
    var navBar = document.getElementById('navBar');

    if (toggle && navBar) {
        var MOBILE_QUERY = '(max-width: 768px)';
        var lastFocus = null;

        // Backdrop (created once; only visible while the drawer is open).
        var backdrop = document.createElement('div');
        backdrop.className = 'nav-backdrop';
        backdrop.setAttribute('aria-hidden', 'true');
        document.body.appendChild(backdrop);

        // Drawer header with a thumb-sized close button (mobile only).
        var head = document.createElement('div');
        head.className = 'nav-drawer-head';
        var headTitle = document.createElement('span');
        headTitle.textContent = 'القائمة';
        var headClose = document.createElement('button');
        headClose.type = 'button';
        headClose.className = 'nav-drawer-close';
        headClose.setAttribute('aria-label', 'إغلاق القائمة');
        headClose.innerHTML = '&times;';
        head.appendChild(headTitle);
        head.appendChild(headClose);
        navBar.insertBefore(head, navBar.firstChild);

        function isMobile() {
            return window.matchMedia(MOBILE_QUERY).matches;
        }

        function setExpanded(expanded) {
            toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            if (expanded || !isMobile()) {
                navBar.removeAttribute('aria-hidden');
            } else {
                navBar.setAttribute('aria-hidden', 'true');
            }
        }

        function openDrawer() {
            if (!navBar.classList.contains('open')) {
                lastFocus = document.activeElement;
            }
            navBar.classList.add('open');
            toggle.classList.add('open');
            document.documentElement.classList.add('nav-open');
            backdrop.classList.add('is-visible');
            setExpanded(true);

            var first = navBar.querySelector('a, button');
            if (first) {
                // Wait for the slide-in to start so focus doesn't scroll the page.
                window.setTimeout(function () {
                    try { first.focus({ preventScroll: true }); } catch (e) { first.focus(); }
                }, 30);
            }
        }

        function closeDrawer(restoreFocus) {
            if (!navBar.classList.contains('open')) return;
            navBar.classList.remove('open');
            toggle.classList.remove('open');
            document.documentElement.classList.remove('nav-open');
            backdrop.classList.remove('is-visible');
            setExpanded(false);

            if (restoreFocus !== false) {
                var target = (lastFocus && document.contains(lastFocus)) ? lastFocus : toggle;
                try { target.focus({ preventScroll: true }); } catch (e) { target.focus(); }
            }
            lastFocus = null;
        }

        setExpanded(navBar.classList.contains('open'));

        toggle.addEventListener('click', function () {
            if (navBar.classList.contains('open')) {
                closeDrawer();
            } else {
                openDrawer();
            }
        });

        headClose.addEventListener('click', function () {
            closeDrawer();
        });

        backdrop.addEventListener('click', function () {
            closeDrawer();
        });

        // Any nav link closes the drawer on mobile.
        navBar.addEventListener('click', function (event) {
            var link = event.target.closest ? event.target.closest('a') : null;
            if (link && isMobile()) {
                closeDrawer(false);
            }
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && navBar.classList.contains('open')) {
                closeDrawer();
            }
        });

        window.addEventListener('resize', function () {
            if (!isMobile()) {
                if (navBar.classList.contains('open')) {
                    closeDrawer(false);
                }
                navBar.removeAttribute('aria-hidden');
            }
        });
    }

    // Mobile search toggle (legacy header only — the redesign header is
    // handled in ui.js through [data-rx-search]).
    var searchToggle = document.getElementById('searchToggle');
    var headerSearch = document.querySelector('.header-search');
    if (searchToggle && headerSearch && !document.querySelector('[data-rx-search]')) {
        searchToggle.addEventListener('click', function () {
            var isOpen = headerSearch.classList.toggle('mobile-open');
            this.classList.toggle('open');
            if (isOpen) {
                var input = headerSearch.querySelector('input');
                if (input) input.focus();
            }
        });
    }

    // Mega-menu book grid expand/collapse ([+] / [-])
    document.querySelectorAll('.nav-dropdown-toggle').forEach(function (toggleEl) {
        toggleEl.addEventListener('click', function (e) {
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
    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        var el = document.activeElement;
        if (el && el.closest && el.closest('.has-mega')) {
            el.blur();
        }
    });
});
