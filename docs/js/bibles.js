/**
 * Bible book & chapter navigator enhancements (bibles.html).
 * Progressive enhancement only: the page is fully usable without JS
 * (details elements toggle natively, anchors navigate to sections).
 * Adds: hash -> panel opening, book search, testament tabs.
 */
(function () {
    'use strict';

    var panels = Array.prototype.slice.call(document.querySelectorAll('.book-panel'));
    var cards = Array.prototype.slice.call(document.querySelectorAll('.bible-book'));
    if (!panels.length && !cards.length) {
        return;
    }

    var filterInput = document.getElementById('bibleFilter');
    var emptyMsg = document.getElementById('bibleEmpty');
    var tabs = Array.prototype.slice.call(
        document.querySelectorAll('.bibles-tabs .filter-btn')
    );
    var state = { testament: 'all', query: '' };

    function openHashTarget(moveFocus) {
        var hash = window.location.hash || '';
        if (hash.length < 2 || hash.indexOf('#book-') !== 0) {
            return;
        }
        var id = decodeURIComponent(hash.slice(1));
        var target = document.getElementById(id);
        if (!target) {
            // #book-x-ch-99 with no such chapter -> fall back to the book panel
            id = id.replace(/-ch-\d+$/, '');
            target = document.getElementById(id);
        }
        if (!target) {
            return;
        }
        var panel = target.classList.contains('book-panel')
            ? target
            : (target.closest ? target.closest('.book-panel') : null);
        if (panel && !panel.open) {
            panel.open = true;
        }
        if (target !== panel && target.scrollIntoView) {
            target.scrollIntoView({ block: 'start' });
        }
        if (moveFocus && panel) {
            var summary = panel.querySelector('summary');
            if (summary && summary.focus) {
                summary.focus({ preventScroll: true });
            }
        }
    }

    function applyFilters() {
        var query = state.query;
        var testament = state.testament;
        var visibleCards = 0;
        var visiblePanels = 0;

        cards.forEach(function (card) {
            var okT = testament === 'all' ||
                card.getAttribute('data-testament') === testament;
            var name = (card.getAttribute('data-name') || '').toLowerCase();
            var okQ = !query || name.indexOf(query) !== -1;
            var show = okT && okQ;
            card.hidden = !show;
            if (show) {
                visibleCards += 1;
            }
        });

        panels.forEach(function (panel) {
            var okT = testament === 'all' ||
                panel.getAttribute('data-testament') === testament;
            var summary = panel.querySelector('summary');
            var name = (summary ? summary.textContent : '').toLowerCase();
            var okQ = !query || name.indexOf(query) !== -1;
            var show = okT && okQ;
            panel.hidden = !show;
            if (show) {
                visiblePanels += 1;
            }
        });

        Array.prototype.forEach.call(
            document.querySelectorAll('.bible-books-section'),
            function (section) {
                section.hidden = !section.querySelector('.bible-book:not([hidden])');
            }
        );

        var panelsSection = document.querySelector('.bible-panels-section');
        if (panelsSection) {
            panelsSection.hidden = visiblePanels === 0;
        }
        if (emptyMsg) {
            emptyMsg.hidden = visibleCards === 0 && visiblePanels === 0;
        }
    }

    if (filterInput) {
        filterInput.addEventListener('input', function () {
            state.query = filterInput.value.trim().toLowerCase();
            applyFilters();
        });
    }

    tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
            state.testament = tab.getAttribute('data-filter') || 'all';
            tabs.forEach(function (other) {
                var active = other === tab;
                other.classList.toggle('active', active);
                other.setAttribute('aria-pressed', active ? 'true' : 'false');
            });
            applyFilters();
        });
    });

    window.addEventListener('hashchange', function () {
        openHashTarget(true);
    });

    document.addEventListener('DOMContentLoaded', function () {
        openHashTarget(false);
    });
    if (document.readyState !== 'loading') {
        openHashTarget(false);
    }
})();
