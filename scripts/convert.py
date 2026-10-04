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
import zipfile
import xml.etree.ElementTree as ET
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
    try:
        fn_refs = run._r.findall(qn('w:footnoteReference'))
    except Exception:
        fn_refs = []
    if fn_refs:
        return ''.join(footnote_ref_html(el.get(qn('w:id'))) for el in fn_refs)
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
    # NOTE: Word run font sizes are deliberately NOT carried over. Source
    # .docx files use anything from 14pt to 72pt, which broke the uniform
    # article typography and the A4 pager layout. Site CSS owns font sizes.
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
        elif tag == qn('w:bookmarkStart'):
            name = child.get(qn('w:name'))
            if name:
                parts.append(f'<span id="{escape_html(name)}"></span>')
        elif tag == qn('w:footnoteReference'):
            parts.append(footnote_ref_html(child.get(qn('w:id'))))
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
        elif tag == qn('w:bookmarkStart'):
            # Keep Word bookmark targets so in-document #anchor links resolve
            name = child.get(qn('w:name'))
            if name:
                parts.append(f'<span id="{escape_html(name)}"></span>')
        else:
            parts.extend(_walk_children(paragraph, child))
    return ''.join(parts)


def process_runs(runs):
    """Process formatting runs (kept for compatibility)."""
    return ''.join(format_run(run) for run in runs)


# Section-break types that start a new page (Layout > Breaks > Next Page and
# its even/odd variants). A missing w:type defaults to nextPage. 'continuous'
# stays on the same page and is NOT a chapter boundary. Deliberately ignores
# w:pageBreakBefore (paragraph formatting, often set on every heading).
_PAGE_BREAK_SECTION_TYPES = {'nextPage', 'evenPage', 'oddPage'}

_EMPTY_LINE_HTML = '<p class="empty-line">&nbsp;</p>'


def _section_break_after(paragraph):
    """True when this paragraph ends a page-starting section (break AFTER it)."""
    try:
        pPr = paragraph._p.find(qn('w:pPr'))
    except Exception:
        return False
    if pPr is None:
        return False
    sectPr = pPr.find(qn('w:sectPr'))
    if sectPr is None:
        return False
    t = sectPr.find(qn('w:type'))
    val = t.get(qn('w:val')) if t is not None else 'nextPage'
    return val in _PAGE_BREAK_SECTION_TYPES


def _has_page_break_run(paragraph):
    """True when the paragraph contains an explicit page break (break BEFORE it)."""
    try:
        for br in paragraph._p.iter(qn('w:br')):
            if br.get(qn('w:type')) == 'page':
                return True
    except Exception:
        return False
    return False


def _render_body_paragraph(paragraph):
    """Render one body paragraph -> html string ('' when empty)."""
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
            return f'<h{level}>{formatted_text}</h{level}>'
        return ''
    if 'list' in style_name:
        formatted_text = process_paragraph(paragraph)
        if formatted_text.strip():
            return f'<li>{formatted_text}</li>'
        return ''
    if not text:
        return _EMPTY_LINE_HTML
    formatted_text = process_paragraph(paragraph)
    if formatted_text.strip():
        if re.match(r'^[\d\s]*\w+\s+\d+:\d+', text) or re.match(r'^[\u0600-\u06FF]+\s+\d+:\d+', text):
            return f'<p class="verse-ref">{formatted_text}</p>'
        return f'<p>{formatted_text}</p>'
    return ''


def _chapter_has_content(blocks):
    return any(b and b != _EMPTY_LINE_HTML for b in blocks)


def _chapter_title(candidate, n):
    title = re.sub(r'\s+', ' ', str(candidate or '')).strip()
    if len(title) > 60:
        title = title[:60].rsplit(' ', 1)[0] + '...'
    return title or f'الفصل {n}'


