#!/usr/bin/env python3
"""
Master Build Script for Arabic Christian Translations Website
Runs the conversion and generates the complete site in docs/
"""

import os
import sys
import json
import shutil
from datetime import datetime
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from convert import main as convert_documents
from convert import escape_html, csp_meta, umami_tag, fonts_tag

UMAMI_SNIPPET = umami_tag()


def setup_directories(base_dir):
    """Create necessary output directories"""
    docs_dir = base_dir / 'docs'
    
    directories = [
        docs_dir,
        docs_dir / 'css',
        docs_dir / 'js',
        docs_dir / 'assets',
        docs_dir / 'assets' / 'images',
        docs_dir / 'documents',
        docs_dir / 'downloads',
    ]
    
    for dir_path in directories:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    return docs_dir


def copy_static_files(base_dir, docs_dir):
    """Copy CSS, JS, fonts, and assets to docs/ (never admin-only files)."""
    # Copy CSS
    css_src = base_dir / 'css'
    css_dst = docs_dir / 'css'
    if css_src.exists():
        if css_dst.exists():
            shutil.rmtree(css_dst)
        shutil.copytree(css_src, css_dst)
        print(f'  [OK] CSS copied')

    # Copy JS (exclude local-only admin scripts)
    js_src = base_dir / 'js'
    js_dst = docs_dir / 'js'
    if js_src.exists():
        if js_dst.exists():
            shutil.rmtree(js_dst)
        shutil.copytree(js_src, js_dst, ignore=shutil.ignore_patterns('admin-*'))
        print(f'  [OK] JS copied (admin scripts excluded)')

    # Copy self-hosted fonts
    fonts_src = base_dir / 'fonts'
    fonts_dst = docs_dir / 'fonts'
    if fonts_src.exists():
        if fonts_dst.exists():
            shutil.rmtree(fonts_dst)
        shutil.copytree(fonts_src, fonts_dst)
        print(f'  [OK] Fonts copied')

    # Copy assets
    assets_src = base_dir / 'assets'
    assets_dst = docs_dir / 'assets'
    if assets_src.exists():
        if assets_dst.exists():
            shutil.rmtree(assets_dst)
        shutil.copytree(assets_src, assets_dst)
        print(f'  [OK] Assets copied')
    
    # Copy categories.json to docs root
    cat_src = base_dir / 'categories.json'
    if cat_src.exists():
        shutil.copy2(cat_src, docs_dir / 'categories.json')
        print(f'  [OK] categories.json copied')


def generate_random_articles(index_data):
    """Generate random 10 completed articles section for home page"""
    import random
    
    documents = index_data.get('documents', [])
    if not documents:
        return ''
    
    # Only completed articles
    completed = [d for d in documents if d.get('completed') is True]
    if not completed:
        return ''
    
    shuffled = list(completed)
    random.shuffle(shuffled)
    selected = shuffled[:10]
    
    html_parts = []
    html_parts.append('<div class="articles-grid">')
    
    for doc in selected:
        title = escape_html(doc.get('title', 'بدون عنوان'))
        author = escape_html(doc.get('author', 'غير معروف'))
        path = escape_html(doc.get('html_path', '#'))
        desc = doc.get('description', '')
        if desc and len(desc) > 150:
            desc = desc[:150] + '...'
        desc = escape_html(desc)
        
        html_parts.append(f'<a href="{path}" class="article-card">')
        html_parts.append(f'    <div class="article-title">{title}</div>')
        html_parts.append(f'    <div class="article-author">{author}</div>')
        if desc:
            html_parts.append(f'    <div class="article-desc">{desc}</div>')
        html_parts.append('</a>')
    
    html_parts.append('</div>')
    return '\n'.join(html_parts)


