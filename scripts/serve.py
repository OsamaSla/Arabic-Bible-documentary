#!/usr/bin/env python3
"""
Local dev server with auto-rebuild.

Usage:
    python scripts/serve.py
    python scripts/serve.py --port 8080

Security:
  - Binds 127.0.0.1 only (not reachable from the LAN)
  - All /api/* routes require a per-run secret token (X-Serve-Token)
  - Browser requests must send a localhost Origin (blocks cross-site CSRF)
  - No CORS headers are emitted
  - Admin pages are served from the repo root (never published to docs/)

Features:
  - Serves docs/ as a static site
  - Serves local-only admin panel + hidden documents
  - GET  /api/changes        -> source + git changes since last build
  - GET  /api/documents      -> full document list (incl. hidden)
  - GET  /api/categories     -> category vocabulary + current assignments
  - POST /api/categories     -> save one or more doc category assignments
  - POST /api/rebuild        -> triggers a full rebuild
  - POST /api/deploy         -> rebuild + git add/commit/push
"""

import sys
import io
import json
import hmac
import secrets
import subprocess
import argparse
import webbrowser
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent
DOCS_DIR = BASE_DIR / 'docs'
SCRIPT_DIR = BASE_DIR / 'scripts'
SOURCE_DIR = Path(r'D:\MegaDrive\ترجمات')
LAST_BUILD_PATH = BASE_DIR / '.last_build'
LOCAL_HIDDEN_DIR = BASE_DIR / 'local-hidden'
ADMIN_PANEL_PATH = BASE_DIR / 'admin-panel.html'
ADMIN_JS_PATH = BASE_DIR / 'js' / 'admin-ui.js'
CATEGORIES_VOCAB_PATH = BASE_DIR / 'categories.json'
DOC_CATEGORIES_PATH = BASE_DIR / 'doc_categories.json'
SERVE_TOKEN = secrets.token_urlsafe(32)
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 8000

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from git_ops import git_add_commit_push

_MIME = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.ico': 'image/x-icon',
    '.woff2': 'font/woff2',
    '.woff': 'font/woff',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.txt': 'text/plain; charset=utf-8',
    '.xml': 'application/xml; charset=utf-8',
}


def _read_last_build():
    if not LAST_BUILD_PATH.exists():
        return None, None
    raw = LAST_BUILD_PATH.read_text(encoding='utf-8').strip()
    try:
        return raw, datetime.fromisoformat(raw)
    except ValueError:
        return raw, None


def _collect_source_changes(since_dt):
    """Return .docx paths under SOURCE_DIR modified after since_dt."""
    if not SOURCE_DIR.exists() or since_dt is None:
        return []
    cutoff = since_dt.timestamp()
    changed = []
    for f in SOURCE_DIR.rglob('*.docx'):
        try:
            if f.stat().st_mtime > cutoff:
                rel = str(f.relative_to(SOURCE_DIR))
                mtime = datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec='seconds')
                changed.append({'path': rel, 'modified': mtime})
        except OSError:
            continue
    changed.sort(key=lambda x: x['modified'], reverse=True)
    return changed


def _collect_git_changes():
    try:
        status = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=15,
        )
        if status.returncode != 0:
            return []
        lines = [ln for ln in status.stdout.splitlines() if ln.strip()]
        return lines[:200]
    except Exception:
        return []


def _collect_git_log(limit=5):
    try:
        log = subprocess.run(
            ['git', 'log', f'-{limit}', '--date=iso', '--pretty=format:%h|%ad|%s'],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=15,
        )
        if log.returncode != 0:
            return []
        commits = []
        for ln in log.stdout.splitlines():
            if '|' not in ln:
                continue
            sha, date, subject = ln.split('|', 2)
            commits.append({'sha': sha, 'date': date, 'subject': subject})
        return commits
    except Exception:
        return []