def extract_chapters_from_docx(docx_path):
    """Split a document at page breaks into chapters.

    Returns (body_html, chapters) where chapters is a list of
    {'n': int, 'title': str, 'anchor': 'ch-N'}. Single-chapter documents
    return plain flat html (no anchors) and a one-item chapters list.
    """
    doc = Document(docx_path)
    blocks_list = [[]]
    titles = [None]
    pending_break = False

    def flush():
        blocks_list.append([])
        titles.append(None)

    for paragraph in doc.paragraphs:
        if _has_page_break_run(paragraph) and _chapter_has_content(blocks_list[-1]):
            flush()
            pending_break = False
        html = _render_body_paragraph(paragraph)
        if pending_break and html and html != _EMPTY_LINE_HTML:
            if _chapter_has_content(blocks_list[-1]):
                flush()
            pending_break = False
        if html:
            # Drop leading blank lines at the very start of a new chapter.
            if not (len(blocks_list[-1]) == 0 and len(blocks_list) > 1
                    and html == _EMPTY_LINE_HTML):
                blocks_list[-1].append(html)
        if titles[-1] is None and paragraph.text.strip():
            titles[-1] = paragraph.text.strip()
        if _section_break_after(paragraph):
            pending_break = True

    for table in doc.tables:
        parts = ['<div class="table-container"><table>']
        for i, row in enumerate(table.rows):
            parts.append('<tr>')
            for cell in row.cells:
                cell_text = ' '.join(p.text.strip() for p in cell.paragraphs if p.text.strip())
                tag = 'th' if i == 0 else 'td'
                parts.append(f'<{tag}>{escape_html(cell_text)}</{tag}>')
            parts.append('</tr>')
        parts.append('</table></div>')
        blocks_list[-1].append('\n'.join(parts))

    # Drop empty chapters (keep at least one).
    kept = [(b, t) for b, t in zip(blocks_list, titles) if _chapter_has_content(b)]
    if not kept:
        kept = [(blocks_list[0], titles[0])]
    chapters = []
    html_chunks = []
    multi = len(kept) > 1
    for i, (blocks, first_text) in enumerate(kept, 1):
        title = _chapter_title(first_text, i)
        chapters.append({'n': i, 'title': title, 'anchor': f'ch-{i}'})
        body = '\n'.join(b for b in blocks if b)
        body = re.sub(r'(<p class="empty-line">&nbsp;</p>\s*){2,}',
                      '<p class="empty-line">&nbsp;</p>', body)
        if multi:
            html_chunks.append(
                f'<span class="doc-chapter-anchor" id="ch-{i}"'
                f' data-chapter-title="{escape_html(title)}"></span>\n' + body)
        else:
            html_chunks.append(body)
    result = '\n'.join(html_chunks)
    result = sanitize_html(result)
    return result, chapters


def extract_text_from_docx(docx_path):
    """Extract formatted text from Word document"""
    try:
        result, _chapters = extract_chapters_from_docx(docx_path)
        return result
    except Exception as e:
        return f'<p class="error">خطأ في قراءة الملف: {escape_html(str(e))}</p>'


_W_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
_NUM_ONLY_RE = re.compile(r'^[\d\s\-–—\(\)\[\]\./\\]*\d[\d\s\-–—\(\)\[\]\./\\]*$')
_URL_RE = re.compile(
    r'(?<![@A-Za-z\u0600-\u06FF])'
    r'(?:https?://[^\s<>"\')\]]+'
    r'|(?:www\.)?[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}'
    r'(?:/[^\s<>"\')\]]*)?)'
)
_MAX_NOTES = 30


def _part_paragraphs(zf, part_name):
    """Plain-text paragraphs of one header/footer part (order preserved)."""
    try:
        data = zf.read(part_name)
    except KeyError:
        return []
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    texts = []
    for p in root.iter(_W_NS + 'p'):
        t = ''.join((n.text or '') for n in p.iter(_W_NS + 't'))
        t = re.sub(r'\s+', ' ', t).strip()
        if t:
            texts.append(t)
    return texts


