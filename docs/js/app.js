/**
 * Arabic Christian Translations - Articles, Search & Filters
 */

document.addEventListener('DOMContentLoaded', function() {
    let allDocuments = [];
    
    function loadAllDocuments() {
        if (window.__DOCUMENTS_DATA__) {
            allDocuments = window.__DOCUMENTS_DATA__;
        } else {
            try {
                var xhr = new XMLHttpRequest();
                xhr.open('GET', 'documents/index.json', false);
                xhr.send();
                if (xhr.status === 200) {
                    var data = JSON.parse(xhr.responseText);
                    allDocuments = data.documents || [];
                }
            } catch (e) {}
        }
    }
    
    loadAllDocuments();
    
    // === RANDOM ARTICLES (completed only) ===
    var articlesGrid = document.getElementById('randomArticles');
    if (articlesGrid) {
        var completedDocs = allDocuments.filter(function(doc) {
            return doc.completed === true;
        });
        
        // Fisher-Yates shuffle
        var arr = completedDocs.slice();
        for (var i = arr.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var temp = arr[i];
            arr[i] = arr[j];
            arr[j] = temp;
        }
        // Offset by time for variety
        var offset = Date.now() % arr.length;
        var selected = [];
        for (var k = 0; k < 10 && k < arr.length; k++) {
            selected.push(arr[(offset + k) % arr.length]);
        }
        
        articlesGrid.innerHTML = selected.map(function(doc) {
            var title = escapeHtml(doc.title || '\u0628\u062f\u0648\u0646 \u0639\u0646\u0648\u0627\u0646');
            var author = escapeHtml(doc.author || '\u063a\u064a\u0631 \u0645\u0639\u0631\u0648\u0641');
            var path = escapeHtml(safePath(doc.html_path || '#'));
            var desc = doc.description ? escapeHtml(doc.description.substring(0, 150) + '...') : '';
            return '<a href="' + path + '" class="article-card">' +
                '<div class="article-title">' + title + '</div>' +
                '<div class="article-author">' + author + '</div>' +
                (desc ? '<div class="article-desc">' + desc + '</div>' : '') +
                '</a>';
        }).join('');
    }
    
    // === RECENT UPDATES ===
    var recentList = document.getElementById('recentUpdates');
    if (recentList) {
        var recent = allDocuments.slice(-5).reverse();
        recentList.innerHTML = recent.map(function(doc) {
            var title = escapeHtml(doc.title || '\u0628\u062f\u0648\u0646 \u0639\u0646\u0648\u0627\u0646');
            var path = escapeHtml(safePath(doc.html_path || '#'));
            return '<li><a href="' + path + '" class="update-title">' + title + '</a></li>';
        }).join('');
    }
    
    // === FILTER BUTTONS (authors.html only) ===
    var filterBtns = document.querySelectorAll('.filter-btn');
    var authorCards = document.querySelectorAll('.author-card');
    
    if (filterBtns.length > 0 && authorCards.length > 0) {
        filterBtns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                filterBtns.forEach(function(b) { b.classList.remove('active'); });
                this.classList.add('active');
                
                var filter = this.dataset.filter;
                
                authorCards.forEach(function(card) {
                    var cardStatus = card.dataset.status || '';
                    
                    if (filter === 'all') {
                        card.style.display = '';
                    } else if (filter === 'completed') {
                        card.style.display = cardStatus === 'completed' ? '' : 'none';
                    } else if (filter === 'in-progress') {
                        card.style.display = (cardStatus === 'in-progress' || cardStatus === 'partial') ? '' : 'none';
                    }
                });
            });
        });
    }
});

/* ============================================================
   REDESIGN (index-new) — all blocks guarded by element existence.
   Original pages: every block below no-ops (its hooks don't exist).
   ============================================================ */