def generate_authors_section(index_data):
    """Generate HTML for authors section on the main page"""
    authors = index_data.get('authors', {})
    documents = index_data.get('documents', [])
    total_count = index_data.get('total_count', 0)
    completed_count = index_data.get('completed_count', 0)

    html_parts = []

    html_parts.append('<div class="stats-bar">')
    html_parts.append(f'    <span class="stat">\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0645\u0633\u062a\u0646\u062f\u0627\u062a: {total_count}</span>')
    html_parts.append(f'    <span class="stat completed">\u0645\u0643\u062a\u0645\u0644: {completed_count}</span>')
    html_parts.append(f'    <span class="stat in-progress">\u0642\u064a\u062f \u0627\u0644\u062a\u0631\u062c\u0645\u0629: {total_count - completed_count}</span>')
    html_parts.append('</div>')

    html_parts.append('<div class="authors-grid" id="authors">')

    for author_name in sorted(authors.keys()):
        author_info = authors[author_name]
        slug = author_info['slug']
        total = author_info['total']
        completed = author_info['completed']

        author_docs = [d for d in documents if d['author'] == author_name][:5]

        if completed == total and total > 0:
            status_class = 'completed'
            status_text = f'\u2713 {completed} \u0645\u0643\u062a\u0645\u0644'
        elif completed > 0:
            status_class = 'partial'
            status_text = f'{completed}/{total} \u0645\u0643\u062a\u0645\u0644'
        else:
            status_class = 'in-progress'
            status_text = f'{total} \u0642\u064a\u062f \u0627\u0644\u062a\u0631\u062c\u0645\u0629'

        html_parts.append(f'<a href="authors/{escape_html(slug)}/index.html" class="author-card">')
        html_parts.append(f'    <h3 class="author-name">{escape_html(author_name)}</h3>')
        html_parts.append(f'    <span class="author-count">{total} مستند</span>')
        html_parts.append(f'    <span class="author-status {status_class}">{escape_html(status_text)}</span>')
        html_parts.append('    <div class="author-docs">')

        for doc in author_docs:
            completed_class = 'completed' if doc.get('completed') else 'in-progress'
            doc_title = escape_html(doc.get('title', 'بدون عنوان'))
            html_parts.append(f'        <span class="doc-link {completed_class}">{doc_title}</span>')

        if total > 5:
            html_parts.append(f'        <span class="more-docs">\u0648 {total - 5} \u0645\u0633\u062a\u0646\u062f \u0622\u062e\u0631...</span>')

        html_parts.append('    </div>')
        html_parts.append('</a>')

    html_parts.append('</div>')

    return '\n'.join(html_parts)

def generate_index_html(base_dir, docs_dir, index_data):
    """Generate the main index.html from template"""
    template_path = base_dir / 'templates' / 'index.html'
    output_path = docs_dir / 'index.html'
    
    if not template_path.exists():
        print('  [WARNING] Template not found, generating minimal index.html')
        generate_minimal_index(output_path, index_data)
        return
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()
    
    # Inject book lists from categories.json
    categories_path = base_dir / 'categories.json'
    if categories_path.exists():
        with open(categories_path, 'r', encoding='utf-8') as f:
            cats = json.load(f)['categories']
        
        ot_books = cats['old_testament']['books']
        ot_html = chr(10).join([f'    <a href="#book-{b["slug"]}">{b["name_ar"]}</a>' for b in ot_books])
        template = template.replace('<!-- BOOKS_OT_PLACEHOLDER -->', ot_html)
        
        nt_books = cats['new_testament']['books']
        nt_html = chr(10).join([f'    <a href="#book-{b["slug"]}">{b["name_ar"]}</a>' for b in nt_books])
        template = template.replace('<!-- BOOKS_NT_PLACEHOLDER -->', nt_html)
        
        topic_books = cats['topics']['books']
        topics_html = chr(10).join([f'    <a href="#topic-{b["slug"]}">{b["name_ar"]}</a>' for b in topic_books])
        template = template.replace('<!-- BOOKS_TOPICS_PLACEHOLDER -->', topics_html)
        
        print(f'  [OK] Injected {len(ot_books)} OT, {len(nt_books)} NT, {len(topic_books)} topic books')
    
    authors_html = generate_authors_section(index_data)
    html = template.replace('<!-- AUTHORS_PLACEHOLDER -->', authors_html)
    
    # Generate random articles for home page
    random_articles_html = generate_random_articles(index_data)
    html = template.replace('<!-- RANDOM_ARTICLES_PLACEHOLDER -->', random_articles_html)
    
    total_count = index_data.get('total_count', 0)
    html = html.replace('id="totalDocs">0</span>', f'id="totalDocs">{total_count}</span>')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f'  [OK] index.html generated')


