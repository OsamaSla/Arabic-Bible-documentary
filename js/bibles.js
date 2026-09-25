/**
 * Bible book & chapter navigator enhancements (bibles.html).
 * Progressive enhancement only: the page is fully usable without JS
 * (details elements toggle natively, anchors navigate to sections).
 * Adds: hash -> panel opening, book search, testament tabs,
 * and Van Dyck Bible chapter text next to the commentaries
 * (fetched on demand from bible/<slug>.json, same-origin).
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

    /* ---- Van Dyck chapter text (bible/<slug>.json, fetched on demand) ---- */

    var bibleCache = {};

    function parseChapterHash() {
        var m = (window.location.hash || '').match(/^#book-(.+)-ch-(\d+)$/);
        if (!m) {
            return null;
        }
        return { slug: m[1], chapter: parseInt(m[2], 10) };
    }

    function loadBookText(slug) {
        if (!bibleCache[slug]) {
            bibleCache[slug] = fetch('bible/' + slug + '.json')
                .then(function (res) {
                    if (!res.ok) {
                        throw new Error('HTTP ' + res.status);
                    }
                    return res.json();
                })
                .catch(function (err) {
                    delete bibleCache[slug];
                    throw err;
                });
        }
        return bibleCache[slug];
    }

    function ensureReader(block, chapter) {
        var reader = block.querySelector('.chapter-reader');
        if (!reader) {
            reader = document.createElement('div');
            reader.className = 'chapter-reader';
            var title = block.querySelector('.chapter-title');
            if (title && title.nextSibling) {
                block.insertBefore(reader, title.nextSibling);
            } else {
                block.appendChild(reader);
            }
        }
        reader.hidden = false;
        reader.setAttribute('data-ch', String(chapter));
        return reader;
    }

    function createChapterBlock(panel, slug, chapter) {
        var id = 'book-' + slug + '-ch-' + chapter;
        var block = document.getElementById(id);
        if (block) {
            return block;
        }
        var body = panel.querySelector('.bp-body');
        if (!body) {
            return null;
        }
        block = document.createElement('section');
        block.className = 'chapter-block';
        block.id = id;
        var h3 = document.createElement('h3');
        h3.className = 'chapter-title';
        h3.textContent = 'الإصحاح ' + chapter;
        block.appendChild(h3);

        // Keep numeric chapter order; the "loose" section stays last.
        var before = null;
        var children = Array.prototype.slice.call(body.children);
        for (var i = 0; i < children.length; i++) {
            var el = children[i];
            if (!el.classList.contains('chapter-block')) {
                continue;
            }
            if (el.classList.contains('loose')) {
                before = el;
                break;
            }
            var m = el.id.match(/-ch-(\d+)$/);
            if (m && parseInt(m[1], 10) > chapter) {
                before = el;
                break;
            }
        }
        if (before) {
            body.insertBefore(block, before);
        } else {
            var empty = body.querySelector('.bp-empty');
            if (empty) {
                body.insertBefore(block, empty);
            } else {
                body.appendChild(block);
            }
        }
        return block;
    }

    function setReaderLoading(reader, chapter) {
        reader.className = 'chapter-reader is-loading';
        reader.setAttribute('data-state', 'loading');
        reader.setAttribute('data-ch', String(chapter));
        reader.innerHTML = '<p class="cr-status" role="status">'
            + 'جارٍ تحميل نص الكتاب المقدس…</p>';
    }

    function setReaderError(reader, chapter) {
        reader.className = 'chapter-reader is-error';
        reader.setAttribute('data-state', 'error');
        reader.setAttribute('data-ch', String(chapter));
        reader.innerHTML = '<p class="cr-status" role="alert">'
            + 'تعذّر تحميل نص الكتاب المقدس.</p>';
    }

    function renderReader(reader, slug, chapter, data) {
        var total = data.chapters || 0;
        var verses = (data.verses && data.verses[String(chapter)]) || [];
        var html = '<div class="cr-head">'
            + '<span class="cr-label">نص الكتاب المقدس — فان دايك</span>'
            + '</div>'
            + '<div class="cr-verses">';
        for (var i = 0; i < verses.length; i++) {
            html += '<p class="cr-verse"><span class="cr-n">' + (i + 1)
                + '</span>' + escapeHtml(verses[i]) + '</p>';
        }
        html += '</div>';
        if (chapter > 1 || chapter < total) {
            html += '<nav class="cr-nav" aria-label="تنقل بين الإصحاحات">';
            if (chapter > 1) {
                html += '<a class="cr-prev" href="#book-' + slug + '-ch-'
                    + (chapter - 1) + '">&#8594; الإصحاح السابق</a>';
            } else {
                html += '<span aria-hidden="true"></span>';
            }
            if (chapter < total) {
                html += '<a class="cr-next" href="#book-' + slug + '-ch-'
                    + (chapter + 1) + '">الإصحاح التالي &#8592;</a>';
            } else {
                html += '<span aria-hidden="true"></span>';
            }
            html += '</nav>';
        }
        reader.className = 'chapter-reader is-ready';
        reader.setAttribute('data-state', 'ok');
        reader.setAttribute('data-ch', String(chapter));
        reader.innerHTML = html;
    }

    function ensureChapterText() {
        var target = parseChapterHash();
        if (!target) {
            return;
        }
        var panel = document.getElementById('book-' + target.slug);
        if (!panel) {
            return;
        }
        var block = document.getElementById(
            'book-' + target.slug + '-ch-' + target.chapter
        );
        var reader = null;
        if (block) {
            reader = block.querySelector('.chapter-reader');
            if (reader && reader.getAttribute('data-state') === 'ok'
                    && reader.getAttribute('data-ch') === String(target.chapter)) {
                return;
            }
            reader = ensureReader(block, target.chapter);
            setReaderLoading(reader, target.chapter);
        }

        loadBookText(target.slug).then(function (data) {
            var key = String(target.chapter);
            if (!data.verses || !data.verses[key]) {
                // Chapter does not exist -> keep the old fallback (book panel).
                if (reader && reader.getAttribute('data-state') === 'loading') {
                    reader.hidden = true;
                    reader.innerHTML = '';
                    reader.removeAttribute('data-state');
                }
                return;
            }
            var created = !block;
            var blk = block || createChapterBlock(panel, target.slug, target.chapter);
            if (!blk) {
                return;
            }
            var rd = ensureReader(blk, target.chapter);
            if (rd.getAttribute('data-state') === 'ok') {
                return;
            }
            renderReader(rd, target.slug, target.chapter, data);
            var cur = parseChapterHash();
            if (created && blk.scrollIntoView && cur
                    && cur.slug === target.slug && cur.chapter === target.chapter) {
                blk.scrollIntoView({ block: 'start' });
            }
        }).catch(function () {
            if (reader && reader.getAttribute('data-state') === 'loading') {
                setReaderError(reader, target.chapter);
            }
        });
    }

    function openHashTarget(moveFocus) {
        var hash = window.location.hash || '';
        if (hash.length < 2 || hash.indexOf('#book-') !== 0) {
            return;
        }
        ensureChapterText();
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
