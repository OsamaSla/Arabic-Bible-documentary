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
- **🎛️ Admin panel** — Web-based document management with login
- **🎲 Random articles** — Homepage shows 10 random completed articles

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

Open `docs/index.html` in your browser.

### 6. Deploy to GitHub Pages

```bash
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
├── docs-input/              # Source Word documents
├── docs/                    # Generated site (GitHub Pages root)
│   ├── index.html           # Homepage
│   ├── translations.html    # Translations page with book categories
│   ├── authors.html         # All authors page
│   ├── admin.html           # Admin login
│   ├── admin-panel.html     # Admin document management
│   ├── documents/           # Generated HTML documents
│   ├── authors/             # Author profile pages
│   ├── css/                 # Stylesheets
│   ├── js/                  # JavaScript files
│   └── assets/              # Images and icons
├── scripts/
│   ├── convert.py           # Word to HTML converter
│   └── build.py             # Master build script
├── templates/
│   └── index.html           # Homepage template
├── css/
│   ├── style.css            # Main site styles
│   └── document.css         # Document viewer styles
├── js/
│   ├── app.js               # Main app (search, articles, filters)
│   ├── nav.js               # Navigation and mobile menu
│   ├── search.js            # Search functionality
│   ├── translations.js      # Translations page logic
│   ├── admin-auth.js        # Admin authentication
│   └── admin-panel.js       # Admin panel logic
├── categories.json          # Book/category definitions
├── doc_categories.json      # Document-to-category assignments
├── doc_overrides.json       # Manual status overrides
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

### doc_overrides.json

Override document status. Use the admin panel or edit directly:

```json
{
  "overrides": {
    "doc_0042": { "completed": true },
    "doc_0103": { "hidden": true }
  }
}
```

| Override | Effect |
|----------|--------|
| `"completed": true` | Marks document as completed (green checkmark) |
| `"hidden": true` | Removes document from the website entirely |

---

## Admin Panel

Access via the gear icon (&#9881;) in the footer, or navigate to `admin.html`.

**Default credentials:**
- Username: `admin`
- Password: `admin123`

> ⚠️ **Change the password** in `js/admin-auth.js` before deploying!

### Admin features:
- Toggle documents as completed/incomplete
- Hide documents from the website
- Search and filter documents
- Export updated `doc_overrides.json`

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

### Topics (11 categories)
- دراسة الكتاب المقدس (Bible Study)
- الروح القدس (Holy Spirit)
- الكتاب المقدس (The Bible)
- الزواج والأسرة (Marriage & Family)
- الإنجيل (The Gospel)
- الحياة الإيمانية (Faith Life)
- يسوع المسيح (Jesus Christ)
- الخلق (Creation)
- الكنيسة (The Church)
- المجلات (Magazines)
- النبوءة والمستقبل (Prophecy & Future)

---

## Build Process

The `build.py` script:

1. **Converts** all `.docx` files in `docs-input/` to HTML
2. **Generates** `index.json` with document metadata
3. **Injects** inline data for offline/file:// compatibility
4. **Creates** author profile pages (108 authors)
5. **Builds** homepage, translations, and authors pages
6. **Copies** admin panel files
7. **Outputs** everything to `docs/`

Run with:
```bash
python scripts/build.py
```

---

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

---

## License

These translations are based on commentaries from [bibelkommentare.de](https://www.bibelkommentare.de) pursuant to their terms of use.