def generate_category_html(categories, index_data):
    """Generate HTML for all categories"""
    html_parts = []
    
    for cat_key, cat_data in categories['categories'].items():
        cat_slug = cat_data['slug']
        cat_name = cat_data['name_ar']
        
        # Get document count for this category
        cat_info = index_data.get('categories', {}).get(cat_key, {})
        doc_count = cat_info.get('count', 0)
        
        html_parts.append(f'''
        <section class="category-section" id="{cat_slug}">
            <h2 class="category-title">{cat_name}</h2>
            <div class="books-grid">
        ''')
        
        for book in cat_data['books']:
            book_slug = book['slug']
            book_name = book['name_ar']
            book_de = book['name_de']
            
            # Count documents for this book
            book_docs = [d for d in index_data.get('documents', []) 
                        if d.get('book') == book_slug or d.get('category') == book_slug]
            book_count = len(book_docs)
            
            if book_count > 0:
                html_parts.append(f'''
                <a href="documents/{book_slug}/" class="book-card has-docs" data-book="{book_slug}">
                    <span class="book-name-ar">{book_name}</span>
                    <span class="book-name-de">{book_de}</span>
                    <span class="book-count">{book_count} مستند</span>
                </a>
                ''')
            else:
                html_parts.append(f'''
                <div class="book-card" data-book="{book_slug}">
                    <span class="book-name-ar">{book_name}</span>
                    <span class="book-name-de">{book_de}</span>
                    <span class="book-count empty">قريباً</span>
                </div>
                ''')
        
        html_parts.append('''
            </div>
        </section>
        ''')
    
    # Add "other documents" section for all docs not in old_testament/new_testament/topics
    known_cats = set(categories['categories'].keys())
    other_docs = [d for d in index_data.get('documents', []) 
                         if d.get('category') not in known_cats]
    if other_docs:
        # Group by author/folder
        authors = {}
        for doc in other_docs:
            cat = doc.get('category', 'أخرى')
            if cat not in authors:
                authors[cat] = []
            authors[cat].append(doc)
        
        html_parts.append('''
        <section class="category-section" id="other_docs">
            <h2 class="category-title">المؤلفون والمواضيع الأخرى</h2>
            <p style="text-align:center;margin-bottom:2rem;color:var(--text-secondary);">
                ''' + f'{len(other_docs)} مستند من {len(authors)} مؤلف' + '''
            </p>
            <div class="authors-grid">
        ''')
        
        for author_name in sorted(authors.keys()):
            docs = authors[author_name]
            slug = author_name.replace(' ', '-').replace('.', '').lower()[:50]
            slug = ''.join(c for c in slug if c.isalnum() or c == '-')
            html_parts.append(f'''
            <a href="authors/{slug}/index.html" class="author-card">
                <h3 class="author-name">{author_name}</h3>
                <span class="author-count">{len(docs)} مستند</span>
                <div class="author-docs">
            ''')
            for doc in docs[:5]:  # Show first 5
                html_parts.append(f'''
                <span class="doc-link">{doc.get('title', 'بدون عنوان')}</span>
                ''')
            if len(docs) > 5:
                html_parts.append(f'<span class="more-docs">و {len(docs) - 5} مستند آخر...</span>')
            html_parts.append('''
                </div>
            </a>
            ''')
        
        html_parts.append('''
            </div>
        </section>
        ''')
    
    return '\n'.join(html_parts)


def generate_minimal_index(output_path, index_data):
    """Generate a minimal index.html if template is missing"""
    total_count = index_data.get('total_count', 0)
    
    html = f'''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {csp_meta()}
    <title>ترجمات تعليقات الكتاب المقدس</title>
    {fonts_tag()}
    <link rel="stylesheet" href="css/style.css">
    {UMAMI_SNIPPET}
</head>
<body>
    <header>
        <h1>✝ ترجمات تعليقات الكتاب المقدس</h1>
        <p>ترجمات عربية لتعليقات الكتاب المقدس من bibelkommentare.de</p>
    </header>
    <main>
        <p>تم العثور على {total_count} مستند.</p>
        <div id="documents-list"></div>
    </main>
    <script src="js/dom.js"></script>
    <script src="js/app.js"></script>
</body>
</html>'''
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


def generate_document_index_pages(base_dir, docs_dir, index_data):
    """Generate index pages for each category/book directory"""
    documents = index_data.get('documents', [])
    
    # Group by category
    categories = {}
    for doc in documents:
        cat = doc.get('category', 'uncategorized')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(doc)
    
    # Generate category index pages
    for cat, cat_docs in categories.items():
        cat_dir = docs_dir / 'documents' / cat
        cat_dir.mkdir(parents=True, exist_ok=True)
        
        # Group by book within category
        books = {}
        for doc in cat_docs:
            book = doc.get('book', 'uncategorized')
            if book not in books:
                books[book] = []
            books[book].append(doc)
        
        # Generate book index pages
        for book, book_docs in books.items():
            book_dir = cat_dir / book
            book_dir.mkdir(parents=True, exist_ok=True)
            
            index_html = f'''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {csp_meta()}
    <title>{escape_html(book)} - ترجمات تعليقات الكتاب المقدس</title>
    {fonts_tag('../../')}
    <link rel="stylesheet" href="../../css/style.css">
    {umami_tag('../../')}
</head>
<body>
    <a class="skip-link" href="#main-content">تخطي إلى المحتوى الرئيسي</a>
    <header class="site-header">
        <div class="container">
            <a href="../../index.html" class="logo">
                <span class="cross">✝</span>
                <span class="logo-text">ترجمات تعليقات الكتاب المقدس</span>
            </a>
        </div>
    </header>
    <main id="main-content" class="container">
        <h1>{book}</h1>
        <div class="documents-list">
'''
            for doc in book_docs:
                index_html += f'''
            <div class="document-item">
                <a href="{escape_html(doc['id'])}.html">{escape_html(doc['title'])}</a>
                <p>{escape_html(doc.get('description', '')[:100])}...</p>
            </div>
'''
            
            index_html += '''
        </div>
        <div class="back-link">
            <a href="../../index.html">← العودة إلى الرئيسية</a>
        </div>
    </main>
</body>
</html>'''
            
            index_path = book_dir / 'index.html'
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(index_html)
    
    print(f'  [OK] Document index pages generated')


