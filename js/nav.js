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

    // Book grid expand/collapse toggles
    var toggles = document.querySelectorAll('.nav-dropdown-toggle');
    toggles.forEach(function(toggleEl) {
        toggleEl.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            var section = this.closest('.nav-dropdown-section');
            var grid = section.querySelector('.nav-book-grid');
            var mark = this.querySelector('.toggle-mark');
            if (grid.classList.contains('expanded')) {
                grid.classList.remove('expanded');
                section.classList.remove('expanded');
                if (mark) mark.textContent = '[+]';
            } else {
                grid.classList.add('expanded');
                section.classList.add('expanded');
                if (mark) mark.textContent = '[-]';
            }
        });
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        var dropdown = document.querySelector('.nav-dropdown');
        if (dropdown && !dropdown.contains(e.target)) {
            var menu = dropdown.querySelector('.nav-dropdown-menu');
            if (menu) menu.classList.remove('show');
        }
    });

    // Dropdown toggle for desktop and mobile
    var navDropdown = document.querySelector('.nav-dropdown');
    if (navDropdown) {
        var navLink = navDropdown.querySelector('.nav-link');
        if (navLink) {
            navLink.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                var menu = this.nextElementSibling;
                if (menu) {
                    var isMobile = window.innerWidth <= 768;
                    if (isMobile) {
                        // On mobile, toggle visibility directly
                        if (menu.classList.contains('show')) {
                            menu.classList.remove('show');
                        } else {
                            // Close other open menus first
                            document.querySelectorAll('.nav-dropdown-menu.show').forEach(function(m) {
                                m.classList.remove('show');
                            });
                            menu.classList.add('show');
                        }
                    } else {
                        // On desktop, toggle visibility
                        menu.classList.toggle('show');
                    }
                }
            });
        }
    }
});
