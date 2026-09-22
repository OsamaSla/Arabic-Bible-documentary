#!/usr/bin/env python3
"""Shared git add/commit/push helper for auto-deploy flows."""

import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def git_add_commit_push(message=None, cwd=None):
    """Stage all changes, commit if needed, and push.

    Returns:
        (ok: bool, detail: str)
    """
    cwd = str(cwd or BASE_DIR)
    if message is None:
        message = f'Auto-deploy: rebuild site ({datetime.now().strftime("%Y-%m-%d %H:%M")})'

    try:
        add = subprocess.run(
            ['git', 'add', '-A'],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=60,
        )
        if add.returncode != 0:
            return False, (add.stderr or add.stdout or 'git add failed').strip()

        status = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30,
        )
        if status.returncode != 0:
            return False, (status.stderr or status.stdout or 'git status failed').strip()
        if not status.stdout.strip():
            return True, 'No changes to push.'

        commit = subprocess.run(
            ['git', 'commit', '-m', message],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=60,
        )
        if commit.returncode != 0:
            return False, (commit.stderr or commit.stdout or 'git commit failed').strip()

        branch = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=15,
        )
        branch_name = (branch.stdout or 'main').strip() or 'main'

        push = subprocess.run(
            ['git', 'push', 'origin', branch_name],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=120,
        )
        if push.returncode != 0:
            return False, (push.stderr or push.stdout or 'git push failed').strip()

        return True, f'Pushed to origin/{branch_name}.'
    except subprocess.TimeoutExpired as e:
        return False, f'git timed out: {e}'
    except FileNotFoundError:
        return False, 'git not found on PATH.'
    except Exception as e:
        return False, f'git error: {e}'
