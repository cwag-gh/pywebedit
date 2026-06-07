"""Tier 1 -- pure-logic tests. ZERO third-party dependencies (stdlib only).

These exercise the riskiest, most bug-prone code in pywebedit -- the code that
turns the two editor panes into a single self-contained HTML file and parses it
back again -- without a browser. ``pywebedit.py`` is Brython, so we import it
behind a fake ``browser`` module (see ``browser_stub``).

Covered:
  * importing the Brython app under CPython
  * ``build_html`` -> ``split_html`` round-trip (body, modules, sounds, images)
  * ``encode_js_for_html`` base64 round-trip (ascii, unicode, >1 chunk)
  * the small string helpers (parse_str_str_dict / extract_between / ...)
  * standalone export shape: libraries inlined as ``data:`` URLs, no http(s)
  * the build scripts that assemble the editor (examples.py, tagreplace.py)

Run directly:  python test/test_logic.py
Or via:        python test/run.py --logic-only
"""

import asyncio
import base64
import contextlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from browser_stub import HELLO_BODY, HELLO_PY, REPO_ROOT, import_pywebedit  # noqa: E402

pwe = import_pywebedit()


def _decode_data_url_scripts(html):
    """Return the decoded UTF-8 bodies of every inlined data: script in html."""
    out = []
    for b64 in re.findall(r'src="data:text/javascript;base64,([A-Za-z0-9+/=\n]+)"', html):
        out.append(base64.b64decode(b64.replace("\n", "")).decode("utf-8"))
    return out


@contextlib.contextmanager
def _stub_dialogs(typed=(), events=None, picked_name=None):
    """Drive pywebedit's async name workflows without a browser.

    Replaces the dialog/picker/aio layer with stubs that script the user:
      typed       - successive values "entered" into EntryDialogs (default '')
      events      - successive aio.event outcomes 'entry'/'cancel' (default 'entry')
      picked_name - filename returned by pick_file_to_open, for file-based flows
    Yields {'prompts': [...]}, each entry the title + message a dialog showed.
    """
    prompts = []
    typed_it = iter(typed)
    events_it = iter(events) if events is not None else None

    class _Dialog:
        def __init__(self, title, message=None, **kwargs):
            prompts.append(f"{title} {message or ''}")
            self.entry = SimpleNamespace(value="")

        @property
        def value(self):
            return next(typed_it, "")

        def close(self):
            pass

    class _Aio:
        async def event(self, dialog, *types):
            return SimpleNamespace(type=next(events_it) if events_it else "entry")

    async def _pick(*args, **kwargs):
        return SimpleNamespace(name=picked_name)

    saved = {n: getattr(pwe, n) for n in ("EntryDialog", "AwaitableEntryDialog", "aio", "pick_file_to_open")}
    try:
        pwe.EntryDialog = pwe.AwaitableEntryDialog = _Dialog
        pwe.aio = _Aio()
        if picked_name is not None:
            pwe.pick_file_to_open = _pick
        yield {"prompts": prompts}
    finally:
        for name, value in saved.items():
            setattr(pwe, name, value)


class StringHelpers(unittest.TestCase):
    def test_strip_extension(self):
        self.assertEqual(pwe.strip_extension("game.html"), "game")
        self.assertEqual(pwe.strip_extension("a.b.c"), "a.b")
        self.assertEqual(pwe.strip_extension("noext"), "noext")

    def test_extract_between(self):
        self.assertEqual(pwe.extract_between("pre[MID]post", "[", "]"), "MID")
        with self.assertRaises(ValueError):
            pwe.extract_between("nope", "[", "]")

    def test_urlname(self):
        self.assertEqual(
            pwe.urlname("https://cdn.example.com/a/b/lib.min.js"), "lib.min.js"
        )

    def test_parse_str_str_dict_roundtrip(self):
        d = {"laser": "data:audio/mpeg;base64,AAAA", "boom": "data:audio/mpeg;base64,BBBB"}
        encoded = ",\n".join(f"'{k}':'{v}'" for k, v in d.items())
        self.assertEqual(pwe.parse_str_str_dict(encoded), d)

    def test_parse_str_str_dict_empty(self):
        self.assertEqual(pwe.parse_str_str_dict(""), {})
        self.assertEqual(pwe.parse_str_str_dict("   "), {})


