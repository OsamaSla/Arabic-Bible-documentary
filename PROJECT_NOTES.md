# PROJECT NOTES — Arabic Bible documentary
Last verified: 2026-10-31, working tree (Firebase hosting + mobile app pass; docs stamp `?v=0d91a7bb`)

## 1. What this is
Static site (docs/) of Arabic Christian translations + Bible indexes.
Source docs under D:\MegaDrive\ترجمات (.docx); public site at docs/.

## 2. Stack & versions
Python 3.12 (Windows); static build (build.py → docs/); no runtime backend.
Hosting: **Firebase Hosting** project `arabic-bible-documentary`
(`firebase.json` → public `docs`; live https://arabic-bible-documentary.web.app)
and still GitHub Pages from `docs/` on `main`.
Firebase CLI `firebase` is on PATH (v15.x, logged in as osama.sla@gmail.com).
local dev: scripts/serve.py (port 8000, 127.0.0.1, X-Serve-Token auth).
Admin files served from repo root (never published): admin-panel.html, js/admin-ui.js.

## 3. Repo map
scripts/  convert.py (cache + stable IDs) | build.py (search index + manifest)
         serve.py (dev server + /api routes)
docs/    built site (published to GitHub Pages from docs/ folder)
local-hidden/ hidden docs index (admin only)

## 4. Commands that work
python scripts/build.py        # full/rebuild (cached when possible)
python scripts/serve.py        # dev server (auto-rebuild not yet non-blocking)
python scripts/convert.py      # stage 1 conversion

## 5. Data model, deploy
- Source: .docx (author folder + rel_path); stable doc IDs (max+1, never reused).
- Build manifest: .build-cache/manifest.json (asset_stamp, nav_sig, finished_at).
- Search index: .build-cache/search-cache.json (schema=1), rebuilt incrementally.
- Firebase: `firebase deploy --only hosting --project arabic-bible-documentary`
  (3,416 files / 127 MB; re-deploys upload only changed files).
- `scripts/git_ops.py` `git_add_commit_push()` now runs `firebase_deploy()` after a
  successful push, so the admin Deploy button and weekly job publish both targets.
- Weekly deploy handled by user (weekly_deploy.py) — out of scope for this stage.
- GitHub Pages published from docs/ folder; build restamp (?v=) applied.

## 6. Verified gotchas (with evidence)
- `finalize_paths` must be initialized before `inject_related_sidebars` call
  (fixed: init `finalize_paths = None` at top of main(), computed after generators).
- Copy steps (`copy_search_page`, `copy_translations_page`) pass `finalize_paths`
  to register themselves for the finalization merge.
- Search index no-op on cached rebuild: `search-index.json unchanged (763 docs, cached)`.
- Build times: 11.5 s first cached, 4.9 s second cached (full pass); no-op faster.
- `docs/` dirty from stage 2 restamp transition: 3 files changed (doc_0172 + index + search-index).
- Build manifest `.build-cache/manifest.json` tracks asset_stamp + nav_sig + finished_at.

## 7. Stage 3 (serve.py) — IMPLEMENTED
- Non-blocking build thread (`_run_build_async_start`) + `_BUILD_LOCK`.
- `/api/update-doc`: POST {docId} triggers async build, returns 202.
- `/api/build-status`: GET returns `_BUILD_STATUS` (running, last_result, messages, timestamps).
- Auto-deploy watcher (`_watcher_loop`): 2 s poll, 10 s stability debounce, ignores `~$*.docx`; starts in `main()`.
- `_clear_doc_lookup()` called in build `finally` block; `Cache-Control: no-store` on all static (`cache=False`) and API responses.
- `_run_build_sync()` preserved for deploy path (needs result before push).
Verified: syntax ok; import ok; module-level functions and endpoints present.

## 8. Stage 4 (admin UI) — IMPLEMENTED & PUSHED (commit 9b47e50a)
- Toggle (`liveLogToggle`): shows/hides `liveLogPanel`; starts 3 s poll of `/api/build-status`.
- Live log (`pollLiveLog`): displays `running`, `last_result` (OK/Failed/None), timestamps, `last_message`.
- Per-row button (`data-update-doc`): calls `POST /api/update-doc` with doc `id`; shows "Started" / "Failed".
Verified: admin-ui.js syntax/intact; build passes (11.5 s first, incremental faster); commit pushed to origin/main (docs/ rebuilt + 14 files, 539 insertions).

## 9. Font & banner fixes (verified 2026-10-29, commit 44a6ac6b)
- Global font-size 150% (`html { font-size: 150%; }` in `css/style.css`).
- Arabic font picker in ruler (`js/ruler.js`): نسخ (default/Naskh), أميري (Amiri), Tajawal (loaded via Google Fonts import in `css/fonts.css`), مبسط (Simplified Arabic).
- Banner resize/alignment: `.logo` 1.1rem, `.logo .cross` 1.8rem, `.main-nav a` 0.9rem, `.main-nav` `align-items: center`.
- Build passes (`python scripts/build.py`); `node --check js/ruler.js` clean; docs rebuilt and pushed.

## 9. Mobile fixes (verified 2026-10-29)
- Header: `.site-header` `min-height` 56px → 64px; `.logo` 0.95rem; `.main-nav a` 0.8rem; `align-items: center` preserved for banner alignment (`الترجمات` aligned).
- Document/article: `.document-viewer` padding 0.75rem 0; `.document-title` 1.2rem / line-height 1.5.
- Ruler toolbar (`css/ruler.css`): `.ruler-base` height 34px → 44px; chip/label/switch/input scaled to `0.75rem`; mobile media query updated (`min-height: 36px`, `max-height: 75vh`).
- Font picker (`rpanel-view`): `traditional` value maps to `'Tajawal', serif` in CSS; chip label stays readable at 150% scale.
- Build passes (`python scripts/build.py`); docs rebuilt (`?v=66149845`); `node --check js/ruler.js` clean.

## 8. Context budget
Checkpoint done after stage 2 (writes to `PROJECT_NOTES.md`, `git log` confirmed
3 commits: 6aa323db, e93f79cc, abfa21df + 9e87b789/ cdd8e5b3 notes).
Before stage 3: /compact then continue.
Next: /compact required before continuing stage 3.

## 10. Firebase Hosting (2026-10-31)
- Project created from CLI: `firebase projects:create arabic-bible-documentary`
  (the `--display-name "..."` form fails here — the shell drops the quoting and
  the CLI reports "Too many arguments"; create without it).
- `firebase.json`: public `docs`, ignore dotfiles/node_modules, headers:
  `/` + `**/*.html` no-store, css/js no-cache (site uses `?v=`), images 7 d,
  fonts 30 d. **No `**` rewrite** (unlike the German site) so broken links 404
  instead of silently serving the homepage.
- Gotcha (verified with `curl -sI`): a `**/*.html` header does NOT match `/`
  — Firebase matches the request path, so `/` needs its own entry, else the
  homepage keeps the default `Cache-Control: max-age=3600`.
- `.firebase/` and `firebase-debug.log` are gitignored.
- Deploy is not CI: build locally, then `firebase deploy`.

## 11. Mobile app pass (2026-10-31)
- Both header systems share `#navToggle` / `#navBar` (legacy `.nav-bar` on
  bible/author pages, redesigned `.rx-nav` on the homepage). `js/nav.js` now
  creates one `.nav-backdrop` + `.nav-drawer-head` and turns either nav into an
  off-canvas drawer at ≤768 px: fixed right panel `min(88vw, 380px)`, `100dvh`,
  `html.nav-open` scroll lock, backdrop / × / Escape / link-click close, focus
  restore, `aria-expanded` + mobile-only `aria-hidden`.
- Drawer markup is injected by JS, so no template/build changes were needed.
- Note: `nav.js` runs on every page (build injects it), and elements are only
  created when `#navToggle` exists.
- Legacy header was 104 px tall on phones because the long logo wrapped; now
  single-line with ellipsis (`.logo-text` 0.8rem) → **68 px** measured with
  mobile media rules forced on.
- Mobile scale: fluid `clamp()` h1–h4 (root stays 127.5 %); 44 px icon buttons
  and nav rows; ruler base 48 px `min-height` + `env(safe-area-inset-bottom)`;
  fmt inputs 16 px (stops iOS focus zoom); quick-lookup stacks at ≤480 px.
- Verification without a mobile viewport: open the page, walk `document.styleSheets`,
  set `mediaText = 'all'` on every `max-width` media rule, then read computed
  styles (`browser.evaluate`). Confirmed: nav closed `display:none` → open
  `position:fixed` 380 px, drawer head `flex`, icons 44 px, inputs 16 px,
  `.rx-lookup-fields` column, no horizontal overflow.
- Screenshots are unavailable in this environment ("needs a visible tab");
  real-device check is still owed by the user.