document.addEventListener('DOMContentLoaded', function() {
    var toast = window.rxShowToast || function () {};

    // === NEW ARTICLE GRID (rx-card schema) ===
    // data-source="static": cards are server-rendered at build time - keep
    // them (no random swap) so content is stable and crawlable.
    var newGrid = document.getElementById('articlesGrid');
    if (newGrid && window.__DOCUMENTS_DATA__ &&
        newGrid.getAttribute('data-source') !== 'static') {
        var completedDocs = window.__DOCUMENTS_DATA__.filter(function(doc) {
            return doc.completed === true;
        });

        var arr = completedDocs.slice();
        for (var i = arr.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var tmp = arr[i];
            arr[i] = arr[j];
            arr[j] = tmp;
        }
        var offset = arr.length ? (Date.now() % arr.length) : 0;
        var picked = [];
        for (var k = 0; k < 10 && arr.length; k++) {
            picked.push(arr[(offset + k) % arr.length]);
        }

        if (picked.length) {
            newGrid.innerHTML = picked.map(function(doc) {
                var title = escapeHtml(doc.title || '\u0628\u062f\u0648\u0646 \u0639\u0646\u0648\u0627\u0646');
                var author = escapeHtml(doc.author || '\u063a\u064a\u0631 \u0645\u0639\u0631\u0648\u0641');
                var path = escapeHtml(safePath(doc.html_path || '#'));
                var desc = doc.description ? doc.description.substring(0, 150) + '...' : '';
                desc = escapeHtml(desc);
                var done = doc.completed === true;
                var badgeCls = done ? 'rx-badge' : 'rx-badge rx-badge-progress';
                var status = done ? '\u2713 \u0645\u0643\u062a\u0645\u0644' : '\u25cf \u0642\u064a\u062f \u0627\u0644\u062a\u0631\u062c\u0645\u0629';
                return '<article class="rx-card" data-title="' + title + '">' +
                    '<div class="rx-card-top">' +
                    '<span class="' + badgeCls + '">' + status + '</span>' +
                    '<span class="rx-card-status">' + author + '</span>' +
                    '</div>' +
                    '<h3 class="rx-card-title"><a href="' + path + '">' + title + '</a></h3>' +
                    '<p class="rx-card-desc rx-clamp-3">' + desc + '</p>' +
                    '<div class="rx-card-foot">' +
                    '<button type="button" class="rx-preview-btn" data-rx-preview' +
                    ' data-rx-title="' + title + '" data-rx-author="' + author + '"' +
                    ' data-rx-desc="' + desc + '" data-rx-path="' + path + '">' +
                    '\u0645\u0639\u0627\u064a\u0646\u0629 \u0633\u0631\u064a\u0639\u0629</button>' +
                    '<a href="' + path + '" class="rx-read-link">\u0627\u0642\u0631\u0623 \u0645\u0632\u064a\u062f \u2190</a>' +
                    '</div>' +
                    '</article>';
            }).join('');
        }
    }

    // === TITLE FILTER ===
    var rxFilter = document.getElementById('rxFilter');
    if (rxFilter) {
        rxFilter.addEventListener('input', function() {
            var q = (rxFilter.value || '').trim().toLowerCase();
            var cards = document.querySelectorAll('#articlesGrid .rx-card');
            cards.forEach(function(card) {
                var title = (card.getAttribute('data-title') || '').toLowerCase();
                card.style.display = (!q || title.indexOf(q) !== -1) ? '' : 'none';
            });
        });
    }

    // === QUICK LOOKUP (testament + book + chapter) ===
    var lookupForm = document.getElementById('rxLookup');
    var testamentSel = document.getElementById('rxTestament');
    var bookSel = document.getElementById('rxBook');
    var chapterInput = document.getElementById('rxChapter');

    if (lookupForm && testamentSel && bookSel) {
        bookSel.disabled = true;

        var groupMap = {
            nt: 'new_testament',
            ot: 'old_testament',
            topics: 'topics'
        };

        var fillBooks = function(cats) {
            var group = cats && cats[groupMap[testamentSel.value]];
            bookSel.innerHTML = '<option value="">\u2014 \u0627\u062e\u062a\u0631 \u0633\u0641\u0631\u0627\u064b \u2014</option>';
            if (group && group.books) {
                group.books.forEach(function(b) {
                    var opt = document.createElement('option');
                    opt.value = b.slug;
                    opt.textContent = b.name_ar;
                    bookSel.appendChild(opt);
                });
                bookSel.disabled = false;
            } else {
                bookSel.disabled = true;
                toast('\u062a\u0639\u0631\u0631 \u062a\u062d\u0645\u064a\u0644 \u0642\u0627\u0626\u0645\u0629 \u0627\u0644\u0643\u062a\u0628');
            }
        };

        var applyCategories = function(categoriesRoot) {
            var cats = (categoriesRoot && categoriesRoot.categories) ? categoriesRoot.categories : categoriesRoot;
            if (!cats) {
                bookSel.disabled = true;
                toast('\u062a\u0639\u0631\u0631 \u062a\u062d\u0645\u064a\u0644 \u0642\u0627\u0626\u0645\u0629 \u0627\u0644\u0643\u062a\u0628');
                return;
            }
            fillBooks(cats);
            testamentSel.addEventListener('change', function() { fillBooks(cats); });
        };

        if (window.__CATEGORIES_DATA__) {
            applyCategories(window.__CATEGORIES_DATA__);
        } else {
            fetch('categories.json')
                .then(function(r) { return r.ok ? r.json() : null; })
                .then(function(j) { applyCategories(j); })
                .catch(function() { applyCategories(null); });
        }

        lookupForm.addEventListener('submit', function(e) {
            e.preventDefault();
            var slug = bookSel.value;
            if (!slug) {
                toast('\u0627\u062e\u062a\u0631 \u0633\u0641\u0631\u0627\u064b \u0623\u0648\u0644\u0627\u064b');
                bookSel.focus();
                return;
            }
            var chapter = chapterInput ? (chapterInput.value || '').trim() : '';

            if (testamentSel && testamentSel.value === 'topics') {
                // Topics live on the subjects category page
                window.location.href = 'translations-subjects.html#book-' + encodeURIComponent(slug);
                return;
            }
            // Bible books open in the book & chapter navigator (deep-links
            // straight to the chapter when one was chosen)
            var hash = '#book-' + encodeURIComponent(slug);
            if (/^\d{1,3}$/.test(chapter)) {
                hash += '-ch-' + parseInt(chapter, 10);
            }
            window.location.href = 'bibles.html' + hash;
        });
    }
});