def extract_header_footer_notes(docx_path, title=''):
    """Header/footer notes missing from the body export.

    Returns (header_notes, footer_notes): deduped, order-preserved lists.
    Drops page numbers, filename echoes, and title echoes.
    """
    header_notes, footer_notes = [], []
    try:
        zf = zipfile.ZipFile(docx_path)
    except Exception:
        return header_notes, footer_notes
    try:
        names = zf.namelist()
        raw_headers, raw_footers = [], []
        for name in sorted(names):
            if name.startswith('word/header') and name.endswith('.xml'):
                raw_headers += _part_paragraphs(zf, name)
            elif name.startswith('word/footer') and name.endswith('.xml'):
                raw_footers += _part_paragraphs(zf, name)
    finally:
        try:
            zf.close()
        except Exception:
            pass
    norm_title = re.sub(r'\s+', ' ', str(title or '')).strip().lower()
    for target, raw in ((header_notes, raw_headers), (footer_notes, raw_footers)):
        for t in raw:
            if not t or len(t) > 500:
                continue
            if _NUM_ONLY_RE.match(t):
                continue
            if '.docx' in t.lower():
                continue
            if norm_title and t.lower() == norm_title:
                continue
            if t not in target:
                target.append(t)
            if len(target) >= _MAX_NOTES:
                break
    return header_notes, footer_notes


def _linkify_escaped(text):
    """Wrap URLs in anchors (input must already be HTML-escaped)."""
    def _sub(match):
        raw = match.group(0).rstrip('.,;:!?)]}')
        trail = match.group(0)[len(raw):]
        url = raw if re.match(r'(?i)^https?://', raw) else 'https://' + raw
        if not safe_url(url):
            return escape_html(match.group(0))
        return f'<a href="{escape_html(url)}" rel="noopener noreferrer">{escape_html(raw)}</a>{escape_html(trail)}'
    return _URL_RE.sub(_sub, text)


def render_notes_section(header_notes, footer_notes):
    """Notes appendix for header/footer content (empty string when none)."""
    groups = []
    if header_notes:
        groups.append(('ترويسة الصفحة', header_notes))
    if footer_notes:
        groups.append(('تذييل الصفحة', footer_notes))
    if not groups:
        return ''
    parts = ['<section class="doc-notes" aria-label="ملاحظات من المستند الأصلي">',
             '<h2 class="doc-notes-title">ملاحظات من المستند الأصلي</h2>']
    if len(groups) > 1:
        for label, items in groups:
            parts.append(f'<h3 class="doc-notes-sub">{escape_html(label)}</h3>')
            parts.append('<ul>')
            for item in items:
                parts.append(f'<li>{_linkify_escaped(escape_html(item))}</li>')
            parts.append('</ul>')
    else:
        parts.append('<ul>')
        for item in groups[0][1]:
            parts.append(f'<li>{_linkify_escaped(escape_html(item))}</li>')
        parts.append('</ul>')
    parts.append('</section>')
    return '\n'.join(parts)


# Per-document footnote context (set fresh for each converted document):
# {'doc': doc_id, 'nums': {footnote_id: display_number}}
_FN_CTX = {'doc': '', 'nums': {}}

_RELS_NS = '{http://schemas.openxmlformats.org/package/2006/relationships}'


def _part_link_targets(zf, part_name):
    """External hyperlink targets of one part: {rId: url}."""
    targets = {}
    if '/' in part_name:
        head, tail = part_name.rsplit('/', 1)
        rels_name = head + '/_rels/' + tail.replace('.xml', '.xml.rels')
    else:
        rels_name = '_rels/' + part_name.replace('.xml', '.xml.rels')
    try:
        data = zf.read(rels_name)
    except KeyError:
        return targets
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return targets
    for rel in root.iter(_RELS_NS + 'Relationship'):
        rid = rel.get('Id')
        target = rel.get('Target') or ''
        if rid and target and safe_url(target):
            targets[rid] = target
    return targets


