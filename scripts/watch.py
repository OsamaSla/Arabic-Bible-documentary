#!/usr/bin/env python3
"""
Watch script: monitors source files and auto-rebuilds on changes.
No extra dependencies required (uses polling, not watchdog).

Usage:
    python scripts/watch.py
    python scripts/watch.py --interval 5
    python scripts/watch.py --push
"""

import sys
import io
import time
import hashlib
import subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

SCRIPT_DIR = Path(__file__).parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from git_ops import git_add_commit_push

SOURCE_DIR = Path(r'D:\MegaDrive\ترجمات')
BASE_DIR = SCRIPT_DIR.parent
CONFIG_FILES = [
    BASE_DIR / 'categories.json',
    BASE_DIR / 'doc_categories.json',
]
TEMPLATE_DIR = BASE_DIR / 'templates'


def get_dir_hash(directory):
    """Get a hash of all .docx files' paths + mtimes in a directory."""
    if not directory.exists():
        return ''
    parts = []
    for f in sorted(directory.rglob('*.docx')):
        parts.append(f'{f}:{f.stat().st_mtime_ns}')
    return hashlib.md5('|'.join(parts).encode()).hexdigest()


def get_files_hash(files):
    """Get a hash of modification times for a list of files."""
    parts = []
    for f in files:
        if f.exists():
            parts.append(f'{f}:{f.stat().st_mtime_ns}')
    return hashlib.md5('|'.join(parts).encode()).hexdigest()


def run_build():
    """Run the build script."""
    print('\n[BUILD] Running build...')
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / 'build.py')],
        cwd=str(BASE_DIR),
    )
    if result.returncode == 0:
        print('[BUILD] Build completed successfully.')
    else:
        print(f'[BUILD] Build failed with code {result.returncode}')
    return result.returncode


def maybe_push(do_push, label='change'):
    """Commit and push after a successful build when --push is set."""
    if not do_push:
        return
    print(f'[PUSH] Deploying after {label}...')
    ok, detail = git_add_commit_push()
    if ok:
        print(f'[PUSH] {detail}')
    else:
        print(f'[PUSH] Failed: {detail}')


def main():
    interval = 3
    if '--interval' in sys.argv:
        idx = sys.argv.index('--interval')
        if idx + 1 < len(sys.argv):
            interval = int(sys.argv[idx + 1])
    do_push = '--push' in sys.argv

    print(f'[WATCH] Watching for changes every {interval}s...')
    print(f'[WATCH] Source: {SOURCE_DIR}')
    print(f'[WATCH] Config: {[str(f.name) for f in CONFIG_FILES]}')
    print(f'[WATCH] Templates: {TEMPLATE_DIR}')
    print(f'[WATCH] Auto-push: {"on" if do_push else "off"}')
    print('[WATCH] Press Ctrl+C to stop.\n')

    # Initial hash snapshot
    prev_source_hash = get_dir_hash(SOURCE_DIR)
    prev_config_hash = get_files_hash(CONFIG_FILES)
    prev_template_hash = get_dir_hash(TEMPLATE_DIR)

    # Run initial build
    if run_build() == 0:
        maybe_push(do_push, 'startup')

    try:
        while True:
            time.sleep(interval)

            curr_source_hash = get_dir_hash(SOURCE_DIR)
            curr_config_hash = get_files_hash(CONFIG_FILES)
            curr_template_hash = get_dir_hash(TEMPLATE_DIR)

            changes = []
            if curr_source_hash != prev_source_hash:
                changes.append('source documents')
                prev_source_hash = curr_source_hash

            if curr_config_hash != prev_config_hash:
                changes.append('config files')
                prev_config_hash = curr_config_hash

            if curr_template_hash != prev_template_hash:
                changes.append('templates')
                prev_template_hash = curr_template_hash

            if changes:
                label = ', '.join(changes)
                print(f'\n[WATCH] Changes detected: {label}')
                if run_build() == 0:
                    maybe_push(do_push, label)
                else:
                    print('[WATCH] Skipping push because build failed.')

    except KeyboardInterrupt:
        print('\n[WATCH] Stopped.')


if __name__ == '__main__':
    main()
