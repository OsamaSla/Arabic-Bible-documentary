/**
 * Local-only admin panel logic.
 * Token is injected by scripts/serve.py as window.__SERVE_TOKEN__.
 */

(function () {
    'use strict';

    var currentSearchQuery = '';
    var filterCompletedActive = false;
    var filterHiddenActive = false;

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

    function postApi(path) {
        return fetch(path, { method: 'POST', headers: apiHeaders() }).then(function (res) {
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
                    throw new Error((result.data && result.data.message) || ('HTTP ' + result.status));
                }
                var docs = result.data.documents || [];
                window.__allDocs = docs;
                applyFiltersAndRender();
                setupControls();
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

        if (!btnAll._listenerAdded) {
            btnAll._listenerAdded = true;
            btnAll.addEventListener('click', function () {
                btnAll.classList.add('active');
                filterCompletedActive = false;
                filterHiddenActive = false;
                btnCompleted.classList.remove('active');
                btnHidden.classList.remove('active');
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
    }

    function applyFiltersAndRender() {
        var docs = window.__allDocs || [];

        if (currentSearchQuery) {
            docs = docs.filter(function (d) {
                return (d.title && d.title.toLowerCase().includes(currentSearchQuery)) ||
                       (d.id && d.id.toLowerCase().includes(currentSearchQuery)) ||
                       (d.author && d.author.toLowerCase().includes(currentSearchQuery));
            });
        }

        var btnAllActive = document.getElementById('btnAll').classList.contains('active');

        docs = docs.filter(function (d) {
            var isCompleted = !!(d.completed || false);
            var isHidden = !!(d.hidden || false);

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
            container.innerHTML = '<p>No documents found.</p>';
            return;
        }

        var html = '';
        docs.forEach(function (doc) {
            var isCompleted = !!(doc.completed || false);
            var isHidden = !!(doc.hidden || false);
            var link = escapeHtml(safePath(doc.html_path || ''));

            html += '<div class="doc-item' + (isHidden ? ' hidden-doc' : '') +
                '" data-doc-id="' + escapeHtml(doc.id) +
                '" data-doc-link="' + link +
                '" role="link" tabindex="0">' +
                '<strong>ID:</strong> ' + escapeHtml(doc.id) + ' | ' +
                '<strong>Title:</strong> ' + escapeHtml(doc.title || 'N/A') + ' | ' +
                '<strong>Author:</strong> ' + escapeHtml(doc.author || 'N/A') + '<br>' +
                '<span class="status-badge ' + (isCompleted ? 'completed-on">✓ مكتمل' : 'completed-off">○ قيد الترجمة') + '</span> ' +
                '<span class="status-badge ' + (isHidden ? 'hidden-on">Hidden' : 'hidden-off">Visible') + '</span>' +
                '</div>';
        });
        container.innerHTML = html;
    }

    document.addEventListener('click', function (e) {
        var item = e.target && e.target.closest ? e.target.closest('.doc-item[data-doc-link]') : null;
        if (item) openDoc(item.getAttribute('data-doc-link'));
    });

    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        var item = e.target && e.target.closest ? e.target.closest('.doc-item[data-doc-link]') : null;
        if (item) {
            e.preventDefault();
            openDoc(item.getAttribute('data-doc-link'));
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        document.getElementById('adminContent').style.display = 'block';
        setupDeployButton();
        setupChangesButton();
        loadDocuments();
    });
})();
