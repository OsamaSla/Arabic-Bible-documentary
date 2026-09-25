#!/usr/bin/env python3
"""
Auto-assign document categories from titles/filenames.

Reads categories.json (vocabulary), scores each document's title+filename
(+author for magazine folders), and writes doc_categories.json.

Existing assignments are kept unless --force is passed.

Usage:
    python scripts/autocategorize.py
    python scripts/autocategorize.py --dry-run
    python scripts/autocategorize.py --force
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CAT_VOCAB_PATH = BASE_DIR / 'categories.json'
DOC_CAT_PATH = BASE_DIR / 'doc_categories.json'
INDEX_CANDIDATES = [
    BASE_DIR / 'local-hidden' / 'documents-index.json',
    BASE_DIR / 'docs' / 'documents' / 'index.json',
]

# Multi-word / spelling aliases keyed by category slug (normalized before match).
ALIASES = {
    # OT
    'takwin': ['سفر التكوين', 'كتاب التكوين', 'في البدء', 'تكوين'],
    'kharuj': ['سفر الخروج', 'الخروج', 'خروج'],
    'lawiyyun': ['سفر اللاويين', 'اللاويين', 'ذبائح اللاويين'],
    'adad': ['سفر العدد', 'العدد'],
    'tathniya': ['سفر التثنية', 'التثنية'],
    'yishu': ['سفر يشوع', 'يشوع'],
    'qudah': ['سفر القضاة', 'القضاة'],
    'rauth': ['سفر راعوث', 'راعوث'],
    'samuil-awwal': ['1. صموئيل', '1 صموئيل', 'صموئيل الأول', 'الصموئيل الأول', 'سفر صموئيل الأول'],
    'samuil-thani': ['2. صموئيل', '2 صموئيل', 'صموئيل الثاني', 'الصموئيل الثاني', 'سفر صموئيل الثاني'],
    'muluk-awwal': ['1. ملوك', '1 ملوك', 'ملوك الأول', 'الملوك الأول', 'سفر ملوك الأول', 'سفر الملوك الأول'],
    'muluk-thani': ['2. ملوك', '2 ملوك', 'ملوك الثاني', 'الملوك الثاني', 'سفر ملوك الثاني', 'سفر الملوك الثاني'],
    'akhbar-ayyam-awwal': ['1. أخبار الأيام', 'أخبار الأيام الأول', 'أخبار أيام الأول'],
    'akhbar-ayyam-thani': ['2. أخبار الأيام', 'أخبار الأيام الثاني', 'أخبار أيام الثاني'],
    'ezra': ['سفر عزرا', 'عزرا'],
    'nahumya': ['سفر نحميا', 'نحميا'],
    'astar': ['أستار', 'أستير', 'أستير', 'سفر أستار'],
    'ayyub': ['سفر أيوب', 'أيوب'],
    'mazamir': ['المزامير', 'سفر المزامير', 'مزمور'],
    'amthal': ['سفر الأمثال', 'الأمثال', 'أمثال سليمان'],
    'jamiya': ['الجامعة', 'سفر الجامعة'],
    'nashid': ['نشيد الأنشاد', 'نشيد الانشاد', 'سفر نشيد'],
    'ishaiya': ['إشعياء', 'أشعياء', 'اشعياء', 'اشفيعاء', 'أشفعياء', 'إشفاياء'],
    'irmiya': ['إرميا', 'إرمياء', 'ارميا', 'ارمياء', 'إرميا النبي'],
    'marathi': ['مراثي إرميا', 'مراثي إرمياء', 'مراثي'],
    'hizqiyal': ['حزقيال', 'حزقيل'],
    'daniyal': ['دانيال', 'سفر دانيال', 'النبي دانيال'],
    'husha': ['هوشع', 'سفر هوشع'],
    'yuil': ['يوئيل', 'يويل', 'سفر يوئيل'],
    'amus': ['عاموس', 'سفر عاموس'],
    'ubadiya': ['عوبديا', 'عبديا', 'سفر عوبديا'],
    'yunan': ['يونان', 'سفر يونان'],
    'mikha': ['ميخا', 'سفر ميخا'],
    'nahum': ['ناحوم', 'نبوة ناحوم', 'النبي ناحوم'],
    'haqquq': ['حبقوق', 'النبي حبقوق'],
    'safaniya': ['صفنيا', 'صفنيا', 'النبي صفنيا'],
    'hajjai': ['حجى', 'حجاي'],
    'zakariya': ['زكريا', 'النبي زكريا', 'سفر زكريا'],
    'malakhi': ['ملاخي', 'ملخي', 'ملكي', 'ملخى'],
    # NT — bare Gospel names are NOT trusted (author names like "يوحنا داربي");
    # use context/chapter patterns via SHORT_NAME_PATTERNS + name_ar below.
    'matta': ['إنجيل متى', 'انجيل متى', 'أنجيل متى', 'تفسير متى', 'شرح متى',
              'الموعظة على الجبل', 'مواعظ الجبل', 'موعظة الجبل'],
    'marqus': ['إنجيل مرقس', 'انجيل مرقس', 'أنجيل مرقس', 'شرح إنجيل مرقس'],
    'luqa': ['إنجيل لوقا', 'انجيل لوقا', 'أنجيل لوقا'],
    'yuanna': ['إنجيل يوحنا', 'انجيل يوحنا', 'أنجيل يوحنا', 'أنجيل يوحنا'],
    'aamal-rusul': ['أعمال الرسل', 'اعمال الرسل', 'كتاب أعمال'],
    'rumiyaya': ['رسالة رومية', 'رسالة إلى رومية', 'الرسالة إلى أهل رومية', 'رومية', 'Römer Brief', 'Rom Brief'],
    'kurunthus-awwal': ['كورنثوس الأولى', 'كورنثوس الاولى', 'رسالة كورنثوس الأولى', '1. كورنثوس'],
    'kurunthus-thani': ['كورنثوس الثانية', 'كورنثوس الثانية', 'رسالة كورنثوس الثانية', '2. كورنثوس'],
    'ghalatiya': ['غلاطية', 'رسالة غلاطية', 'Galater Brief'],
    'afsus': ['أفسس', 'افسس', 'رسالة أفسس', 'رسالة افسس'],
    'filippi': ['فيلبي', 'رسالة فيلبي', 'فيلبي'],
    'kulusi': ['كولوسي', 'رسالة كولوسي'],
    'tassaluniki-awwal': ['تسالونيكي الأولى', 'تسالونيكي الاولى', '1. تسالونيكي', 'رسالة تسالونيكي الأولى'],
    'tassaluniki-thani': ['تسالونيكي الثانية', 'تسالونيكي الثانية', '2. تسالونيكي', 'رسالة تسالونيكي الثانية'],
    'timuthawus-awwal': ['تيموثاوس الأولى', 'تيموثاوس الاولى', '1. تيموثاوس', 'رسالة تيموثاوس الأولى'],
    'timuthawus-thani': ['تيموثاوس الثانية', 'تيموثاوس الثانية', '2. تيموثاوس', 'رسالة تيموثاوس الثانية'],
    'tits': ['تيطس', 'رسالة تيطس'],
    'filemun': ['فليمون', 'رسالة فيلمون'],
    'ibranin': ['العبرانيين', 'عبرانيين', 'رسالة العبرانيين', 'Hebräer Brief'],
    'yaqub': ['يعقوب', 'رسالة يعقوب', 'رسالة الرسول يعقوب'],
    'butrus-awwal': ['بطرس الأولى', 'بطرس الاولى', 'رسالة بطرس الأولى', '1. بطرس'],
    'butrus-thani': ['بطرس الثانية', 'بطرس الثانية', 'رسالة بطرس الثانية', '2. بطرس'],
    'yuanna-awwal': ['يوحنا الأولى', 'يوحنا الاولى', 'رسالة يوحنا الأولى', '1. يوحنا', 'رسالة 1. يوحنا'],
    'yuanna-thani': ['يوحنا الثانية', 'يوحنا الثانية', 'رسالة يوحنا الثانية', '2. يوحنا'],
    'yuanna-thalitha': ['يوحنا الثالثة', 'رسالة يوحنا الثالثة', '3. يوحنا'],
    'yahuda': ['يهوذا', 'رسالة يهوذا'],
    'mukashafa': ['المكشوف', 'سفر الرؤيا', 'الرؤيا', 'مكشوف', 'رؤيا'],
    # Topics
    'bible-study': ['دراسة الكتاب المقدس', 'دراسة كتابية', 'دروس كتابية'],
    'holy-spirit': ['الروح القدس', 'روح القدس', 'المعمودية بالروح'],
    'scripture': ['الكتاب المقدس', 'أسفار الكتاب', 'كتاب الله'],
    'marriage-family': ['الزواج والأسرة', 'الزواج', 'الأسرة'],
    'gospel': ['الإنجيل', 'انجيل', 'سر الإنجيل', 'بشارة الإنجيل'],
    'faith-life': ['الحياة الإيمانية', 'طريق الإيمان', 'حياة الإيمان', 'الإيمان'],
    'jesus-christ': ['يسوع المسيح', 'الرب يسوع', 'مجد الرب يسوع'],
        'creation': ['الخلق', 'الخليقة', 'أيام الخلق', 'في البدء خلق'],
        'church': ['الكنيسة', 'الاجتماع', 'كنية الله'],
        'prophecy': ['أواخر الأمور', 'النبوءة', 'النبوة', 'المستقبل', 'الأمور الأخيرة', 'الدهر الآتي'],
}

# Strong context words that license short book names.
CONTEXT_RE = re.compile(
    r'(?:سفر|رسال(?:ة|تي|ات)|إنجيل|انجيل|أنجيل|كتاب|النبي|نبي|نبوة|نبوءة|'
    r'تفسير|شرح|تأمل|دراسة|دروس|عظ|مقدمة|أصحاح|صحاح|مقتطف|'
    r'محاضرة|عظات|بحث|حوار|سينوبسيس)'
)

# Very short / author-name-colliding Arabic names need a strong pattern.
SHORT_NAME_PATTERNS = {
    'matta': [r'إنجيل\s+متى', r'انجيل\s+متى', r'أنجيل\s+متى', r'تفسير\s+متى',
              r'شرح\s+متى', r'الموعظة\s+على\s+الجبل', r'متى\s+\d+', r'متى\s*\d+'],
    'marqus': [r'إنجيل\s+مرقس', r'انجيل\s+مرقس', r'شرح\s+\S+\s+مرقس', r'مرقس\s+\d+'],
    'luqa': [r'إنجيل\s+لوقا', r'انجيل\s+لوقا', r'لوقا\s+\d+'],
    'yuanna': [r'إنجيل\s+يوحنا', r'انجيل\s+يوحنا', r'أنجيل\s+يوحنا',
               r'شرح\s+يوحنا', r'يوحنا\s+\d+', r'رسالة\s+يوحنا'],
}

# Dual/plural forms that span two books (ambiguous — skip for manual review).
AMBIGUOUS_PATTERNS = [
    (re.compile(r'رسالتا\s+تسالونيكي|رسالتي\s+تسالونيكي|شروحات\s+في\s+رسالتي\s+تسالونيكي'), 'dual-thessalonians'),
    (re.compile(r'ملاخي\s+ويهوذا|يهوذا\s+وملاخي'), 'malachi-jude'),
    (re.compile(r'رسائل\s+يوحنا|رسالتي\s+يوحنا'), 'epistles-of-john'),
    (re.compile(r'رسالتا?\s+تيموثاوس|رسالتي\s+تيموثاوس'), 'pastoral-epistles-dual'),
]


def normalize(text: str) -> str:
    """Aggressive Arabic-friendly normalization for matching."""
    if not text:
        return ''
    s = unicodedata.normalize('NFKC', str(text))
    # Strip Arabic diacritics + tatweel
    s = re.sub(r'[\u064B-\u065F\u0670\u0640]', '', s)
    # Alef variants → bare alef
    s = (s.replace('\u0622', '\u0627').replace('\u0623', '\u0627')
           .replace('\u0625', '\u0627'))
    # Yaa / alef maqsura
    s = s.replace('\u0649', '\u064A')
    # Taa marbuta → haa (looser match for spelling drift)
    s = s.replace('\u0629', '\u0647')
    # Common punctuation → space (keeps Arabic letters + digits)
    s = re.sub(r'[^\w\u0600-\u06FF]+', ' ', s, flags=re.UNICODE)
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s


def norm_kw(s: str) -> str:
    return normalize(s)


def word_boundary_find(hay: str, needle: str) -> bool:
    if not needle:
        return False
    if len(needle) >= 6:
        return needle in hay
    # Word-ish boundaries (Arabic letters count as \w in Unicode mode)
    return re.search(
        r'(?<![\w\u0600-\u06FF])' + re.escape(needle) + r'(?![\w\u0600-\u06FF])',
        hay,
    ) is not None


def build_catalog(vocab: dict):
    """Return list of (slug, group, keywords_norm, is_book)."""
    # Slugs whose bare name_ar must not be used alone (collides with author names).
    bare_untrusted = {'yuanna', 'matta', 'marqus', 'luqa'}
    entries = []
    categories = vocab.get('categories', {})
    for group_key in ('old_testament', 'new_testament', 'topics'):
        group = categories.get(group_key) or {}
        is_book = group_key != 'topics'
        for book in group.get('books', []):
            slug = book['slug']
            kws = []
            name_ar = book.get('name_ar', '')
            if name_ar and not (is_book and slug in bare_untrusted):
                kws.append(norm_kw(name_ar))
            name_de = book.get('name_de', '')
            if name_de and len(name_de) >= 5:
                kws.append(norm_kw(name_de))
            for raw in ALIASES.get(slug, []):
                kws.append(norm_kw(raw))
            # de-dup preserve order
            seen = set()
            uniq = []
            for k in kws:
                if k and k not in seen:
                    seen.add(k)
                    uniq.append(k)
            entries.append((slug, group_key, uniq, is_book))
    return entries


def score_book(slug: str, text: str, is_book: bool) -> int:
    # Short-name / high-precision patterns first
    best = 0
    for pat in SHORT_NAME_PATTERNS.get(slug, []):
        if re.search(pat, text):
            best = max(best, 80)

    has_context = bool(CONTEXT_RE.search(text))
    for kw in _keywords_for_slug(slug):
        if not kw:
            continue
        if len(kw) <= 3:
            continue  # handled by SHORT_NAME_PATTERNS
        if len(kw) >= 4 and word_boundary_find(text, kw):
            score = len(kw) * 10
            if has_context:
                score += 15
            # Chapter/verse digits after a shortish keyword
            if len(kw) <= 8 and re.search(re.escape(kw) + r'\s*\d+', text):
                score += 20
            best = max(best, score)
    return best


# Precompute keyword lookup
_KW_CACHE = {}


def _keywords_for_slug(slug: str):
    if slug not in _KW_CACHE:
        # filled in main after catalog build
        return []
    return _KW_CACHE[slug]


def find_ambiguous(text: str):
    for pat, label in AMBIGUOUS_PATTERNS:
        if pat.search(text):
            return label
    return None


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value and value != 'uncategorized' else []
    if isinstance(value, list):
        return [str(v) for v in value if v and v != 'uncategorized']
    return []


def main():
    parser = argparse.ArgumentParser(description='Auto-assign document categories')
    parser.add_argument('--dry-run', action='store_true', help='Print summary only')
    parser.add_argument('--force', action='store_true', help='Overwrite existing assignments')
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    with open(CAT_VOCAB_PATH, 'r', encoding='utf-8') as f:
        vocab = json.load(f)

    catalog = build_catalog(vocab)
    _KW_CACHE.clear()
    for slug, group, kws, is_book in catalog:
        _KW_CACHE[slug] = kws

    index_path = next((p for p in INDEX_CANDIDATES if p.exists()), None)
    if not index_path:
        print('[ERROR] No documents index found. Run scripts/build.py first.')
        return 1

    with open(index_path, 'r', encoding='utf-8') as f:
        index_data = json.load(f)
    docs = index_data.get('documents', [])

    existing = {}
    if DOC_CAT_PATH.exists():
        with open(DOC_CAT_PATH, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        raw_existing = existing_data.get('assignments', {}) or {}
        # Normalize every existing value to a list (migrates old str form)
        existing = {k: _as_list(v) for k, v in raw_existing.items() if _as_list(v)}

    book_slugs = {slug for slug, _, _, is_book in catalog if is_book}

    assignments = {k: list(v) for k, v in existing.items()}
    stats = {
        'total': len(docs),
        'kept': 0,
        'assigned_book': 0,
        'assigned_topic': 0,
        'assigned_both': 0,
        'ambiguous': 0,
        'unmatched': 0,
        'overwritten': 0,
    }
    ambiguous_list = []
    unmatched_list = []
    by_cat = {}

    def bump(cats):
        for c in cats:
            by_cat[c] = by_cat.get(c, 0) + 1

    for doc in docs:
        doc_id = doc.get('id', '')
        filename = doc.get('filename', '') or ''
        title = doc.get('title', '') or ''
        author = doc.get('author', '') or ''
        if doc_id in assignments and not args.force:
            stats['kept'] += 1
            bump(assignments[doc_id])
            continue

        text = normalize(f'{title} {filename}')
        text_with_author = normalize(f'{title} {filename} {author}')
        # Prefer title over filename when both match different books
        title_text = normalize(title)
        file_text = normalize(filename)

        amb = find_ambiguous(text)
        if amb:
            stats['ambiguous'] += 1
            ambiguous_list.append((doc_id, amb, title[:60]))
            if doc_id in assignments and args.force:
                del assignments[doc_id]
            continue

        # Score books: title×2 + filename×1 so title signals win ties
        best_slug = None
        best_score = 0
        book_scores = {}
        for slug, group, kws, is_book in catalog:
            if not is_book:
                continue
            sc = score_book(slug, title_text, True) * 2 + score_book(slug, file_text, True)
            # also allow combined text for multi-field patterns
            sc = max(sc, score_book(slug, text, True))
            book_scores[slug] = sc
            if sc > best_score:
                best_slug, best_score = slug, sc

        chosen_books = []
        if best_slug and best_score >= 40:
            equal_ties = {
                s for s, sc in book_scores.items()
                if s != best_slug and sc == best_score and sc > 0
            }
            if equal_ties:
                stats['ambiguous'] += 1
                ambiguous_list.append(
                    (doc_id, 'tie:' + '+'.join(sorted(equal_ties) + [best_slug]), title[:60])
                )
                continue
            chosen_books = [best_slug]

        # Strongly-signaled topics (option: books + strong topics together)
        chosen_topics = []
        for slug, group, kws, is_book in catalog:
            if is_book:
                continue
            sc = score_book(slug, title_text, False) * 2 + score_book(slug, file_text, False)
            sc = max(sc, score_book(slug, text, False))
            if sc >= 50:
                chosen_topics.append((slug, sc))
        chosen_topics.sort(key=lambda x: (-x[1], x[0]))
        # Keep topics that are clearly strong (>=50); allow up to 2 if both strong
        topic_slugs = []
        for slug, sc in chosen_topics[:2]:
            topic_slugs.append(slug)

        if not chosen_books and not topic_slugs:
            stats['unmatched'] += 1
            unmatched_list.append((doc_id, title[:70]))
            continue

        cats = list(chosen_books) + [t for t in topic_slugs if t not in chosen_books]
        if doc_id in assignments:
            stats['overwritten'] += 1
        assignments[doc_id] = cats
        has_book = any(c in book_slugs for c in cats)
        has_topic = any(c not in book_slugs for c in cats)
        if has_book and has_topic:
            stats['assigned_both'] += 1
        elif has_book:
            stats['assigned_book'] += 1
        else:
            stats['assigned_topic'] += 1
        bump(cats)

    # Stable key order: by doc id; every value is a list
    ordered = {k: assignments[k] for k in sorted(assignments.keys())}
    payload = {
        '_comment': 'Map document IDs or filenames to arrays of category slugs. Managed by scripts/autocategorize.py + admin panel.',
        'assignments': ordered,
    }

    if not args.dry_run:
        tmp = DOC_CAT_PATH.with_suffix('.json.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write('\n')
        tmp.replace(DOC_CAT_PATH)

    print(f'[CAT] Index: {index_path.name}')
    print(f'[CAT] Total documents: {stats["total"]}')
    print(f'[CAT] Existing kept: {stats["kept"]}')
    print(f'[CAT] Newly assigned (book only): {stats["assigned_book"]}')
    print(f'[CAT] Newly assigned (topic only): {stats["assigned_topic"]}')
    print(f'[CAT] Newly assigned (book+topic): {stats["assigned_both"]}')
    print(f'[CAT] Ambiguous (left for manual): {stats["ambiguous"]}')
    print(f'[CAT] Unmatched (left uncategorized): {stats["unmatched"]}')
    print(f'[CAT] Total assignments in file: {len(ordered)}')
    print(f'[CAT] Per-category counts may sum > docs (multi-category).')
    if args.dry_run:
        print('[CAT] DRY RUN — file not written')

    if ambiguous_list:
        print('\n[AMBIGUOUS] Assign manually in the admin panel:')
        for doc_id, label, t in ambiguous_list[:40]:
            print(f'  {doc_id}  ({label})  {t}')
        if len(ambiguous_list) > 40:
            print(f'  ... and {len(ambiguous_list) - 40} more')

    if unmatched_list and unmatched_list:
        print(f'\n[UNMATCHED] {len(unmatched_list)} docs (sample):')
        for doc_id, t in unmatched_list[:25]:
            print(f'  {doc_id}  {t}')
        if len(unmatched_list) > 25:
            print(f'  ... and {len(unmatched_list) - 25} more')

    # Top categories
    top = sorted(by_cat.items(), key=lambda x: -x[1])[:15]
    if top:
        print('\n[TOP CATEGORIES]')
        for slug, n in top:
            print(f'  {n:4d}  {slug}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