def _footnote_run_html(r_el):
    """One footnote run -> inline HTML (bold/italic/underline/sup/sub/color)."""
    rPr = r_el.find(_W_NS + 'rPr')
    bold = italic = under = sup = sub = False
    color = None
    if rPr is not None:
        bold = rPr.find(_W_NS + 'b') is not None
        italic = rPr.find(_W_NS + 'i') is not None
        under = rPr.find(_W_NS + 'u') is not None
        va = rPr.find(_W_NS + 'vertAlign')
        if va is not None:
            val = va.get(_W_NS + 'val')
            sup = (val == 'superscript')
            sub = (val == 'subscript')
        c_el = rPr.find(_W_NS + 'color')
        if c_el is not None:
            c_val = c_el.get(_W_NS + 'val')
            if c_val and c_val.lower() != 'auto':
                color = c_val
    text = ''.join((n.text or '') for n in r_el.iter(_W_NS + 't'))
    if not text:
        return ''
    out = _linkify_escaped(escape_html(text))
    if sup:
        out = f'<sup>{out}</sup>'
    elif sub:
        out = f'<sub>{out}</sub>'
    styles = []
    if bold:
        styles.append('font-weight:600')
    if italic:
        styles.append('font-style:italic')
    if under:
        styles.append('text-decoration:underline')
    if color:
        styles.append(f'color:#{escape_html(color)}')
    if styles:
        out = f'<span style="{";".join(styles)}">{out}</span>'
    return out


def _footnote_paragraph_html(p_el, link_targets):
    """One footnote paragraph -> inline HTML (links resolved via part rels)."""
    parts = []
    for child in p_el:
        tag = child.tag
        if tag == _W_NS + 'pPr':
            continue
        if tag == _W_NS + 'r':
            parts.append(_footnote_run_html(child))
        elif tag == _W_NS + 'hyperlink':
            rid = child.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            url = link_targets.get(rid) if rid else None
            inner = ''.join(_footnote_run_html(el) for el in child.iter(_W_NS + 'r'))
            if not inner:
                continue
            if url:
                parts.append(f'<a href="{escape_html(url)}" rel="noopener noreferrer">{inner}</a>')
            else:
                parts.append(inner)
        else:
            for el in child.iter(_W_NS + 'r'):
                parts.append(_footnote_run_html(el))
    return ''.join(parts)


def extract_footnotes(docx_path):
    """Word footnotes with real text: [(fid, html), ...] in id order.

    Skips separators and empty stubs so in-text markers never dangle.
    """
    notes = []
    try:
        zf = zipfile.ZipFile(docx_path)
    except Exception:
        return notes
    try:
        try:
            data = zf.read('word/footnotes.xml')
        except KeyError:
            return notes
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            return notes
        link_targets = _part_link_targets(zf, 'word/footnotes.xml')
        for fn in root.iter(_W_NS + 'footnote'):
            if fn.get(_W_NS + 'type') is not None:
                continue
            fid = fn.get(_W_NS + 'id')
            chunks = []
            for p_el in fn.iter(_W_NS + 'p'):
                html = _footnote_paragraph_html(p_el, link_targets)
                if html.strip():
                    chunks.append(html)
            if not chunks:
                continue
            visible = re.sub(r'<[^>]+>', '', ' '.join(chunks)).strip()
            if not visible:
                continue
            notes.append((fid, '<br>'.join(chunks) if len(chunks) > 1 else chunks[0]))
    finally:
        try:
            zf.close()
        except Exception:
            pass
    return notes


def footnote_ref_html(fid):
    """In-text footnote marker (sup link) or '' when the note was skipped."""
    nums = _FN_CTX.get('nums') or {}
    doc = _FN_CTX.get('doc') or ''
    num = nums.get(str(fid))
    if not num:
        return ''
    return (f'<sup class="fn-ref"><a href="#fn-{doc}-{num}" '
            f'id="fnref-{doc}-{num}">[{num}]</a></sup>')


def render_footnotes_section(numbered):
    """Footnote appendix with backlinks: [(num, html)] or ''."""
    if not numbered:
        return ''
    doc = _FN_CTX.get('doc') or ''
    parts = ['<section class="doc-footnotes" aria-label="الحواشي">',
             '<h2 class="doc-notes-title">الحواشي</h2>',
             '<ol class="doc-footnotes-list">']
    for num, html in numbered:
        parts.append(
            f'<li id="fn-{doc}-{num}">{html} '
            f'<a class="fn-back" href="#fnref-{doc}-{num}" '
            f'aria-label="رجوع إلى موضع الحاشية">↩</a></li>')
    parts.append('</ol>')
    parts.append('</section>')
    return '\n'.join(parts)


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


def _normalize_text(text):
    """Normalize text for comparison (collapse whitespace, casefold)."""
    return re.sub(r'\s+', ' ', str(text or '')).strip().casefold()