def _as_category_list(value):
    """Normalize assignment value: str | list | None -> list of slugs."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value and value != 'uncategorized' else []
    if isinstance(value, list):
        return [str(v) for v in value if v and v != 'uncategorized']
    return []


def _load_documents_payload():
    """Full document list for the local admin panel (includes hidden docs)."""
    admin_index = LOCAL_HIDDEN_DIR / 'documents-index.json'
    public_index = DOCS_DIR / 'documents' / 'index.json'
    path = admin_index if admin_index.exists() else public_index
    if not path.exists():
        return {'documents': [], 'total_count': 0, 'source': None}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['source'] = str(path.name)
        # Overlay live assignments so admin sees unsaved-to-index changes
        assignments = _load_assignments()
        if assignments:
            for doc in data.get('documents', []):
                raw = assignments.get(doc.get('id', ''))
                if raw is None:
                    raw = assignments.get(doc.get('filename', ''))
                cats = _as_category_list(raw) if raw is not None else _as_category_list(doc.get('categories') or doc.get('category'))
                if raw is not None or 'categories' not in doc:
                    doc['categories'] = cats
                doc['category'] = cats[0] if cats else 'uncategorized'
        else:
            for doc in data.get('documents', []):
                cats = _as_category_list(doc.get('categories') or doc.get('category'))
                doc['categories'] = cats
                doc['category'] = cats[0] if cats else 'uncategorized'
        return data
    except Exception as e:
        return {'documents': [], 'total_count': 0, 'source': None, 'error': str(e)}


def _load_vocabulary():
    if not CATEGORIES_VOCAB_PATH.exists():
        return {}
    try:
        with open(CATEGORIES_VOCAB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _load_assignments():
    if not DOC_CATEGORIES_PATH.exists():
        return {}
    try:
        with open(DOC_CATEGORIES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        raw = data.get('assignments', {}) or {}
        # Normalize every value to a list
        return {k: _as_category_list(v) for k, v in raw.items() if _as_category_list(v)}
    except Exception:
        return {}


def _valid_category_slugs(vocab):
    slugs = {'uncategorized'}
    for group in (vocab.get('categories') or {}).values():
        for book in group.get('books', []) or []:
            slug = book.get('slug')
            if slug:
                slugs.add(slug)
    return slugs


def _save_assignments(assignments):
    payload = {
        '_comment': 'Map document IDs or filenames to arrays of category slugs. Managed by scripts/autocategorize.py + admin panel.',
        'assignments': {k: _as_category_list(assignments[k]) for k in sorted(assignments.keys()) if _as_category_list(assignments[k])},
    }
    tmp = DOC_CATEGORIES_PATH.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write('\n')
    tmp.replace(DOC_CATEGORIES_PATH)


class DevHandler(BaseHTTPRequestHandler):
    """Serves docs/, local-only admin files, and token-gated API routes."""

    server_version = 'DevServer'

    # ---- security helpers ----

    def _origin_allowed(self):
        origin = self.headers.get('Origin')
        if not origin:
            return True
        try:
            parsed = urlparse(origin)
        except Exception:
            return False
        host = parsed.hostname or ''
        return host in ('localhost', '127.0.0.1', '::1')

    def _authorize_api(self):
        if not self._origin_allowed():
            return False
        provided = self.headers.get('X-Serve-Token', '')
        return hmac.compare_digest(provided, SERVE_TOKEN)

    def _deny(self, code, message):
        body = json.dumps({'ok': False, 'message': message}, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _json_response(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, cache=False):
        if not path.is_file():
            self.send_error(404, 'Not found')
            return
        try:
            data = path.read_bytes()
        except OSError:
            self.send_error(500, 'Cannot read file')
            return
        ctype = _MIME.get(path.suffix.lower(), 'application/octet-stream')
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        if not cache:
            self.send_header('Cache-Control', 'no-store')
        if path.suffix == '.html':
            self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def _resolve_static(self, url_path):
        """Map a URL path to a file under docs/, local-hidden/, or local admin files."""
        # Decode percent-encoding first (Arabic/German folder names), then check traversal
        clean = unquote(url_path.split('?', 1)[0])
        # prevent traversal
        if '..' in clean or '\x00' in clean:
            return None
        if clean in ('/admin-panel.html', '/admin.html'):
            if clean == '/admin-panel.html':
                return ADMIN_PANEL_PATH
            return None  # admin.html is no longer served
        if clean == '/js/admin-ui.js':
            return ADMIN_JS_PATH
        if clean.startswith('/local-hidden/'):
            rel = clean[len('/local-hidden/'):]
            return LOCAL_HIDDEN_DIR / rel
        if clean == '/':
            clean = '/index.html'
        return DOCS_DIR / clean.lstrip('/')

    def _serve_admin_panel(self):
        if not ADMIN_PANEL_PATH.is_file():
            self.send_error(404, 'Not found')
            return
        html = ADMIN_PANEL_PATH.read_text(encoding='utf-8')
        # Meta tag (CSP-safe: script-src 'self' blocks inline <script>)
        injected = (
            '<meta name="robots" content="noindex,nofollow">\n'
            f'<meta name="serve-token" content="{SERVE_TOKEN}">'
        )
        if '</head>' in html:
            html = html.replace('</head>', injected + '\n</head>', 1)
        else:
            html = injected + html
        data = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    # ---- HTTP verbs ----

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/api/changes':
            if not self._authorize_api():
                self._deny(403, 'Forbidden: missing or invalid token/origin.')
                return
            self._handle_changes()
        elif path == '/api/documents':
            if not self._authorize_api():
                self._deny(403, 'Forbidden: missing or invalid token/origin.')
                return
            self._handle_documents()
        elif path == '/api/categories':
            if not self._authorize_api():
                self._deny(403, 'Forbidden: missing or invalid token/origin.')
                return
            self._handle_categories_get()
        elif path == '/admin-panel.html':
            if not self._origin_allowed():
                self._deny(403, 'Forbidden origin.')
                return
            self._serve_admin_panel()
        else:
            self._serve_static()

    def do_POST(self):
        path = self.path.split('?', 1)[0]
        if path not in ('/api/rebuild', '/api/deploy', '/api/categories'):
            self.send_error(404, 'Not found')
            return
        if not self._authorize_api():
            self._deny(403, 'Forbidden: missing or invalid token/origin.')
            return
        if path == '/api/rebuild':
            self._handle_rebuild()
        elif path == '/api/categories':
            self._handle_categories_post()
        else:
            self._handle_deploy()

    def _read_json_body(self):
        length = int(self.headers.get('Content-Length') or 0)
        if length <= 0 or length > 1_000_000:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return None

    def _serve_static(self):
        target = self._resolve_static(self.path)
        if target is None:
            self.send_error(403, 'Forbidden')
            return
        # only allow reads from known roots
        allowed_roots = [DOCS_DIR.resolve(), LOCAL_HIDDEN_DIR.resolve(), BASE_DIR.resolve()]
        try:
            resolved = target.resolve()
        except OSError:
            self.send_error(404, 'Not found')
            return
        if not any(str(resolved) == str(r) or str(resolved).startswith(str(r) + __import__('os').sep) for r in allowed_roots):
            self.send_error(403, 'Forbidden')
            return
        if str(resolved) == str(BASE_DIR.resolve() / 'admin-panel.html'):
            self._serve_admin_panel()
            return
        self._send_file(resolved, cache=True)

    # ---- API handlers ----

    def _handle_changes(self):
        raw, since_dt = _read_last_build()
        if since_dt is None:
            source_changes = _collect_source_changes(None)
            source_note = 'No .last_build stamp yet — showing nothing for source (run a build first).'
        else:
            source_changes = _collect_source_changes(since_dt)
            source_note = f'Source files modified after {raw}'

        payload = {
            'ok': True,
            'lastBuild': raw,
            'sourceNote': source_note,
            'sourceChanges': source_changes,
            'sourceCount': len(source_changes),
            'gitChanges': _collect_git_changes(),
            'recentCommits': _collect_git_log(),
            'checkedAt': datetime.now().isoformat(timespec='seconds'),
        }
        self._json_response(200, payload)

    def _handle_documents(self):
        payload = _load_documents_payload()
        payload['ok'] = True
        self._json_response(200, payload)

    def _handle_categories_get(self):
        vocab = _load_vocabulary()
        assignments = _load_assignments()
        docs_payload = _load_documents_payload()
        by_category = {}
        for doc in docs_payload.get('documents', []):
            cats = _as_category_list(doc.get('categories') or doc.get('category'))
            if not cats:
                by_category['uncategorized'] = by_category.get('uncategorized', 0) + 1
            else:
                for c in cats:
                    by_category[c] = by_category.get(c, 0) + 1
        self._json_response(200, {
            'ok': True,
            'vocabulary': vocab,
            'assignments': assignments,
            'counts': by_category,
            'total': docs_payload.get('total_count', 0),
        })

    def _handle_categories_post(self):
        body = self._read_json_body()
        if not isinstance(body, dict):
            self._json_response(400, {'ok': False, 'message': 'Invalid JSON body.'})
            return

        vocab = _load_vocabulary()
        valid = _valid_category_slugs(vocab)
        assignments = _load_assignments()

        # Accept: {docId, categories:[...]} | {docId, category: str|list} | {assignments:{id: cats}}
        updates = {}
        if 'docId' in body:
            if 'categories' in body:
                updates[str(body['docId'])] = body.get('categories')
            else:
                updates[str(body['docId'])] = body.get('category')
        if isinstance(body.get('assignments'), dict):
            for k, v in body['assignments'].items():
                updates[str(k)] = v

        if not updates:
            self._json_response(400, {'ok': False, 'message': 'No assignment provided.'})
            return

        applied = 0
        new_assignments = dict(assignments)
        for doc_id, raw_cats in updates.items():
            if not doc_id:
                continue
            cats = _as_category_list(raw_cats)
            invalid = [c for c in cats if c not in valid]
            if invalid:
                self._json_response(400, {
                    'ok': False,
                    'message': f'Unknown category slug(s): {", ".join(invalid)}',
                })
                return
            # de-dup preserve order
            seen = set()
            cats = [c for c in cats if not (c in seen or seen.add(c))]
            if cats:
                new_assignments[doc_id] = cats
            else:
                new_assignments.pop(doc_id, None)
            applied += 1

        try:
            _save_assignments(new_assignments)
        except OSError as e:
            self._json_response(500, {'ok': False, 'message': f'Write failed: {e}'})
            return

        print(f'[CAT] Saved {applied} assignment(s) -> doc_categories.json')
        self._json_response(200, {
            'ok': True,
            'message': f'Saved {applied} assignment(s). Rebuild to publish.',
            'assignments': new_assignments,
            'applied': applied,
        })

    def _handle_rebuild(self):
        success = self._run_build()
        if success:
            self._json_response(200, {'ok': True, 'message': 'Site rebuilt.'})
        else:
            self._json_response(500, {'ok': False, 'message': 'Build failed.'})

    def _handle_deploy(self):
        if not self._run_build():
            self._json_response(500, {'ok': False, 'message': 'Build failed.', 'pushed': False})
            return

        print('[SERVER] Pushing to GitHub...')
        ok, detail = git_add_commit_push()
        if ok:
            self._json_response(200, {
                'ok': True,
                'pushed': True,
                'message': f'Scanned source, rebuilt site. {detail}',
                'detail': detail,
            })
        else:
            self._json_response(500, {
                'ok': False,
                'pushed': False,
                'message': f'Scanned and rebuilt, but push failed: {detail}',
                'detail': detail,
            })

    def _run_build(self):
        print('[SERVER] Running build (scan source + regenerate)...')
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / 'build.py')],
                cwd=str(BASE_DIR),
                timeout=300,
            )
            success = result.returncode == 0
            if success:
                print('[SERVER] Build succeeded.')
            else:
                print(f'[SERVER] Build failed with code {result.returncode}')
            return success
        except subprocess.TimeoutExpired:
            print('[SERVER] Build timed out.')
            return False
        except Exception as e:
            print(f'[SERVER] Build error: {e}')
            return False

    def log_message(self, format, *args):
        if hasattr(self, 'path') and self.path.startswith('/api/'):
            return
        super().log_message(format, *args)


def main():
    global SERVER_PORT
    parser = argparse.ArgumentParser(description='Local dev server with auto-rebuild')
    parser.add_argument('--port', type=int, default=8000, help='Port to serve on (default: 8000)')
    parser.add_argument('--no-open', action='store_true', help='Do not auto-open the admin panel in the browser')
    args = parser.parse_args()
    SERVER_PORT = args.port

    if not DOCS_DIR.exists():
        print(f'[SERVER] docs/ not found. Running initial build...')
        subprocess.run([sys.executable, str(SCRIPT_DIR / 'build.py')], cwd=str(BASE_DIR))

    server = HTTPServer((SERVER_HOST, args.port), DevHandler)
    admin_url = f'http://{SERVER_HOST}:{args.port}/admin-panel.html'
    print(f'[SERVER] Serving docs/ at http://localhost:{args.port} (127.0.0.1 only)')
    print(f'[SERVER] Admin panel: {admin_url}')
    print(f'[SERVER] API token (X-Serve-Token): {SERVE_TOKEN}')
    print('[SERVER] API endpoints (token required):')
    print('  GET  /api/changes        - Changes since last build')
    print('  GET  /api/documents      - Full document list (incl. hidden)')
    print('  GET  /api/categories     - Category vocabulary + assignments')
    print('  POST /api/categories     - Save category assignment(s)')
    print('  POST /api/rebuild        - Trigger rebuild')
    print('  POST /api/deploy         - Rebuild + git push')
    print('[SERVER] Press Ctrl+C to stop.\n')
    sys.stdout.flush()
    sys.stderr.flush()

    if not args.no_open:
        def _open_browser():
            try:
                webbrowser.open(admin_url)
                print(f'[SERVER] Opened {admin_url}')
            except Exception as e:
                print(f'[SERVER] Could not open browser: {e}. Open manually: {admin_url}')
        threading.Timer(0.4, _open_browser).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[SERVER] Stopped.')
        server.server_close()


if __name__ == '__main__':
    main()