def generate_author_pages(docs_dir, index_data):
    """Generate individual author pages with documents grouped by subfolder"""
    import urllib.parse
    from collections import defaultdict
    documents = index_data.get('documents', [])
    authors = index_data.get('authors', {})

    print(f'  [INFO] Generating pages for {len(authors)} authors')

    authors_dir = docs_dir / 'authors'
    authors_dir.mkdir(parents=True, exist_ok=True)

    for author_name, author_info in authors.items():
        slug = author_info.get('slug', '')
        total = author_info.get('total', 0)
        completed = author_info.get('completed', 0)

        author_docs = [d for d in documents if d.get('author') == author_name]

        author_dir = authors_dir / slug
        author_dir.mkdir(parents=True, exist_ok=True)

        # Group documents by subfolder
        grouped = defaultdict(list)
        for doc in author_docs:
            rel = doc.get('rel_path', '')
            grouped[rel].append(doc)

        # Build HTML with subfolder sections
        docs_html = ''
        # Sort: root files first, then subfolders alphabetically
        sorted_keys = sorted(grouped.keys(), key=lambda k: (k != '', k))
        
        for rel_path in sorted_keys:
            docs = grouped[rel_path]
            # Show subfolder name as section header
            if rel_path:
                folder_display = rel_path.replace(os.sep, ' / ').replace('-', ' ')
                docs_html += f'<div class="subfolder-section">'
                docs_html += f'<h3 class="subfolder-title">{folder_display}</h3>'
            
            for doc in sorted(docs, key=lambda d: d.get('title', '')):
                title = escape_html(doc.get('title', 'بدون عنوان'))
                desc = escape_html(doc.get('description', '')[:150])
                html_path = escape_html(doc.get('html_path', '#'))
                download_path = escape_html(doc.get('download_path', '#'))
                is_completed = doc.get('completed', False)

                if is_completed:
                    badge = '<span class="badge completed">\u2713 \u0645\u0643\u062a\u0645\u0644</span>'
                else:
                    badge = '<span class="badge in-progress">\u0642\u064a\u062f \u0627\u0644\u062a\u0631\u062c\u0645\u0629</span>'

                docs_html += '<div class="document-item">'
                docs_html += f'<a href="../../{html_path}" class="doc-title">{title} {badge}</a>'
                docs_html += f'<p class="doc-desc">{desc}...</p>'
                docs_html += f'<a href="../../{download_path}" class="doc-download" download>\u062a\u062d\u0645\u064a\u0644</a>'
                docs_html += '</div>\n'
            
            if rel_path:
                docs_html += '</div>'

        if completed == total and total > 0:
            status_class = 'completed'
            status_text = f'\u2713 \u062c\u0645\u064a\u0639 \u0627\u0644\u0645\u0633\u062a\u0646\u062f\u0627\u062a \u0645\u0643\u062a\u0645\u0644\u0629 ({completed})'
        elif completed > 0:
            status_class = 'partial'
            status_text = f'{completed} \u0645\u0643\u062a\u0645\u0644 \u0645\u0646 {total}'
        else:
            status_class = 'in-progress'
            status_text = f'\u062c\u0645\u064a\u0639 \u0627\u0644\u0645\u0633\u062a\u0646\u062f\u0627\u062a \u0642\u064a\u062f \u0627\u0644\u062a\u0631\u062c\u0645\u0629 ({total})'

        page = []
        page.append('<!DOCTYPE html>')
        page.append('<html lang="ar" dir="rtl">')
        page.append('<head>')
        page.append('    <meta charset="UTF-8">')
        page.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        page.append(f'    {csp_meta()}')
        page.append(f'    <title>{escape_html(author_name)} - ترجمات تعليقات الكتاب المقدس</title>')
        page.append(f'    {fonts_tag("../../")}')
        page.append('    <link rel="stylesheet" href="../../css/style.css">')
        page.append('    <link rel="stylesheet" href="../../css/fonts.css">')
        page.append('    <script src="../../js/theme-init.js"></script>')
        page.append('    <style>')
        page.append('        .subfolder-section { margin: 1.5rem 0; padding: 1rem; background: var(--bg-light); border-radius: var(--radius-md); }')
        page.append('        .subfolder-title { color: var(--color-primary); font-size: 1.1rem; margin-bottom: 0.75rem; padding-bottom: 0.5rem; border-bottom: 2px solid var(--color-secondary); }')
        page.append('    </style>')
        page.append(f'    {umami_tag("../../")}')
        page.append('</head>')
        page.append('<body>')
        page.append('    <a class="skip-link" href="#main-content">تخطي إلى المحتوى الرئيسي</a>')
        page.append('    <header class="site-header">')
        page.append('        <div class="header-top"><div class="container">')
        page.append('            <a href="../../index.html" class="logo">')
        page.append('                <span class="cross">✝</span>')
        page.append('                <span class="logo-text">ترجمات تعليقات الكتاب المقدس</span>')
        page.append('            </a>')
        page.append('            <div class="header-actions">')
        page.append('                <button type="button" class="theme-toggle" id="themeToggle" aria-pressed="false" aria-label="تبديل المظهر">')
        page.append('                    <span class="theme-icon-moon" aria-hidden="true">&#9790;</span>')
        page.append('                    <span class="theme-icon-sun" aria-hidden="true">&#9728;</span>')
        page.append('                </button>')
        page.append('            </div>')
        page.append('        </div></div>')
        page.append('    </header>')
        page.append('    <main id="main-content" class="author-page">')
        page.append('        <div class="container">')
        page.append('            <div class="breadcrumb">')
        page.append('                <a href="../../index.html">\u0627\u0644\u0631\u0626\u064a\u0633\u064a\u0629</a>')
        page.append('                <span class="separator">&larr;</span>')
        page.append(f'                <span class="current">{escape_html(author_name)}</span>')
        page.append('            </div>')
        page.append(f'            <h1 class="author-title">{escape_html(author_name)}</h1>')
        page.append(f'            <p class="author-count">{total} \u0645\u0633\u062a\u0646\u062f</p>')
        page.append(f'            <p class="author-status {status_class}">{status_text}</p>')
        page.append('            <div class="documents-list">')
        page.append(docs_html)
        page.append('            </div>')
        page.append('            <div class="back-link">')
        page.append('                <a href="../../index.html">\u0627\u0644\u0639\u0648\u062f\u0629 \u0625\u0644\u0649 \u0627\u0644\u0631\u0626\u064a\u0633\u064a\u0629</a>')
        page.append('            </div>')
        page.append('        </div>')
        page.append('    </main>')
        page.append('    <footer class="site-footer">')
        page.append('        <div class="container">')
        page.append('            <p>\u062a\u0631\u062c\u0645\u0627\u062a \u062a\u0639\u0644\u064a\u0642\u0627\u062a \u0627\u0644\u0643\u062a\u0627\u0628 \u0627\u0644\u0645\u0642\u062f\u0633</p>')
        page.append('            <p class="footer-cross">\u271d</p>')
        page.append('        </div>')
        page.append('    </footer>')
        page.append('    <script src="../../js/dom.js"></script>')
        page.append('    <script src="../../js/theme.js"></script>')
        page.append('    <script src="../../js/ui.js"></script>')
        page.append('</body>')
        page.append('</html>')

        page_path = author_dir / 'index.html'
        with open(page_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(page))

    print(f'  [OK] Generated {len(authors)} author pages')

