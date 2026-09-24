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
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
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
        return data
    except Exception as e:
        return {'documents': [], 'total_count': 0, 'source': None, 'error': str(e)}


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
        clean = url_path.split('?', 1)[0]
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
        injected = (
            '<meta name="robots" content="noindex,nofollow">\n'
            f'<script>window.__SERVE_TOKEN__={json.dumps(SERVE_TOKEN)};</script>'
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
        elif path == '/admin-panel.html':
            if not self._origin_allowed():
                self._deny(403, 'Forbidden origin.')
                return
            self._serve_admin_panel()
        else:
            self._serve_static()

    def do_POST(self):
        path = self.path.split('?', 1)[0]
        if path not in ('/api/rebuild', '/api/deploy'):
            self.send_error(404, 'Not found')
            return
        if not self._authorize_api():
            self._deny(403, 'Forbidden: missing or invalid token/origin.')
            return
        if path == '/api/rebuild':
            self._handle_rebuild()
        else:
            self._handle_deploy()

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
    args = parser.parse_args()
    SERVER_PORT = args.port

    if not DOCS_DIR.exists():
        print(f'[SERVER] docs/ not found. Running initial build...')
        subprocess.run([sys.executable, str(SCRIPT_DIR / 'build.py')], cwd=str(BASE_DIR))

    server = HTTPServer((SERVER_HOST, args.port), DevHandler)
    print(f'[SERVER] Serving docs/ at http://localhost:{args.port} (127.0.0.1 only)')
    print(f'[SERVER] Admin panel: http://localhost:{args.port}/admin-panel.html')
    print(f'[SERVER] API token (X-Serve-Token): {SERVE_TOKEN}')
    print('[SERVER] API endpoints (token required):')
    print('  GET  /api/changes        - Changes since last build')
    print('  GET  /api/documents      - Full document list (incl. hidden)')
    print('  POST /api/rebuild        - Trigger rebuild')
    print('  POST /api/deploy         - Rebuild + git push')
    print('[SERVER] Press Ctrl+C to stop.\n')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[SERVER] Stopped.')
        server.server_close()


if __name__ == '__main__':
    main()
