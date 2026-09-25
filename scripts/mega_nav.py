"""Bibelkommentare-style hover mega-menu for the الترجمات nav item.

Markers embedded by templates / page generators are replaced at build time:

    <!-- MEGA_BAR prefix="" active="1" -->      (classic .nav-bar pages)
    <!-- MEGA_MAIN prefix="../" -->             (.main-nav: doc & author pages)
    <!-- MEGA_RX prefix="" -->                  (index-new rx-nav)

The panel content is fully static (build-time counts) - no client data
fetch, no CLS (absolute overlay), strict CSP compliant.
"""

import re

MARKER_RE = re.compile(
    r'<!--\s*MEGA_(BAR|MAIN|RX)((?:\s+[a-z_]+="[^"]*")*)\s*-->'
)
ATTR_RE = re.compile(r'([a-z_]+)="([^"]*)"')

TRANSLATIONS_LABEL = 'الترجمات'

# categories.json group -> category page
GROUP_PAGE = {
    'old_testament': 'translations-ot.html',
    'new_testament': 'translations-nt.html',
    'topics': 'translations-subjects.html',
}
GROUP_LABEL = {
    'old_testament': 'العهد القديم',
    'new_testament': 'العهد الجديد',
    'topics': 'مواضيع',
}


def compute_counts(documents, categories):
    """Per-book document counts, mirroring js/translations.js getDocsForBook.

    Membership: docs match via categories[] (or legacy category string);
    uncategorized docs fall back to an Arabic-title substring match.
    Returns {slug: count} for every book/topic in categories.json.
    """
    groups = []
    for group_key in ('old_testament', 'new_testament', 'topics'):
        for book in (categories.get(group_key) or {}).get('books', []):
            slug = book.get('slug')
            if slug:
                groups.append(slug)

    lower_groups = [(g, g.lower()) for g in groups]
    counts = {g: 0 for g in groups}

    for doc in documents:
        cats = doc.get('categories')
        if not isinstance(cats, list):
            cats = []
        if not cats:
            cat = doc.get('category')
            if cat and cat != 'uncategorized':
                cats = [cat]

        if cats:
            lowered = {str(c or '').lower() for c in cats}
            for raw, low in lower_groups:
                if low in lowered:
                    counts[raw] += 1
        else:
            title = (doc.get('title') or '').lower()
            if not title:
                continue
            for book in _books_iter(categories):
                name = (book.get('name_ar') or '').lower()
                if name and name in title:
                    counts[book['slug']] += 1
    return counts


def _books_iter(categories):
    for group_key in ('old_testament', 'new_testament', 'topics'):
        for book in (categories.get(group_key) or {}).get('books', []):
            if book.get('slug'):
                yield book


def _book_grid(prefix, categories, group_key, counts, grid_id):
    books = (categories.get(group_key) or {}).get('books', [])
    parts = []
    for book in books:
        slug = book.get('slug')
        if not slug:
            continue
        name = book.get('name_ar') or slug
        n = counts.get(slug, 0)
        count_html = f'<span class="mega-count">{n}</span>' if n else ''
        page = GROUP_PAGE[group_key]
        parts.append(
            f'<a href="{prefix}{page}#book-{slug}">'
            f'<span class="mega-book-name">{name}</span>{count_html}</a>'
        )
    return f'<div class="nav-book-grid" id="{grid_id}">' + ''.join(parts) + '</div>'


def mega_panel_html(prefix, categories, counts):
    """Full-width hover panel (inner markup, no wrapper)."""
    def section(group_key, grid_id):
        label = GROUP_LABEL[group_key]
        grid = _book_grid(prefix, categories, group_key, counts, grid_id)
        return (
            '<div class="nav-dropdown-section">'
            f'<button type="button" class="nav-dropdown-toggle" '
            f'aria-expanded="false" aria-controls="{grid_id}">'
            f'<span>{label}</span>'
            '<span class="toggle-mark" aria-hidden="true">[+]</span>'
            '</button>'
            f'{grid}'
            '</div>'
        )

    sections = (
        section('old_testament', 'megaGridOt')
        + section('new_testament', 'megaGridNt')
    )
    links = (
        f'<a class="mega-link" href="{prefix}translations-subjects.html">مواضيع</a>'
        '<div class="nav-dropdown-divider"></div>'
        f'<a class="mega-link" href="{prefix}translations.html">كل الترجمات</a>'
        f'<a class="mega-link" href="{prefix}authors.html">المؤلفون</a>'
        f'<a class="mega-link" href="{prefix}bibles.html">فهرس الآيات</a>'
    )
    return (
        '<div class="nav-mega" id="navMega" aria-label="قائمة الترجمات">'
        '<div class="mega-inner">'
        f'<div class="mega-col mega-col-books">{sections}</div>'
        f'<div class="mega-col mega-col-links">{links}</div>'
        '</div></div>'
    )


def mega_item_html(variant, prefix, active, categories, counts):
    """Wrapper markup for one nav variant (BAR | MAIN | RX)."""
    prefix = prefix or ''
    panel = mega_panel_html(prefix, categories, counts)
    active_cls = ' active' if active else ''
    aria = ' aria-current="page"' if active else ''
    if variant == 'BAR':
        return (
            '<div class="nav-item has-mega">'
            f'<a href="{prefix}translations.html" class="nav-link{active_cls}"'
            f'{aria}>{TRANSLATIONS_LABEL}</a>{panel}</div>'
        )
    if variant == 'MAIN':
        return (
            '<div class="has-mega main-has-mega">'
            f'<a href="{prefix}translations.html">{TRANSLATIONS_LABEL}</a>'
            f'{panel}</div>'
        )
    # RX
    return (
        '<div class="rx-nav-item has-mega">'
        f'<a href="{prefix}translations.html" class="rx-nav-link{active_cls}"'
        f'{aria}>{TRANSLATIONS_LABEL}</a>{panel}</div>'
    )


def _replace_match(match, categories, counts):
    variant = match.group(1)
    attrs = dict(ATTR_RE.findall(match.group(2) or ''))
    prefix = attrs.get('prefix', '')
    active = attrs.get('active', '') in ('1', 'true', 'yes')
    return mega_item_html(variant, prefix, active, categories, counts)


def inject_mega_nav(html, categories, counts):
    """Replace every MEGA_* marker in an HTML string; returns (html, n)."""
    count = 0

    def _sub(match):
        nonlocal count
        count += 1
        return _replace_match(match, categories, counts)

    return MARKER_RE.sub(_sub, html), count


def inject_mega_nav_in_files(root, categories, counts):
    """Walk *root* (docs/ or local-hidden/) and replace markers in place."""
    if not root or not root.exists():
        return 0, 0
    replaced = 0
    files = 0
    for path in root.rglob('*.html'):
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        if 'MEGA_' not in text:
            continue
        new_text, n = inject_mega_nav(text, categories, counts)
        if n:
            try:
                path.write_text(new_text, encoding='utf-8')
                replaced += n
                files += 1
            except OSError:
                continue
    return replaced, files
