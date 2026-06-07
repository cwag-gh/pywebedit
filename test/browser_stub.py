"""Minimal stand-in for Brython's ``browser`` package, so ``pywebedit.py`` can
be imported under plain CPython for logic testing.

``pywebedit.py`` is written in Python but *runs in the browser via Brython*:
its very first lines are ``from browser import ...``. None of that exists in
CPython. To unit-test the pure-Python parts of the app (HTML generation,
round-trip parsing, base64 encoding) without spinning up a browser, we install
lightweight fakes into ``sys.modules`` *before* importing ``pywebedit``.

The philosophy: fake the *minimum*. DOM/UI calls collapse into a permissive
"black-hole" object (``_Any``); we only add real behaviour where the module
would otherwise fail to import (the ``<=`` append operator and the dialog base
classes). The interesting logic under test -- ``App.build_html`` /
``App.split_html`` / ``encode_js_for_html`` and friends -- is plain Python that
needs none of this.
"""

import builtins
import os
import sys
import types


class _Any:
    """A permissive black-hole object.

    Any attribute access, call, or indexing yields another ``_Any``; Brython's
    DOM append (``parent <= child``) and ``+`` element-concatenation return an
    ``_Any``; iterating yields nothing. This lets ``App()``/``UI()`` construct
    against a fake DOM without us hand-modelling every widget method.
    """

    def __call__(self, *args, **kwargs):
        return _Any()

    def __getattr__(self, name):
        # Only invoked when normal lookup fails, so it won't shadow real dunders.
        return _Any()

    def __setattr__(self, name, value):
        pass

    def __getitem__(self, key):
        return _Any()

    def __setitem__(self, key, value):
        pass

    def __le__(self, other):  # Brython DOM append: parent <= child
        return self

    def __add__(self, other):  # Brython element concatenation: a + b
        return _Any()

    def __radd__(self, other):
        return _Any()

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False

    def __repr__(self):
        return "<browser_stub._Any>"


def install():
    """Install the fake ``browser`` package into ``sys.modules`` (idempotent)."""
    existing = sys.modules.get("browser")
    if isinstance(existing, types.ModuleType) and getattr(
        existing, "_pywebedit_stub", False
    ):
        return

    browser = types.ModuleType("browser")
    browser._pywebedit_stub = True
    browser.document = _Any()
    browser.window = _Any()
    browser.console = _Any()
    browser.html = _Any()
    browser.bind = _Any()
    browser.aio = _Any()

    # ``browser.widgets.dialog`` exposes classes that pywebedit *subclasses*
    # at import time, so these must be real classes -- not black-hole objects.
    class _StubDialog:
        def __init__(self, *args, **kwargs):
            self.panel = _Any()
            self.entry = _Any()
            self.value = ""

        def close(self, *args, **kwargs):
            pass

        def bind(self, *args, **kwargs):
            pass

    class InfoDialog(_StubDialog):
        pass

    class Dialog(_StubDialog):
        pass

    class EntryDialog(_StubDialog):
        pass

    widgets = types.ModuleType("browser.widgets")
    dialog = types.ModuleType("browser.widgets.dialog")
    dialog.InfoDialog = InfoDialog
    dialog.Dialog = Dialog
    dialog.EntryDialog = EntryDialog
    widgets.dialog = dialog
    browser.widgets = widgets

    sys.modules["browser"] = browser
    sys.modules["browser.widgets"] = widgets
    sys.modules["browser.widgets.dialog"] = dialog

    # Brython injects ``JavascriptError`` as a builtin; a few ``except`` clauses
    # reference it. Provide one so those code paths don't NameError if reached.
    if not hasattr(builtins, "JavascriptError"):
        builtins.JavascriptError = type("JavascriptError", (Exception,), {})


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def import_pywebedit():
    """Install the stub, then import and return the real ``pywebedit`` module."""
    install()
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    import pywebedit  # noqa: E402  (deferred on purpose -- needs the stub first)

    return pywebedit