def generate_authors_page(docs_dir, index_data):
    """Generate a separate authors.html page"""
    authors = index_data.get('authors', {})
    documents = index_data.get('documents', [])
    
    html_parts = []
    html_parts.append('<!DOCTYPE html>')
    html_parts.append('<html lang="ar" dir="rtl">')
    html_parts.append('<head>')
    html_parts.append('    <meta charset="UTF-8">')
    html_parts.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    html_parts.append(f'    {csp_meta()}')
    html_parts.append('    <title>المؤلفون - ترجمات تعليقات الكتاب المقدس</title>')
    html_parts.append(f'    {fonts_tag()}')
    html_parts.append('    <link rel="stylesheet" href="css/fonts.css">')
    html_parts.append('    <link rel="stylesheet" href="css/style.css">')
    html_parts.append('    <link rel="icon" href="data:image/svg+xml,<svg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 100 100\'><text y=\'.9em\' font-size=\'90\'>✝</text></svg>">')
    html_parts.append('    <script src="js/theme-init.js"></script>')
    html_parts.append(f'    {UMAMI_SNIPPET}')
    html_parts.append('</head>')
    html_parts.append('<body>')
    html_parts.append('    <a class="skip-link" href="#main-content">تخطي إلى المحتوى الرئيسي</a>')
    html_parts.append('    <header class="site-header">')
    html_parts.append('        <div class="header-top">')
    html_parts.append('            <div class="container">')
    html_parts.append('                <a href="index.html" class="logo">')
    html_parts.append('                    <span class="cross">&#10013;</span>')
    html_parts.append('                    <span class="logo-text">\u062a\u0631\u062c\u0645\u0627\u062a \u062a\u0639\u0644\u064a\u0642\u0627\u062a \u0627\u0644\u0643\u062a\u0627\u0628 \u0627\u0644\u0645\u0642\u062f\u0633</span>')
    html_parts.append('                </a>')
    html_parts.append('                <div class="header-search">')
    html_parts.append('                    <input type="text" id="searchInput" placeholder="\u0627\u0628\u062d\u062b..." autocomplete="off">')
    html_parts.append('                    <span class="search-icon-btn">&#128269;</span>')
    html_parts.append('                    <div class="search-results" id="searchResults"></div>')
    html_parts.append('                </div>')
    html_parts.append('                <div class="header-actions">')
    html_parts.append('                    <button type="button" class="theme-toggle" id="themeToggle" aria-pressed="false" aria-label="تبديل المظهر">')
    html_parts.append('                        <span class="theme-icon-moon" aria-hidden="true">&#9790;</span>')
    html_parts.append('                        <span class="theme-icon-sun" aria-hidden="true">&#9728;</span>')
    html_parts.append('                    </button>')
    html_parts.append('                </div>')
    html_parts.append('                <div class="nav-toggle" id="navToggle">')
    html_parts.append('                    <span class="nav-toggle-open">&#9776;</span>')
    html_parts.append('                    <span class="nav-toggle-close">&times;</span>')
    html_parts.append('                </div>')
    html_parts.append('            </div>')
    html_parts.append('        </div>')
    html_parts.append('        <nav class="nav-bar" id="navBar">')
    html_parts.append('            <div class="container">')
    html_parts.append('                <div class="nav-item">')
    html_parts.append('                    <a href="index.html" class="nav-link">\u0627\u0644\u0631\u0626\u064a\u0633\u064a\u0629</a>')
    html_parts.append('                </div>')
    html_parts.append('                <div class="nav-item">')
    html_parts.append('                    <a href="translations.html" class="nav-link">\u0627\u0644\u062a\u0631\u062c\u0645\u0627\u062a</a>')
    html_parts.append('                </div>')
    html_parts.append('                <div class="nav-item">')
    html_parts.append('                    <a href="authors.html" class="nav-link active">\u0627\u0644\u0645\u0624\u0644\u0641\u0648\u0646</a>')
    html_parts.append('                </div>')
    html_parts.append('            </div>')
    html_parts.append('        </nav>')
    html_parts.append('    </header>')
    html_parts.append('    <main id="main-content" class="author-page">')
    html_parts.append('        <div class="container">')
    html_parts.append('            <h1 class="author-title">\u0627\u0644\u0645\u0624\u0644\u0641\u0648\u0646</h1>')
    html_parts.append(f'            <p class="author-count">{len(authors)} \u0645\u0624\u0644\u0641</p>')
    html_parts.append('            <div class="filter-section">')
    html_parts.append('                <div class="filter-container">')
    html_parts.append('                    <button class="filter-btn active" data-filter="all">\u0627\u0644\u0643\u0644</button>')
    html_parts.append('                    <button class="filter-btn" data-filter="completed">\u2713 \u0645\u0643\u062a\u0645\u0644</button>')
    html_parts.append('                    <button class="filter-btn" data-filter="in-progress">\u0642\u064a\u062f \u0627\u0644\u062a\u0631\u062c\u0645\u0629</button>')
    html_parts.append('                </div>')
    html_parts.append('            </div>')
    html_parts.append('            <div class="authors-grid">')
    
    for author_name in sorted(authors.keys()):
        author_info = authors[author_name]
        slug = author_info['slug']
        total = author_info['total']
        completed = author_info['completed']
        
        if completed == total and total > 0:
            status_class = 'completed'
            status_text = f'\u2713 {completed} \u0645\u0643\u062a\u0645\u0644'
        elif completed > 0:
            status_class = 'partial'
            status_text = f'{completed}/{total} \u0645\u0643\u062a\u0645\u0644'
        else:
            status_class = 'in-progress'
            status_text = f'{total} \u0642\u064a\u062f \u0627\u0644\u062a\u0631\u062c\u0645\u0629'
        
        # Get first 3 doc titles for this author
        author_docs = [d for d in documents if d.get('author') == author_name][:3]
        docs_preview = ''
        if author_docs:
            docs_preview = '<div class="author-docs-preview">'
            for d in author_docs:
                doc_title = escape_html(d.get('title', 'بدون عنوان'))
                is_done = d.get('completed', False)
                icon = '&#10003;' if is_done else '&#9679;'
                cls = 'completed' if is_done else 'in-progress'
                docs_preview += f'<span class="doc-preview-title {cls}"><span class="doc-icon">{icon}</span> {doc_title}</span>'
            if total > 3:
                docs_preview += f'<span class="doc-preview-more">و {total - 3} مستندات أخرى...</span>'
            docs_preview += '</div>'
        
        html_parts.append(f'            <a href="authors/{escape_html(slug)}/index.html" class="author-card" data-status="{status_class}">')
        html_parts.append(f'                <h3 class="author-name">{escape_html(author_name)}</h3>')
        html_parts.append(f'                <span class="author-count">{total} مستند</span>')
        html_parts.append(f'                <span class="author-status {status_class}">{escape_html(status_text)}</span>')
        html_parts.append(f'                {docs_preview}')
        html_parts.append('            </a>')
    
    html_parts.append('            </div>')
    html_parts.append('        </div>')
    html_parts.append('    </main>')
    html_parts.append('    <footer class="site-footer">')
    html_parts.append('        <div class="container footer-grid">')
    html_parts.append('            <div class="footer-brand">')
    html_parts.append('                <p>\u062a\u0631\u062c\u0645\u0627\u062a \u062a\u0639\u0644\u064a\u0642\u0627\u062a \u0627\u0644\u0643\u062a\u0627\u0628 \u0627\u0644\u0645\u0642\u062f\u0633</p>')
    html_parts.append('            </div>')
    html_parts.append('            <div>')
    html_parts.append('                <h3>المحتوى</h3>')
    html_parts.append('                <button type="button" data-href="index.html">الرئيسية</button>')
    html_parts.append('                <button type="button" data-href="translations.html">الترجمات</button>')
    html_parts.append('                <button type="button" data-href="authors.html">المؤلفون</button>')
    html_parts.append('                <button type="button" data-href="index.html#newsletterForm">النشرة البريدية</button>')
    html_parts.append('            </div>')
    html_parts.append('        </div>')
    html_parts.append('        <div class="footer-bottom container">')
    html_parts.append('            <span>© 2024 - 2026 ترجمات تعليقات الكتاب المقدس</span>')
    html_parts.append('        </div>')
    html_parts.append('    </footer>')
    html_parts.append('    <script src="js/data-visible.js"></script>')
    html_parts.append('    <script src="js/dom.js"></script>')
    html_parts.append('    <script src="js/theme.js"></script>')
    html_parts.append('    <script src="js/nav.js"></script>')
    html_parts.append('    <script src="js/ui.js"></script>')
    html_parts.append('    <script src="js/app.js"></script>')
    html_parts.append('    <script src="js/search.js"></script>')
    html_parts.append('</body>')
    html_parts.append('</html>')
    
    output_path = docs_dir / 'authors.html'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_parts))
    
    print(f'  [OK] authors.html generated')