def strip_leading_author(text, author='', title=''):
    """Remove a leading author-name prefix from a description string.

    Many Word files repeat the author name as the first body paragraph, so
    descriptions built from the opening paragraphs start with e.g.
    "Marco Leßmann حينما عاد اليهود...". The card already shows the author
    separately, so the prefix must go.
    """
    cleaned = str(text or '').strip()
    norm_author = _normalize_text(author)
    if norm_author:
        norm_clean = _normalize_text(cleaned)
        if norm_clean == norm_author:
            return ''
        if norm_clean.startswith(norm_author):
            # Cut the real author prefix (whitespace-tolerant), then drop
            # separators/dashes left behind.
            cut = re.match(r'\s*' + re.escape(author.strip()),
                           cleaned, re.IGNORECASE)
            rest = cleaned[cut.end():] if cut else cleaned[len(author.strip()):]
            # Drop separators plus a leftover parenthesized page number
            # from the running head (e.g. "Author (19) ...").
            rest = re.sub(r'^[\s\-–—:؛,،.\|/\\\[\]"\'«»]+', '', rest)
            rest = re.sub(r'^\(\d{1,4}\)', '', rest)
            rest = re.sub(r'^[\s\-–—:؛,،.\|/\\\[\]"\'«»]+', '', rest)
            return rest.strip()
    return cleaned


def get_description_from_docx(docx_path, max_length=200, author='', title=''):
    """Extract description: first real sentence longer than half an A4 row.

    Opening fragments (bylines in any script, running heads, verse refs,
    page numbers) live in their own short paragraphs and are skipped whole,
    so the description always starts at a sentence start and (after
    truncation) ends with punctuation.
    """
    try:
        doc = Document(docx_path)
        norm_author = _normalize_text(author)
        norm_title = _normalize_text(title)
        fallback_parts = []
        fallback = ''
        for paragraph in doc.paragraphs[1:14]:
            text = paragraph.text.strip()
            if not text:
                continue
            norm_text = _normalize_text(text)
            if norm_text == norm_author and norm_author:
                continue
            if norm_text == norm_title and norm_title:
                continue
            if _is_frag_paragraph(text):
                continue
            fallback_parts.append(text)
            sentence = first_long_sentence(text, author, title)
            if len(sentence) >= _MIN_SENTENCE_LEN:
                return cut_at_sentence(sentence, max_length)
            if not fallback and sentence:
                fallback = sentence
        joined = strip_leading_author(' '.join(fallback_parts), author, title)
        joined = re.sub(r'^\(\d{1,4}\)[\s\-–—:؛,،.]*', '', joined).strip()
        sentence = first_long_sentence(joined, author, title)
        if len(sentence) >= _MIN_SENTENCE_LEN:
            return cut_at_sentence(sentence, max_length)
        return cut_at_sentence(fallback or sentence or joined, max_length)
    except:
        return ''


# A paragraph that can never start the description: author bylines and
# header echoes (short lines without a terminator, bare refs/numbers).
_FRAG_REF_RE = re.compile(
    r'^[\s\(\[]*(\d+\s*:\s*\d+|\d{1,4})[\s.\-–—:؛,،\)\]]*$'
    r'|^\s*[IVXLCDM\-–—:؛,،.\s]+\s*$')


def _is_frag_paragraph(text):
    """True for byline/header-echo paragraphs (no sentence starts here)."""
    t = str(text or '').strip()
    if not t:
        return True
    if _FRAG_REF_RE.match(t):
        return True
    # Short line without any sentence terminator: byline, headline echo,
    # or a bare "book 12" / "author" line in any script.
    if len(t) < _MIN_SENTENCE_LEN and not re.search(r'[.؟!…]', t):
        return True
    return False


