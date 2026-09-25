#!/usr/bin/env python3
"""
Build docs/bible/<slug>.json from the public-domain Arabic Van Dyck Bible.

Source: https://eBible.org/Bible/details.php?id=arb-vd
        (Arabic Van Dyck Bible, Public Domain — Syrian Mission / ABS)
Format: arb-vd_vpl.txt (VPL: "BOOK CH:V verse text" per line, UTF-8)

Usage:
    python -X utf8 scripts/build_bible_data.py <path/to/arb-vd_vpl.txt>

Output (committed to the repo, served statically):
    docs/bible/<slug>.json
        ->  {slug, name, chapters, verses: {"1": ["verse text", ...], ...}}
            (array index + 1 = verse number, strictly 1..N — validated)
"""

import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# VPL book code -> site book slug (categories.json order)
CODE_TO_SLUG = {
    'GEN': 'takwin', 'EXO': 'kharuj', 'LEV': 'lawiyyun', 'NUM': 'adad',
    'DEU': 'tathniya', 'JOS': 'yishu', 'JDG': 'qudah', 'RUT': 'rauth',
    '1SA': 'samuil-awwal', '2SA': 'samuil-thani', '1KI': 'muluk-awwal',
    '2KI': 'muluk-thani', '1CH': 'akhbar-ayyam-awwal',
    '2CH': 'akhbar-ayyam-thani', 'EZR': 'ezra', 'NEH': 'nahumya',
    'EST': 'astar', 'JOB': 'ayyub', 'PSA': 'mazamir', 'PRO': 'amthal',
    'ECC': 'jamiya', 'SOL': 'nashid', 'ISA': 'ishaiya', 'JER': 'irmiya',
    'LAM': 'marathi', 'EZE': 'hizqiyal', 'DAN': 'daniyal', 'HOS': 'husha',
    'JOE': 'yuil', 'AMO': 'amus', 'OBA': 'ubadiya', 'JON': 'yunan',
    'MIC': 'mikha', 'NAH': 'nahum', 'HAB': 'haqquq', 'ZEP': 'safaniya',
    'HAG': 'hajjai', 'ZEC': 'zakariya', 'MAL': 'malakhi',
    'MAT': 'matta', 'MAR': 'marqus', 'LUK': 'luqa', 'JOH': 'yuanna',
    'ACT': 'aamal-rusul', 'ROM': 'rumiyaya', '1CO': 'kurunthus-awwal',
    '2CO': 'kurunthus-thani', 'GAL': 'ghalatiya', 'EPH': 'afsus',
    'PHI': 'filippi', 'COL': 'kulusi', '1TH': 'tassaluniki-awwal',
    '2TH': 'tassaluniki-thani', '1TI': 'timuthawus-awwal',
    '2TI': 'timuthawus-thani', 'TIT': 'tits', 'PHM': 'filemun',
    'HEB': 'ibranin', 'JAM': 'yaqub', '1PE': 'butrus-awwal',
    '2PE': 'butrus-thani', '1JO': 'yuanna-awwal', '2JO': 'yuanna-thani',
    '3JO': 'yuanna-thalitha', 'JUD': 'yahuda', 'REV': 'mukashafa',
}

# Canonical chapter counts per VPL code (sanity check)
CANON = {
    'GEN': 50, 'EXO': 40, 'LEV': 27, 'NUM': 36, 'DEU': 34, 'JOS': 24,
    'JDG': 21, 'RUT': 4, '1SA': 31, '2SA': 24, '1KI': 22, '2KI': 25,
    '1CH': 29, '2CH': 36, 'EZR': 10, 'NEH': 13, 'EST': 10, 'JOB': 42,
    'PSA': 150, 'PRO': 31, 'ECC': 12, 'SOL': 8, 'ISA': 66, 'JER': 52,
    'LAM': 5, 'EZE': 48, 'DAN': 12, 'HOS': 14, 'JOE': 3, 'AMO': 9,
    'OBA': 1, 'JON': 4, 'MIC': 7, 'NAH': 3, 'HAB': 3, 'ZEP': 3,
    'HAG': 2, 'ZEC': 14, 'MAL': 4, 'MAT': 28, 'MAR': 16, 'LUK': 24,
    'JOH': 21, 'ACT': 28, 'ROM': 16, '1CO': 16, '2CO': 13, 'GAL': 6,
    'EPH': 6, 'PHI': 4, 'COL': 4, '1TH': 5, '2TH': 3, '1TI': 6,
    '2TI': 4, 'TIT': 3, 'PHM': 1, 'HEB': 13, 'JAM': 5, '1PE': 5,
    '2PE': 3, '1JO': 5, '2JO': 1, '3JO': 1, 'JUD': 1, 'REV': 22,
}

