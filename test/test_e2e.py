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

  4. test_load_and_play_sound ...... A sound loaded through the (faked) file
                                     picker appears in the sounds dialog and
                                     actually plays (HTMLMediaElement.play()).

  5. test_load_and_preview_image ... An image loaded the same way appears as a
                                     thumbnail with its decoded dimensions, and
                                     opens in the interactive canvas previewer.

Requires Playwright + its Chromium browser, and a built ``dist/`` (run ``make``).
Tests skip cleanly, with guidance, if either is missing.

Run directly:  test/.venv/bin/python test/test_e2e.py
Or via:        test/.venv/bin/python test/run.py
"""

import base64
import os
import contextlib
import struct
import sys
import unittest
import zlib
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from browser_stub import HELLO_BODY, HELLO_PY, REPO_ROOT, import_pywebedit  # noqa: E402

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


def _tiny_wav():
    """A minimal but valid WAV (8-bit mono) the browser can actually play."""
    sr = 8000
    data = b"\x80" * 8
    header = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(data), b"WAVE",
                         b"fmt ", 16, 1, 1, sr, sr, 1, 8, b"data", len(data))
    return header + data


def _tiny_png(w, h, rgba=(220, 40, 40, 255)):
    """A minimal but valid w*h RGBA PNG, so the previewer reads real dimensions."""
    def chunk(typ, payload):
        body = typ + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)  # 8-bit RGBA
    raw = b"".join(b"\x00" + bytes(rgba) * w for _ in range(h))
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


# Stand in for the File System Access picker (a native dialog Playwright can't
# drive). Returns a handle whose getFile() yields the bytes we hand it, so the
# real read_file_as_data_url -> add_sound/add_image path runs unchanged. Also
# spies on HTMLMediaElement.play() so the sound test can confirm playback.
_FAKE_PICKER_JS = """
([b64, name, mime]) => {
  window.__plays = 0;
  const proto = window.HTMLMediaElement.prototype;
  if (!proto.__spied) {
    const orig = proto.play;
    proto.play = function () {
      window.__plays++;
      try { return orig.apply(this, arguments).catch(() => {}); } catch (e) { return; }
    };
    proto.__spied = true;
  }
  window.showOpenFilePicker = async () => {
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    const file = new File([bytes], name, { type: mime });
    return [{ name: name, getFile: async () => file }];
  };
}
"""


def _install_fake_picker(page, file_bytes, name, mime):
    page.evaluate(_FAKE_PICKER_JS, [base64.b64encode(file_bytes).decode(), name, mime])


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

    @contextlib.contextmanager
    def _editor_page(self):
        """Yield an offline page with the editor mounted, plus its pageerror list."""
        context = self._offline_context()
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            page.goto(INDEX_URL)
            page.wait_for_selector(".cm-editor", timeout=25000)
            yield page, errors
        finally:
            context.close()

    # --- 1. Editor comes up (offline, via local brython fallback) -----------
    def test_editor_mounts(self):
        with self._editor_page() as (page, errors):
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

    # --- 2. Run executes code in a generated window (offline) ---------------
    def test_run_works_offline(self):
        with self._editor_page() as (page, _errors):
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

    # --- 4. A loaded sound shows up and plays -------------------------------
    def test_load_and_play_sound(self):
        with self._editor_page() as (page, _errors):
            _install_fake_picker(page, _tiny_wav(), "ping.wav", "audio/wav")
            page.select_option("#pyfiles", "__add_sounds")  # opens the sounds dialog
            page.locator("button:has-text('Add sound')").first.click()

            # The loaded sound appears as a row with a play (▶) button.
            page.wait_for_selector("button:has-text('▶')", timeout=10000)
            page.locator("button:has-text('▶')").first.click()

            page.wait_for_function("window.__plays >= 1", timeout=5000)
            self.assertGreaterEqual(page.evaluate("window.__plays"), 1)

    # --- 5. A loaded image shows up and opens in the previewer --------------
    def test_load_and_preview_image(self):
        with self._editor_page() as (page, _errors):
            _install_fake_picker(page, _tiny_png(8, 8), "dot.png", "image/png")
            page.select_option("#pyfiles", "__add_images")  # opens the images dialog
            page.locator("button:has-text('Add image')").first.click()

            # The loaded image appears as a clickable data: thumbnail, and its
            # decoded dimensions show up once it has really loaded.
            thumb = page.locator("img[src^='data:image']")
            thumb.first.wait_for(timeout=10000)
            page.wait_for_function("() => document.body.innerText.includes('8\\u00d78')", timeout=10000)

            thumb.first.click()  # open the interactive previewer
            page.wait_for_selector("canvas", timeout=10000)
            self.assertGreaterEqual(page.locator("canvas").count(), 1, "previewer canvas missing")
            self.assertEqual(
                page.locator("button:has-text('Reset View')").count(), 1, "previewer controls missing"
            )

    # --- 6. Exported file is standalone AND runs fully offline --------------
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
