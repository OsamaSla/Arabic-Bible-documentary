#!/usr/bin/env python3
"""
Local dev server with auto-rebuild.

Usage:
    python scripts/serve.py
    python scripts/serve.py --port 8080

Features:
  - Serves docs/ as a static site
  - GET  /api/changes        -> source + git changes since last build
  - POST /api/rebuild        -> triggers a full rebuild
  - POST /api/deploy         -> rebuild + git add/commit/push
"""

import sys
import io
import json
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent
DOCS_DIR = BASE_DIR / 'docs'
SCRIPT_DIR = BASE_DIR / 'scripts'
SOURCE_DIR = Path(r'D:\MegaDrive\ترجمات')
LAST_BUILD_PATH = BASE_DIR / '.last_build'
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from git_ops import git_add_commit_push


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


class DevHandler(SimpleHTTPRequestHandler):
    """Custom handler that serves from docs/ and handles API routes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOCS_DIR), **kwargs)

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/api/changes':
            self._handle_changes()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.split('?', 1)[0] == '/api/rebuild':
            self._handle_rebuild()
        elif self.path.split('?', 1)[0] == '/api/deploy':
            self._handle_deploy()
        else:
            self.send_error(404, 'Not found')

    def _handle_changes(self):
        """Report source + repo changes since the last successful build."""
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

    def _handle_rebuild(self):
        """Trigger a full rebuild (scan source + regenerate docs/)."""
        success = self._run_build()
        if success:
            self._json_response(200, {'ok': True, 'message': 'Site rebuilt.'})
        else:
            self._json_response(500, {'ok': False, 'message': 'Build failed.'})

    def _handle_deploy(self):
        """Scan source + rebuild (same as one watch cycle), then push."""
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
        """Run build.py (converts source tree into docs/)."""
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

    def _json_response(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        # Suppress default access logs for API endpoints
        if hasattr(self, 'path') and self.path.startswith('/api/'):
            return
        super().log_message(format, *args)


def main():
    parser = argparse.ArgumentParser(description='Local dev server with auto-rebuild')
    parser.add_argument('--port', type=int, default=8000, help='Port to serve on (default: 8000)')
    args = parser.parse_args()

    # Ensure docs/ exists
    if not DOCS_DIR.exists():
        print(f'[SERVER] docs/ not found. Running initial build...')
        subprocess.run([sys.executable, str(SCRIPT_DIR / 'build.py')], cwd=str(BASE_DIR))

    server = HTTPServer(('0.0.0.0', args.port), DevHandler)
    print(f'[SERVER] Serving docs/ at http://localhost:{args.port}')
    print(f'[SERVER] Open admin: http://localhost:{args.port}/admin-panel.html')
    print(f'[SERVER] API endpoints:')
    print(f'  GET  /api/changes        - Changes since last build')
    print(f'  POST /api/rebuild        - Trigger rebuild')
    print(f'  POST /api/deploy         - Rebuild + git push')
    print(f'[SERVER] Press Ctrl+C to stop.\n')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[SERVER] Stopped.')
        server.server_close()


if __name__ == '__main__':
    main()
