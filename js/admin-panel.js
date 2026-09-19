/**
 * Admin Panel - Document Management
 */

var AdminPanel = {
    documents: [],
    overrides: {},
    currentPage: 1,
    perPage: 50,
    searchQuery: '',
    
    init: function() {
        if (!AdminAuth.isLoggedIn()) {
            window.location.href = 'admin.html';
            return;
        }
        
        this.loadData();
        this.setupSearch();
    },
    
    loadData: function() {
        var self = this;
        
        // Load documents
        var xhr = new XMLHttpRequest();
        xhr.open('GET', 'documents/index.json', false);
        xhr.send();
        if (xhr.status === 200) {
            var data = JSON.parse(xhr.responseText);
            self.documents = data.documents || [];
        }
        
        // Load existing overrides from embedded data or file
        if (window.__OVERRIDES_DATA__) {
            self.overrides = window.__OVERRIDES_DATA__;
        } else {
            try {
                var xhr2 = new XMLHttpRequest();
                xhr2.open('GET', 'doc_overrides.json', false);
                xhr2.send();
                if (xhr2.status === 200) {
                    var ovData = JSON.parse(xhr2.responseText);
                    self.overrides = ovData.overrides || {};
                }
            } catch (e) {
                self.overrides = {};
            }
        }
        
        self.render();
    },
    
    setupSearch: function() {
        var self = this;
        var searchBox = document.getElementById('searchBox');
        searchBox.addEventListener('input', function() {
            self.searchQuery = this.value.toLowerCase();
            self.currentPage = 1;
            self.render();
        });
    },
    
    getFilteredDocs: function() {
        var self = this;
        var docs = this.documents;
        
        if (this.searchQuery) {
            docs = docs.filter(function(doc) {
                var title = (doc.title || '').toLowerCase();
                var author = (doc.author || '').toLowerCase();
                var id = (doc.id || '').toLowerCase();
                return title.includes(self.searchQuery) || 
                       author.includes(self.searchQuery) || 
                       id.includes(self.searchQuery);
            });
        }
        
        return docs;
    },
    
    getOverride: function(docId) {
        return this.overrides[docId] || {};
    },
    
    toggleCompleted: function(docId) {
        var ov = this.getOverride(docId);
        if (ov.completed) {
            delete ov.completed;
        } else {
            ov.completed = true;
        }
        if (Object.keys(ov).length === 0) {
            delete this.overrides[docId];
        } else {
            this.overrides[docId] = ov;
        }
        this.render();
    },
    
    toggleHidden: function(docId) {
        var ov = this.getOverride(docId);
        if (ov.hidden) {
            delete ov.hidden;
        } else {
            ov.hidden = true;
        }
        if (Object.keys(ov).length === 0) {
            delete this.overrides[docId];
        } else {
            this.overrides[docId] = ov;
        }
        this.render();
    },
    
    render: function() {
        var filtered = this.getFilteredDocs();
        var totalPages = Math.ceil(filtered.length / this.perPage);
        var start = (this.currentPage - 1) * this.perPage;
        var pageDocs = filtered.slice(start, start + this.perPage);
        
        // Update stats
        var total = this.documents.length;
        var completed = 0;
        var hidden = 0;
        var self = this;
        
        this.documents.forEach(function(doc) {
            var ov = self.getOverride(doc.id);
            if (ov.completed || (!ov.completed && !ov.hidden && doc.completed)) {
                completed++;
            }
            if (ov.hidden) {
                hidden++;
            }
        });
        
        document.getElementById('statTotal').textContent = total;
        document.getElementById('statCompleted').textContent = completed;
        document.getElementById('statProgress').textContent = total - completed;
        document.getElementById('statHidden').textContent = hidden;
        
        // Render table
        var tbody = document.getElementById('docsTableBody');
        tbody.innerHTML = '';
        
        pageDocs.forEach(function(doc) {
            var ov = self.getOverride(doc.id);
            var isCompleted = ov.completed !== undefined ? ov.completed : doc.completed;
            var isHidden = ov.hidden || false;
            var hasOverride = ov.completed !== undefined || ov.hidden !== undefined;
            
            var row = document.createElement('tr');
            if (isHidden) row.className = 'hidden-doc';
            
            row.innerHTML = '<td><code>' + doc.id + '</code></td>' +
                '<td class="doc-title-cell">' + (doc.title || '') + '</td>' +
                '<td>' + (doc.author || '') + '</td>' +
                '<td><label class="toggle-switch"><input type="checkbox" ' + 
                (isCompleted ? 'checked' : '') + 
                ' onchange="AdminPanel.toggleCompleted(\'' + doc.id + '\')"><span class="toggle-slider"></span></label></td>' +
                '<td><label class="toggle-switch"><input type="checkbox" ' + 
                (isHidden ? 'checked' : '') + 
                ' onchange="AdminPanel.toggleHidden(\'' + doc.id + '\')"><span class="toggle-slider"></span></label></td>';
            
            tbody.appendChild(row);
        });
        
        // Render pagination
        var pagination = document.getElementById('pagination');
        pagination.innerHTML = '';
        
        if (totalPages > 1) {
            for (var i = 1; i <= totalPages; i++) {
                var btn = document.createElement('button');
                btn.className = 'page-btn' + (i === this.currentPage ? ' active' : '');
                btn.textContent = i;
                btn.onclick = (function(page) {
                    return function() {
                        AdminPanel.currentPage = page;
                        AdminPanel.render();
                    };
                })(i);
                pagination.appendChild(btn);
            }
        }
    },
    
    exportOverrides: function() {
        var output = {
            "_comment": "Override document settings. Changes take effect after rebuilding the site.",
            "_instructions": {
                "completed": "Set to true to mark a document as completed",
                "hidden": "Set to true to completely hide a document from the website"
            },
            "overrides": this.overrides
        };
        
        var json = JSON.stringify(output, null, 2);
        document.getElementById('jsonPreview').value = json;
        document.getElementById('exportModal').style.display = 'block';
    },
    
    closeModal: function() {
        document.getElementById('exportModal').style.display = 'none';
    },
    
    downloadFile: function() {
        var json = document.getElementById('jsonPreview').value;
        var blob = new Blob([json], { type: 'application/json' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'doc_overrides.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },
    
    copyToClipboard: function() {
        var textarea = document.getElementById('jsonPreview');
        textarea.select();
        document.execCommand('copy');
        alert('تم النسخ للمحافظة!');
    }
};

document.addEventListener('DOMContentLoaded', function() {
    AdminPanel.init();
});
