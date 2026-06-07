"""Tier 2 -- browser end-to-end tests, driven by Playwright (one dependency).

Every test runs in a fully OFFLINE browser context (``set_offline(True)``) and
loads pages from ``file://``, so the suite needs no network and is
deterministic. This also exercises pywebedit's whole reason for existing -- the
CDN-with-local-fallback wiring that lets everything work with no internet.

  1. test_editor_mounts ............ The editor comes up offline: the CDN
                                     Brython fails, the local fallback loads it
                                     from disk, both CodeMirror panes mount, and
                                     the toolbar + examples menu populate.

  2. test_run_works_offline ........ Clicking "Run" opens a generated window
                                     that executes the Python and renders
                                     "Hello, World!" -- offline. The popup
                                     inherits the editor's base URL, so the same
                                     local-brython fallback resolves there too.

  3. test_exported_file_runs_fully_offline ...... An exported file (Brython
                                     inlined as base64) renders "Hello, World!"
                                     from disk while offline AND attempts zero
                                     external requests -- the definitive
                                     "standalone, offline" proof.

Requires Playwright + its Chromium browser, and a built ``dist/`` (run ``make``).
Tests skip cleanly, with guidance, if either is missing.

Run directly:  test/.venv/bin/python test/test_e2e.py
Or via:        test/.venv/bin/python test/run.py
"""

import os
import sys
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from browser_stub import import_pywebedit, REPO_ROOT  # noqa: E402

pwe = import_pywebedit()

try:
    from playwright.sync_api import sync_playwright

    HAVE_PLAYWRIGHT = True
except ImportError:
    HAVE_PLAYWRIGHT = False

DIST = os.path.join(REPO_ROOT, "dist")
INDEX_URL = Path(DIST, "index.html").as_uri()
REQUIRED_DIST = [
    "index.html",
    "brython.min.js",
    "brython_stdlib.js",
    "pywebeditor.min.js",
    "examples.js",
]

HELLO_BODY = "<h1 id='text'></h1>"
HELLO_PY = "from browser import document\ndocument['text'].textContent = 'Hello, World!'"

# Brython reports errors to an on-screen div rather than throwing, but a working
# "Hello, World!" page sets #text; wait for that as the signal that code ran.
TEXT_READY = (
    "document.getElementById('text') && "
    "document.getElementById('text').textContent.length > 0"
)


def _dist_ready():
    return all(os.path.exists(os.path.join(DIST, f)) for f in REQUIRED_DIST)


def _build_standalone_hello():
    """Use the real export code path to inline real Brython into one file."""
    app = pwe.App()
    for lib, fname in (("brython", "brython.min.js"), ("brython_stdlib", "brython_stdlib.js")):
        with open(os.path.join(DIST, fname), encoding="utf-8") as f:
            app.libraries[lib] = f.read()
    return app.build_html(HELLO_BODY, HELLO_PY, libs_to_bundle=["brython", "brython_stdlib"])


@unittest.skipUnless(HAVE_PLAYWRIGHT, "playwright not installed (see project README)")
@unittest.skipUnless(_dist_ready(), "dist/ not built -- run `make` in the repo root")
class BrowserE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._pw = sync_playwright().start()
        cls.browser = cls._pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls._pw.stop()

    def _offline_context(self):
        """A browser context with no network at all."""
        context = self.browser.new_context()
        context.set_offline(True)
        return context

    # --- 1. Editor comes up (offline, via local brython fallback) -----------
    def test_editor_mounts(self):
        context = self._offline_context()
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            page.goto(INDEX_URL)
            page.wait_for_selector(".cm-editor", timeout=25000)

            self.assertEqual(
                len(page.query_selector_all(".cm-editor")), 2, "expected two editors"
            )
            for btn in ("#btnrun", "#btnopen", "#btnsave", "#btnsaveas", "#btnexport"):
                self.assertIsNotNone(page.query_selector(btn), f"missing {btn}")

            n_optgroups = page.eval_on_selector(
                "#examples", "el => el.querySelectorAll('optgroup').length"
            )
            self.assertGreaterEqual(n_optgroups, 1, "examples menu not populated")
            self.assertIn("Hello, World!", page.inner_text("#python_editor"))
            self.assertEqual(errors, [], f"unexpected page errors: {errors}")
        finally:
            context.close()

    # --- 2. Run executes code in a generated window (offline) ---------------
    def test_run_works_offline(self):
        context = self._offline_context()
        page = context.new_page()
        try:
            page.goto(INDEX_URL)
            page.wait_for_selector(".cm-editor", timeout=25000)

            with page.expect_popup(timeout=25000) as popup_info:
                page.click("#btnrun")
            popup = popup_info.value
            popup_errors = []
            popup.on("pageerror", lambda e: popup_errors.append(str(e)))

            popup.wait_for_function(TEXT_READY, timeout=25000)
            self.assertEqual(
                popup.eval_on_selector("#text", "el => el.textContent"),
                "Hello, World!",
                f"generated window did not run the code (errors: {popup_errors})",
            )
        finally:
            context.close()

    # --- 3. Exported file is standalone AND runs fully offline --------------
    def test_exported_file_runs_fully_offline(self):
        html = _build_standalone_hello()
        self.assertNotIn("https://", html, "exported file still references the network")

        out = os.path.join(HERE, "output", "standalone_hello.html")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)

        context = self._offline_context()
        external = []

        def block_external(route):
            url = route.request.url
            if url.startswith("file:"):
                route.continue_()
            else:
                external.append(url)  # any non-file request = not standalone
                route.abort()

        context.route("**/*", block_external)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            page.goto(Path(out).as_uri())
            page.wait_for_function(TEXT_READY, timeout=25000)
            self.assertEqual(
                page.eval_on_selector("#text", "el => el.textContent"), "Hello, World!"
            )
            self.assertEqual(external, [], f"file made external requests: {external}")
            self.assertEqual(errors, [], f"unexpected page errors: {errors}")
        finally:
            context.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
