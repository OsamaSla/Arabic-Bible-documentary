#!/usr/bin/env python3
"""Verse / passage indexing for the static site build.

Extracts scripture references (Book, Chapter, Verse) from document
metadata (title + description) and builds a Book -> Chapter -> Documents
index that powers bibles.html and the document-page related-commentaries
sidebar.

Book-name vocabulary comes from categories.json (name_ar) plus the
curated Arabic alias lists in autocategorize.ALIASES. Only OT/NT books
are indexed (topics are book-less by definition).
"""

import json
import re
import unicodedata
from pathlib import Path

from autocategorize import ALIASES

# Bare gospel names collide with author names ("يوحنا داربي"), but in
# reference extraction a chapter digit must directly follow the book name,
# so the bare name_ar is safe there (e.g. "متى 5", "يوحنا 3:16").
BARE_UNTRUSTED = {'yuanna', 'matta', 'marqus', 'luqa'}

MAX_CHAPTER = 250       # Psalm 150 is the longest book
MAX_VERSE = 200
MAX_CHAPTER_SPAN = 12   # expand "يشوع 1-3" ranges at most this far
MAX_VERSE_SPAN = 60
MAX_REFS_PER_DOC = 30

_BOUNDARY_CLASSES = r'\w\u0600-\u06FF'

_REF_RE_CACHE = {}


def load_categories(base_dir):
    """Return the categories object from categories.json ({} when missing)."""
    path = Path(base_dir) / 'categories.json'
    if not path.exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f).get('categories', {})


def normalize_ref_text(text):
    """Arabic-friendly normalization that KEEPS digits, colon, dot, dash.

    Mirrors autocategorize.normalize() (diacritics/alef/ya/ta-marbuta
    folding) but preserves the punctuation structure of "_book 12: 3-5"
    references instead of blanking it.
    """
    if not text:
        return ''
    s = unicodedata.normalize('NFKC', str(text))
    s = re.sub(r'[\u064B-\u065F\u0670\u0640]', '', s)
    s = (s.replace('\u0622', '\u0627').replace('\u0623', '\u0627')
           .replace('\u0625', '\u0627'))
    s = s.replace('\u0649', '\u064A').replace('\u0629', '\u0647')
    s = s.replace('\u2014', '-').replace('\u2013', '-').replace('\u2212', '-')
    # Drop noise punctuation, keep letters, digits, ':', '.', '-'
    s = re.sub(r'[^\w\u0600-\u06FF:.\-]+', ' ', s, flags=re.UNICODE)
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s


def build_book_catalog(categories):
    """slug -> {name_ar, name_de, group, order, aliases} for OT/NT books."""
    catalog = {}
    for group_key in ('old_testament', 'new_testament'):
        group = categories.get(group_key) or {}
        for book in group.get('books', []):
            slug = book.get('slug')
            if not slug:
                continue
            names = []
            name_ar = book.get('name_ar', '')
            if name_ar and slug not in BARE_UNTRUSTED:
                names.append(name_ar)
            elif name_ar:
                names.append(name_ar)  # digit-anchored by the ref pattern
            for raw in ALIASES.get(slug, []):
                names.append(raw)
            aliases = []
            seen = set()
            for raw in names:
                norm = normalize_ref_text(raw)
                if norm and norm not in seen:
                    seen.add(norm)
                    aliases.append(norm)
            aliases.sort(key=len, reverse=True)
            catalog[slug] = {
                'name_ar': name_ar,
                'name_de': book.get('name_de', ''),
                'group': group_key,
                'order': book.get('order', 999),
                'aliases': aliases,
            }
    return catalog


def _ref_regex(alias):
    rx = _REF_RE_CACHE.get(alias)
    if rx is None:
        rx = re.compile(
            r'(?<![' + _BOUNDARY_CLASSES + r'])' + re.escape(alias) +
            r'\s*(?P<chapter>\d{1,3})(?!\d)'
            r'(?:'
            r'\s*:\s*(?P<verse>\d{1,3})(?!\d)'
            r'(?:\s*-\s*(?P<verse_end>\d{1,3})(?!\d))?'
            r'|'
            r'\s*-\s*(?P<chap_end>\d{1,3})(?!\d)'
            r')?'
        )
        _REF_RE_CACHE[alias] = rx
    return rx


def extract_doc_refs(doc, catalog):
    """Extract sorted refs [{b, c, ce?, v?, ve?}] from a document's metadata."""
    if not catalog:
        return []
    text = normalize_ref_text(
        '{} . {}'.format(doc.get('title', ''), doc.get('description', ''))
    )
    if not text:
        return []

    candidates = []
    for slug, info in catalog.items():
        for alias in info['aliases']:
            for m in _ref_regex(alias).finditer(text):
                candidates.append((m.start(), m.end() - m.start(), slug, m))
    if not candidates:
        return []
    # Longest match wins so qualified aliases beat shorter nested ones
    candidates.sort(key=lambda item: (-item[1], item[0]))

    taken = []
    refs = []
    seen = set()
    for start, _length, slug, m in candidates:
        if any(start < t_end and t_start < m.end() for t_start, t_end in taken):
            continue
        try:
            chapter = int(m.group('chapter'))
        except (TypeError, ValueError):
            continue
        if not (1 <= chapter <= MAX_CHAPTER):
            continue
        taken.append((start, m.end()))
        verse = m.group('verse')
        verse_end = m.group('verse_end')
        chap_end = m.group('chap_end')
        ref = {'b': slug, 'c': chapter}
        if chap_end:
            ce = int(chap_end)
            if ce > chapter and ce - chapter <= MAX_CHAPTER_SPAN:
                ref['ce'] = ce
        if verse:
            v = int(verse)
            if 1 <= v <= MAX_VERSE:
                ref['v'] = v
                if verse_end:
                    ve = int(verse_end)
                    if ve >= v and ve - v <= MAX_VERSE_SPAN:
                        ref['ve'] = ve
        key = (ref['b'], ref['c'], ref.get('ce'), ref.get('v'), ref.get('ve'))
        if key in seen:
            continue
        seen.add(key)
        refs.append(ref)
        if len(refs) >= MAX_REFS_PER_DOC:
            break

    def sort_key(r):
        info = catalog[r['b']]
        return (0 if info['group'] == 'old_testament' else 1,
                info['order'], r['c'], r.get('v') or 0)

    refs.sort(key=sort_key)
    return refs


