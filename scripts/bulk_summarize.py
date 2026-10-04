#!/usr/bin/env python3
"""Bulk-generate AI summaries for all documents via local Ollama.

Usage:
    python scripts/bulk_summarize.py              # skip docs that already have ai_summary
    python scripts/bulk_summarize.py --force      # regenerate all
    python scripts/bulk_summarize.py --limit 10   # only process first 10
    python scripts/bulk_summarize.py --dry-run    # show what would be processed
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DOCS_DIR = BASE_DIR / 'docs'
LOCAL_HIDDEN_DIR = BASE_DIR / 'local-hidden'
OLLAMA_URL = 'http://localhost:11434/api/generate'
MODEL = 'qwen3:8b'

PROMPT_TEMPLATE = (
    'لخص النص التالي في جملة عربية واحدة لا تتجاوز 40 كلمة تنتهي بعلامة ترقيم. '
    'لخص فقط ما ورد في النص، ممنوع اختراع أسماء أو شواهد أو تفاصيل غير مذكورة. النص: '
)


def extract_article_text(html_path: Path) -> str:
    if not html_path.exists():
        return ''
    html = html_path.read_text(encoding='utf-8')
    m = re.search(r'<article class="document-content"[^>]*>([\s\S]*?)</article>', html)
    if not m:
        return ''
    text = re.sub(r'<[^>]+>', ' ', m.group(1))
    return re.sub(r'\s+', ' ', text).strip()


def call_ollama(text: str) -> str:
    payload = json.dumps({
        'model': MODEL,
        'think': False,
        'prompt': PROMPT_TEMPLATE + text[:5000],
        'stream': False,
        'options': {'temperature': 0.2, 'num_predict': 120},
    }, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    summary = (data.get('response') or '').strip()
    if not summary:
        raise RuntimeError('Empty response from Ollama')
    if summary[-1:] not in '.?!…':
        summary += '.'
    return summary


def load_index(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_index(path: Path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def patch_data_visible(doc_id: str, ai_summary: str):
    dv_path = DOCS_DIR / 'js' / 'data-visible.js'
    if not dv_path.exists():
        return
    text = dv_path.read_text(encoding='utf-8')
    md = 'window.__DOCUMENTS_DATA__ = '
    mc = ';\nwindow.__CATEGORIES_DATA__ = '
    try:
        i = text.index(md) + len(md)
        j = text.index(mc)
    except ValueError:
        return
    embedded = json.loads(text[i:j])
    for d in embedded:
        if str(d.get('id')) == doc_id:
            d['ai_summary'] = ai_summary
            break
    newj = json.dumps(embedded, ensure_ascii=False)
    newj = newj.replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    dv_path.write_text(text[:i] + newj + text[j:], encoding='utf-8')


def patch_cards(doc_id: str, ai_summary: str):
    """Update homepage card and author pages with the new summary."""
    from convert import escape_html
    pub_idx = DOCS_DIR / 'documents' / 'index.json'
    if not pub_idx.exists():
        return
    data = load_index(pub_idx)
    doc = next((d for d in data.get('documents', []) if str(d.get('id')) == doc_id), None)
    if not doc:
        return
    html_path = doc.get('html_path', '')

    # Homepage
    home_path = DOCS_DIR / 'index.html'
    if home_path.exists():
        home_html = home_path.read_text(encoding='utf-8')
        m = re.search(
            r'<article class="rx-card"[^>]*data-rx-path="' + re.escape(html_path) + r'"[\s\S]*?</article>',
            home_html)
        if m:
            block = m.group(0)
            new_block = re.sub(
                r'data-rx-desc="[^"]*"',
                f'data-rx-desc="{escape_html(ai_summary)}"', block)
            new_block = re.sub(
                r'(<p class="rx-card-desc rx-clamp-3">)[^<]*(</p>)',
                r'\1' + escape_html(ai_summary) + r'\2', new_block)
            home_html = home_html[:m.start()] + new_block + home_html[m.end():]
            home_path.write_text(home_html, encoding='utf-8')

    # Author pages
    for auth_root in (DOCS_DIR / 'authors', LOCAL_HIDDEN_DIR / 'authors'):
        if not auth_root.exists():
            continue
        for auth_page in auth_root.rglob('index.html'):
            try:
                html = auth_page.read_text(encoding='utf-8')
                if html_path not in html:
                    continue
                new_html, n = re.subn(
                    r'(<div class="document-item">(?:(?!</div>).)*?href="../../' + re.escape(html_path)
                    + r'"(?:(?!</div>).)*?<p class="doc-desc">).*?(</p>)',
                    lambda m: m.group(1) + escape_html(ai_summary) + m.group(2),
                    html, flags=re.DOTALL)
                if n:
                    auth_page.write_text(new_html, encoding='utf-8')
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description='Bulk AI summary generation')
    parser.add_argument('--force', action='store_true', help='Regenerate even if ai_summary exists')
    parser.add_argument('--limit', type=int, default=0, help='Max docs to process (0 = all)')
    parser.add_argument('--dry-run', action='store_true', help='Show plan without processing')
    parser.add_argument('--delay', type=float, default=1.0, help='Seconds between requests')
    args = parser.parse_args()

    # Collect docs from both indexes
    docs = {}
    for idx_path in (LOCAL_HIDDEN_DIR / 'documents-index.json',
                     DOCS_DIR / 'documents' / 'index.json'):
        if not idx_path.exists():
            continue
        data = load_index(idx_path)
        for doc in data.get('documents', []):
            doc_id = str(doc.get('id'))
            if doc_id not in docs:
                docs[doc_id] = doc

    # Filter
    to_process = []
    for doc_id, doc in sorted(docs.items()):
        if not args.force and doc.get('ai_summary'):
            continue
        to_process.append(doc)

    if args.limit:
        to_process = to_process[:args.limit]

    total = len(to_process)
    print(f'Documents to process: {total}')
    if not to_process:
        print('Nothing to do.')
        return

    if args.dry_run:
        for i, doc in enumerate(to_process[:20], 1):
            print(f'  [{i}] {doc.get("id")} - {doc.get("title", "?")[:60]}')
        if total > 20:
            print(f'  ... and {total - 20} more')
        return

    # Check Ollama is reachable
    try:
        test_req = urllib.request.Request(
            'http://localhost:11434/api/tags', method='GET')
        with urllib.request.urlopen(test_req, timeout=5) as resp:
            models = json.loads(resp.read().decode('utf-8'))
        model_names = [m.get('name', '') for m in models.get('models', [])]
        if not any(MODEL in name for name in model_names):
            print(f'WARNING: model {MODEL} not found. Available: {model_names}')
            return
        print(f'Ollama OK, model {MODEL} found.')
    except Exception as e:
        print(f'Cannot reach Ollama at {OLLAMA_URL}: {e}')
        return

    # Process
    ok_count = 0
    fail_count = 0
    for i, doc in enumerate(to_process, 1):
        doc_id = str(doc.get('id'))
        title = doc.get('title', '?')[:50]
        html_path = DOCS_DIR / doc.get('html_path', '')

        print(f'[{i}/{total}] {doc_id} {title} ... ', end='', flush=True)

        text = extract_article_text(html_path)
        if not text:
            print('SKIP (no article text)')
            fail_count += 1
            continue

        try:
            summary = call_ollama(text)
        except Exception as e:
            print(f'FAIL ({e})')
            fail_count += 1
            continue

        # Update indexes
        for idx_path in (LOCAL_HIDDEN_DIR / 'documents-index.json',
                         DOCS_DIR / 'documents' / 'index.json'):
            if not idx_path.exists():
                continue
            data = load_index(idx_path)
            for d in data.get('documents', []):
                if str(d.get('id')) == doc_id:
                    d['ai_summary'] = summary
                    break
            save_index(idx_path, data)

        # Patch data-visible.js
        patch_data_visible(doc_id, summary)

        # Patch cards
        patch_cards(doc_id, summary)

        print(f'OK ({len(summary)} chars)')
        ok_count += 1

        if args.delay and i < total:
            time.sleep(args.delay)

    print(f'\nDone. {ok_count} succeeded, {fail_count} failed.')


if __name__ == '__main__':
    main()