class EncodeJsForHtml(unittest.TestCase):
    def _roundtrip(self, js):
        tag = pwe.encode_js_for_html(js)
        self.assertIn("data:text/javascript;base64,", tag)
        decoded = _decode_data_url_scripts(tag)
        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0], js)

    def test_ascii(self):
        self._roundtrip("console.log('hi');")

    def test_unicode(self):
        # The chunked-base64 scheme exists specifically to survive unicode.
        self._roundtrip("const s = 'héllo • wörld — ✓';")

    def test_multi_chunk(self):
        # Larger than the 1023-byte chunk size, to exercise padding-stripping.
        self._roundtrip("x=" + ("ABCDEFGHIJ" * 500) + ";")


class BuildHtmlBasics(unittest.TestCase):
    def setUp(self):
        self.app = pwe.App()

    def test_contains_editor_content(self):
        html = self.app.build_html(HELLO_BODY, HELLO_PY)
        self.assertIn(HELLO_BODY, html)
        self.assertIn("document['text'].textContent = 'Hello, World!'", html)

    def test_has_required_script_blocks(self):
        html = self.app.build_html(HELLO_BODY, HELLO_PY)
        self.assertIn('<script type="text/python" id="pythoncode">', html)
        self.assertIn('<script type="text/python" id="brythonpre">', html)
        self.assertIn("__brython_pre_then_code", html)

    def test_empty_assets_render_empty_dicts(self):
        html = self.app.build_html(HELLO_BODY, HELLO_PY)
        self.assertIn("window.SOUNDS = {}", html)
        self.assertIn("window.IMAGES = {}", html)

    def test_unbundled_uses_cdn_loader_with_fallback(self):
        html = self.app.build_html(HELLO_BODY, HELLO_PY)
        # Not bundled -> references the CDN with a local document.write fallback,
        # rather than inlining as data: URLs.
        self.assertIn(pwe.JSLIBS["brython"][2], html)  # CDN url
        self.assertIn("document.write", html)          # local fallback loader
        self.assertNotIn("data:text/javascript;base64,", html)


class RoundTrip(unittest.TestCase):
    """build_html -> split_html must reconstruct everything losslessly."""

    def test_full_roundtrip(self):
        app = pwe.App()
        app.sounds = {"laser": "data:audio/mpeg;base64,QUFBQQ=="}
        app.images = {"bunny": "data:image/png;base64,Qk1Q"}
        app.modules["util"] = "PI = 3.14159\n\ndef area(r):\n    return PI * r * r\n"
        html = app.build_html(HELLO_BODY, HELLO_PY)

        reader = pwe.App()
        body, modules, sounds, images = reader.split_html(html)

        self.assertEqual(body.strip(), HELLO_BODY.strip())
        self.assertEqual(modules["main"].strip(), HELLO_PY.strip())
        self.assertEqual(modules["util"].strip(), app.modules["util"].strip())
        self.assertEqual(sounds, app.sounds)
        self.assertEqual(images, app.images)

    def test_roundtrip_no_assets(self):
        app = pwe.App()
        html = app.build_html(HELLO_BODY, HELLO_PY)
        body, modules, sounds, images = pwe.App().split_html(html)
        self.assertEqual(body.strip(), HELLO_BODY.strip())
        self.assertEqual(modules["main"].strip(), HELLO_PY.strip())
        self.assertEqual(sounds, {})
        self.assertEqual(images, {})


