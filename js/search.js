/**
 * Arabic Christian Translations - Search Functionality
 * Instant search across all documents
 */

class Search {
    constructor() {
        this.documents = [];
        this.searchInput = null;
        this.searchResults = null;
        this.isOpen = false;
        this.activeIndex = -1;
        this.debounceTimer = null;
        this.loadError = false;
        this.isLoading = false;

        this.init();
    }

    async init() {
        this.searchInput = document.getElementById('searchInput');
        this.searchResults = document.getElementById('searchResults');

        if (!this.searchInput || !this.searchResults) return;

        if (!this.searchResults.id) {
            this.searchResults.id = 'searchResults';
        }
        this.searchResults.setAttribute('role', 'listbox');
        this.searchResults.setAttribute('aria-label', 'نتائج البحث');

        this.setupEventListeners();
        this.isLoading = true;
        await this.loadDocuments();
        this.isLoading = false;
    }

    async loadDocuments() {
        if (window.__DOCUMENTS_DATA__) {
            this.documents = window.__DOCUMENTS_DATA__;
            return;
        }

        const paths = [
            'documents/index.json',
            '../documents/index.json',
            '../../documents/index.json',
            '../../../documents/index.json'
        ];
        for (const path of paths) {
            try {
                const response = await fetch(path);
                if (response.ok) {
                    const data = await response.json();
                    this.documents = data.documents || [];
                    return;
                }
            } catch (error) {
                console.error('Search load failed:', error);
            }
        }
        this.loadError = true;
    }

    setupEventListeners() {
        this.searchInput.setAttribute('role', 'combobox');
        this.searchInput.setAttribute('aria-expanded', 'false');
        this.searchInput.setAttribute('aria-controls', 'searchResults');
        this.searchInput.setAttribute('aria-autocomplete', 'list');

        this.searchInput.addEventListener('input', () => {
            clearTimeout(this.debounceTimer);
            this.debounceTimer = setTimeout(() => {
                this.handleSearch(this.searchInput.value);
            }, 150);
        });

        this.searchInput.addEventListener('focus', () => {
            if (this.searchInput.value.trim().length >= 2) {
                this.showResults();
            }
        });

        this.searchInput.addEventListener('keydown', (e) => {
            const items = this.getResultItems();

            if (e.key === 'Escape') {
                this.hideResults();
                this.clearActive();
                return;
            }

            if (e.key === 'ArrowDown' && items.length) {
                e.preventDefault();
                this.moveActive(1, items);
            } else if (e.key === 'ArrowUp' && items.length) {
                e.preventDefault();
                this.moveActive(-1, items);
            } else if (e.key === 'Enter' && this.activeIndex >= 0 && items[this.activeIndex]) {
                e.preventDefault();
                items[this.activeIndex].click();
            }
        });

        document.addEventListener('click', (e) => {
            if (!this.searchInput.contains(e.target) &&
                !this.searchResults.contains(e.target)) {
                this.hideResults();
                this.clearActive();
            }
        });
    }

    getResultItems() {
        return Array.from(this.searchResults.querySelectorAll('a.search-result-item'));
    }

    moveActive(delta, items) {
        if (this.activeIndex >= 0 && items[this.activeIndex]) {
            items[this.activeIndex].classList.remove('is-active');
            items[this.activeIndex].removeAttribute('aria-selected');
        }
        this.activeIndex += delta;
        if (this.activeIndex < 0) this.activeIndex = items.length - 1;
        if (this.activeIndex >= items.length) this.activeIndex = 0;
        const el = items[this.activeIndex];
        el.classList.add('is-active');
        el.setAttribute('aria-selected', 'true');
        el.scrollIntoView({ block: 'nearest' });
        this.searchInput.setAttribute('aria-activedescendant', el.id || '');
        if (!el.id) {
            el.id = 'search-result-' + this.activeIndex;
            this.searchInput.setAttribute('aria-activedescendant', el.id);
        }
    }

    clearActive() {
        this.activeIndex = -1;
        this.searchResults.querySelectorAll('.is-active').forEach(el => {
            el.classList.remove('is-active');
            el.removeAttribute('aria-selected');
        });
        this.searchInput.removeAttribute('aria-activedescendant');
    }

