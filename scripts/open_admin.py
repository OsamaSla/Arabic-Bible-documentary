#!/usr/bin/env python3
"""Launcher: ensure the local admin server is up, then open the panel.

Safe to double-click anytime: if the server already runs, it just opens
the browser. If not, it starts the server (background, no console window)
and waits until it answers before opening the panel.
Usage: open_admin.py [--no-open]
"""
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
HOST, PORT = '127.0.0.1', 8000
URL = f'http://{HOST}:{PORT}/admin-panel.html'


def port_open():
    try:
        with socket.create_connection((HOST, PORT), timeout=2):
            return True
    except OSError:
        return False


def main():
    no_open = '--no-open' in sys.argv
    if not port_open():
        print('Starting local server...', flush=True)
        subprocess.Popen(
            [sys.executable, str(BASE_DIR / 'scripts' / 'serve.py'), '--no-open'],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(150):  # up to ~5 min (first run may build the site)
            time.sleep(2)
            if port_open():
                break
        else:
            print('Server did not answer in time.', flush=True)
            return 1
    if not no_open:
        webbrowser.open(URL)
    return 0


if __name__ == '__main__':
    sys.exit(main())
