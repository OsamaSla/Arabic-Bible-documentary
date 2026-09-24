#!/usr/bin/env python3
"""
Word to HTML Converter for Arabic Christian Translations
Scans author folders, detects completion status (تم subfolder) and hidden status (hidden/مخفي subfolder),
generates flat HTML pages and index.json.
"""

import os
import sys
import json
import re
import hashlib
import shutil
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from docx.text.run import Run


def slugify(text):
    """Convert text to URL-friendly slug"""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:50]


def get_file_hash(filepath):
    """Get MD5 hash of file for unique identification"""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()[:8]


def escape_html(text):
    """Escape HTML special characters (including quotes for attribute safety)."""
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#39;')
    return text


_SAFE_URL_RE = re.compile(r'^(https?://|mailto:|#)', re.I)


def safe_url(url):
    """Allow only http(s), mailto, and fragment URLs; reject everything else."""
    if not url:
        return None
    url = str(url).strip()
    if not url:
        return None
    if _SAFE_URL_RE.match(url):
        return url
    return None


def sanitize_html(html):
    """Strip active content (scripts, event handlers, dangerous URLs) from generated HTML."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return html
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'iframe', 'object', 'embed', 'form', 'base', 'link', 'meta']):
        tag.decompose()
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr.lower().startswith('on'):
                del tag[attr]
        if tag.name == 'a':
            href = tag.get('href')
            if href is not None:
                cleaned = safe_url(href if isinstance(href, str) else (href[0] if href else ''))
                if cleaned is None:
                    del tag['href']
                else:
                    tag['href'] = cleaned
            tag['rel'] = ['noopener', 'noreferrer']
        if tag.name in ('img', 'source', 'video', 'audio'):
            for attr in ('src', 'srcset'):
                if attr in tag.attrs:
                    val = tag[attr]
                    val = val if isinstance(val, str) else (val[0] if val else '')
                    if not val.startswith(('http://', 'https://', 'data:image/', '/')) and not val.startswith('../'):
                        del tag[attr]
    return str(soup)


def format_run(run):
    """Apply run-level formatting to text."""
    text = run.text
    if not text:
        return ''
    formatted = escape_html(text)
    styles = []
    if run.bold:
        styles.append('font-weight:600')
    if run.italic:
        styles.append('font-style:italic')
    if run.underline:
        styles.append('text-decoration:underline')
    if run.font.color and run.font.color.rgb:
        color = str(run.font.color.rgb)
        styles.append(f'color:#{color}')
    if run.font.size:
        size_pt = run.font.size.pt if hasattr(run.font.size, 'pt') else run.font.size / 12700
        if size_pt > 14:
            styles.append(f'font-size:{size_pt}pt')
    if run.font.superscript:
        formatted = f'<sup>{formatted}</sup>'
    elif run.font.subscript:
        formatted = f'<sub>{formatted}</sub>'
    if styles:
        formatted = f'<span style="{";".join(styles)}">{formatted}</span>'
    return formatted


def _rel_target(paragraph, rid):
    if not rid:
        return None
    try:
        rel = paragraph.part.rels[rid]
    except KeyError:
        return None
    if rel.is_external:
        return rel.target_ref
    return None


def _field_hyperlink_url(instr):
    m = re.search(r'HYPERLINK\s+(?:\\l\s+)?"([^"]+)"', instr or '', re.I)
    return m.group(1) if m else None


def _runs_xml(container_el):
    for el in container_el.iter():
        if el.tag == qn('w:r'):
            yield el


def _render_hyperlink(paragraph, container, url):
    inner = ''.join(format_run(Run(el, paragraph)) for el in _runs_xml(container))
    if not inner:
        return ''
    if url:
        cleaned = safe_url(url)
        if cleaned:
            return f'<a href="{escape_html(cleaned)}" rel="noopener noreferrer">{inner}</a>'
    return inner


def _walk_children(paragraph, parent):
    parts = []
    for child in parent:
        tag = child.tag
        if tag == qn('w:pPr') or tag == qn('w:hyperlink') or tag == qn('w:fldSimple'):
            continue
        if tag == qn('w:r'):
            parts.append(format_run(Run(child, paragraph)))
        elif tag == qn('w:sdt'):
            for sub in child:
                if sub.tag == qn('w:sdtContent'):
                    parts.extend(_walk_children(paragraph, sub))
        else:
            parts.extend(_walk_children(paragraph, child))
    return parts


def process_paragraph(paragraph):
    """Process formatting and hyperlinks in a paragraph (walks paragraph XML)."""
    parts = []
    for child in paragraph._p:
        tag = child.tag
        if tag == qn('w:pPr'):
            continue
        if tag == qn('w:r'):
            parts.append(format_run(Run(child, paragraph)))
        elif tag == qn('w:hyperlink'):
            url = _rel_target(paragraph, child.get(qn('r:id')))
            if not url:
                anchor = child.get(qn('w:anchor'))
                if anchor:
                    url = f'#{anchor}'
            parts.append(_render_hyperlink(paragraph, child, url))
        elif tag == qn('w:fldSimple'):
            url = _field_hyperlink_url(child.get(qn('w:instr')))
            parts.append(_render_hyperlink(paragraph, child, url))
        else:
            parts.extend(_walk_children(paragraph, child))
    return ''.join(parts)


def process_runs(runs):
    """Process formatting runs (kept for compatibility)."""
    return ''.join(format_run(run) for run in runs)


def extract_text_from_docx(docx_path):
    """Extract formatted text from Word document"""
    try:
        doc = Document(docx_path)
        html_parts = []
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            style_name = paragraph.style.name.lower() if paragraph.style else ''
            if 'heading' in style_name or 'title' in style_name:
                level = 2
                for n in ['1', '2', '3', '4', '5']:
                    if f'heading {n}' in style_name or f'title {n}' in style_name:
                        level = int(n) + 1
                        break
                if 'title' in style_name:
                    level = 1
                formatted_text = process_paragraph(paragraph)
                if formatted_text.strip():
                    html_parts.append(f'<h{level}>{formatted_text}</h{level}>')
                continue
            if 'list' in style_name:
                formatted_text = process_paragraph(paragraph)
                if formatted_text.strip():
                    html_parts.append(f'<li>{formatted_text}</li>')
                continue
            if not text:
                html_parts.append('<p class="empty-line">&nbsp;</p>')
                continue
            formatted_text = process_paragraph(paragraph)
            if formatted_text.strip():
                if re.match(r'^[\d\s]*\w+\s+\d+:\d+', text) or re.match(r'^[\u0600-\u06FF]+\s+\d+:\d+', text):
                    html_parts.append(f'<p class="verse-ref">{formatted_text}</p>')
                else:
                    html_parts.append(f'<p>{formatted_text}</p>')
        for table in doc.tables:
            html_parts.append('<div class="table-container"><table>')
            for i, row in enumerate(table.rows):
                html_parts.append('<tr>')
                for cell in row.cells:
                    cell_text = ' '.join(p.text.strip() for p in row.paragraphs if p.text.strip())
                    tag = 'th' if i == 0 else 'td'
                    html_parts.append(f'<{tag}>{escape_html(cell_text)}</{tag}>')
                html_parts.append('</tr>')
            html_parts.append('</table></div>')
        result = '\n'.join(html_parts)
        result = re.sub(r'(<p class="empty-line">&nbsp;</p>\s*){2,}', '<p class="empty-line">&nbsp;</p>', result)
        return sanitize_html(result)
    except Exception as e:
        return f'<p class="error">خطأ في قراءة الملف: {escape_html(str(e))}</p>'


def get_title_from_docx(docx_path):
    """Extract title from first heading or first paragraph"""
    try:
        doc = Document(docx_path)
        for paragraph in doc.paragraphs[:10]:
            text = paragraph.text.strip()
            if text:
                style_name = paragraph.style.name.lower() if paragraph.style else ''
                if 'heading' in style_name or 'title' in style_name:
                    return text
                return text[:100]
    except:
        pass
    return Path(docx_path).stem


def get_description_from_docx(docx_path, max_length=200):
    """Extract description from first few paragraphs"""
    try:
        doc = Document(docx_path)
        text_parts = []
        for paragraph in doc.paragraphs[1:6]:
            text = paragraph.text.strip()
            if text:
                text_parts.append(text)
        full_text = ' '.join(text_parts)
        if len(full_text) > max_length:
            full_text = full_text[:max_length].rsplit(' ', 1)[0] + '...'
        return full_text
    except:
        return ''


CSP_CONTENT = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self' https://gateway.umami.is; "
    "object-src 'none'; base-uri 'self'; form-action 'self'"
)


def csp_meta():
    return f'<meta http-equiv="Content-Security-Policy" content="{CSP_CONTENT}">'


def umami_tag(prefix=''):
    return (
        f'<script defer src="{prefix}js/vendor/umami.js" '
        'data-website-id="4bf9e517-428f-466b-a83e-5873974e1e8f"></script>'
    )


def fonts_tag(prefix=''):
    return f'<link rel="stylesheet" href="{prefix}css/fonts.css">'


def create_document_page(title, content, doc_id, author_name, completed, prefix="../", download_rel=None):
    """Create HTML page for a document"""
    author_slug = slugify(author_name)
    if download_rel:
        download_url = download_rel
    else:
        download_url = f'downloads/{author_slug}/{doc_id}.docx'
    status_badge = '<span class="badge completed">مكتمل</span>' if completed else '<span class="badge in-progress">قيد الترجمة</span>'
    safe_title = escape_html(title)
    safe_author = escape_html(author_name)
    return f'''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {csp_meta()}
    <title>{safe_title} - ترجمات تعليقات الكتاب المقدس</title>
    {fonts_tag(prefix)}
    <link rel="stylesheet" href="{prefix}css/style.css">
    <link rel="stylesheet" href="{prefix}css/document.css">
    <script src="{prefix}js/theme-init.js"></script>
    {umami_tag(prefix)}
</head>
<body>
    <a class="skip-link" href="#main-content">تخطي إلى المحتوى الرئيسي</a>
    <header class="site-header">
        <div class="container">
            <a href="{prefix}index.html" class="logo">
                <span class="cross">✝</span>
                <span class="logo-text">ترجمات تعليقات الكتاب المقدس</span>
            </a>
            <nav class="main-nav">
                <a href="{prefix}index.html">الرئيسية</a>
                <a href="{prefix}authors.html">المؤلفون</a>
                <a href="{prefix}index.html#other_docs">المؤلفون والمواضيع الأخرى</a>
            </nav>
            <div class="header-actions">
                <button type="button" class="theme-toggle" id="themeToggle" aria-pressed="false" aria-label="تبديل المظهر">
                    <span class="theme-icon-moon" aria-hidden="true">&#9790;</span>
                    <span class="theme-icon-sun" aria-hidden="true">&#9728;</span>
                </button>
            </div>
        </div>
    </header>
    <main id="main-content" class="document-viewer">
        <div class="container">
            <div class="document-header">
                <div class="breadcrumb">
                    <a href="{prefix}index.html">الرئيسية</a>
                    <span class="separator">&larr;</span>
                    <a href="{prefix}authors/{author_slug}/index.html">{safe_author}</a>
                </div>
                <h1 class="document-title">{safe_title} {status_badge}</h1>
                <p class="document-author">المؤلف: {safe_author}</p>
                <div class="document-actions">
                    <a href="{escape_html(prefix + download_url)}" class="btn btn-download" download>
                        <span class="btn-icon">&#128229;</span>
                        <span class="btn-text">تحميل الملف الأصلي</span>
                    </a>
                    <button type="button" data-action="print" class="btn btn-print">
                        <span class="btn-icon">&#128424;</span>
                        <span class="btn-text">طباعة</span>
                    </button>
                </div>
            </div>
            <article class="document-content">
                {content}
            </article>
            <div class="document-footer">
                <div class="back-link">
                    <a href="{prefix}authors/{author_slug}/index.html">العودة إلى المؤلف</a>
                </div>
            </div>
        </div>
    </main>
    <footer class="site-footer">
        <div class="container">
            <p>ترجمات تعليقات الكتاب المقدس</p>
            <p class="footer-cross">&#10013;</p>
        </div>
    </footer>
    <script src="{prefix}js/dom.js"></script>
    <script src="{prefix}js/theme.js"></script>
    <script src="{prefix}js/ui.js"></script>
    <script src="{prefix}js/search.js"></script>
</body>
</html>'''


HIDDEN_FOLDER_NAMES = {'hidden', 'مخفي'}


def _is_hidden_folder(name: str) -> bool:
    return name.lower() in HIDDEN_FOLDER_NAMES or name in HIDDEN_FOLDER_NAMES


def scan_source_directory(input_dir):
    """Recursively scan source directory, preserving subfolder structure.
    Tracks relative path from author root for each document.
    Status folders: تم = completed, hidden/مخفي = hidden."""
    documents = []
    for author_name in sorted(os.listdir(input_dir)):
        author_path = os.path.join(input_dir, author_name)
        if not os.path.isdir(author_path):
            continue
        if author_name in ['Rubbish', 'Trados', 'كتب ترانيم']:
            continue
        _scan_recursive(author_path, author_path, author_name, documents, is_done=False, is_hidden=False)
    return documents


def _scan_recursive(current_path, author_root, author_name, documents, is_done, is_hidden):
    """Recursively scan a directory for .docx files.
    Exact folder 'تم' marks subtree completed; 'hidden'/'مخفي' marks subtree hidden."""
    for item in sorted(os.listdir(current_path)):
        item_path = os.path.join(current_path, item)
        if os.path.isdir(item_path):
            if item == 'تم':
                _scan_recursive(item_path, author_root, author_name, documents, True, is_hidden)
            elif _is_hidden_folder(item):
                _scan_recursive(item_path, author_root, author_name, documents, is_done, True)
            else:
                sub_is_done = is_done or ('تم' in item and item != 'تم')
                sub_is_hidden = is_hidden or _is_hidden_folder(item)
                _scan_recursive(item_path, author_root, author_name, documents, sub_is_done, sub_is_hidden)
        elif item.lower().endswith('.docx') and not item.startswith('~'):
            rel_path = os.path.relpath(current_path, author_root)
            if rel_path == '.':
                rel_path = ''
            documents.append({
                'author': author_name,
                'filename': item,
                'filepath': item_path,
                'rel_path': rel_path,
                'completed': is_done,
                'hidden': is_hidden
            })


def main():
    base_dir = Path(__file__).parent.parent
    input_dir = Path('D:\\MegaDrive\\ترجمات')
    output_dir = base_dir / 'docs'
    local_hidden_dir = base_dir / 'local-hidden'
    if not input_dir.exists():
        print(f'[ERROR] Input directory not found: {input_dir}')
        sys.exit(1)
    docs_dir = output_dir / 'documents'
    downloads_dir = output_dir / 'downloads'
    hidden_docs_dir = local_hidden_dir / 'documents'
    hidden_dl_dir = local_hidden_dir / 'downloads'
    docs_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir.mkdir(parents=True, exist_ok=True)
    hidden_docs_dir.mkdir(parents=True, exist_ok=True)
    hidden_dl_dir.mkdir(parents=True, exist_ok=True)
    print('[SCAN] Scanning source directory...')
    source_docs = scan_source_directory(input_dir)
    print(f'[SCAN] Found {len(source_docs)} documents ({sum(1 for d in source_docs if d["completed"])} completed, {sum(1 for d in source_docs if d.get("hidden"))} hidden)')
    documents = []
    doc_counter = 0
    for source_doc in source_docs:
        doc_id = f"doc_{doc_counter:04d}"
        doc_counter += 1
        title = get_title_from_docx(source_doc['filepath'])
        content = extract_text_from_docx(source_doc['filepath'])
        description = get_description_from_docx(source_doc['filepath'])
        author_slug = slugify(source_doc['author'])
        rel_path = source_doc['rel_path']
        is_hidden = bool(source_doc.get('hidden', False))
        # Hidden docs are written OUTSIDE docs/ so they are never published
        if is_hidden:
            page_root = local_hidden_dir
            docs_root = hidden_docs_dir
            dls_root = hidden_dl_dir
        else:
            page_root = output_dir
            docs_root = docs_dir
            dls_root = downloads_dir
        # Build output paths preserving subfolder structure
        if rel_path:
            rel_path_slug = slugify(rel_path.replace(os.sep, '-'))
            doc_out_dir = docs_root / author_slug / rel_path_slug
            dl_out_dir = dls_root / author_slug / rel_path_slug
        else:
            doc_out_dir = docs_root / author_slug
            dl_out_dir = dls_root / author_slug
        doc_out_dir.mkdir(parents=True, exist_ok=True)
        dl_out_dir.mkdir(parents=True, exist_ok=True)
        doc_filename = f"{doc_id}.html"
        doc_path = doc_out_dir / doc_filename
        rel_to_root = doc_path.relative_to(page_root)
        depth = len(rel_to_root.parts)
        if is_hidden:
            # URL is /local-hidden/... so one extra level up to reach site root
            prefix = '../' * (depth + 1)
        else:
            prefix = '../' * depth
        download_path = dl_out_dir / f"{doc_id}.docx"
        download_rel = str(download_path.relative_to(page_root)).replace(os.sep, '/')
        doc_html = create_document_page(title, content, doc_id, source_doc['author'], source_doc['completed'], prefix, download_rel)
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(doc_html)
        shutil.copy2(source_doc['filepath'], download_path)
        # Public paths are relative to docs/; hidden paths are served under /local-hidden/
        html_rel = str(doc_path.relative_to(page_root)).replace(os.sep, '/')
        dl_rel = str(download_path.relative_to(page_root)).replace(os.sep, '/')
        if is_hidden:
            html_rel = 'local-hidden/' + html_rel
            dl_rel = 'local-hidden/' + dl_rel
        documents.append({
            'id': doc_id,
            'title': title,
            'description': description,
            'author': source_doc['author'],
            'author_slug': author_slug,
            'completed': source_doc['completed'],
            'hidden': is_hidden,
            'categories': [],
            'category': 'uncategorized',
            'filename': source_doc['filename'],
            'rel_path': rel_path,
            'html_path': html_rel,
            'download_path': dl_rel,
            'file_hash': get_file_hash(source_doc['filepath'])
        })
        try:
            status = 'v' if source_doc['completed'] else 'o'
            print(f'  [{status}] {title[:50]}')
        except UnicodeEncodeError:
            print(f'  [{status}] Document {doc_id} converted')

    def _as_category_list(value):
        """Normalize assignment value: str | list | None -> list of slugs."""
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value and value != 'uncategorized' else []
        if isinstance(value, list):
            return [str(v) for v in value if v and v != 'uncategorized']
        return []

    # Load category assignments
    cat_file = base_dir / 'doc_categories.json'
    cat_assignments = {}
    if cat_file.exists():
        with open(cat_file, 'r', encoding='utf-8') as f:
            cat_data = json.load(f)
            cat_assignments = cat_data.get('assignments', {})
        print(f'[CAT] Loaded {len(cat_assignments)} category assignments')

    # Apply categories to documents (multi: categories[] + legacy category string)
    for doc in documents:
        doc_id = doc['id']
        filename = doc['filename']
        raw = cat_assignments.get(doc_id, cat_assignments.get(filename))
        cats = _as_category_list(raw)
        doc['categories'] = cats
        doc['category'] = cats[0] if cats else 'uncategorized'

    hidden_count = sum(1 for d in documents if d.get('hidden'))
    if hidden_count:
        print(f'[SCAN] {hidden_count} documents in hidden folders (written to local-hidden/)')

    # Public index.json: VISIBLE documents only (hidden docs never listed)
    visible_documents = [d for d in documents if not d.get('hidden', False)]

    def build_authors(docs_list):
        authors = {}
        for doc in docs_list:
            author = doc['author']
            if author not in authors:
                authors[author] = {
                    'slug': doc['author_slug'],
                    'total': 0,
                    'completed': 0
                }
            authors[author]['total'] += 1
            if doc['completed']:
                authors[author]['completed'] += 1
        return authors

    index_data = {
        'documents': visible_documents,
        'total_count': len(visible_documents),
        'completed_count': sum(1 for d in visible_documents if d['completed']),
        'authors': build_authors(visible_documents)
    }
    index_path = docs_dir / 'index.json'
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    # Local-only full index (incl. hidden) for the admin panel — never published
    admin_index = {
        'documents': documents,
        'total_count': len(documents),
        'completed_count': sum(1 for d in documents if d['completed']),
        'authors': build_authors(documents),
        'hidden_count': hidden_count,
    }
    admin_index_path = local_hidden_dir / 'documents-index.json'
    with open(admin_index_path, 'w', encoding='utf-8') as f:
        json.dump(admin_index, f, ensure_ascii=False, indent=2)

    print(f'\n[DONE] Converted {len(documents)} documents successfully')
    print(f'[DONE] Public index: {len(visible_documents)} visible ({hidden_count} hidden excluded)')
    print(f'[DONE] {index_data["completed_count"]} completed, {len(visible_documents) - index_data["completed_count"]} in progress')
    print(f'[DONE] Files at: {output_dir}')
    print(f'[DONE] Hidden files at: {local_hidden_dir}')
    return documents
