#!/usr/bin/env python3
"""One-off: migrate doc_categories.json string values -> arrays."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

p = Path(__file__).resolve().parent.parent / 'doc_categories.json'
data = json.loads(p.read_text(encoding='utf-8'))
a = data.get('assignments', {})
n_str = 0
for k, v in list(a.items()):
    if isinstance(v, str):
        a[k] = [v] if v and v != 'uncategorized' else []
        n_str += 1
    elif isinstance(v, list):
        a[k] = [x for x in v if x and x != 'uncategorized']
    else:
        a[k] = []
a = {k: a[k] for k in sorted(a) if a[k]}
data['assignments'] = a
data['_comment'] = 'Map document IDs or filenames to arrays of category slugs. Managed by scripts/autocategorize.py + admin panel.'
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# verify
data2 = json.loads(p.read_text(encoding='utf-8'))
a2 = data2['assignments']
print('converted strings:', n_str)
print('final count:', len(a2))
print('all lists:', all(isinstance(v, list) for v in a2.values()))
print('sample:', list(a2.items())[:3])
