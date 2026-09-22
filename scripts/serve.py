#!/usr/bin/env python3
"""
Local dev server with auto-rebuild.

Usage:
    python scripts/serve.py
    python scripts/serve.py --port 8080

Features:
  - Serves docs/ as a static site
  - POST /api/rebuild         -> triggers a full rebuild
  - POST /api/deploy          -> rebuild + git add/commit/push
"""

import sys
import io
import json
import subprocess
import argparse
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent
DOCS_DIR = BASE_DIR / 'docs'
SCRIPT_DIR = BASE_DIR / 'scripts'
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from git_ops import git_add_commit_push


class DevHandler(SimpleHTTPRequestHandler):
    """Custom handler that serves from docs/ and handles API routes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOCS_DIR), **kwargs)

    def do_POST(self):
        if self.path == '/api/rebuild':
            self._handle_rebuild()
        elif self.path == '/api/deploy':
            self._handle_deploy()
        else:
            self.send_error(404, 'Not found')

    def _handle_rebuild(self):
        """Trigger a full rebuild."""
        success = self._run_build()
        if success:
            self._json_response(200, {'ok': True, 'message': 'Site rebuilt.'})
        else:
            self._json_response(500, {'ok': False, 'message': 'Build failed.'})

    def _handle_deploy(self):
        """Rebuild, then commit and push to GitHub."""
        if not self._run_build():
            self._json_response(500, {'ok': False, 'message': 'Build failed.', 'pushed': False})
            return

        print('[SERVER] Pushing to GitHub...')
        ok, detail = git_add_commit_push()
        if ok:
            self._json_response(200, {
                'ok': True,
                'pushed': True,
                'message': detail,
                'detail': detail,
            })
        else:
            self._json_response(500, {
                'ok': False,
                'pushed': False,
                'message': f'Push failed: {detail}',
                'detail': detail,
            })

    def _run_build(self):
        """Run build.py and return success/failure."""
        print('[SERVER] Running build...')
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
    print(f'[SERVER] API endpoints:')
    print(f'  POST /api/rebuild         - Trigger rebuild')
    print(f'  POST /api/deploy          - Rebuild + git push')
    print(f'[SERVER] Press Ctrl+C to stop.\n')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[SERVER] Stopped.')
        server.server_close()


if __name__ == '__main__':
    main()