def copy_translations_page(base_dir, docs_dir):
    """Copy translations.html from templates to docs"""
    src = base_dir / 'templates' / 'translations.html'
    dst = docs_dir / 'translations.html'
    if src.exists():
        shutil.copy2(src, dst)
        print(f'  [OK] translations.html copied')
    else:
        print(f'  [WARNING] translations.html not found in templates')


def write_site_data(docs_dir, index_data):
    """Write external data file (CSP-safe replacement for inline <script> JSON)."""
    base_dir = Path(__file__).parent.parent
    cats_path = base_dir / 'categories.json'
    categories = {}
    if cats_path.exists():
        with open(cats_path, 'r', encoding='utf-8') as f:
            categories = json.load(f)

    docs_json = json.dumps(index_data.get('documents', []), ensure_ascii=False)
    cats_json = json.dumps(categories, ensure_ascii=False)
    # Escape JS line separators for maximum compatibility
    docs_json = docs_json.replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    cats_json = cats_json.replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')

    content = (
        '/* Generated by build.py - do not edit */\n'
        f'window.__DOCUMENTS_DATA__ = {docs_json};\n'
        f'window.__CATEGORIES_DATA__ = {cats_json};\n'
    )
    out = docs_dir / 'js' / 'data-visible.js'
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'  [OK] js/data-visible.js written ({len(content)} bytes)')
    return out


