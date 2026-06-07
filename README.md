# pywebedit

Build python programs that can run in the browser, from your browser.

See the live version [here](https://robotfantastic.org/pywebedit/).


## Goals

- Run python programs on a classroom Chromebook, without having to
  install Linux, or anything
- Have a way to keep everything local, in-browser, standalone, so we
  don't even need web access (sites like [replit](https://replit.com/)
  are often blocked and [runpython](https://runpython.org))
- Make sure python errors are reported to the screen, as opposed to
  the developer console (also often blocked)
- Allow distribution of resulting programs as standalone html files,
  which can be run directly from the browser, and shared using Google
  Drive
- These files should also be able to be run fully offline using the same
  files as from the original download
- Maximize vertical space for coding on a Chromebook


## Approach

- Use [brython](https://www.brython.info/)
- Use [Codemirror 6](https://codemirror.net) for the editor components
- Inspired by [brython's editor
  example](https://www.brython.info/tests/editor.html?lang=en) and
  [urfdvw's Brython Editor](https://github.com/urfdvw/Brython-Editor)
- Use a fallback so that it can run using local copies of the main
  javascript libraries (both the editor and the generated webpages)
- Embed images and sound files to be truly portable, even offline
  (where you can't load non-image files)


## Implementation notes

- Mixing tabs and spaces results in confusing errors. For now, we
  replace all tabs with spaces on Run.
- Some CDNs are better than others for this project, in that they
  allow fetching resources from Origin: Null (like when you are
  running / testing locally). This is nice, so prefer them (unpkg).


## Testing

A small test harness lives in [`test/`](test/). It exercises the three things
that actually matter for this project:

1. **The editor comes up** – Brython compiles the app, both CodeMirror panes
   mount, and the toolbar + examples menu populate.
2. **Code runs dynamically** – clicking **Run** opens a generated window that
   executes the Python and renders its output.
3. **Export is standalone & offline** – the exported HTML, with Brython inlined
   as base64, runs from disk with the network fully cut off and makes *zero*
   external requests.
4. **Sounds & images** – a loaded sound is embedded, survives save/reopen, and
   plays; a loaded image is embedded and opens in the canvas previewer.

The browser tests all run in a fully **offline** context, so they also prove
the CDN-with-local-fallback wiring works with no internet (Run included).

### Two tiers

- **Tier 1 – logic tests (`test/test_logic.py`), zero dependencies.**
  `pywebedit.py` is Brython, so it can't be imported under normal CPython
  (`from browser import ...`). The harness installs a tiny fake `browser`
  module (`test/browser_stub.py`) so the *pure-Python* core can be unit-tested
  directly: the `build_html` ⇄ `split_html` round-trip (body, modules, sounds,
  images), the chunked base64 `encode_js_for_html`, the standalone-export shape
  (libraries inlined as `data:` URLs, no `http(s)`), and the build scripts
  (`examples.py`, `utils/tagreplace.py`). Needs only **Python 3.10+** — no pip
  installs at all.

- **Tier 2 – browser end-to-end tests (`test/test_e2e.py`), one dependency:
  [Playwright](https://playwright.dev/python/).** Drives a headless Chromium
  (Chromium because the app relies on Chrome-only APIs) to prove the three
  behaviours above in a real browser, all with the network forced off.
  Playwright bundles its own browser, so there's nothing else to install. These
  tests **skip cleanly** if Playwright (or a built `dist/`) is missing, so the
  suite still runs with zero dependencies.

### Setup (isolated, via `uv`)

The browser tier's one dependency lives in a project-local virtualenv so it
never touches your other environments. Either let `make` do it:

```sh
make test-setup     # create test/.venv and install Playwright + its browser
```

…or run the same steps by hand:

```sh
uv venv test/.venv --python 3.13
uv pip install --python test/.venv/bin/python playwright
test/.venv/bin/python -m playwright install chromium
```

### Running

```sh
make test          # build dist/ + test env as needed, then run both tiers
make test-logic    # Tier 1 only — zero deps, no dist/, just Python 3.10+

# Or invoke the runner directly:
test/.venv/bin/python test/run.py              # both tiers
test/.venv/bin/python test/run.py --logic-only # Tier 1 only
test/.venv/bin/python test/run.py --e2e-only   # Tier 2 only
test/.venv/bin/python test/run.py --build      # `make` dist/ first, then run
python test/run.py --logic-only                # Tier 1 on any bare Python 3.10+
```

(Tier 2 needs a built `dist/`; `make test` builds it for you. If `dist/` is
missing when running the runner directly, the browser tests skip with a hint.)

### Notes / caveats

- **Everything is tested offline.** The browser context uses Playwright's
  `set_offline(True)` and loads from `file://`, so the CDN Brython fails exactly
  as it would on a disconnected machine and the local `brython.min.js` fallback
  takes over — for the editor, the Run popup, and exported files alike.
- Don't intercept the CDN with Playwright *routing* to fake offline: aborting or
  fulfilling a parser-blocking `<script>` mid-`document.write` truncates the
  generated popup (a CDP quirk, not real browser behaviour). `set_offline` lets
  the request fail naturally, which is why the Run test uses it.
- Generated artifacts land in `test/output/` (git-ignored), including a real
  `standalone_hello.html` you can open by hand.


## TODO

- Increase speed of export
  - Test out speed of non-chuncked encode approach
- Improve speed of loading
  - Check out Blob approach instead of directly embedding script
- Maybe "use" statements that load scripts in a useful way?
- Support export to github
- support save/load from google drive?
- Disable other buttons when help window is up
- Add console
- Fix keypresses on Windows
- Fix issue where mismatched tags in the body section will screw up
  code generation. Need to parse it?
- Fix behavior with long lines - editor grows, which may not be what
  we want
- Add [indentation markers](https://github.com/replit/codemirror-indentation-markers)
- Don't add the stdlib if the python doesn't require it
  - No, can't do this yet, as error handling depends on stdlib
- Consider using brython's browser.widgets.menu to make more complex
  menu interfaces
- Add all examples from Brython website?


## References

- Game libraries
  - pixi.js
      - https://waelyasmina.net/articles/pixi-js-tutorial-for-complete-beginners/
  - https://ggame.readthedocs.io/en/latest/introduction.html
  - phaser.js
- Sound:
  - https://tonejs.github.io/
  - https://buzz.jaysalvat.com/ for audio
  - pixi-sound.js
- For oauth server for github:
  - https://sphaerula.com/blog/posts/wsgi-and-cgi-apps-in-a-dreamhost-shared-hosting-account/
    - Seems that running python as cgi is still working and dead
      simple
    - And, from https://docs.python.org/2/howto/webservers.html shows
      how to enable nice debugging