def attach_refs(documents, catalog):
    """Attach scripture refs to every document; returns extraction stats."""
    total_refs = 0
    with_refs = 0
    for doc in documents:
        refs = extract_doc_refs(doc, catalog)
        doc['refs'] = refs
        if refs:
            with_refs += 1
            total_refs += len(refs)
    return {'docs_with_refs': with_refs, 'total_refs': total_refs}


def ref_chapters(ref):
    """Chapter numbers covered by a ref (inclusive ranges expanded)."""
    start = ref['c']
    end = ref.get('ce') or start
    end = min(end, start + MAX_CHAPTER_SPAN)
    return list(range(start, end + 1))


def ref_label(ref, catalog):
    """Human label like "إشعياء 53:1-4" / "يشوع 1-3" for a single ref."""
    info = catalog.get(ref['b']) or {}
    name = info.get('name_ar') or ref['b']
    chapter = str(ref['c'])
    if ref.get('ce') and ref['ce'] != ref['c']:
        chapter = '{}-{}'.format(ref['c'], ref['ce'])
    if ref.get('v'):
        verse = str(ref['v'])
        if ref.get('ve') and ref['ve'] != ref['v']:
            verse = '{}-{}'.format(ref['v'], ref['ve'])
        return '{} {}:{}'.format(name, ref['c'], verse)
    return '{} {}'.format(name, chapter)


def book_membership(doc, catalog):
    """Bible books a doc belongs to: categories (OT/NT) + extracted refs."""
    books = set()
    for cat in doc.get('categories') or []:
        if cat in catalog:
            books.add(cat)
    for ref in doc.get('refs') or []:
        if ref.get('b') in catalog:
            books.add(ref['b'])
    return books


def build_scripture_index(documents, catalog):
    """Book -> chapters -> documents index for the Bible navigator.

    Returns {'books': {slug: {'chapters': {int: [entry]}, 'loose': [entry],
    'docs': int}}, 'stats': {...}}. A doc appears under every book it
    belongs to; chapter placement comes from extracted verse refs, docs
    without chapter refs land in 'loose' (book-level introductions).
    """
    books = {
        slug: {'chapters': {}, 'loose': [], 'docs': 0}
        for slug in catalog
    }
    docs_indexed = 0
    for doc in documents:
        memberships = book_membership(doc, catalog)
        if not memberships:
            continue
        docs_indexed += 1
        refs = doc.get('refs') or []
        base_entry = {
            'id': doc.get('id', ''),
            'title': doc.get('title', ''),
            'author': doc.get('author', ''),
            'author_slug': doc.get('author_slug', ''),
            'html_path': doc.get('html_path', '#'),
            'completed': bool(doc.get('completed')),
        }
        for slug in memberships:
            bucket = books[slug]
            bucket['docs'] += 1
            entry = dict(base_entry)
            doc_refs = [r for r in refs if r.get('b') == slug]
            chapter_map = {}
            for ref in doc_refs:
                for ch in ref_chapters(ref):
                    if ch > MAX_CHAPTER:
                        continue
                    chapter_map.setdefault(ch, set())
                    if ref.get('v'):
                        verse = str(ref['v'])
                        if ref.get('ve') and ref['ve'] != ref['v']:
                            verse = '{}-{}'.format(ref['v'], ref['ve'])
                        chapter_map[ch].add(verse)
            if chapter_map:
                entry['chapters'] = {
                    ch: sorted(verses, key=_verse_sort_key)
                    for ch, verses in sorted(chapter_map.items())
                }
                for ch in entry['chapters']:
                    bucket['chapters'].setdefault(ch, []).append(entry)
            else:
                bucket['loose'].append(entry)

    for slug, bucket in books.items():
        for ch in bucket['chapters']:
            bucket['chapters'][ch].sort(key=_doc_sort_key)
        bucket['loose'].sort(key=_doc_sort_key)

    stats = {
        'books_total': len(catalog),
        'books_with_docs': sum(1 for b in books.values() if b['docs']),
        'chapters_indexed': sum(len(b['chapters']) for b in books.values()),
        'docs_indexed': docs_indexed,
    }
    return {'books': books, 'stats': stats}


def _verse_sort_key(label):
    try:
        return int(str(label).split('-')[0])
    except (TypeError, ValueError):
        return MAX_VERSE + 1


def _doc_sort_key(entry):
    return (0 if entry.get('completed') else 1, entry.get('title') or '')


def dump_json_js(path, var_name, payload):
    """Write a CSP-safe external data script: window.<var> = {...};"""
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    body = body.replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('window.{} = {};\n'.format(var_name, body))