def inject_data_script_tag(html_path):
    """Ensure the page loads js/data-visible.js before other scripts."""
    if not html_path.exists():
        return False
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'js/data-visible.js' in content:
        return False
    if '<script src="js/' not in content:
        return False
    content = content.replace(
        '<script src="js/',
        '<script src="js/data-visible.js"></script>\n    <script src="js/',
        1,
    )
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return True


def main():
    base_dir = Path(__file__).parent.parent
    
    print('[BUILD] Starting site build...\n')
    
    # Setup directories
    print('[BUILD] Creating directories...')
    docs_dir = setup_directories(base_dir)
    
    # Run conversion
    print('\n[BUILD] Converting Word documents...')
    try:
        documents = convert_documents()
    except Exception as e:
        print(f'  [WARNING] Conversion error: {e}')
        documents = []
    
    # Load index data
    index_path = docs_dir / 'documents' / 'index.json'
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
    else:
        index_data = {'documents': [], 'categories': {}, 'total_count': 0}
    
    # Create visible-only version for main site pages (excludes hidden docs)
    all_documents = index_data.get('documents', [])
    visible_documents = [d for d in all_documents if not d.get('hidden', False)]
    visible_index_data = dict(index_data)
    visible_index_data['documents'] = visible_documents
    visible_index_data['total_count'] = len(visible_documents)
    visible_index_data['completed_count'] = sum(1 for d in visible_documents if d.get('completed'))
    # Rebuild authors dict from visible docs only
    visible_authors = {}
    for doc in visible_documents:
        author = doc.get('author', '')
        if author not in visible_authors:
            visible_authors[author] = {
                'slug': doc.get('author_slug', ''),
                'total': 0,
                'completed': 0
            }
        visible_authors[author]['total'] += 1
        if doc.get('completed'):
            visible_authors[author]['completed'] += 1
    visible_index_data['authors'] = visible_authors
    hidden_count = len(all_documents) - len(visible_documents)
    if hidden_count > 0:
        print(f'[BUILD] {hidden_count} hidden documents excluded from main site')
    
    # Copy static files
    print('\n[BUILD] Copying static files...')
    copy_static_files(base_dir, docs_dir)

    # Write external data file (visible docs only) for CSP-safe loading
    print('\n[BUILD] Writing site data file...')
    write_site_data(docs_dir, visible_index_data)
    
    # Generate index.html (uses visible docs only)
    print('\n[BUILD] Generating index.html...')
    generate_index_html(base_dir, docs_dir, visible_index_data)
    
    # Ensure index.html loads data file
    if inject_data_script_tag(docs_dir / 'index.html'):
        print(f'  [OK] data script tag added to index.html')
    
    # Generate document index pages
    print('\n[BUILD] Generating document index pages...')
    # generate_document_index_pages(base_dir, docs_dir, index_data)  # Not needed with flat structure
    
    # Generate author pages (visible docs only)
    print('\n[BUILD] Generating author pages...')
    generate_author_pages(docs_dir, visible_index_data)
    
    # Generate separate authors page (visible docs only)
    print('\n[BUILD] Generating authors.html...')
    generate_authors_page(docs_dir, visible_index_data)
    
    # Copy translations page
    print('\n[BUILD] Copying translations page...')
    copy_translations_page(base_dir, docs_dir)
    
    # Ensure translations.html loads data file
    if inject_data_script_tag(docs_dir / 'translations.html'):
        print(f'  [OK] data script tag added to translations.html')

    # Remove any previously-published admin files from docs/
    for stale in ('admin.html', 'admin-panel.html'):
        stale_path = docs_dir / stale
        if stale_path.exists():
            stale_path.unlink()
            print(f'  [OK] removed stale {stale} from docs/')
    for stale_js in ('admin-auth.js', 'admin-panel.js', 'admin-ui.js'):
        stale_path = docs_dir / 'js' / stale_js
        if stale_path.exists():
            stale_path.unlink()
            print(f'  [OK] removed stale js/{stale_js} from docs/')
    
    print('\n[BUILD] Site build completed successfully!')
    print(f'[BUILD] Site ready at: docs/')
    stamp_path = base_dir / '.last_build'
    try:
        stamp_path.write_text(datetime.now().isoformat(timespec='seconds'), encoding='utf-8')
        print(f'[BUILD] Stamped {stamp_path.name}')
    except Exception as e:
        print(f'[BUILD] Could not write .last_build: {e}')
    print('\nTo deploy on GitHub Pages:')
    print('  1. git add docs/')
    print('  2. git commit -m "Build site"')
    print('  3. git push')
    print('  4. Enable GitHub Pages from docs/ folder')


if __name__ == '__main__':
    main()
