/**
 * Local-only admin panel logic.
 * Token is injected by scripts/serve.py as window.__SERVE_TOKEN__.
 */

(function () {
    'use strict';

    var currentSearchQuery = '';
    var filterCompletedActive = false;
    var filterHiddenActive = false;
    var filterUncategorizedActive = false;
    var categoryFilterValue = '';
    var categoryVocabulary = null;
    var categoryAssignments = {};
    var categoryLabelMap = {};
    var categoryGroupOrder = ['old_testament', 'new_testament', 'topics'];
    var categoryGroupLabels = {
        old_testament: 'العهد القديم',
        new_testament: 'العهد الجديد',
        topics: 'المواضيع'
    };

    // Prefer inline token if present; otherwise read CSP-safe meta tag injected by serve.py
    if (!window.__SERVE_TOKEN__) {
        var meta = document.querySelector('meta[name="serve-token"]');
        if (meta && meta.content) window.__SERVE_TOKEN__ = meta.content;
    }

    function apiHeaders() {
        return { 'X-Serve-Token': window.__SERVE_TOKEN__ || '' };
    }

    function setDeployStatus(text, cls) {
        var el = document.getElementById('deployStatus');
        if (!el) return;
        el.textContent = text || '';
        el.className = 'deploy-status' + (cls ? ' ' + cls : '');
    }

    function getLocalApiError() {
        if (location.protocol === 'file:') {
            return 'This page is open as a file (file://). The admin panel needs the local server:\n' +
                '1) python scripts\\serve.py\n' +
                '2) Open http://localhost:8000/admin-panel.html';
        }
        var host = location.hostname || '';
        var isLocal = host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]';
        if (!isLocal) {
            return 'You are on ' + location.origin + ' — the admin panel only works on the local server.\n' +
                'Run: python scripts\\serve.py\n' +
                'Then open: http://localhost:8000/admin-panel.html';
        }
        if (!window.__SERVE_TOKEN__) {
            return 'Missing server token. Open this page through scripts/serve.py (not a plain file).';
        }
        return null;
    }

    function postApi(path, body) {
        var opts = { method: 'POST', headers: apiHeaders() };
        if (body !== undefined && body !== null) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(body);
        }
        return fetch(path, opts).then(function (res) {
            return res.json().catch(function () {
                return { ok: false, message: 'Bad server response (HTTP ' + res.status + ').' };
            }).then(function (data) {
                return { status: res.status, data: data };
            });
        });
    }

    function getApi(path) {
        return fetch(path, { method: 'GET', headers: apiHeaders() }).then(function (res) {
            return res.json().catch(function () {
                return { ok: false, message: 'Bad server response (HTTP ' + res.status + ').' };
            }).then(function (data) {
                return { status: res.status, data: data };
            });
        });
    }

    function buildCategoryLabelMap(vocab) {
        categoryLabelMap = { uncategorized: 'بدون فئة' };
        var cats = (vocab && vocab.categories) || {};
        categoryGroupOrder.forEach(function (key) {
            var group = cats[key];
            if (!group || !group.books) return;
            group.books.forEach(function (b) {
                if (b && b.slug) {
                    categoryLabelMap[b.slug] = b.name_ar || b.slug;
                }
            });
        });
    }

    function populateCategoryControls(vocab) {
        var groupsHtml = '';
        var cats = (vocab && vocab.categories) || {};
        categoryGroupOrder.forEach(function (key) {
            var group = cats[key];
            if (!group || !group.books) return;
            groupsHtml += '<optgroup label="' + escapeHtml(categoryGroupLabels[key] || group.name_ar || key) + '">';
            group.books.forEach(function (b) {
                if (!b || !b.slug) return;
                groupsHtml += '<option value="' + escapeHtml(b.slug) + '">' +
                    escapeHtml(b.name_ar || b.slug) + '</option>';
            });
            groupsHtml += '</optgroup>';
        });

        var filter = document.getElementById('categoryFilter');
        if (filter) {
            var prevF = filter.value;
            filter.innerHTML = '<option value="">كل الفئات</option>' +
                '<option value="uncategorized">بدون فئة فقط</option>' + groupsHtml;
            if (prevF) filter.value = prevF;
            if (!filter._listenerAdded) {
                filter._listenerAdded = true;
                filter.addEventListener('change', function () {
                    categoryFilterValue = filter.value || '';
                    applyFiltersAndRender();
                });
            }
        }

        var countsEl = document.getElementById('categoryCounts');
        if (countsEl && window.__categoryCounts) {
            var n = window.__categoryCounts.uncategorized || 0;
            countsEl.textContent = n + ' بدون فئة';
        }
    }

    function categoryOptionGroupsHtml() {
        var html = '';
        var cats = (categoryVocabulary && categoryVocabulary.categories) || {};
        categoryGroupOrder.forEach(function (key) {
            var group = cats[key];
            if (!group || !group.books) return;
            html += '<div class="cat-tray-group">' +
                '<div class="cat-tray-group-title" id="cat-grp-' + escapeHtml(key) + '">' +
                escapeHtml(categoryGroupLabels[key] || group.name_ar || key) + '</div>' +
                '<div class="cat-tray-chips" role="group" aria-labelledby="cat-grp-' + escapeHtml(key) + '">';
            group.books.forEach(function (b) {
                if (!b || !b.slug) return;
                html += '<button type="button" class="cat-opt" data-slug="' + escapeHtml(b.slug) + '" ' +
                    'role="checkbox" aria-checked="false">' +
                    escapeHtml(b.name_ar || b.slug) + '</button>';
            });
            html += '</div></div>';
        });
        return html;
    }

    function currentCategoriesFor(doc) {
        var byId = categoryAssignments[doc.id];
        if (byId && byId.length) return byId.slice();
        if (doc.filename && categoryAssignments[doc.filename] && categoryAssignments[doc.filename].length) {
            return categoryAssignments[doc.filename].slice();
        }
        if (Array.isArray(doc.categories) && doc.categories.length) return doc.categories.slice();
        if (doc.category && doc.category !== 'uncategorized') return [doc.category];
        return [];
    }

    function currentCategoryFor(doc) {
        var cats = currentCategoriesFor(doc);
        return cats.length ? cats[0] : 'uncategorized';
    }

    function setCategorySaveStatus(docId, text, cls) {
        var el = document.querySelector('.cat-save-status[data-doc-id="' + docId + '"]');
        if (!el) return;
        el.textContent = text || '';
        el.className = 'cat-save-status' + (cls ? ' ' + cls : '');
    }

    function updateDocChips(docId, cats) {
        var wrap = document.querySelector('.cat-chips[data-doc-id="' + docId + '"]');
        if (wrap) {
            wrap.innerHTML = chipsInnerHtml(docId, cats);
            wrap.className = 'cat-chips ' + (cats.length ? 'has-cats' : 'none');
        }
        var trigger = document.querySelector('.cat-trigger[data-doc-id="' + docId + '"]');
        if (trigger) {
            var txt = trigger.querySelector('.cat-trigger-text');
            if (txt) txt.textContent = 'الفئات';
        }
        (window.__allDocs || []).forEach(function (d) {
            if (d.id === docId) {
                d.categories = cats.slice();
                d.category = cats.length ? cats[0] : 'uncategorized';
            }
        });
        syncPopoverState(docId, cats);
    }

    function chipsInnerHtml(docId, cats) {
        if (!cats || !cats.length) {
            return '<span class="cat-chip empty" data-slug="uncategorized">بدون فئة</span>';
        }
        return cats.map(function (slug) {
            var label = categoryLabelMap[slug] || slug;
            return '<span class="cat-chip assigned" data-slug="' + escapeHtml(slug) + '">' +
                escapeHtml(label) + '</span>';
        }).join('');
    }

    function closeAllCatPopovers(exceptEl) {
        document.querySelectorAll('.cat-tray.open').forEach(function (p) {
            if (exceptEl && p === exceptEl) return;
            p.classList.remove('open');
            p.hidden = true;
            var owner = p.closest('.cat-multi');
            if (owner) {
                var t = owner.querySelector('.cat-trigger');
                if (t) {
                    t.setAttribute('aria-expanded', 'false');
                    t.classList.remove('is-open');
                }
            }
        });
    }

    function openCatTray(trigger) {
        var multi = trigger.closest('.cat-multi');
        var tray = multi ? multi.querySelector('.cat-tray') : null;
        if (!tray) return;
        closeAllCatPopovers(tray);
        tray.hidden = false;
        tray.classList.add('open');
        trigger.setAttribute('aria-expanded', 'true');
        trigger.classList.add('is-open');
        var docId = trigger.getAttribute('data-doc-id');
        var docT = (window.__allDocs || []).find(function (d) { return d.id === docId; });
        syncPopoverState(docId, docT ? currentCategoriesFor(docT) : []);
    }

    function closeCatTray(trigger) {
        var multi = trigger.closest('.cat-multi');
        var tray = multi ? multi.querySelector('.cat-tray') : null;
        if (!tray) return;
        tray.classList.remove('open');
        tray.hidden = true;
        trigger.setAttribute('aria-expanded', 'false');
        trigger.classList.remove('is-open');
        trigger.focus();
    }

    function saveCategories(docId, cats, trayEl) {
        var cleaned = [];
        var seen = {};
        (cats || []).forEach(function (c) {
            if (!c || c === 'uncategorized' || seen[c]) return;
            seen[c] = true;
            cleaned.push(c);
        });
        var trigger = trayEl && trayEl.closest('.cat-multi')
            ? trayEl.closest('.cat-multi').querySelector('.cat-trigger') : null;
        if (trigger) trigger.disabled = true;
        setCategorySaveStatus(docId, 'جارٍ الحفظ…', '');
        postApi('/api/categories', { docId: docId, categories: cleaned })
            .then(function (result) {
                var data = result.data || {};
                if (result.status === 200 && data.ok) {
                    if (cleaned.length) {
                        categoryAssignments[docId] = cleaned.slice();
                    } else {
                        delete categoryAssignments[docId];
                    }
                    updateDocChips(docId, cleaned);
                    setCategorySaveStatus(docId, '✓ تم الحفظ — أعد البناء للنشر', 'ok');
                    setDeployStatus(data.message || 'Categories saved.', 'is-ok');
                    refreshCategoryCounts();
                } else {
                    setCategorySaveStatus(docId, data.message || ('فشل الحفظ (HTTP ' + result.status + ')'), 'err');
                    setDeployStatus(data.message || ('Save failed (HTTP ' + result.status + ').'), 'is-err');
                }
            })
            .catch(function (err) {
                setCategorySaveStatus(docId, 'خطأ شبكة: ' + (err && err.message ? err.message : 'network'), 'err');
                setDeployStatus('Cannot reach local server. Start: python scripts\\serve.py', 'is-err');
            })
            .then(function () {
                if (trigger) trigger.disabled = false;
            });
    }

    function loadCategories() {
        var originErr = getLocalApiError();
        if (originErr) return Promise.resolve(null);
        return getApi('/api/categories').then(function (result) {
            if (result.status === 200 && result.data && result.data.ok) {
                categoryVocabulary = result.data.vocabulary || null;
                categoryAssignments = result.data.assignments || {};
                window.__categoryCounts = result.data.counts || {};
                buildCategoryLabelMap(categoryVocabulary);
                populateCategoryControls(categoryVocabulary);
                return result.data;
            }
            return null;
        }).catch(function () {
            return null;
        });
    }

    function refreshCategoryCounts() {
        var counts = {};
        (window.__allDocs || []).forEach(function (d) {
            var cats = currentCategoriesFor(d);
            if (!cats.length) {
                counts.uncategorized = (counts.uncategorized || 0) + 1;
            } else {
                cats.forEach(function (c) {
                    counts[c] = (counts[c] || 0) + 1;
                });
            }
        });
        window.__categoryCounts = counts;
        var countsEl = document.getElementById('categoryCounts');
        if (countsEl) {
            countsEl.textContent = (counts.uncategorized || 0) + ' بدون فئة';
        }
    }

    function renderChanges(data) {
        var panel = document.getElementById('changesPanel');
        if (!panel) return;
        var html = '<h3>Changes since last build</h3>';
        html += '<p class="muted">Last build: <code>' + escapeHtml(data.lastBuild || 'never') + '</code>' +
            ' · Checked: <code>' + escapeHtml(data.checkedAt || '') + '</code></p>';

        html += '<p><strong>Source (.docx):</strong> ' + (data.sourceCount || 0) + ' changed</p>';
        if (data.sourceNote) {
            html += '<p class="muted">' + escapeHtml(data.sourceNote) + '</p>';
        }
        if (data.sourceChanges && data.sourceChanges.length) {
            html += '<ul>';
            data.sourceChanges.slice(0, 50).forEach(function (item) {
                html += '<li><code>' + escapeHtml(item.path) + '</code> <span class="muted">(' +
                    escapeHtml(item.modified) + ')</span></li>';
            });
            html += '</ul>';
            if (data.sourceChanges.length > 50) {
                html += '<p class="muted">…and ' + (data.sourceChanges.length - 50) + ' more</p>';
            }
        }

        var git = data.gitChanges || [];
        html += '<p><strong>Git working tree:</strong> ' + git.length + ' path(s)</p>';
        if (git.length) {
            html += '<ul>';
            git.slice(0, 50).forEach(function (line) {
                html += '<li><code>' + escapeHtml(line) + '</code></li>';
            });
            html += '</ul>';
        }

        var commits = data.recentCommits || [];
        if (commits.length) {
            html += '<p><strong>Recent commits:</strong></p><ul>';
            commits.forEach(function (c) {
                html += '<li><code>' + escapeHtml(c.sha) + '</code> ' + escapeHtml(c.date) +
                    ' — ' + escapeHtml(c.subject) + '</li>';
            });
            html += '</ul>';
        }

        if (!git.length && !(data.sourceChanges && data.sourceChanges.length)) {
            html += '<p class="muted">Nothing pending since last build.</p>';
        }

        panel.innerHTML = html;
        panel.hidden = false;
    }

    function setupDeployButton() {
        var btn = document.getElementById('deployBtn');
        if (!btn || btn._listenerAdded) return;
        btn._listenerAdded = true;
        btn.addEventListener('click', function () {
            if (btn.disabled) return;

            var originErr = getLocalApiError();
            if (originErr) {
                setDeployStatus(originErr, 'is-err');
                return;
            }

            btn.disabled = true;
            var prevLabel = btn.textContent;
            btn.textContent = 'Deploying…';
            setDeployStatus('Scanning source, rebuilding, then pushing…', 'is-busy');

            postApi('/api/deploy')
                .then(function (result) {
                    var data = result.data || {};
                    if (result.status === 200 && data.ok) {
                        setDeployStatus(data.message || 'Deployed.', 'is-ok');
                    } else {
                        setDeployStatus(data.message || ('Deploy failed (HTTP ' + result.status + ').'), 'is-err');
                    }
                })
                .catch(function (err) {
                    setDeployStatus(
                        'Cannot reach local server at ' + location.origin +
                        '. Start it with: python scripts\\serve.py then open http://localhost:8000/admin-panel.html (' +
                        (err && err.message ? err.message : 'network error') + ')',
                        'is-err'
                    );
                })
                .then(function () {
                    btn.disabled = false;
                    btn.textContent = prevLabel;
                });
        });
    }

    function setupChangesButton() {
        var btn = document.getElementById('changesBtn');
        if (!btn || btn._listenerAdded) return;
        btn._listenerAdded = true;
        btn.addEventListener('click', function () {
            if (btn.disabled) return;

            var originErr = getLocalApiError();
            if (originErr) {
                setDeployStatus(originErr, 'is-err');
                return;
            }

            btn.disabled = true;
            var prevLabel = btn.textContent;
            btn.textContent = 'Checking…';
            setDeployStatus('Checking source and git changes…', 'is-busy');

            getApi('/api/changes')
                .then(function (result) {
                    var data = result.data || {};
                    if (result.status === 200 && data.ok) {
                        renderChanges(data);
                        setDeployStatus(
                            (data.sourceCount || 0) + ' source change(s), ' +
                            ((data.gitChanges || []).length) + ' git path(s) since last build.',
                            'is-ok'
                        );
                    } else {
                        setDeployStatus(data.message || ('Check failed (HTTP ' + result.status + ').'), 'is-err');
                    }
                })
                .catch(function (err) {
                    setDeployStatus(
                        'Cannot reach local server at ' + location.origin +
                        '. Start it with: python scripts\\serve.py then open http://localhost:8000/admin-panel.html (' +
                        (err && err.message ? err.message : 'network error') + ')',
                        'is-err'
                    );
                })
                .then(function () {
                    btn.disabled = false;
                    btn.textContent = prevLabel;
                });
        });
    }

    function loadDocuments() {
        var originErr = getLocalApiError();
        if (originErr) {
            document.getElementById('docsContainer').innerHTML = '<p>' + escapeHtml(originErr) + '</p>';
            return;
        }

        getApi('/api/documents')
            .then(function (result) {
                if (result.status !== 200 || !result.data || !result.data.ok) {
                    var msg = (result.data && (result.data.message || result.data.error)) ||
                        ('HTTP ' + result.status);
                    if (result.status === 403) {
                        msg = 'Forbidden (403): ' + msg +
                            '. Token missing/invalid — reopen the panel via python scripts\\serve.py';
                    }
                    throw new Error(msg);
                }
                var docs = result.data.documents || [];
                if (!docs.length) {
                    document.getElementById('docsContainer').innerHTML =
                        '<p style="min-height:72px;">No documents in index. Source index: ' +
                        escapeHtml(result.data.source || 'unknown') +
                        '. Run a rebuild from the server or scripts/build.py.</p>';
                    return;
                }
                window.__allDocs = docs;
                // Sync categories onto docs from assignments cache
                docs.forEach(function (d) {
                    d.categories = currentCategoriesFor(d);
                    d.category = d.categories.length ? d.categories[0] : 'uncategorized';
                });
                applyFiltersAndRender();
                setupControls();
                refreshCategoryCounts();
            })
            .catch(function (err) {
                document.getElementById('docsContainer').innerHTML =
                    '<p style="min-height:72px;">Error loading documents: ' + escapeHtml(err && err.message) + '</p>';
            });
    }

    function setupControls() {
        var filterBox = document.getElementById('filterBox');
        if (!filterBox._listenerAdded) {
            filterBox._listenerAdded = true;
            filterBox.addEventListener('input', function (e) {
                currentSearchQuery = e.target.value.toLowerCase();
                applyFiltersAndRender();
            });
        }

        var btnAll = document.getElementById('btnAll');
        var btnCompleted = document.getElementById('btnCompleted');
        var btnHidden = document.getElementById('btnHidden');
        var btnUncat = document.getElementById('btnUncat');

        if (!btnAll._listenerAdded) {
            btnAll._listenerAdded = true;
            btnAll.addEventListener('click', function () {
                btnAll.classList.add('active');
                filterCompletedActive = false;
                filterHiddenActive = false;
                filterUncategorizedActive = false;
                btnCompleted.classList.remove('active');
                btnHidden.classList.remove('active');
                if (btnUncat) btnUncat.classList.remove('active');
                applyFiltersAndRender();
            });
        }

        if (!btnCompleted._listenerAdded) {
            btnCompleted._listenerAdded = true;
            btnCompleted.addEventListener('click', function () {
                filterCompletedActive = !filterCompletedActive;
                if (filterCompletedActive) {
                    btnCompleted.classList.add('active');
                    btnAll.classList.remove('active');
                } else {
                    btnCompleted.classList.remove('active');
                }
                applyFiltersAndRender();
            });
        }

        if (!btnHidden._listenerAdded) {
            btnHidden._listenerAdded = true;
            btnHidden.addEventListener('click', function () {
                filterHiddenActive = !filterHiddenActive;
                if (filterHiddenActive) {
                    btnHidden.classList.add('active');
                    btnAll.classList.remove('active');
                } else {
                    btnHidden.classList.remove('active');
                }
                applyFiltersAndRender();
            });
        }

        if (btnUncat && !btnUncat._listenerAdded) {
            btnUncat._listenerAdded = true;
            btnUncat.addEventListener('click', function () {
                filterUncategorizedActive = !filterUncategorizedActive;
                if (filterUncategorizedActive) {
                    btnUncat.classList.add('active');
                    btnAll.classList.remove('active');
                } else {
                    btnUncat.classList.remove('active');
                }
                applyFiltersAndRender();
            });
        }
    }

    function applyFiltersAndRender() {
        var docs = window.__allDocs || [];

        if (currentSearchQuery) {
            docs = docs.filter(function (d) {
                var cats = currentCategoriesFor(d);
                var catLabels = cats.map(function (c) {
                    return (c || '') + ' ' + (categoryLabelMap[c] || '');
                }).join(' ');
                return (d.title && d.title.toLowerCase().includes(currentSearchQuery)) ||
                       (d.id && d.id.toLowerCase().includes(currentSearchQuery)) ||
                       (d.author && d.author.toLowerCase().includes(currentSearchQuery)) ||
                       catLabels.toLowerCase().includes(currentSearchQuery);
            });
        }

        if (categoryFilterValue) {
            docs = docs.filter(function (d) {
                if (categoryFilterValue === 'uncategorized') {
                    return currentCategoriesFor(d).length === 0;
                }
                return currentCategoriesFor(d).indexOf(categoryFilterValue) !== -1;
            });
        }

        var btnAllActive = document.getElementById('btnAll').classList.contains('active');

        docs = docs.filter(function (d) {
            var isCompleted = !!(d.completed || false);
            var isHidden = !!(d.hidden || false);
            var isUncat = currentCategoriesFor(d).length === 0;

            if (filterUncategorizedActive) {
                return isUncat;
            }

            if (btnAllActive) {
                return true;
            }
            if (!filterCompletedActive && !filterHiddenActive) {
                return !isCompleted && !isHidden;
            }
            if (filterCompletedActive && filterHiddenActive) {
                return isCompleted && isHidden;
            }
            if (filterCompletedActive) {
                return isCompleted;
            }
            if (filterHiddenActive) {
                return isHidden;
            }
            return !isCompleted && !isHidden;
        });

        renderDocs(docs);
    }

    function openDoc(htmlPath) {
        var path = safePath(htmlPath);
        if (path && path !== '#') window.open(path, '_blank');
    }

    function renderDocs(docs) {
        var container = document.getElementById('docsContainer');
        if (docs.length === 0) {
            container.innerHTML = '<p style="min-height:72px;">No documents found.</p>';
            return;
        }

        var popHtml = categoryOptionGroupsHtml();
        var html = '';
        docs.forEach(function (doc) {
            var isCompleted = !!(doc.completed || false);
            var isHidden = !!(doc.hidden || false);
            var link = escapeHtml(safePath(doc.html_path || ''));
            var cats = currentCategoriesFor(doc);
            var isAssigned = cats.length > 0;
            var trayId = 'cat-tray-' + escapeHtml(doc.id);

            html += '<div class="doc-item' + (isHidden ? ' hidden-doc' : '') +
                '" data-doc-id="' + escapeHtml(doc.id) +
                '" data-doc-link="' + link +
                '" role="article">' +
                '<strong>ID:</strong> ' + escapeHtml(doc.id) + ' | ' +
                '<strong>Title:</strong> ' + escapeHtml(doc.title || 'N/A') + ' | ' +
                '<strong>Author:</strong> ' + escapeHtml(doc.author || 'N/A') + '<br>' +
                '<span class="status-badge ' + (isCompleted ? 'completed-on">✓ مكتمل' : 'completed-off">○ قيد الترجمة') + '</span> ' +
                '<span class="status-badge ' + (isHidden ? 'hidden-on">Hidden' : 'hidden-off">Visible') + '</span>' +
                '<div class="cat-multi" data-doc-id="' + escapeHtml(doc.id) + '">' +
                    '<div class="doc-meta">' +
                        '<div class="cat-chips' + (isAssigned ? ' has-cats' : ' none') +
                            '" data-doc-id="' + escapeHtml(doc.id) + '" aria-live="polite">' +
                            chipsInnerHtml(doc.id, cats) +
                        '</div>' +
                        '<button type="button" class="cat-trigger" data-doc-id="' + escapeHtml(doc.id) + '" ' +
                            'aria-expanded="false" aria-controls="' + trayId + '" ' +
                            'aria-label="تعديل فئات المستند ' + escapeHtml(doc.id) + '">' +
                            '<span class="cat-trigger-text">الفئات</span>' +
                            '<span class="cat-trigger-caret" aria-hidden="true">▾</span>' +
                        '</button>' +
                        '<span class="cat-save-status" data-doc-id="' + escapeHtml(doc.id) + '" aria-live="polite"></span>' +
                        '<button type="button" class="admin-btn admin-btn-secondary" ' +
                            'data-doc-open="' + link + '" style="padding:0.3rem 0.7rem;font-size:0.88rem;">فتح</button>' +
                    '</div>' +
                    '<div class="cat-tray" id="' + trayId + '" hidden data-doc-id="' + escapeHtml(doc.id) + '" ' +
                        'role="group" aria-label="اختيار فئات ' + escapeHtml(doc.id) + '">' +
                        '<div class="cat-tray-body">' + popHtml + '</div>' +
                        '<div class="cat-tray-footer">' +
                            '<button type="button" class="cat-clear" data-doc-id="' + escapeHtml(doc.id) + '">مسح الكل</button>' +
                            '<button type="button" class="cat-done" data-doc-id="' + escapeHtml(doc.id) + '">تم</button>' +
                        '</div>' +
                    '</div>' +
                '</div>' +
                '</div>';
        });
        container.innerHTML = html;
        docs.forEach(function (doc) {
            syncPopoverState(doc.id, currentCategoriesFor(doc));
        });
    }

    function syncPopoverState(docId, cats) {
        var multi = document.querySelector('.cat-multi[data-doc-id="' + docId + '"]');
        var tray = multi ? multi.querySelector('.cat-tray') : null;
        if (!tray) return;
        var set = {};
        (cats || []).forEach(function (c) { set[c] = true; });
        tray.querySelectorAll('.cat-opt').forEach(function (btn) {
            var on = !!set[btn.getAttribute('data-slug')];
            btn.setAttribute('aria-checked', on ? 'true' : 'false');
            btn.classList.toggle('selected', on);
        });
    }

    function getSelectedCatsFromPopover(trayEl) {
        var cats = [];
        trayEl.querySelectorAll('.cat-opt.selected').forEach(function (btn) {
            cats.push(btn.getAttribute('data-slug'));
        });
        return cats;
    }

    document.addEventListener('click', function (e) {
        var t = e.target;
        if (!t || !t.closest) return;

        var trigger = t.closest('.cat-trigger');
        if (trigger) {
            e.preventDefault();
            e.stopPropagation();
            var multi = trigger.closest('.cat-multi');
            var tray = multi ? multi.querySelector('.cat-tray') : null;
            if (!tray) return;
            if (tray.classList.contains('open')) {
                closeCatTray(trigger);
            } else {
                openCatTray(trigger);
            }
            return;
        }

        var opt = t.closest('.cat-opt');
        if (opt) {
            e.preventDefault();
            e.stopPropagation();
            var on = opt.getAttribute('aria-checked') === 'true';
            opt.setAttribute('aria-checked', on ? 'false' : 'true');
            opt.classList.toggle('selected', !on);
            var multiO = opt.closest('.cat-multi');
            var docIdO = multiO ? multiO.getAttribute('data-doc-id') : null;
            if (docIdO) {
                var trayO = multiO.querySelector('.cat-tray');
                saveCategories(docIdO, getSelectedCatsFromPopover(trayO), trayO);
            }
            return;
        }

        var clearBtn = t.closest('.cat-clear');
        if (clearBtn) {
            e.preventDefault();
            e.stopPropagation();
            var multiC = clearBtn.closest('.cat-multi');
            var trayC = multiC ? multiC.querySelector('.cat-tray') : null;
            if (trayC) {
                trayC.querySelectorAll('.cat-opt.selected').forEach(function (b) {
                    b.setAttribute('aria-checked', 'false');
                    b.classList.remove('selected');
                });
                saveCategories(clearBtn.getAttribute('data-doc-id'), [], trayC);
            }
            return;
        }

        var doneBtn = t.closest('.cat-done');
        if (doneBtn) {
            e.preventDefault();
            e.stopPropagation();
            var multiD = doneBtn.closest('.cat-multi');
            if (multiD) {
                var trg = multiD.querySelector('.cat-trigger');
                if (trg) closeCatTray(trg);
            }
            return;
        }

        // Click outside any tray closes open trays
        if (!t.closest('.cat-tray') && !t.closest('.cat-trigger')) {
            closeAllCatPopovers(null);
        }

        var openBtn = t.closest('[data-doc-open]');
        if (openBtn) {
            e.preventDefault();
            openDoc(openBtn.getAttribute('data-doc-open'));
            return;
        }

        if (t.closest('.cat-multi, .cat-chips, .cat-save-status, .cat-badge, select, option, label, button')) {
            return;
        }

        var item = t.closest('.doc-item[data-doc-link]');
        if (item) openDoc(item.getAttribute('data-doc-link'));
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            var openTray = document.querySelector('.cat-tray.open');
            if (openTray) {
                var owner = openTray.closest('.cat-multi');
                if (owner) {
                    var trgE = owner.querySelector('.cat-trigger');
                    if (trgE) closeCatTray(trgE);
                }
            }
            return;
        }
        if (e.key !== 'Enter' && e.key !== ' ') return;
        var t = e.target;
        if (t && t.closest && t.closest('.cat-multi, select, option, label, button, input, textarea')) return;
        var item = t && t.closest ? t.closest('.doc-item[data-doc-link]') : null;
        if (item) {
            e.preventDefault();
            openDoc(item.getAttribute('data-doc-link'));
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        document.getElementById('adminContent').style.display = 'block';
        setupDeployButton();
        setupChangesButton();
        loadCategories().then(function () {
            loadDocuments();
        });
    });
})();