LINE_RE = re.compile(r'^([A-Z0-9]{1,4})\s+(\d{1,3}):(\d{1,3})\s+(.*)$')


def load_arabic_names(base_dir):
    """slug -> name_ar from categories.json (repo root)."""
    path = Path(base_dir) / 'categories.json'
    with open(path, 'r', encoding='utf-8') as f:
        cats = json.load(f).get('categories', {})
    names = {}
    for group in ('old_testament', 'new_testament'):
        for book in cats.get(group, {}).get('books', []):
            if book.get('slug'):
                names[book['slug']] = book.get('name_ar', '')
    return names


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = Path(sys.argv[1])
    base_dir = Path(__file__).resolve().parent.parent
    out_dir = base_dir / 'docs' / 'bible'
    out_dir.mkdir(parents=True, exist_ok=True)

    names = load_arabic_names(base_dir)

    books = {}       # code -> {chapters: {ch: [[n, text], ...]}}
    bad_lines = 0
    total_verses = 0
    with open(src, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line:
                continue
            m = LINE_RE.match(line)
            if not m:
                bad_lines += 1
                continue
            code, ch, v, text = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
            if code not in CODE_TO_SLUG:
                bad_lines += 1
                continue
            bucket = books.setdefault(code, {})
            bucket.setdefault(ch, []).append([v, text])
            total_verses += 1

    errors = []
    if set(books) != set(CODE_TO_SLUG):
        missing = set(CODE_TO_SLUG) - set(books)
        errors.append(f'missing books: {sorted(missing)}')

    total_bytes = 0
    written = 0
    for code, slug in CODE_TO_SLUG.items():
        chapters = books.get(code)
        if not chapters:
            continue
        expected = CANON.get(code)
        got = len(chapters)
        if expected is not None and got != expected:
            errors.append(f'{code}: chapter count {got} != canon {expected}')
        for ch, verses in chapters.items():
            if expected and ch < 1 or ch > (expected or 999):
                errors.append(f'{code}: chapter {ch} out of range')
            nums = [v[0] for v in verses]
            if nums != list(range(1, len(nums) + 1)):
                errors.append(f'{code} {ch}: verse numbering not 1..N '
                              f'({nums[:5]}...)')
        # verses: chapter -> [verse_text, ...] (array index + 1 = verse number;
        # converter validates numbering is strictly 1..N)
        payload = {
            'slug': slug,
            'name': names.get(slug, ''),
            'chapters': got,
            'verses': {str(ch): [v[1] for v in chapters[ch]]
                       for ch in sorted(chapters)},
        }
        out = out_dir / f'{slug}.json'
        data = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        out.write_text(data, encoding='utf-8')
        total_bytes += len(data.encode('utf-8'))
        written += 1

    print(f'books written: {written}  verses: {total_verses}  '
          f'bad lines: {bad_lines}  total: {total_bytes / 1024 / 1024:.2f} MB')
    if bad_lines:
        print(f'  [NOTE] {bad_lines} unparsed lines (headers/footnotes?)')
    if errors:
        print('ERRORS:')
        for e in errors[:30]:
            print('  -', e)
        sys.exit(2)
    print('[OK] bible data valid')


if __name__ == '__main__':
    main()
