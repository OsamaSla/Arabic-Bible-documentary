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
