# Arabic Bible Documentary Translations

<div dir="rtl">

## ترجمات تعليقات الكتاب المقدس

</div>

A static website hosting **774 Arabic translations** of Christian Bible commentaries from [bibelkommentare.de](https://www.bibelkommentare.de), built for GitHub Pages with instant search, author pages, and admin management.

**Live site:** [https://osamasla.github.io/Arabic-Bible-documentary/](https://osamasla.github.io/Arabic-Bible-documentary/)

---

## Features

- **✝️ Christian-themed design** — Deep blue, gold, and burgundy color scheme
- **📱 Fully responsive** — Works on mobile, tablet, and desktop
- **🔍 Instant search** — Search across all 774 documents by title, author, or content
- **📖 Browser viewing** — Read documents directly in the browser
- **📥 Word download** — Download original `.docx` files
- **🌐 Arabic RTL** — Full right-to-left support
- **👤 Author pages** — 108 author profiles with document listings
- **📊 Completion tracking** — 342 completed, 432 in progress
- **🎲 Random articles** — Homepage shows 10 random completed articles
- **🔒 Hardened static site** — CSP, self-hosted fonts/analytics, no admin files published

## Stats

| Metric | Count |
|--------|-------|
| Total documents | 774 |
| Completed translations | 342 |
| In progress | 432 |
| Authors | 108 |
| Old Testament books | 39 |
| New Testament books | 27 |
| Topic categories | 11 |

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/OsamaSla/Arabic-Bible-documentary.git
cd Arabic-Bible-documentary
```

### 2. Install dependencies

```bash
pip install python-docx beautifulsoup4 lxml
```

### 3. Add Word documents

Place `.docx` files in the `docs-input/` folder. Organize by author:

```
docs-input/
├── john-darby/
│   ├── commentary-on-genesis.docx
│   └── commentary-on-exodus.docx
├── charles-spurgeon/
│   └── sermons.docx
└── arend-remmers/
    └── notes.docx
```

### 4. Build the site

```bash
python scripts/build.py
```

### 5. Preview locally

Open `docs/index.html` in your browser, or run the dev server:

```bash
python scripts/serve.py
```

### 6. Deploy to GitHub Pages

**Option A — watch + auto-push** (recommended while editing source folders):

```bash
python scripts/watch.py --push
```

Every detected change rebuilds `docs/`, then commits and pushes.

**Option B — Admin panel** (requires `python scripts/serve.py`):

1. Open `http://localhost:8000/admin-panel.html` (no password; bound to `127.0.0.1` only)
2. **Check changes** — source `.docx` + git changes since last build
3. **Deploy to GitHub** — same as one watch cycle: scan source → rebuild → push

> Deploy only works on `http://localhost:8000/...`. Opening the file directly (`file://`) or GitHub Pages cannot run local scripts.
> API routes (`/api/changes`, `/api/documents`, `/api/rebuild`, `/api/deploy`) require the per-run `X-Serve-Token` header injected into the local admin page.

**Option C — manual:**

```bash
python scripts/build.py
git add .
git commit -m "Build site"
git push origin main
```

Then go to **Settings → Pages → Source: main branch, folder: /docs → Save**

Your site will be live at: `https://osamasla.github.io/Arabic-Bible-documentary/`

---

## Project Structure

```
Arabic-Bible-documentary/
├── docs/                    # Generated site (GitHub Pages root — public only)
│   ├── index.html           # Homepage (original design)
│   ├── index-new.html       # Redesign preview (Slide1-style, static cards + latest list)
│   ├── translations.html    # Translations landing (3 count cards)
│   ├── translations-ot.html # Old Testament books category page
│   ├── translations-nt.html # New Testament books category page
│   ├── translations-subjects.html  # Topics category page
│   ├── authors.html         # All authors page
│   ├── documents/           # Generated HTML (visible docs only; index.json is visible-only)
│   ├── authors/             # Author profile pages
│   ├── css/                 # Stylesheets (incl. fonts.css)
│   ├── fonts/               # Self-hosted Noto Naskh Arabic woff2
│   ├── js/                  # Public JavaScript (no admin scripts)
│   └── assets/              # Images and icons
├── local-hidden/            # Hidden docs + full admin index (gitignored, never published)
├── admin-panel.html         # Local-only admin (served by serve.py, not copied to docs/)
├── scripts/
│   ├── convert.py           # Word to HTML converter
│   ├── build.py             # Master build script
│   ├── mega_nav.py          # Hover mega-menu builder (build-time counts)
│   ├── watch.py             # Poll source + optional --push auto-deploy
│   ├── serve.py             # Localhost-only server + token-gated /api/*
│   └── git_ops.py           # Shared git add/commit/push helper
├── templates/
│   ├── index-new.html       # Redesign homepage template
│   ├── translations*.html   # Translations landing + 3 category pages
│   └── bibles.html          # Book & chapter navigator template
├── css/
│   ├── style.css            # Main site styles
│   ├── fonts.css            # Self-hosted @font-face
│   └── document.css         # Document viewer styles
├── js/
│   ├── app.js               # Main app (search, articles, filters)
│   ├── nav.js               # Navigation and mobile menu
│   ├── search.js            # Search functionality
│   ├── translations.js      # Translations page logic
│   ├── ui.js                # Delegated CSP-safe click/submit handlers
│   ├── dom.js               # escapeHtml / safePath helpers
│   ├── theme-init.js        # FOUC-safe theme bootstrap
│   ├── admin-ui.js          # Local admin logic (not copied to docs/)
│   └── vendor/umami.js      # Self-hosted analytics snippet
├── categories.json          # Book/category definitions
├── doc_categories.json      # Document-to-category assignments
└── README.md
```

---

## Configuration Files

### categories.json

Defines the 39 OT books, 27 NT books, and 11 topic categories with Arabic and German names.

### doc_categories.json

Maps documents to categories. Edit to assign documents to books:

```json
{
  "assignments": {
    "doc_0042": "takwin",
    "my-document.docx": "matta"
  }
}
```

### Status folders (source tree)

Status is controlled only by folders under each author directory (no JSON overrides):

| Folder | Effect |
|--------|--------|
| `تم/` | Marks documents inside as **completed** |
| `hidden/` or `مخفي/` | Marks documents inside as **hidden** — written to gitignored `local-hidden/`, never published |

Nesting works: `hidden/تم/` = completed **and** hidden. Move a file out of the folder and rebuild to revert.

Hidden documents are **not** listed in public `docs/documents/index.json` and their HTML/`.docx` are never written under `docs/`.

---

## Admin Panel (local only)

Open `http://localhost:8000/admin-panel.html` while `python scripts/serve.py` is running.

- Server binds to `127.0.0.1` only; no CORS headers.
- There is **no password** (and none is embedded in the site). The panel gets a random per-run `window.__SERVE_TOKEN__` injected by `serve.py`.
- `/api/changes`, `/api/documents`, `/api/rebuild`, `/api/deploy` reject requests without that token (and check `Origin`).
- `admin.html`, `admin-panel.html`, `admin-auth.js`, `admin-ui.js` are **never** copied into `docs/` (GitHub Pages cannot serve them).

### Admin features (read-only + local deploy):
- View all documents including hidden ones (via `local-hidden/documents-index.json`)
- Search and filter by completed / hidden status
- Open a document from its row
- **Check changes** — what changed in source/git since last build
- **Deploy to GitHub** — scan + rebuild + push (local `serve.py` only)

---

## Categories

### Old Testament (39 books)
| # | Arabic | German | Slug |
|---|--------|--------|------|
| 1 | التكوين | 1. Mose | takwin |
| 2 | الخروج | 2. Mose | kharuj |
| 3 | اللاويين | 3. Mose | lawiyyun |
| 4 | العدد | 4. Mose | adad |
| 5 | التثنية | 5. Mose | tathniya |
| ... | ... | ... | ... |

### New Testament (27 books)
| # | Arabic | German | Slug |
|---|--------|--------|------|
| 1 | متى | Mt | matta |
| 2 | مرقس | Mk | marqus |
| 3 | لوقا | Lk | luqa |
| 4 | يوحنا | Joh | yuanna |
| ... | ... | ... | ... |

### Topics (10 categories)
- دراسة الكتاب المقدس (Bible Study)
- الروح القدس (Holy Spirit)
- الكتاب المقدس (The Bible)
- الزواج والأسرة (Marriage & Family)
- الإنجيل (The Gospel)
- حياة الإيمان (Faith Life)
- يسوع المسيح (Jesus Christ)
- الخليقة (Creation)
- الكنيسة (The Church)
- النبوءة والمستقبل (Prophecy & Future)

---

## Build Process

The `build.py` script:

1. **Converts** all `.docx` files to HTML (hidden ones → `local-hidden/`)
2. **Generates** `docs/documents/index.json` (visible docs only) + `local-hidden/documents-index.json` (full list)
3. **Writes** `docs/js/data-visible.js` (external JSON — CSP-safe, no inline `<script>` breakout)
4. **Creates** author profile pages
5. **Builds** homepage, translations, and authors pages with CSP + local fonts/analytics
6. **Copies** `css/`, `fonts/`, `js/` (excluding `admin-*`), `assets/`
7. **Removes** any stale admin/hidden files from `docs/`
8. **Outputs** everything to `docs/`

Run with:
```bash
python scripts/build.py
```

---

## Security

**Already implemented in the site/build:**

- Content-Security-Policy meta on generated pages: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' https://gateway.umami.is; object-src 'none'; base-uri 'self'; form-action 'self'`
- Self-hosted fonts (`css/fonts.css` + `fonts/*.woff2`) and Umami (`js/vendor/umami.js` → `https://gateway.umami.is`)
- All dynamic titles/authors/paths HTML-escaped; link URLs sanitized (`http`/`https`/`mailto`/`#` only); Word HTML stripped of script/iframe/`on*`
- No inline event handlers; delegated handlers in `js/ui.js`
- Hidden documents and admin tooling never published under `docs/`

**GitHub-side checklist (do once):**

1. Enable **2FA** for your GitHub account (Settings → Password and authentication).
2. Repo **Settings → Branches**: require pull request reviews before merging to `main`.
3. Repo **Settings → Code security**: enable Secret scanning + Push protection (if available on your plan).
4. Do not commit tokens/keys; only `docs/` is published (Pages source: `main` → `/docs`).
5. Prefer a fine-grained PAT or deploy key with `contents:write` limited to this repo if automating pushes.
6. Review Actions/workflows for arbitrary `pull_request_target` + checkout of untrusted PRs if you add CI later.

---

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

---

## License

These translations are based on commentaries from [bibelkommentare.de](https://www.bibelkommentare.de) pursuant to their terms of use.
