(function () {
    var STORAGE_KEY = 'theme';

    function getPreferred() {
        try {
            var stored = localStorage.getItem(STORAGE_KEY);
            if (stored === 'dark' || stored === 'light') return stored;
        } catch (e) {}
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        return 'light';
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch (e) {}
        syncToggle(theme);
    }

    function syncToggle(theme) {
        var btn = document.getElementById('themeToggle');
        if (!btn) return;
        var isDark = theme === 'dark';
        btn.setAttribute('aria-pressed', isDark ? 'true' : 'false');
        btn.setAttribute(
            'aria-label',
            isDark ? 'تبديل إلى الوضع النهاري' : 'تبديل إلى الوضع الليلي'
        );
    }

    if (!document.documentElement.getAttribute('data-theme')) {
        applyTheme(getPreferred());
    }

    function bind() {
        var btn = document.getElementById('themeToggle');
        var current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
        syncToggle(current);
        if (!btn) return;
        btn.addEventListener('click', function () {
            var cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
            applyTheme(cur === 'dark' ? 'light' : 'dark');
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bind);
    } else {
        bind();
    }
})();