class Assets(unittest.TestCase):
    """Sound/image management at the model level (the browser-free half of
    'load a sound or image'). The actual play/preview UI is covered by the
    Tier 2 tests ``test_load_and_play_sound`` / ``test_load_and_preview_image``.
    """

    def test_add_rename_delete(self):
        app = pwe.App()
        app.add_sound("laser", "data:audio/wav;base64,UklGRg==")
        app.add_image("hero", "data:image/png;base64,iVBORw0K")

        self.assertEqual(app.get_sound("laser"), "data:audio/wav;base64,UklGRg==")
        self.assertEqual(app.get_sound_names(), ["laser"])
        self.assertEqual(app.get_image("hero"), "data:image/png;base64,iVBORw0K")
        self.assertEqual(app.get_image_names(), ["hero"])

        # Adding under an existing name replaces it.
        app.add_sound("laser", "data:audio/wav;base64,QQ==")
        self.assertEqual(app.get_sound("laser"), "data:audio/wav;base64,QQ==")
        self.assertEqual(app.get_sound_names(), ["laser"])

        app.rename_sound("laser", "zap")
        self.assertEqual(app.get_sound_names(), ["zap"])
        self.assertIsNone(app.get_sound("laser"))

        app.delete_sound("zap")
        app.delete_image("hero")
        self.assertEqual(app.get_sound_names(), [])
        self.assertEqual(app.get_image_names(), [])

    def test_loaded_assets_survive_save_load(self):
        """A loaded sound/image must be embedded in the saved file and come
        back intact when that file is re-opened."""
        app = pwe.App()
        app.add_sound("laser", "data:audio/mpeg;base64,QUFBQQ==")
        app.add_image("bunny", "data:image/png;base64,Qk1Q")
        html = app.build_html(HELLO_BODY, HELLO_PY)

        _, _, sounds, images = pwe.App().split_html(html)
        self.assertEqual(sounds, {"laser": "data:audio/mpeg;base64,QUFBQQ=="})
        self.assertEqual(images, {"bunny": "data:image/png;base64,Qk1Q"})

    def _check_rename_collision(self, dialog_cls, add, names, get):
        """Renaming an asset onto an existing name must re-prompt, not accept
        the duplicate (which would trip rename_sound/rename_image's assert)."""
        app = pwe.App()
        add(app, "alpha", "data:x;base64,AAAA")
        add(app, "beta", "data:x;base64,BBBB")
        dialog = dialog_cls(app)
        with _stub_dialogs(typed=["beta", "gamma"]) as state:  # taken, then free
            asyncio.run(dialog.rename("alpha"))

        self.assertEqual(set(names(app)), {"beta", "gamma"})  # alpha -> gamma
        self.assertIsNone(get(app, "alpha"))
        self.assertTrue(
            any("already exists" in p.lower() for p in state["prompts"]),
            f"expected an inline duplicate-name message; saw {state['prompts']}",
        )

    def test_rename_sound_collision_reprompts(self):
        self._check_rename_collision(
            pwe.SoundsDialog,
            lambda app, name, url: app.add_sound(name, url),
            lambda app: app.get_sound_names(),
            lambda app, name: app.get_sound(name),
        )

    def test_rename_image_collision_reprompts(self):
        self._check_rename_collision(
            pwe.ImageDialog,
            lambda app, name, url: app.add_image(name, url),
            lambda app: app.get_image_names(),
            lambda app, name: app.get_image(name),
        )


class ModuleNameCollision(unittest.TestCase):
    """Regression tests for module name-collision handling.

    `load_asset`/`rename_asset` proceed only when `name_is_unused(name)` is
    True (the name is free). The module import/rename paths used to pass
    `lambda name: name in self.app.modules`, which is inverted: importing a
    file whose name matched an existing module was treated as a fresh name, so
    it skipped the overwrite prompt and silently called `import_module` (and
    rename then tripped `rename_module`'s assert). Separately, creating a new
    module skipped the uniqueness check entirely and hit `new_module`'s assert.
    """

    def test_module_name_is_unused_semantics(self):
        app = pwe.App()
        app.modules["util"] = "x = 1\n"
        ui = app.ui
        # Existing names are NOT free...
        self.assertFalse(ui._module_name_is_unused("util"))
        self.assertFalse(ui._module_name_is_unused("main"))
        # ...a new name is free.
        self.assertTrue(ui._module_name_is_unused("fresh"))

    def test_import_existing_name_prompts_overwrite(self):
        """Importing a file named like an existing module must show the
        overwrite prompt, not silently replace the module."""
        app = pwe.App()
        app.modules["util"] = "old = 1\n"
        imported = []

        async def _fake_import_module(name, file_handle, code):
            imported.append(name)

        app.import_module = _fake_import_module
        with _stub_dialogs(typed=["util"], picked_name="util.py") as state:
            asyncio.run(app.ui.on_import())

        self.assertTrue(
            any("already exists" in p.lower() for p in state["prompts"]),
            f"expected an overwrite prompt for the colliding name; saw {state['prompts']}",
        )
        self.assertEqual(imported, ["util"])

    def test_new_module_reprompts_on_duplicate(self):
        """Creating a module with an existing name must re-prompt inline, not
        replace the module or crash on new_module's assert."""
        app = pwe.App()
        app.modules["util"] = "x = 1\n"
        with _stub_dialogs(typed=["util", "fresh"]) as state:  # taken, then free
            asyncio.run(app.ui.on_new())

        self.assertEqual(app.modules["util"], "x = 1\n")  # untouched
        self.assertIn("fresh", app.modules)
        self.assertEqual(app.active_module, "fresh")
        self.assertTrue(
            any("already exists" in p.lower() for p in state["prompts"]),
            f"expected an inline duplicate-name message; saw {state['prompts']}",
        )

    def test_new_module_cancel_creates_nothing(self):
        app = pwe.App()
        before = dict(app.modules)
        with _stub_dialogs(events=["cancel"]):
            asyncio.run(app.ui.on_new())
        self.assertEqual(app.modules, before)
        self.assertEqual(app.active_module, "main")


