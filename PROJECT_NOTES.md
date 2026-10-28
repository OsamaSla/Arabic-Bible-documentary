# PROJECT NOTES — Arabic Bible Documentary (ترجمات)

Last verified: 2026-10-28, commit cd7ff5f8

## 1. What this is

- Static Arabic archive of ~775 translated Bible commentaries, published on
  GitHub Pages: https://osamasla.github.io/Arabic-Bible-documentary/
- Repo: https://github.com/OsamaSla/Arabic-Bible-documentary (branch `main`,
  Pages source = `main` / `/docs`).
- Single editor workflow: Word `.docx` files live outside the repo in
  `D:\MegaDrive\ترجمات` (MEGA-synced drive). The repo only holds the generated
  site plus build scripts.
- Admin panel runs **locally only** (`scripts/serve.py`, binds 127.0.0.1, random
  token injected per run); admin files are never copied into `docs/`.

## 2. Stack & versions

- Python 3.11 (`C:\Users\osama\AppData\Local\Programs\Python\Python311`),
  stdlib + `python-docx`, `beautifulsoup4`, `lxml` (see `scripts/requirements.txt`).
- No JS framework; static HTML/CSS/JS. CSP meta on every generated page.
- Scripts talk to each other in-process: `build.py` imports `convert.main`,
  `scripture_index`, `mega_nav`. There is no task runner or packaging.
- Source path is hardcoded in 4 scripts (`convert.py`, `serve.py`, `watch.py`,
  `weekly_deploy.py`) as `D:\MegaDrive\ترجمات`. Renaming the *project* folder
  does not affect it.

## 3. Repo map

- `docs/` — generated site (3,414 files, 908 HTML). Committed; Pages serves it.
- `local-hidden/` — hidden docs + full `documents-index.json` (gitignored).
- `scripts/build.py` — master build (2,229 lines): conversion → site pages.
- `scripts/convert.py` — docx → HTML + `docs/documents/index.json`.
- `scripts/serve.py` — localhost server + token-gated admin API.
- `scripts/watch.py` — polling rebuild/auto-push loop (separate from serve.py).
- `scripts/weekly_deploy.py` — Windows scheduled task registration + runner.
- `js/admin-ui.js`, `admin-panel.html` — admin UI (not published).
- `categories.json` / `doc_categories.json` — vocabulary + doc→category map.

## 4. Commands

- `python scripts/build.py` — full rebuild (writes `docs/`, `local-hidden/`,
  `.last_build`).
- `python scripts/serve.py` — local server + opens admin panel at
  `http://127.0.0.1:8000/admin-panel.html`.
- `Open Admin.bat` / `Preview Site.bat` / `AdminMenu.bat` — wrappers.
- `python scripts/build.py` does not accept flags today (see section 8).

## 5. Data model & deploy

- `docs/documents/index.json` — visible docs only; `local-hidden/documents-index.json`
  — all docs incl. hidden. Fields include `id`, `title`, `author`, `rel_path`,
  `html_path`, `download_path`, `mtime`, `file_hash`, `completed`, `hidden`,
  `categories`.
- Doc ids are currently **positional** (`doc_0000`… in scan order). Adding or
  removing a docx shifts every later id and URL. Incremental work must pin ids
  from the existing index.
- Deploy = build → `git add -A` → commit → push (scripts/git_ops.py) → GitHub
  Pages rebuild (~30–90 s, outside our control).

## 6. Conventions

- Arabic RTL site; UI strings Arabic; comments/scripts English.
- All generated page paths are relative; asset URLs get `?v=<hash>` stamp.
- No inline JS (CSP); admin UI uses delegated handlers in `js/admin-ui.js`.
- Hidden folders: `hidden/` or `مخفي/`; completed folder: `تم/` (nestable).

## 7. Verified gotchas

- **Full build is slow by construction**: `convert.py` re-parses all 775 docx
  every run (~0.152 s/doc measured on 20 files → ~2 min), then rewrites every
  page. Total deploy ~3–5 min.
- `serve.py` runs the build synchronously (timeout 300 s) and is
  single-threaded: the panel is frozen during a build and two deploys can run
  concurrently (no lock).
- `_DOC_LOOKUP` in `serve.py` is cached forever → "open original Word" fails for
  newly added docs until the server restarts.
- Doc ids are positional (see §5).
- Weekly scheduled task `ArabicBibleWeeklyDeploy` still points at the old path
  (`D:\MegaDrive\Designs\...\My-Projects\ترجمات`) after the project move. Fix:
  re-save the schedule from the admin panel, which recreates the task with the
  current `BASE_DIR` (`weekly_deploy.py:222`). User is handling this.
- Global `~/.config/opencode/opencode.jsonc` had a missing comma in `policies`
  (invalid JSON) — fixed 2026-10-28.

## 8. Known issues / cleanup candidates

- `scripts/watch.py` duplicates the polling logic and is not used by the admin
  panel; consider merging into `serve.py`.
- `build.py` regenerates every page even when inputs are unchanged (caused git
  churn before `_write_if_changed` was added for some pages).
- `convert.py` writes every article page unconditionally.

## 9. Current task: fast article publishing (4 stages)

Goal: edit `.docx` → local preview in ~5 s → live site in ~1–1.5 min.
Decisions: incremental build (no Firebase/runtime layer); per-article button;
auto-deploy after 10 s idle; keep SEO/URLs; IDs must stay stable.

- **Stage 1 (in progress)** — `convert.py`: reuse previous index, skip unchanged
  docx by `mtime_ns`+`size`, hash only when mtime changed, backfill `size`/
  `mtime_ns`, stable ids (`max+1`), purge removed docs, expose changed paths.
  Verify: full build output identical except new index fields.
- **Stage 2** — `build.py`: target asset/nav/cache-bust passes to changed pages,
  incremental `search-index.json`, paired sidebar/chapter markers,
  `_write_if_changed` everywhere, `.build-cache/manifest.json`, `--full` flag.
- **Stage 3** — `serve.py`: build thread + lock, `/api/build-status`,
  `/api/update-doc`, auto-deploy watcher (2 s poll, 10 s debounce, ignore Word
  lock files), `no-store` for local HTML, clear `_DOC_LOOKUP` after builds.
- **Stage 4** — admin UI: auto-publish toggle, live log, per-row update button,
  focus-visible + no CLS; verification; note update.

## 10. Definition of done

- Full rebuild matches current site (no content diff beyond index fields).
- Single-doc edit: build < 10 s, only affected files changed.
- Add docx → id appended, no existing path changes; delete docx → page removed.
- One real end-to-end publish reaches the live Pages URL.
- Admin UI keyboard/focus/CLS checked.
