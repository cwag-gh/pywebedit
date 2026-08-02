# pywebedit

In-browser Python IDE built on **Brython** that exports **self-contained,
offline-capable HTML files**. Audience: students on locked-down classroom
Chromebooks (no install, often no network). See `README.md` for goals/approach
and the full testing guide.

## Architecture essentials

- **`pywebedit.py` is Brython** — written in Python but it runs *in the browser*
  (`from browser import ...`); plain CPython can't import it directly. It is the
  whole editor: `App` (state/model), `UI` (two CodeMirror panes + toolbar), and
  the dialogs (`AssetDialog` → `SoundsDialog`/`ImageDialog`/`ResourceDialog`,
  plus `ImageViewDialog`/`ResourceViewDialog`).
- **Build pipeline** (`Makefile`): `utils/tagreplace.py` injects `pywebedit.py`
  into `pywebedit.html_template` → `dist/pywebedit.html` (copied to
  `dist/index.html`). `pywebeditor/editor.mjs` → rollup → `dist/pywebeditor.min.js`
  (CodeMirror 6 on `window`). `examples.py` base64-bundles `examples/*.html` →
  `dist/examples.js`. Brython/pixi/three are downloaded into `dist/` (gitignored).
- **After editing `pywebedit.py`, run `make`** to rebuild `dist/index.html`
  before the editor or the E2E tests reflect the change.
- **Saved-file format**: `App.build_html()` writes the page; `App.split_html()`
  parses it back — keep this round-trip lossless. Templates use
  `%script%`/`%endscript%` placeholders (avoids script-in-script breakage) and
  `%sounds%`/`%images%`/`%resources%`.
- **Embedded assets** are `name → data: URL` dicts emitted as
  `window.SOUNDS`/`IMAGES`/`RESOURCES` in the page preamble and read from there
  by user code. Default save does **not** inline Brython (CDN + local fallback),
  so saved files stay small; **Export** inlines Brython (base64) for one fully
  offline file.
- **Asset model**: `App` has parallel method sets per type
  (`get_*_names/get_*/add_*/rename_*/delete_*`); dialogs share `AssetDialog`'s
  add/rename/delete workflow. Resources keep the file extension in the name
  (`keep_extension=True`); sounds/images strip it.
- **Name collisions** go through the looping `rename_asset`/`load_asset` helpers;
  `name_is_unused(name)` must return True when the name is FREE (inverting it was
  a real bug). New-module reuses `rename_asset('', ...)`.
- **Unsaved-changes**: `_remember_saved_state()` snapshots modules + all assets
  (called in `__init__`/`load_html`/`save_file`); `anything_modified()` compares.

## Build & test

- `make` build `dist/` · `make test` full suite · `make test-logic` Tier 1 only
  (zero deps, no dist) · `make test-setup` create `test/.venv` + Playwright.
- **Tier 1** `test/test_logic.py`: stdlib `unittest`, zero deps, Python **3.10+**.
  Imports `pywebedit` behind a fake `browser` module (`test/browser_stub.py`: an
  `_Any` black-hole object + real dialog base classes). Drive async dialog flows
  with the `_stub_dialogs` helper.
- **Tier 2** `test/test_e2e.py`: Playwright headless Chromium, all offline.
- Isolated env is `test/.venv`, created with **`uv`** — never touch other Python
  environments.

## Hard-won gotchas

- **Chrome-only**: relies on the File System Access API
  (`showOpenFilePicker`/`showSaveFilePicker`). Verify in Chromium.
- **Faking offline in tests**: use Playwright `context.set_offline(True)`, NOT
  route abort/fulfill — intercepting a parser-blocking `<script>` mid
  `document.write` truncates the Run popup (a CDP quirk, not a product bug).
- **Data URLs just work**: embedded CSS via `<link href="data:text/css;...">`
  and fonts via `@font-face` load offline in Chrome regardless of MIME — no MIME
  massaging needed.
- **Action buttons are emoji** (▶️ ⏹️ ✏️ 🗑️ 🔍) so they size consistently; don't
  mix text glyphs (▶/■) and `font-size` hacks.
- **Drive the picker in tests** by overriding `window.showOpenFilePicker` to
  return a handle whose `getFile()` yields bytes; the real read→data-URL→add path
  then runs unchanged.
- A sample TTF lives at `playground/pygame/aliens/data/sans.ttf` (untracked; the
  font E2E test skips if absent).

## Working style (learned preferences)

- **Minimal dependencies.** One well-justified dep is acceptable (Playwright for
  E2E); otherwise stdlib.
- **Concise code; let names document it.** Comments very sparingly, especially in
  `pywebedit.py`. Delete dead/debug code rather than leaving it.
- **Reuse existing workflows** instead of adding near-duplicates; prefer the
  smallest change consistent with the existing paradigm; don't over-engineer.
- **Verify, don't guess**: screenshot UI changes with Playwright before claiming
  done; for a bug fix, confirm the regression test fails on the old code, then
  restore the fix.
- Don't register new files in the bundled examples (`examples.py`) unless asked.
