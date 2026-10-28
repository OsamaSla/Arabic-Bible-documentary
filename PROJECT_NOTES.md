# PROJECT NOTES — Arabic Bible documentary
Last verified: 2026-10-29, commit 9e87b789 (notes-stage2), abfa21df (build); stage 3 implemented in scripts/serve.py (uncommitted)

## 1. What this is
Static site (docs/) of Arabic Christian translations + Bible indexes.
Source docs under D:\MegaDrive\ترجمات (.docx); public site at docs/.

## 2. Stack & versions
Python 3.12 (Windows); static build (build.py → docs/); no Firebase/runtime.
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

## 8. Context budget
Checkpoint done after stage 2 (writes to `PROJECT_NOTES.md`, `git log` confirmed
3 commits: 6aa323db, e93f79cc, abfa21df + 9e87b789/ cdd8e5b3 notes).
Before stage 3: /compact then continue.
Next: /compact required before continuing stage 3.
