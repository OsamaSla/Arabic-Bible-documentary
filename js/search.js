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
        
        this.init();
    }

    async init() {
        this.searchInput = document.getElementById('searchInput');
        this.searchResults = document.getElementById('searchResults');
        
        if (!this.searchInput || !this.searchResults) return;
        
        await this.loadDocuments();
        this.setupEventListeners();
    }

    async loadDocuments() {
        if (window.__DOCUMENTS_DATA__) {
            this.documents = window.__DOCUMENTS_DATA__;
            return;
        }
        
        try {
            const response = await fetch('documents/index.json');
            if (response.ok) {
                const data = await response.json();
                this.documents = data.documents || [];
                return;
            }
        } catch (error) {}
        
        try {
            const response = await fetch('../documents/index.json');
            if (response.ok) {
                const data = await response.json();
                this.documents = data.documents || [];
                return;
            }
        } catch (error) {}
    }

    setupEventListeners() {
        this.searchInput.addEventListener('input', (e) => {
            this.handleSearch(e.target.value);
        });
        
        this.searchInput.addEventListener('focus', () => {
            if (this.searchInput.value.length > 0) {
                this.showResults();
            }
        });
        
        document.addEventListener('click', (e) => {
            if (!this.searchInput.contains(e.target) && 
                !this.searchResults.contains(e.target)) {
                this.hideResults();
            }
        });
        
        this.searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hideResults();
                this.searchInput.blur();
            }
        });
    }

    handleSearch(query) {
        query = query.trim();
        
        if (query.length < 2) {
            this.hideResults();
            return;
        }
        
        const results = this.searchDocuments(query);
        this.displayResults(results, query);
    }

    searchDocuments(query) {
        const normalizedQuery = query.toLowerCase();
        
        return this.documents.filter(doc => {
            const title = (doc.title || '').toLowerCase();
            const description = (doc.description || '').toLowerCase();
            const author = (doc.author || '').toLowerCase();
            const category = (doc.category || '').toLowerCase();
            
            return title.includes(normalizedQuery) || 
                   description.includes(normalizedQuery) ||
                   author.includes(normalizedQuery) ||
                   category.includes(normalizedQuery);
        }).slice(0, 20);
    }

    displayResults(results, query) {
        if (results.length === 0) {
            this.searchResults.innerHTML = `
                <div class="search-result-item">
                    <div class="search-result-title">\u0644\u0627 \u062a\u0648\u062c\u062f \u0646\u062a\u0627\u0626\u062c</div>
                    <div class="search-result-category">\u062c\u0631\u0628 \u0643\u0644\u0645\u0627\u062a \u0628\u062d\u062b \u0645\u062e\u062a\u0644\u0641\u0629</div>
                </div>
            `;
        } else {
            this.searchResults.innerHTML = results.map(doc => {
                const path = doc.html_path || '#';
                const author = doc.author || '';
                return `
                <a href="${path}" class="search-result-item">
                    <div class="search-result-title">${this.highlightText(doc.title, query)}</div>
                    <div class="search-result-category">${author}</div>
                </a>
                `;
            }).join('');
        }
        
        this.showResults();
    }

    highlightText(text, query) {
        if (!query) return text;
        const regex = new RegExp(`(${query})`, 'gi');
        return text.replace(regex, '<strong>$1</strong>');
    }

    showResults() {
        this.searchResults.classList.add('active');
        this.isOpen = true;
    }

    hideResults() {
        this.searchResults.classList.remove('active');
        this.isOpen = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.search = new Search();
});
