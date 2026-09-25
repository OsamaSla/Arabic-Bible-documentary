/**
 * Translations Page - Load books from categories.json and match documents
 */

let allDocs = [];
let categories = null;

document.addEventListener('DOMContentLoaded', function() {
    loadAllData();
});

function toggleBook(bookSlug) {
    var docsDiv = document.getElementById('docs-' + bookSlug);
    var bookItem = document.querySelector('[data-book="' + bookSlug + '"]');
    if (docsDiv) {
        var isOpen = docsDiv.style.display === 'block';
        document.querySelectorAll('.book-docs').forEach(d => d.style.display = 'none');
        document.querySelectorAll('.book-item').forEach(b => {
            b.classList.remove('active');
            if (b.hasAttribute('aria-expanded')) b.setAttribute('aria-expanded', 'false');
        });
        if (!isOpen) {
            docsDiv.style.display = 'block';
            if (bookItem) {
                bookItem.classList.add('active');
                bookItem.setAttribute('aria-expanded', 'true');
            }
        }
    }
}

async function loadAllData() {
    // Try inline data first
    if (window.__CATEGORIES_DATA__) {
        categories = window.__CATEGORIES_DATA__;
    }
    if (window.__DOCUMENTS_DATA__) {
        allDocs = window.__DOCUMENTS_DATA__;
    }
    
    // Fallback to fetch
    if (!categories) {
        try {
            const response = await fetch('categories.json');
            if (response.ok) {
                categories = await response.json();
            }
        } catch (e) {}
        if (!categories) {
            try {
                const response = await fetch('../categories.json');
                if (response.ok) {
                    categories = await response.json();
                }
            } catch (e) {}
        }
    }
    
    if (allDocs.length === 0) {
        try {
            const response = await fetch('documents/index.json');
            if (response.ok) {
                const data = await response.json();
                allDocs = data.documents || [];
            }
        } catch (e) {}
        if (allDocs.length === 0) {
            try {
                const response = await fetch('../documents/index.json');
                if (response.ok) {
                    const data = await response.json();
                    allDocs = data.documents || [];
                }
            } catch (e) {}
        }
    }
    
    if (!categories || !categories.categories) {
        return;
    }
    
    const cats = categories.categories;
    
    function getDocsForBook(book) {
        const bookName = book.name_ar.toLowerCase();
        const bookSlug = book.slug.toLowerCase();
        return allDocs.filter(d => {
            // Multi-category: prefer categories[]; fall back to legacy category
            let cats;
            if (Array.isArray(d.categories)) {
                cats = d.categories;
            } else if (d.category && d.category !== 'uncategorized') {
                cats = [d.category];
            } else {
                cats = [];
            }
            if (cats.length) {
                // Membership: show under EVERY assigned category (no exclusivity)
                return cats.some(c => String(c || '').toLowerCase() === bookSlug);
            }
            // Fallback: title match for uncategorized docs
            const title = (d.title || '').toLowerCase();
            return title.includes(bookName);
        });
    }
    
    function generateBookItems(books) {
        return books.map(book => {
            const docs = getDocsForBook(book);
            const count = docs.length;
            
            let docsList = '';
            if (count > 0) {
                docsList = '<div class="book-docs" id="docs-' + escapeHtml(book.slug) + '">';
                docs.forEach(doc => {
                    const title = escapeHtml(doc.title || '\u0628\u062f\u0648\u0646 \u0639\u0646\u0648\u0627\u0646');
                    const author = escapeHtml(doc.author || '');
                    const path = escapeHtml(safePath(doc.html_path || '#'));
                    const isCompleted = doc.completed;
                    const icon = isCompleted ? '&#10003;' : '&#9679;';
                    const cls = isCompleted ? 'completed' : 'in-progress';
                    docsList += '<a href="' + path + '" class="book-doc-link ' + cls + '">';
                    docsList += '<span class="doc-icon">' + icon + '</span> ';
                    docsList += '<span class="doc-title">' + title + '</span>';
                    docsList += '<span class="doc-author">' + author + '</span>';
                    docsList += '</a>';
                });
                docsList += '</div>';
            }
            
            const interactive = count > 0;
            const rowAttrs = interactive
                ? ' role="button" tabindex="0" aria-expanded="false" aria-controls="docs-' + escapeHtml(book.slug) + '"'
                : '';

            return '<div class="book-item" data-book="' + escapeHtml(book.slug) + '"' + rowAttrs + '>' +
                '<span class="book-name">' + escapeHtml(book.name_ar) + '</span>' +
                '<span class="book-badges">' +
                '<span class="book-count">' + count + ' \u0645\u0633\u062a\u0646\u062f</span>' +
                (interactive ? '<span class="book-chevron" aria-hidden="true">&#9662;</span>' : '') +
                '</span>' +
                '</div>' +
                docsList;
        }).join('');
    }

    document.addEventListener('click', function(e) {
        const item = e.target && e.target.closest ? e.target.closest('.book-item[data-book]') : null;
        if (item) toggleBook(item.getAttribute('data-book'));
    });

    document.addEventListener('keydown', function(e) {
        if (e.key !== 'Enter' && e.key !== ' ' && e.key !== 'Spacebar') return;
        const item = e.target && e.target.closest
            ? e.target.closest('.book-item[data-book][role="button"]')
            : null;
        if (!item) return;
        e.preventDefault();
        toggleBook(item.getAttribute('data-book'));
    });
    
    if (cats.old_testament) {
        const otList = document.getElementById('otBooksList');
        if (otList) {
            otList.innerHTML = generateBookItems(cats.old_testament.books);
        }
    }
    
    if (cats.new_testament) {
        const ntList = document.getElementById('ntBooksList');
        if (ntList) {
            ntList.innerHTML = generateBookItems(cats.new_testament.books);
        }
    }
    
    if (cats.topics) {
        const topicsList = document.getElementById('topicsBooksList');
        if (topicsList) {
            topicsList.innerHTML = generateBookItems(cats.topics.books);
        }
    }
    
    // Add stats near title
    const titleEl = document.querySelector('.translations-page h1');
    if (titleEl && allDocs.length > 0) {
        const total = allDocs.length;
        const completed = allDocs.filter(d => d.completed === true).length;
        const inProgress = total - completed;
        const statsHtml = '<div class="translations-stats">' +
            '<span class="stat-total">' + total + ' \u0645\u0633\u062a\u0646\u062f</span>' +
            '<span class="stat-separator">|</span>' +
            '<span class="stat-completed">\u2713 ' + completed + ' \u0645\u0643\u062a\u0645\u0644</span>' +
            '<span class="stat-separator">|</span>' +
            '<span class="stat-progress">' + inProgress + ' \u0642\u064a\u062f \u0627\u0644\u062a\u0631\u062c\u0645\u0629</span>' +
            '</div>';
        titleEl.insertAdjacentHTML('afterend', statsHtml);
    }
    
    // Filter buttons for translations page
    const filterBtns = document.querySelectorAll('.filter-btn');
    const bookItems = document.querySelectorAll('.book-item');
    
    // Store original counts
    const originalCounts = new Map();
    bookItems.forEach(item => {
        const countEl = item.querySelector('.book-count');
        if (countEl) {
            originalCounts.set(item, countEl.textContent);
        }
    });
    
    filterBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            filterBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            const filter = this.dataset.filter;
            
            bookItems.forEach(item => {
                const docsDiv = item.nextElementSibling;
                const countEl = item.querySelector('.book-count');
                
                if (!docsDiv || !docsDiv.classList.contains('book-docs')) {
                    if (filter === 'all') {
                        item.style.display = '';
                        if (countEl) countEl.textContent = originalCounts.get(item) || '';
                    } else {
                        item.style.display = 'none';
                    }
                    return;
                }
                
                const docLinks = docsDiv.querySelectorAll('.book-doc-link');
                if (docLinks.length === 0) {
                    item.style.display = filter === 'all' ? '' : 'none';
                    if (countEl && filter !== 'all') countEl.textContent = '0 \u0645\u0633\u062a\u0646\u062f';
                    if (countEl && filter === 'all') countEl.textContent = originalCounts.get(item) || '';
                    return;
                }
                
                let visibleCount = 0;
                docLinks.forEach(link => {
                    const isCompleted = link.classList.contains('completed');
                    const isInProgress = link.classList.contains('in-progress');
                    
                    if (filter === 'all') {
                        link.style.display = '';
                        visibleCount++;
                    } else if (filter === 'completed') {
                        if (isCompleted) {
                            link.style.display = '';
                            visibleCount++;
                        } else {
                            link.style.display = 'none';
                        }
                    } else if (filter === 'in-progress') {
                        if (isInProgress) {
                            link.style.display = '';
                            visibleCount++;
                        } else {
                            link.style.display = 'none';
                        }
                    }
                });
                
                if (countEl) {
                    countEl.textContent = visibleCount + ' \u0645\u0633\u062a\u0646\u062f';
                }
                
                item.style.display = visibleCount > 0 ? '' : 'none';
            });
        });
    });
}
