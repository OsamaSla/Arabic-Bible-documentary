#!/usr/bin/env python3
"""Verify multi-category output + 404 fix + API."""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = Path(__file__).resolve().parent.parent

# 1) index.json categories[]
idx = json.loads((BASE / 'docs' / 'documents' / 'index.json').read_text(encoding='utf-8'))
docs = idx['documents']
has_cats = sum(1 for d in docs if isinstance(d.get('categories'), list) and d['categories'])
legacy_ok = sum(1 for d in docs if isinstance(d.get('category'), str))
multi = [d for d in docs if isinstance(d.get('categories'), list) and len(d['categories']) > 1]
print(f'[1] index docs={len(docs)} with categories[]={has_cats} legacy category str={legacy_ok} multi={len(multi)}')
if multi:
    print('    multi sample:', multi[0]['id'], multi[0]['categories'], multi[0].get('category'))

# 2) data-visible.js contains categories
dv = (BASE / 'docs' / 'js' / 'data-visible.js').read_text(encoding='utf-8')
has_cat_field = 'categories' in dv
print(f'[2] data-visible has categories field: {has_cat_field}')

# 3) Per-book membership counts (sum may > docs)
from collections import Counter
cnt = Counter()
for d in docs:
    for c in (d.get('categories') or []):
        cnt[c] += 1
print(f'[3] unique cats in index={len(cnt)} total memberships={sum(cnt.values())} (docs={len(docs)})')
print('    top5:', cnt.most_common(5))

# 4) Start server and test 404 + API
import subprocess
port = 8771
proc = subprocess.Popen(
    [sys.executable, '-u', str(BASE / 'scripts' / 'serve.py'), '--port', str(port)],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    cwd=str(BASE),
)
token = None
try:
    # Read token line from stdout (non-blocking-ish with timeout via poll)
    deadline = time.time() + 15
    buf = b''
    while time.time() < deadline and token is None:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.1)
            continue
        sys.stdout.write('[serve] ' + line.decode('utf-8', 'replace'))
        if b'Token' in line or b'token' in line:
            # extract token-like string
            text = line.decode('utf-8', 'replace')
            for part in text.replace(':', ' ').replace('=', ' ').split():
                if len(part) >= 16 and part.isalnum():
                    token = part
                    break
            if token is None and ':' in text:
                token = text.split(':', 1)[1].strip()

    if token is None:
        # try whole buffer approach - read more lines
        deadline2 = time.time() + 5
        while time.time() < deadline2 and token is None:
            line = proc.stdout.readline()
            if not line:
                break
            text = line.decode('utf-8', 'replace')
            sys.stdout.write('[serve] ' + text)
            if 'token' in text.lower():
                token = text.split()[-1]

    print('[4] token:', (token[:8] + '...') if token else 'NONE')

    # Find an Arabic html_path
    target = None
    for d in docs:
        p = d.get('html_path') or ''
        if p and any(ord(c) > 127 for c in p):
            target = p
            break
    if not target:
        for d in docs:
            p = d.get('html_path') or ''
            if p:
                target = p
                break
    print('[5] test path:', target)
    url = 'http://127.0.0.1:%d/%s' % (port, urllib.parse.quote(target, safe='/'))
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            body = r.read(200)
            print(f'[5] GET Arabic path -> {r.status} bytes_sample={len(body)} OK')
    except urllib.error.HTTPError as e:
        print(f'[5] GET Arabic path -> HTTP {e.code} FAIL')
    except Exception as e:
        print('[5] ERROR', e)

    # ASCII path too
    ascii_target = next((d.get('html_path') for d in docs if d.get('html_path') and all(ord(c) < 128 for c in d['html_path'])), None)
    if ascii_target:
        url2 = 'http://127.0.0.1:%d/%s' % (port, urllib.parse.quote(ascii_target, safe='/'))
        try:
            with urllib.request.urlopen(url2, timeout=5) as r:
                print(f'[6] GET ASCII path -> {r.status} OK')
        except urllib.error.HTTPError as e:
            print(f'[6] GET ASCII path -> HTTP {e.code}')

    # API GET categories
    def api(path, data=None, tok=None):
        req = urllib.request.Request('http://127.0.0.1:%d%s' % (port, path), method='POST' if data is not None else 'GET')
        if tok:
            req.add_header('X-Serve-Token', tok)
        if data is not None:
            req.add_header('Content-Type', 'application/json')
            req.data = json.dumps(data).encode('utf-8')
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            raw = e.read().decode('utf-8', 'replace')
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, {'raw': raw[:200]}

    # GET without token should 403
    st, body = api('/api/categories')
    print(f'[7] GET no token -> {st}')

    if token:
        st, body = api('/api/categories', tok=token)
        assigns = body.get('assignments', {}) if isinstance(body, dict) else {}
        sample = list(assigns.items())[:2]
        print(f'[8] GET with token -> {st} assignments={len(assigns)} sample={sample}')
        all_lists = all(isinstance(v, list) for v in assigns.values())
        print(f'    all assignment values are lists: {all_lists}')

        # POST multi categories
        st, body = api('/api/categories', {'docId': 'doc_0000', 'categories': ['yuanna', 'gospel']}, token)
        print(f'[9] POST multi -> {st} ok={body.get("ok")} msg={body.get("message")}')
        st, body = api('/api/categories', tok=token)
        v = (body.get('assignments') or {}).get('doc_0000')
        print(f'    readback doc_0000 = {v}')

        # invalid slug
        st, body = api('/api/categories', {'docId': 'doc_0000', 'categories': ['not-a-real-slug']}, token)
        print(f'[10] POST invalid slug -> {st} msg={body.get("message")}')

        # clear
        st, body = api('/api/categories', {'docId': 'doc_0000', 'categories': []}, token)
        print(f'[11] POST clear -> {st} ok={body.get("ok")}')
        st, body = api('/api/categories', tok=token)
        print(f'    readback after clear = {(body.get("assignments") or {}).get("doc_0000")}')

        # restore original
        st, body = api('/api/categories', {'docId': 'doc_0000', 'categories': ['yuanna']}, token)
        print(f'[12] restore doc_0000 -> {st} ok={body.get("ok")}')
except Exception as e:
    print('TEST ERROR:', type(e).__name__, e)
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
