#!/usr/bin/env python3
"""
Word to HTML Converter for Arabic Christian Translations
Scans author folders, detects completion status (تم subfolder),
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
    """Escape HTML special characters"""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


def process_runs(runs):
    """Process formatting runs in a paragraph"""
    parts = []
    for run in runs:
        text = run.text
        if not text:
            continue
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
        parts.append(formatted)
    return ''.join(parts)


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
                formatted_text = process_runs(paragraph.runs)
                if formatted_text.strip():
                    html_parts.append(f'<h{level}>{formatted_text}</h{level}>')
                continue
            if 'list' in style_name:
                formatted_text = process_runs(paragraph.runs)
                if formatted_text.strip():
                    html_parts.append(f'<li>{formatted_text}</li>')
                continue
            if not text:
                html_parts.append('<p class="empty-line">&nbsp;</p>')
                continue
            formatted_text = process_runs(paragraph.runs)
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
                    cell_text = ' '.join(p.text.strip() for p in cell.paragraphs if p.text.strip())
                    tag = 'th' if i == 0 else 'td'
                    html_parts.append(f'<{tag}>{cell_text}</{tag}>')
                html_parts.append('</tr>')
            html_parts.append('</table></div>')
        result = '\n'.join(html_parts)
        result = re.sub(r'(<p class="empty-line">&nbsp;</p>\s*){2,}', '<p class="empty-line">&nbsp;</p>', result)
        return result
    except Exception as e:
        return f'<p class="error">خطأ في قراءة الملف: {str(e)}</p>'


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


def create_document_page(title, content, doc_id, author_name, completed, prefix="../"):
    """Create HTML page for a document"""
    author_slug = slugify(author_name)
    download_url = f'downloads/{author_slug}/{doc_id}.docx' 
    status_badge = '<span class="badge completed">مكتمل</span>' if completed else '<span class="badge in-progress">قيد الترجمة</span>'
    return f'''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - ترجمات تعليقات الكتاب المقدس</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Naskh+Arabic:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="{prefix}css/style.css">
    <link rel="stylesheet" href="{prefix}css/document.css">
</head>
<body>
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
        </div>
    </header>
    <main class="document-viewer">
        <div class="container">
            <div class="document-header">
                <div class="breadcrumb">
                    <a href="{prefix}index.html">الرئيسية</a>
                    <span class="separator">&larr;</span>
                    <a href="{prefix}authors/{author_slug}/index.html">{author_name}</a>
                </div>
                <h1 class="document-title">{title} {status_badge}</h1>
                <p class="document-author">المؤلف: {author_name}</p>
                <div class="document-actions">
                    <a href="{prefix}{download_url}" class="btn btn-download" download>
                        <span class="btn-icon">&#128229;</span>
                        <span class="btn-text">تحميل الملف الأصلي</span>
                    </a>
                    <button onclick="window.print()" class="btn btn-print">
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
    <script src="{prefix}js/search.js"></script>
</body>
</html>'''


def scan_source_directory(input_dir):
    """Recursively scan source directory, preserving subfolder structure.
    Tracks relative path from author root for each document."""
    documents = []
    for author_name in sorted(os.listdir(input_dir)):
        author_path = os.path.join(input_dir, author_name)
        if not os.path.isdir(author_path):
            continue
        if author_name in ['Rubbish', 'Trados', 'كتب ترانيم']:
            continue
        # Recursively scan all subfolders
        _scan_recursive(author_path, author_path, author_name, documents, is_done=False)
    return documents


def _scan_recursive(current_path, author_root, author_name, documents, is_done):
    """Recursively scan a directory for .docx files."""
    for item in sorted(os.listdir(current_path)):
        item_path = os.path.join(current_path, item)
        if os.path.isdir(item_path):
            # Check if this is a "done" folder
            sub_is_done = is_done or ('تم' in item and item != 'تم')
            # Special case: exact "تم" folder marks its SIBLING files as done
            if item == 'تم':
                # Files in this folder are completed
                _scan_done_folder(item_path, author_root, author_name, documents)
            else:
                # Recurse into subfolder
                _scan_recursive(item_path, author_root, author_name, documents, sub_is_done)
        elif item.lower().endswith('.docx') and not item.startswith('~'):
            # Calculate relative path from author root
            rel_path = os.path.relpath(current_path, author_root)
            if rel_path == '.':
                rel_path = ''
            documents.append({
                'author': author_name,
                'filename': item,
                'filepath': item_path,
                'rel_path': rel_path,
                'completed': is_done
            })


def _scan_done_folder(done_path, author_root, author_name, documents):
    """Scan a "تم" folder and mark all files as completed."""
    for root, dirs, files in os.walk(done_path):
        for f in sorted(files):
            if f.lower().endswith('.docx') and not f.startswith('~'):
                f_path = os.path.join(root, f)
                rel_path = os.path.relpath(root, author_root)
                if rel_path == '.':
                    rel_path = ''
                documents.append({
                    'author': author_name,
                    'filename': f,
                    'filepath': f_path,
                    'rel_path': rel_path,
                    'completed': True
                })
def main():
    base_dir = Path(__file__).parent.parent
    input_dir = Path('D:\\MegaDrive\\ترجمات')
    output_dir = base_dir / 'docs'
    if not input_dir.exists():
        print(f'[ERROR] Input directory not found: {input_dir}')
        sys.exit(1)
    docs_dir = output_dir / 'documents'
    downloads_dir = output_dir / 'downloads'
    docs_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir.mkdir(parents=True, exist_ok=True)
    print('[SCAN] Scanning source directory...')
    source_docs = scan_source_directory(input_dir)
    print(f'[SCAN] Found {len(source_docs)} documents ({sum(1 for d in source_docs if d["completed"])} completed)')
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
        # Build output paths preserving subfolder structure
        if rel_path:
            rel_path_slug = slugify(rel_path.replace(os.sep, '-'))
            doc_out_dir = docs_dir / author_slug / rel_path_slug
            dl_out_dir = downloads_dir / author_slug / rel_path_slug
        else:
            doc_out_dir = docs_dir / author_slug
            dl_out_dir = downloads_dir / author_slug
        doc_out_dir.mkdir(parents=True, exist_ok=True)
        dl_out_dir.mkdir(parents=True, exist_ok=True)
        doc_filename = f"{doc_id}.html"
        doc_path = doc_out_dir / doc_filename
        # Calculate depth for relative paths in HTML
        # doc_path is like docs/documents/author/file.html
        # We need to get back to docs/ (2 levels up from author/)
        rel_to_docs = doc_path.relative_to(docs_dir)
        depth = len(rel_to_docs.parts)  # includes filename, so subtract 0 for dir depth
        # For docs/documents/author/file.html, parts = (author, file.html)
        # We need ../../ to get to docs/, so depth = len(parts)
        prefix = '../' * depth
        doc_html = create_document_page(title, content, doc_id, source_doc['author'], source_doc['completed'], prefix)
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(doc_html)
        download_path = dl_out_dir / f"{doc_id}.docx"
        shutil.copy2(source_doc['filepath'], download_path)
        # Store relative paths from output dir (docs/)
        html_rel = str(doc_path.relative_to(output_dir)).replace(os.sep, '/')
        dl_rel = str(download_path.relative_to(output_dir)).replace(os.sep, '/')
        documents.append({
            'id': doc_id,
            'title': title,
            'description': description,
            'author': source_doc['author'],
            'author_slug': author_slug,
            'completed': source_doc['completed'],
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
    # Load category assignments
    cat_file = base_dir / 'doc_categories.json'
    cat_assignments = {}
    if cat_file.exists():
        with open(cat_file, 'r', encoding='utf-8') as f:
            cat_data = json.load(f)
            cat_assignments = cat_data.get('assignments', {})
        print(f'[CAT] Loaded {len(cat_assignments)} category assignments')

    # Apply categories to documents
    for doc in documents:
        doc_id = doc['id']
        filename = doc['filename']
        cat = cat_assignments.get(doc_id, cat_assignments.get(filename, 'uncategorized'))
        doc['category'] = cat

    # Load overrides (completed + hidden)
    overrides_file = base_dir / 'doc_overrides.json'
    overrides = {}
    if overrides_file.exists():
        with open(overrides_file, 'r', encoding='utf-8') as f:
            ov_data = json.load(f)
            overrides = ov_data.get('overrides', {})
        print(f'[OV] Loaded {len(overrides)} document overrides')

    # Apply overrides
    hidden_count = 0
    override_count = 0
    for doc in documents:
        doc_id = doc['id']
        filename = doc['filename']
        ov = overrides.get(doc_id, overrides.get(filename, None))
        if ov:
            if 'completed' in ov:
                doc['completed'] = ov['completed']
                override_count += 1
            if ov.get('hidden', False):
                doc['hidden'] = True
                hidden_count += 1
    if override_count > 0:
        print(f'[OV] Applied {override_count} completed overrides')
    if hidden_count > 0:
        print(f'[OV] Hiding {hidden_count} documents')

    # Filter out hidden documents (keep them in index.json with hidden flag for admin panel)
    visible_documents = [d for d in documents if not d.get('hidden', False)]

    index_data = {
        'documents': documents,
        'total_count': len(documents),
        'completed_count': sum(1 for d in visible_documents if d['completed']),
        'authors': {}
    }
    for doc in visible_documents:
        author = doc['author']
        if author not in index_data['authors']:
            index_data['authors'][author] = {
                'slug': doc['author_slug'],
                'total': 0,
                'completed': 0
            }
        index_data['authors'][author]['total'] += 1
        if doc['completed']:
            index_data['authors'][author]['completed'] += 1
    index_path = docs_dir / 'index.json'
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    print(f'\n[DONE] Converted {len(documents)} documents successfully')
    print(f'[DONE] {index_data["completed_count"]} completed, {len(documents) - index_data["completed_count"]} in progress')
    print(f'[DONE] Files at: {output_dir}')
    return documents