def _clean_sentence_start(sentence, author='', title=''):
    """Drop byline/verse-ref/page-stub prefixes so text starts at words."""
    s = strip_leading_author(str(sentence or '').strip(), author, title)
    s = re.sub(r'^\(\d{1,4}\)[\s\-–—:؛,،.]*', '', s)
    s = re.sub(r'^\d{1,3}\.\s+', '', s)
    s = re.sub(r'^[«"\(\[]?\d+\s*:\s*\d+[^.؟!…]{0,40}?\s*[»"\)\]]?\s*', '', s)
    # Structural "Book 12[:34]" labels (chapter < 1000, so years survive).
    m = re.match(r'^([\u0600-\u06FFA-Za-z]+(?:\s+[\u0600-\u06FFA-Za-z]+){0,2})'
                 r'\s+(\d+)\s*(:\s*\d+)?', s)
    if m and int(m.group(2)) < 1000:
        s = s[m.end():].lstrip(' \t\-–—:؛,،.')
    return s.strip()


# About half an A4 text row at the article body size (1.15rem Naskh).
_MIN_SENTENCE_LEN = 50
_SENTENCE_RE = re.compile(r'[^.؟!…]*[.؟!…]["\'"\'»)\]]*')


def first_long_sentence(text, author='', title='', min_len=_MIN_SENTENCE_LEN):
    """First cleaned sentence longer than half an A4 row, else best fallback.

    Candidates are stripped of author bylines and page-number stubs before
    measuring, so headers like "Author (19) ..." never seed the description.
    """
    fallback = ''
    for m in _SENTENCE_RE.finditer(str(text or '')):
        sentence = _clean_sentence_start(m.group(0), author, title)
        if not sentence:
            continue
        if not fallback:
            fallback = sentence
        if len(sentence) >= min_len:
            return sentence
    return fallback


def cut_at_sentence(text, limit):
    """Shorten text to <= limit chars, preferably ending with punctuation."""
    text = str(text or '').strip()
    if len(text) <= limit:
        return text
    head = text[:limit]
    idx = max(head.rfind(t) for t in '.؟!…')
    if idx >= 40:
        return head[:idx + 1].strip()
    return head.rsplit(' ', 1)[0].rstrip(' ,،;:') + '...'


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
    <meta name="description" content="{safe_title} - {safe_author} | ترجمات تعليقات الكتاب المقدس">
    <meta property="og:type" content="article">
    <meta property="og:title" content="{safe_title}">
    <meta property="og:description" content="{safe_title} - {safe_author} | ترجمات تعليقات الكتاب المقدس">
    <meta property="og:locale" content="ar_AR">
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
                <a href="{prefix}bibles.html">الكتاب المقدس</a>
                <!-- MEGA_MAIN prefix="{prefix}" -->
                <a href="{prefix}authors.html">المؤلفون</a>
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
                    <button type="button" data-action="share" class="btn btn-share" aria-label="مشاركة المقال">
                        <span class="btn-icon" aria-hidden="true">&#128279;</span>
                        <span class="btn-text">مشاركة</span>
                    </button>
                </div>
            </div>
            <div class="document-layout">
                <!-- CHAPTERS_NAV -->
                <article class="document-content">
                    {content}
                </article>
                <!-- RELATED_SIDEBAR -->
            </div>
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
    <script src="{prefix}js/nav.js"></script>
    <script src="{prefix}js/pager.js"></script>
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
        footnotes = extract_footnotes(source_doc['filepath'])
        _FN_CTX['doc'] = doc_id
        _FN_CTX['nums'] = {str(fid): n for n, (fid, _html) in enumerate(footnotes, 1)}
        content, chapters = extract_chapters_from_docx(source_doc['filepath'])
        fn_html = render_footnotes_section(
            [(n, html) for n, (_fid, html) in enumerate(footnotes, 1)])
        if fn_html:
            content = content + '\n' + fn_html
        header_notes, footer_notes = extract_header_footer_notes(
            source_doc['filepath'], title)
        notes_html = render_notes_section(header_notes, footer_notes)
        if notes_html:
            content = content + '\n' + notes_html
        description = get_description_from_docx(
            source_doc['filepath'], author=source_doc['author'], title=title)
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
        # Directory depth only (exclude the filename) - matches build.py's
        # prefix helper; off-by-one here would escape the site root when
        # hosted under a subpath (GitHub project pages).
        depth = max(len(rel_to_root.parts) - 1, 0)
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
            'chapters': chapters if len(chapters) > 1 else [],
            'mtime': int(os.path.getmtime(source_doc['filepath'])),
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