    handleSearch(query) {
        query = (query || '').trim();

        if (query.length < 2) {
            this.hideResults();
            this.announce('');
            return;
        }

        if (this.loadError) {
            this.searchResults.innerHTML = `
                <div class="search-result-item" role="presentation">
                    <div class="search-result-title">تعذر تحميل نتائج البحث</div>
                    <div class="search-result-category">حاول تحديث الصفحة</div>
                </div>
            `;
            this.showResults();
            this.announce('خطأ في تحميل البحث');
            return;
        }

        if (this.isLoading) {
            this.searchResults.innerHTML = `
                <div class="search-result-item" role="presentation">
                    <div class="search-result-title">جاري التحميل...</div>
                </div>
            `;
            this.showResults();
            return;
        }

        try {
            const results = this.searchDocuments(query);
            this.displayResults(results, query);
        } catch (error) {
            console.error('Search error:', error);
            this.searchResults.innerHTML = `
                <div class="search-result-item" role="presentation">
                    <div class="search-result-title">حدث خطأ في البحث</div>
                </div>
            `;
            this.showResults();
        }
    }

    searchDocuments(query) {
        const normalizedQuery = query.toLowerCase();
        const matched = this.documents.filter(doc => {
            const title = (doc.title || '').toLowerCase();
            const description = (doc.description || '').toLowerCase();
            const author = (doc.author || '').toLowerCase();
            // Array-safe: search across all assigned categories
            let catStr = '';
            if (Array.isArray(doc.categories)) {
                catStr = doc.categories.join(' ').toLowerCase();
            } else {
                catStr = String(doc.category || '').toLowerCase();
            }

            return title.includes(normalizedQuery) ||
                   description.includes(normalizedQuery) ||
                   author.includes(normalizedQuery) ||
                   catStr.includes(normalizedQuery);
        });
        return { all: matched, shown: matched.slice(0, 20) };
    }

    displayResults(resultObj, query) {
        const results = resultObj.shown || [];
        const total = resultObj.all ? resultObj.all.length : results.length;
        this.activeIndex = -1;

        if (results.length === 0) {
            this.searchResults.innerHTML = `
                <div class="search-result-item" role="presentation">
                    <div class="search-result-title">لا توجد نتائج</div>
                    <div class="search-result-category">جرّب كلمات بحث مختلفة</div>
                </div>
            `;
            this.announce('لا توجد نتائج');
        } else {
            const moreNote = total > results.length
                ? `<div class="search-result-more">عرض ${results.length} من ${total} نتيجة</div>`
                : '';
            this.searchResults.innerHTML = results.map((doc, i) => {
                const path = safePath(doc.html_path || '#');
                const author = escapeHtml(doc.author || '');
                const title = doc.title || 'بدون عنوان';
                return `
                <a href="${escapeHtml(path)}" class="search-result-item" role="option" id="search-result-${i}" aria-selected="false">
                    <div class="search-result-title">${this.highlightText(title, query)}</div>
                    <div class="search-result-category">${author}</div>
                </a>
                `;
            }).join('') + moreNote;
            this.announce(`${total} نتيجة`);
        }

        this.showResults();
    }

    escapeRegex(str) {
        return String(str).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    highlightText(text, query) {
        const safe = escapeHtml(String(text || 'بدون عنوان'));
        if (!query) return safe;
        try {
            const regex = new RegExp(`(${this.escapeRegex(escapeHtml(query))})`, 'gi');
            return safe.replace(regex, '<strong>$1</strong>');
        } catch (e) {
            return safe;
        }
    }

    announce(message) {
        let live = document.getElementById('searchLive');
        if (!live) {
            live = document.createElement('div');
            live.id = 'searchLive';
            live.setAttribute('aria-live', 'polite');
            live.className = 'visually-hidden';
            document.body.appendChild(live);
        }
        live.textContent = message;
    }

    showResults() {
        this.searchResults.classList.add('active');
        this.searchInput.setAttribute('aria-expanded', 'true');
        this.isOpen = true;
    }

    hideResults() {
        this.searchResults.classList.remove('active');
        this.searchInput.setAttribute('aria-expanded', 'false');
        this.isOpen = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.search = new Search();
});