class StandaloneExportShape(unittest.TestCase):
    """The export path must inline libraries as data: URLs (offline-ready).

    Uses tiny fake library bytes -- this test is about *shape*, not whether
    real Brython runs. The 'does it actually run offline' proof is the Tier 2
    test ``test_exported_file_runs_fully_offline``.
    """

    def test_bundled_libs_are_inlined(self):
        app = pwe.App()
        app.libraries["brython"] = "/*FAKE-BRYTHON*/ var brython=1;"
        app.libraries["brython_stdlib"] = "/*FAKE-STDLIB*/ var stdlib=1;"
        html = app.build_html(
            HELLO_BODY, HELLO_PY, libs_to_bundle=["brython", "brython_stdlib"]
        )
        # No network references at all.
        self.assertNotIn("https://", html)
        self.assertNotIn('src="http', html)
        # Libraries present, inlined as data: URLs.
        self.assertIn("data:text/javascript;base64,", html)
        decoded = _decode_data_url_scripts(html)
        joined = "\n".join(decoded)
        self.assertIn("FAKE-BRYTHON", joined)
        self.assertIn("FAKE-STDLIB", joined)
        # The brython shim that makes inlined brython find its path must be present.
        self.assertIn("__BRYTHON__.brython_path", html)


class BuildScripts(unittest.TestCase):
    """The pure-CPython scripts that assemble the editor distribution."""

    def test_examples_bundling(self):
        import examples as examples_mod  # on sys.path via import_pywebedit()

        out = os.path.join(HERE, "output", "_test_examples.js")
        os.makedirs(os.path.dirname(out), exist_ok=True)

        cwd = os.getcwd()
        try:
            os.chdir(REPO_ROOT)  # examples.py reads from ./examples
            with contextlib.redirect_stdout(io.StringIO()):  # silence its prints
                examples_mod.bundle_examples_to_javascript(out)
        finally:
            os.chdir(cwd)

        with open(out, encoding="utf-8") as f:
            js = f.read()
        self.assertTrue(js.startswith("window.EXAMPLES_DATA = "))

        data = json.loads(js[len("window.EXAMPLES_DATA = ") : -1])
        ids = {ex["id"]: ex for cat in data for ex in cat["examples"]}
        self.assertIn("hello", ids)
        decoded = base64.b64decode(ids["hello"]["content"]).decode("utf-8")
        self.assertIn("Hello, World!", decoded)

    def test_tagreplace(self):
        path = os.path.join(REPO_ROOT, "utils", "tagreplace.py")
        spec = importlib.util.spec_from_file_location("tagreplace", path)
        tagreplace = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tagreplace)

        with tempfile.NamedTemporaryFile(
            "w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write("<head><script>OLD</script></head>")
            tmp = f.name
        try:
            with contextlib.redirect_stdout(io.StringIO()):  # it prints by default
                result = tagreplace.replace_between_tags(
                    tmp, "<script>", "</script>", "NEW", in_place=False, output_file=None
                )
            self.assertIn("<script>NEW</script>", result)
        finally:
            os.unlink(tmp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
