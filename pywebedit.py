# Main python code

import base64
from dataclasses import dataclass
from typing import Callable

from browser import document, window, bind, aio, console, html
from browser.widgets.dialog import InfoDialog, Dialog, EntryDialog


BRYTHON_VERSION = '3.13.1'
PYWEBEDIT_VERSION = '0.2.0'


INITIAL_HTML = """
<!-- Write HTML on this side -->
<h1 id='text'></h1>
""".strip()


INITIAL_PYTHON = """
# Write python on this side
from browser import document
document['text'].textContent='Hello, World!'
""".strip()


HELP = f"""
<div>
  <h3>&ltpywebedit&gt</h3>
  <p>In-browser python editing and running, allowing creation of
     standalone webpages that use python. </p>
  <p>Download the standalone version
     <a href="https://robotfantastic.org/pywebedit/pywebedit.zip">here</a>.
     Just unzip, then open pywebedit.html in your browser.</p>
</div>
<div>
  Keys:
  <ul>
    <li>Return: Accepts suggested completion</li>
    <li>Ctrl-f: Find / replace</li>
    <li>Ctrl-Alt-\\ (Cmd-Alt-\\ on MacOS): Indent selection - can fix indentation</li>
    <li>Ctrl-/: Toggle comments on line</li>
    <li>Shift-Alt-a: Toggle block comments on selection</li>
    <li>Tab: Indent line (press Esc then Tab to use default Tab functionality)</li>
    <li>Shift-Tab: Unindent line</li>
    <li>Shift-Ctrl-k (Shift-Cmd-k on MacOS): Delete line</li>
    <li>Shift-Ctrl-\\ (Shift-Cmd-\\ on MacOS): Move cursor to matching bracket or parenthesis</li>
    <li>Alt-j: Select previous python module</li>
    <li>Alt-l: Select next python module</li>
  </ul>
</div>

<div>
  Links:
  <ul>
    <li><a href="https://robotfantastic.org/pywebedit/pywebedit.zip">pywebedit offline distribution</a> (v{PYWEBEDIT_VERSION})</li>
    <li><a href="https://github.com/cwag-gh/pywebedit/">pywebedit source</a></li>
    <li><a href="https://www.brython.info/">Brython</a> (using v{BRYTHON_VERSION})</li>
    <li><a href="https://www.python.org/">Python</a></li>
    <li><a href="https://codemirror.net/">Codemirror</a> editor component (v6)</li>
  </ul>
</div>
""".strip()


def wrapscript(s):
    """Safely wrap string in script tags."""
    assert '>' in s
    return '<' + 'script' + s + '<' + '/script>'

# A little fix to get brython to load properly when it is embedded as a script element
SCRIPT_LOCAL_BRYTHON_SHIM = """
%script% type="text/javascript">
globalThis.__BRYTHON__ = {};
globalThis.__BRYTHON__.brython_path = document.location.href.substring(0, document.location.href.lastIndexOf('/') + 1);
%endscript%
"""

# Template for generated final page. Do not include script tags, which
# screws up the html in python in html. Use alternate replacement
# syntax (other than format()) to avoid syntax conflicts. Note the
# second level of indirection when defining the fallback script tags.
PAGE_TEMPLATE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">

%libraries%

%script% type="text/javascript">
function __brython_pre_then_code() {
  brython({debug:1, ids:["brythonpre"]});
}
%endscript%
</head>

<body onload="__brython_pre_then_code()">
%html_body%
%script% type="text/python" id="brythonpre">
from browser import document, window

import sys
class __ErrorReporter:
    def __init__(self):
        self.errdiv = None
    def write(self, msg):
        if self.errdiv is None:
            self.errdiv = document.createElement("div")
            self.errdiv.style = "white-space: pre-wrap; font-family: monospace; color:red"
            document.body.insertBefore(self.errdiv, document.body.firstChild)
        self.errdiv.textContent += ("\\n" + msg)
sys.stderr = __ErrorReporter()

# Load sound resouces
window.SOUNDS = %sounds%

# Load image resources
window.IMAGES = %images%

# Load modules - use runPythonSource as it is synchronous
for module in [%modules%]:
    __BRYTHON__.runPythonSource(document[module].text, module.replace('__pwe_', ''))

# Now run main code
window.brython({'debug': 1, 'ids': ["pythoncode"]})
%endscript%

%modulescripts%

%script% type="text/python" id="pythoncode">
%python_code%
%endscript%
</body>
</html>
""".strip()

MODULE_TEMPLATE = """
%script% type="text/python" id="%moduleid%">
%modulecode%
%endscript%
""".strip()


# Dict of name: javascript library info tuples (desc, var, url), where:
# - name is the name of the javascript library without the js
# - var is the name of a global variable that will have been
#   defined after the javascript library has loaded.
# TODO: add these as a rightclick menu
JSLIBS = {
    'brython': ('Core Brython functionality', '__BRYTHON__', f'https://cdn.jsdelivr.net/npm/brython@{BRYTHON_VERSION}/brython.min.js'),
    'brython_stdlib': ('Brython standard library', '__BRYTHON__.use_VFS', f'https://cdn.jsdelivr.net/npm/brython@{BRYTHON_VERSION}/brython_stdlib.js'),
    'pixi': ('Fast 2D WebGL renderer', 'PIXI', 'https://unpkg.com/pixi.js@8.9.2/dist/pixi.min.js'),
    'pixi-sound': ('Sound extension for pixi.js', 'PIXI.sound', 'https://unpkg.com/@pixi/sound@6.0.1/dist/pixi-sound.js'),
    'three': ('3D graphics library', 'THREE', 'https://cdnjs.cloudflare.com/ajax/libs/three.js/100/three.min.js'),
}


PYFILES = [('main', 'main'),
           (None, None),
           ('New python module', '__new'),
           ('Import existing module', '__import'),
           (None, None),
           ('Export this python module', '__export'),
           ('Rename this python module', '__rename'),
           ('Remove this python module', '__remove'),
           (None, None),
           ('Add sounds...', '__add_sounds'),
           ('Add images...', '__add_images')]


PICKER_ID = 'choosefile'

## General utilities

def strip_extension(filename):
    if '.' not in filename:
        return filename
    return filename[:filename.rindex('.')]


def extract_between(s, start_token, end_token):
    """Extracts the string between two tokens, exclusive.

    Raises error if token is not present.
    """
    i_start = s.index(start_token) + len(start_token)
    i_end = s.index(end_token, i_start)
    return s[i_start:i_end]


def parse_str_str_dict(s):
    """Parse a dict[str, str] encoded as a string back into a dict.
    """
    d = {}
    if not s or s.isspace():
        return d
    for row in s.split(',\n'):
        i_q0 = row.index("'", 0)
        i_q1 = row.index("'", i_q0+1)
        i_q2 = row.index("'", i_q1+1)
        i_q3 = row.index("'", i_q2+1)
        d[row[i_q0+1:i_q1]] = row[i_q2+1:i_q3]
    return d


def encode_js_for_html(js_content, chunk_size=1023):
    """
    Encode JavaScript content to base64 data URL and format as HTML script tag.

    Rationale:
    1. Encode to UTF-8 bytes first to properly handle unicode characters
    2. Process in chunks (multiple of 3) to work around Brython's b64encode limitations
    3. Base64 encode each chunk separately, strip intermediate padding, concatenate
    4. Wrap at 76 characters (RFC 2045 standard for base64 line length)
    5. Output as ready-to-use HTML script tag with data URL
    """
    # Convert unicode string to UTF-8 bytes
    utf8_bytes = js_content.encode('utf-8')

    # Ensure chunk_size is multiple of 3 for proper base64 encoding
    chunk_size = chunk_size - (chunk_size % 3)
    if chunk_size == 0:
        chunk_size = 3

    # Encode in chunks to avoid Brython b64encode bugs
    encoded_parts = []
    for i in range(0, len(utf8_bytes), chunk_size):
        chunk = utf8_bytes[i:i + chunk_size]
        encoded_chunk = base64.b64encode(chunk).decode('ascii')

        # Strip padding from intermediate chunks (we'll add it back at the end)
        if i + chunk_size < len(utf8_bytes):
            encoded_chunk = encoded_chunk.rstrip('=')

        encoded_parts.append(encoded_chunk)

    # Concatenate all encoded chunks
    encoded_str = ''.join(encoded_parts)

    # Manually wrap at 76 characters for readability
    col_wrap = 76
    wrapped_lines = []
    for i in range(0, len(encoded_str), col_wrap):
        wrapped_lines.append(encoded_str[i:i + col_wrap])

    # Format as HTML script tag with data URL
    script_tag = '<' + 'script' + ' src="data:text/javascript;base64,' + \
        '\n'.join(wrapped_lines) + '"' + '></' + 'script>'

    return script_tag


def urlname(url):
    return url.split('/')[-1]


def create_script_loader(libname):
    """Returns a script tag that loads the library, with a fallback to load a local copy."""
    url = JSLIBS[libname][2]
    var = JSLIBS[libname][1]
    jslibname = urlname(url)
    s = f'%script% type="text/javascript" src="{url}">%endscript%\n'
    s += f'%script%> typeof {var} === "undefined" && document.write("%script% src="{jslibname}">\\x3C/script>")%endscript%'
    return s


## Brython html utilities

def add_option(select, title, value):
    if title is None:
        select <= html.HR()
    else:
        option = html.OPTION(title)
        option.attrs['value'] = value
        select <= option


def msg(title, text, top=None, left=None):
    return InfoDialog(title, text, ok='Ok', top=top, left=left)


def err(text, title='Unfortunately...'):
    return msg(title, text)


def erropen():
    return err('This browser does not support opening and saving local files. Try Chrome.')


def inputdialog(title, prompt, onok, value=None):
    d = EntryDialog(title, prompt)
    if value is not None:
        d.entry.value = value

    @bind(d, 'entry')
    def entry(ev):
        value = d.value
        d.close()
        if value:
            onok(value)


async def pick_file_to_open(**file_picker_args):
    try:
        args = {'id': PICKER_ID} # Use same id between pickers to save folder
        args.update(file_picker_args)
        file_handles = await window.showOpenFilePicker(args)
        if len(file_handles) == 0:
            return None
    except AttributeError:
        erropen()
        return None
    except JavascriptError:
        # User cancelled
        return None
    return file_handles[0]


async def read_file_as_data_url(file_handle):
    file = await file_handle.getFile()  # Get the actual File object first
    reader = window.FileReader.new()
    reader.readAsDataURL(file)  # Pass the File object, not the handle
    event = await aio.event(reader, 'load', 'error')
    if event.type == 'error':
        return None
    return reader.result # the data_url


class AwaitableDialog(Dialog):
    """Dialog that can be awaited for both ok and cancel."""
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)

        # Listen for dialog_close on document and dispatch a cancel event
        # on this dialog when it matches this instance
        def on_dialog_close(evt):
            if evt.dialog == self:
                self.dispatchEvent(window.Event.new('cancel'))
                document.unbind('dialog_close', on_dialog_close)

        def on_ok_button(evt):
            self.dispatchEvent(window.Event.new('ok'))
            self.unbind('click', on_ok_button)

        document.bind('dialog_close', on_dialog_close)
        if hasattr(self, 'ok_button'):
            self.ok_button.bind('click', on_ok_button)


async def amsg(title, text, top=None, left=None):
    d = AwaitableDialog(title, ok_cancel=True)
    d.panel <= text
    event = await aio.event(d, 'ok', 'cancel')
    d.close()
    return event.type == 'ok'


class AwaitableEntryDialog(EntryDialog):
    """EntryDialog that can be awaited for both entry and cancel.

    Example:

    d = AwaitableEntryDialog('title', 'msg')
    event = await aio.event(d, 'entry', 'cancel')
    if event.type == 'entry':
        console.log(f'Got value {d.value}')
    """

    def __init__(self, title, message=None, **kwargs):
        super().__init__(title, message, **kwargs)

        # Listen for dialog_close on document and dispatch a cancel event
        # on this dialog when it matches this instance
        def on_dialog_close(evt):
            if evt.dialog == self:
                self.dispatchEvent(window.Event.new('cancel'))
                document.unbind('dialog_close', on_dialog_close)

        document.bind("dialog_close", on_dialog_close)


## UI workflow fragment utilities

async def rename_asset(initial_name: str,
                       asset_type: str,
                       name_is_valid: Callable[[str], str | None],
                       name_is_unused: Callable[[str], bool]) -> str | None:
    """Rename workflow. Ensures picked name is valid and unused."""
    errmsg = ''
    spacer = '<br><br>'
    name = initial_name
    while True:
        d = EntryDialog(f'Rename {asset_type} {initial_name}',
                        f'{errmsg}New name:')
        d.entry.value = name
        event = await aio.event(d, 'entry', 'cancel')
        name = d.value
        d.close()
        if event.type == 'cancel':
            return None

        errmsg = name_is_valid(name)
        if errmsg:
            errmsg = errmsg + spacer
            continue

        if name == initial_name:
            errmsg = f'{asset_type} is already named {name}. Choose a different name.'
        elif name_is_unused(name):
            break
        errmsg = f'Already exists {asset_type} named {name}.' + spacer
    return name


async def load_asset(asset_type: str,
                     name_is_valid: Callable[[str], str | None],
                     name_is_unused: Callable[[str], bool]):
    """Opens file for import. Runs through workflow checking name conflicts."""
    file_handle = await pick_file_to_open()
    if file_handle is None:
        return None, None
    asset_name = strip_extension(file_handle.name)
    while True:
        while True:
            errmsg = name_is_valid(asset_name)
            if errmsg is None:
                break
            d = AwaitableEntryDialog(f'Refer to this {asset_name} as...',
                                     f'{errmsg}<br><br>Choose a new name:')
            d.entry.value = asset_name
            event = await aio.event(d, 'entry', 'cancel')
            asset_name = d.value
            d.close()
            if event.type == 'cancel':
                return None, None

        if name_is_unused(asset_name):
            break  # Success, name is unique

        d = EntryDialog(
            f'{asset_type.capitalize()} {asset_name} already exists',
            f'Enter a new name, or just keep the same to overwrite the existing {asset_name}.'
            f'<br><br>Import {asset_type} as:')
        d.entry.value = asset_name
        old_name = asset_name
        event = await aio.event(d, 'entry', 'cancel')
        asset_name = d.value
        d.close()
        if event.type == 'cancel':
            return None, None

        if asset_name == old_name:
            break  # Success, user has decided to overwrite

    return asset_name, file_handle


async def confirm_remove_asset(name: str, asset_type: str) -> bool:
    d = AwaitableDialog("Confirm removal", ok_cancel=("Remove", "Cancel"))
    d.panel <= html.DIV(f"Are you sure you want to remove {asset_type} '{name}'?")

    event = await aio.event(d, 'ok', 'cancel')
    d.close()
    return event.type == 'ok'


@dataclass
class ViewInfo:
    """Holds the cursor and scroll state of an editor view."""
    scrolltop: int
    scrollleft: int
    cursor_anchor: int
    cursor_head: int


class UI:
    def __init__(self, app):
        self.app = app
        self.app_window = None
        self.html_editor = window.EditorView(
            {'parent': document['html_editor'],
             'extensions': [window.basicSetup,
                            window.html(),
                            window.indentUnit.of('    '),
                            window.keymap.of([window.indentWithTab])]})
        self.python_editor = window.EditorView(
            {'parent': document['python_editor'],
             'extensions': [
                 window.basicSetup,
                 window.python(),
                 window.indentUnit.of('    '),
                 window.keymap.of(
                     [window.indentWithTab,
                      {'key': 'Alt-j', 'preventDefault': True,
                       'run': lambda e: self.incr_module(-1)},
                      {'key': 'Alt-l', 'preventDefault': True,
                       'run': lambda e: self.incr_module(+1)}])]})

        self._init_examples()
        self._init_pyfiles()

        # Set up the events
        document['btnrun'].bind('click', self.on_run)
        document['btnopen'].bind('click', self.on_open_precheck)
        document['btnsave'].bind('click', lambda e: aio.run(self.on_save()))
        document['btnsaveas'].bind('click', lambda e: aio.run(self.on_save_as()))
        document['btnexport'].bind('click', self.export_dialog)
        document['examples'].bind('change', self.on_example_select)
        document['pyfiles'].bind('change', self.on_pyfiles_select)
        document['btnhelp'].bind('click', self.on_help)
        window.addEventListener('beforeunload', self._close_app_window)

    def _close_app_window(self, evt):
        return self.app_window.close() if self.app_window else None

    def _init_examples(self):
        select = document['examples']
        add_option(select, 'Load example...', '')
        # global variable window.EXAMPLES_DATA is defined in examples.js
        for category in window.EXAMPLES_DATA:
            group = html.OPTGROUP()
            group.attrs['label'] = category['category']
            for example in category['examples']:
                add_option(group, example['help'], example['id'])
            select <= group

    def _init_pyfiles(self):
        select = document['pyfiles']
        for title, value in PYFILES:
            add_option(select, title, value)

    def on_run(self, evt):
        # Pass through application layer first
        self.app.run(self.contents_html(), self.contents_python())

    def run_html_in_new_window(self, html):
        try:
            if self.app_window:
                self.app_window.close()
        except:
            # Weird error in Chrome when someone reloads the generated tab,
            # and we then can't access it
            pass

        self.app_window = window.open()
        self.app_window.document.write(html)
        self.app_window.document.close()

        # Download to a file - user has to click on it, but works
        # blob = window.Blob.new([build_html()], {'type': 'text/html' })
        # a = document.createElement('a')
        # a.href = window.URL.createObjectURL(blob)
        # a.download = 'generated.html'
        # a.click()

    def on_open_precheck(self, evt):
        self.warn_if_modified(onok=self.on_open())

    async def on_open(self):
        """Pick a file, then load it."""
        file_handle = await pick_file_to_open()
        if file_handle is None:
            return
        await self.app.open_file(file_handle)

    async def on_save(self, force_picker=False, libs_to_bundle=None):
        handle = self.app.file_handle
        if force_picker or not self.app.has_file():
            name = 'myprogram.html'
            if self.app.file_name is not None:
                name = self.app.file_name
            try:
                handle = await window.showSaveFilePicker({
                   'id': PICKER_ID, # Use same id between pickers to save folder
                   'suggestedName': name,
                   'types': [{'description': 'Text documents',
                              'accept': {'text/html': ['.html']}}]})
            except AttributeError:
                erropen()
                return
            except JavascriptError:
                # User cancelled
                return
        await self.app.save_file(handle, self.contents_html(),
                                 self.contents_python(), self.viewinfo_python(),
                                 libs_to_bundle=libs_to_bundle)

    async def on_save_as(self):
        await self.on_save(force_picker=True)

    def _check_valid_module_name(self, name):
        if len(name) > 20:
            return 'Module names must be no more than 20 letters.'
        elif name.startswith('__'):
            return 'Module names must not start with two underscores.'
        elif not name.replace('_', '').isalnum():
            return 'Module names must only include letters, numbers, and underscores.'
        return None

    def _check_newname(self, name):
        if self._check_valid_module_name(name) is None:
            self.app.new_module(name, self.contents_python(), self.viewinfo_python())

    async def on_rename(self):
        if self.app.active_module == 'main':
            err("Can't rename main module.")
            return
        name = await rename_asset(self.app.active_module,
                                  'module',
                                  self._check_valid_module_name,
                                  lambda name: name in self.app.modules)
        if name is not None:
            self.app.rename_module(name)

    async def on_import(self):
        name, file_handle = await load_asset(
            'module',
            self._check_valid_module_name,
            lambda name: name in self.app.modules)
        if not name:
            return
        await self.app.import_module(name, file_handle, self.contents_python())

    async def on_export(self):
        name = f'{self.app.active_module}.py'
        try:
            handle = await window.showSaveFilePicker({
               'id': PICKER_ID, # Use same id between pickers to save folder
               'suggestedName': name,
               'types': [{'description': 'Python files',
                          'accept': {'text/py': ['.py']}}]})
        except AttributeError:
            erropen()
            return
        except JavascriptError:
            # User cancelled
            return
        await self.app.export_module(handle, self.contents_python())

    def on_pyfiles_select(self, evt):
        module = evt.target.value
        if module.startswith('__'):
            self.set_active_module(self.app.active_module)
        if module == '__new':
            inputdialog('New module', 'Module name:', self._check_newname)
        elif module == '__import':
            aio.run(self.on_import())
        elif module == '__export':
            aio.run(self.on_export())
        elif module == '__rename':
            aio.run(self.on_rename())
        elif module == '__remove':
            self.on_remove()
        elif module == '__add_sounds':
            self.on_add_sounds()
        elif module == '__add_images':
            self.on_add_images()
        else:
            self.app.select_module(module, self.contents_python(), self.viewinfo_python())

    def on_add_sounds(self):
        """Show the add sounds dialog."""
        # Store reference to the dialog so we can update it
        self.sounds_dialog = SoundsDialog(self.app, top=100, left=200)

    def update_sound_dialog(self):
        """Update the sound dialog if it's currently open."""
        if hasattr(self, 'sounds_dialog') and self.sounds_dialog:
            self.sounds_dialog.populate_table()

    def update_image_dialog(self):
        """Update the image dialog if it's currently open."""
        if hasattr(self, 'images_dialog') and self.images_dialog:
            self.images_dialog.populate_table()

    def on_add_images(self):
        """Show a dialog with a table of already included images, and a button to add more."""
        self.images_dialog = ImageDialog(self.app, top=100, left=200)

    def _current_module_index(self):
        modnames = list(self.app.modules.keys())
        i_name = modnames.index(self.app.active_module)
        return i_name

    def incr_module(self, incr: int):
        if len(self.app.modules) <= 1:
            return
        i_next = (self._current_module_index() + incr) % len(self.app.modules)
        modnames = list(self.app.modules.keys())
        self.app.select_module(modnames[i_next], self.contents_python(),
                               self.viewinfo_python())

    def on_example_select(self, evt):
        # Since we really use this as a menu, automatically return to first choice.
        # Don't want to have to deal with situation where an example has been
        # modified - do we change the example choice or not?
        self.warn_if_modified(onok=self.app.load_example(evt.target.value))
        self.set_example_choice('')

    def on_help(self, evt):
        return msg('Help', HELP, top=100, left=200)

    def warn_if_modified(self, onok):
        if self.app.anything_modified(self.contents_html(), self.contents_python()):
            d = Dialog('Warning...', ok_cancel=('Proceed', 'Cancel'))
            d.panel <= html.DIV('Code changes will be lost. Proceed anyway? '
                                'Or, cancel (so you can then save first)?')

            @bind(d.ok_button, 'click')
            def ok(_):
                aio.run(onok)
                d.close()
        else:
            aio.run(onok)

    def show_save_on_run_dialog(self, save_on_run: bool):
        """Shows a save dialog with options for 'Save on run' and 'Don't show again'."""
        d = Dialog("Save on run", ok_cancel=True, top=100, left=200)

        # Create container for checkbox elements
        container = html.DIV(style="margin: 10px 0")

        # Create first checkbox for "Save on run?"
        save_checkbox_div = html.DIV(style="margin-bottom: 10px")
        save_checkbox = html.INPUT(type="checkbox", id="save_on_run_checkbox")
        save_checkbox.checked = save_on_run
        save_checkbox_label = html.LABEL("Automatically save when run?", style="margin-left: 5px")
        save_checkbox_label.attrs["for"] = "save_on_run_checkbox"
        save_checkbox_div <= save_checkbox + save_checkbox_label

        # Create second checkbox for "Don't show this again"
        show_checkbox_div = html.DIV()
        show_checkbox = html.INPUT(type="checkbox", id="dont_show_checkbox")
        show_checkbox.checked = True
        show_checkbox_label = html.LABEL("Don't show this again", style="margin-left: 5px")
        show_checkbox_label.attrs["for"] = "dont_show_checkbox"
        show_checkbox_div <= show_checkbox + show_checkbox_label

        # Add both checkbox divs to the container
        container <= save_checkbox_div + show_checkbox_div

        # Add the container to the dialog panel
        d.panel <= container

        # Define event handler for OK button
        @bind(d.ok_button, "click")
        def ok(evt):
            save_on_run = save_checkbox.checked
            dont_show_again = show_checkbox.checked
            d.close()

            # Update app settings
            self.app.set_save_on_run(save_on_run, dont_show_again)

    def contents_html(self):
        return self.html_editor.state.doc.toString()

    def contents_python(self):
        return self.python_editor.state.doc.toString().replace('\t', '    ')

    def viewinfo_python(self) -> ViewInfo:
        return ViewInfo(scrolltop =self.python_editor.scrollDOM.scrollTop,
                        scrollleft=self.python_editor.scrollDOM.scrollLeft,
                        cursor_anchor=self.python_editor.state.selection.main.anchor,
                        cursor_head=self.python_editor.state.selection.main.head)

    def set_loaded_file(self, file_name):
        document.getElementById('filename').innerHTML = f'&lt;pywebedit&gt; {file_name}'
        document.title = f'<pywebedit> {file_name}'

    def set_contents_html(self, code):
        self.html_editor.dispatch({'changes': {'from': 0,
                                               'to': self.html_editor.state.doc.length,
                                               'insert': code}})

    def set_contents_python(self, code, viewinfo=None):
        transaction = {'changes': {'from': 0,
                                   'to': self.python_editor.state.doc.length,
                                   'insert': code}}
        if viewinfo is not None:
            transaction['selection'] = {'anchor': viewinfo.cursor_anchor,
                                        'head': viewinfo.cursor_head}
        self.python_editor.dispatch(transaction)

        if viewinfo is not None:
              self.python_editor.scrollDOM.scrollTop = viewinfo.scrolltop
              self.python_editor.scrollDOM.scrollLeft = viewinfo.scrollleft

    def set_example_choice(self, value):
        document['examples'].value = value

    def set_active_module(self, module_name):
        document['pyfiles'].value = module_name

    def set_module_list(self, names):
        select = document['pyfiles']
        select.innerHTML = ''  # This clears the selection box
        for name in names:
            add_option(select, name, name)
        # Don't add the remove option if there is only one
        pyfiles = PYFILES[1:]
        if len(self.app.modules) == 1:
            pyfiles = [(title, val) for title, val in pyfiles if val != '__remove']
        for title, value in pyfiles:
            add_option(select, title, value)

    def set_focus_python(self):
        self.python_editor.focus()

    def on_remove(self):
        d = Dialog('Warning...', ok_cancel=('Proceed', 'Cancel'))
        d.panel <= html.DIV(f'Proceed with removing module {self.app.active_module}? '
                            'Non-exported changes will be lost.')

        @bind(d.ok_button, 'click')
        def ok(_):
            d.close()
            self.app.remove_module()

    def export_dialog(self, evt):
        "Display a dialog with checkboxes for selecting JavaScript libraries to include in the export."
        d = Dialog("Export HTML with bundled libraries", ok_cancel=("Export", "Cancel"), top=100, left=200)
        container = html.DIV(style="max-height: 500px; overflow-y: auto;")
        container <= html.P("Select which JavaScript libraries to bundle in your exported file.")
        container <= html.P("If you bundle everything, then your file can run completely offline.")
        container <= html.P("If you are running this exporter offline, "
                            "you will need to manually find the selected libraries on your computer.",
                             style="margin-bottom: 15px;")

        # TODO: scan current code and see if any of the library names exist; then use those
        # to add the check

        # Dictionary to keep track of checkboxes
        checkboxes = {}

        for lib_name in JSLIBS:
            desc, globalvar, url = JSLIBS[lib_name]

            lib_div = html.DIV(style="margin-bottom: 10px; display: flex; align-items: center;")

            checkbox = html.INPUT(type="checkbox", id=f"lib_{lib_name.replace('.', '_')}")
            # TODO: remember the ones that have been checked

            label_text = f"{lib_name} - {desc}"
            label = html.LABEL(label_text, style="margin-left: 8px; flex: 1;")
            label.attrs["for"] = checkbox.id

            lib_div <= checkbox + label
            container <= lib_div

            checkboxes[lib_name] = checkbox             # Store the checkbox reference

        # Add the container to the dialog
        d.panel <= container

        # Handle the OK button click
        @bind(d.ok_button, "click")
        def ok_click(evt):
            # Get the list of selected libraries
            selected_libs = [lib_name for lib_name, checkbox in checkboxes.items()
                             if checkbox.checked]
            d.close()
            aio.run(self.retrieve_libraries_and_export_html(selected_libs))

    async def retrieve_libraries_and_export_html(self, libs_to_bundle):
        """Make sure libraries are cached, then export."""
        # TODO: try to get all the libraries in parallel
        for libname in libs_to_bundle:
            if not await self.app.fetchlib(libname):
                # Was not able to get it through internet access;
                # need to get it through direct loading.
                # TODO: change title to find file.
                _, _, url = JSLIBS[libname]
                filename = url[(url.rfind('/')+1):]
                ok = await amsg('Info', f'Unable to load {filename} from internet. '
                                f'Opening file browser to find local copy of {filename}.')
                if not ok:
                    msg('Info', 'Cancelling HTML export')
                    return
                file_handle_of_lib = await pick_file_to_open(
                    suggestedName=filename,
                    types=[{'description': 'JavaScript files',
                            'accept': {'text/js': ['.js']}}])
                if file_handle_of_lib is None:
                    msg('Info', 'Cancelling HTML export')
                    return
                await self.app.fileloadlib(libname, file_handle_of_lib) # This should succeed
        await self.on_save(force_picker=True, libs_to_bundle=libs_to_bundle)


class AssetDialog(Dialog):
    """Dialog for managing assets (sounds, images).

    Shows a list of assets as rows in a table. For each asset in the row, the user can
    perform several actions (delete, rename, etc).

    Asset size is shown in the row, in kB, as well as other asset specific data.
    """
    def __init__(self, app, title, top=100, left=200):
        super().__init__(title, ok_cancel=False, top=top, left=left)
        self.app = app
        self.main_table = html.TABLE()
        self.init_ui()
        self.populate_table()

    def init_ui(self):
        """Initialize the dialog UI with a table for assets and an add button."""
        container = html.DIV(style="width: 600px; max-height: 550px; overflow-y: auto;")

        # Add explanation at the top
        div_help = html.DIV(self.helptext(), style="margin-bottom: 10px;")
        container.appendChild(div_help)

        # Create table for sounds
        self.main_table = html.TABLE(style="width: 100%; border-collapse: collapse;")
        rowtext  = html.TH("Name", style="text-align: left;")
        rowtext += html.TH("Size", style="text-align: right;")
        for col in self.additional_columns():
            rowtext += html.TH(col, style="text-align: right;")
        rowtext += html.TH("Actions", style="text-align: center;")
        self.main_table.appendChild(html.TR(rowtext))
        container.appendChild(self.main_table)

        # Add button at the bottom
        add_button = html.BUTTON("Add " + self.asset_type(), style="margin-top: 10px;")
        add_button.bind("click", lambda evt: aio.run(self.add()))
        container.appendChild(add_button)

        self.panel <= container

    def clear_table(self):
        """Clear all rows except for header row."""
        if self.main_table and len(self.main_table.childNodes) > 1:
            while len(self.main_table.childNodes) > 1:
                self.main_table.removeChild(self.main_table.lastChild)

    def populate_table(self):
        """Fill the table with assets."""
        self.clear_table()

        for name in self.names():
            row = html.TR(style="border-bottom: 1px solid #ddd;")
            row <= self.row_cells(name)
            self.main_table.appendChild(row)

    def cell(self, contents, align=None):
        alignstr = '' if align is None else f' text-align: {align}'
        return html.TD(contents, style=f"padding: 5px;{alignstr}")

    def size_cell(self, data_url):
        # Calculate size in kB
        # Remove the data:audio/* prefix to get the raw base64
        base64_data = data_url.split(',')[1]
        size_kb = round(len(base64_data) * 3 / 4 / 1024, 1)  # Approximate size in kB
        return self.cell(f'{size_kb} kB', align='right')

    def row_buttons(self, name):
        rename_button = html.BUTTON("✏️", style="margin-right: 5px;")
        delete_button = html.BUTTON("🗑️")

        # Add tooltips
        rename_button.title = f"Rename {self.asset_type()}"
        delete_button.title = f"Delete {self.asset_type()}"

        rename_button.bind('click', lambda evt, n=name: aio.run(self.rename(n)))
        delete_button.bind('click', lambda evt, n=name: aio.run(self.delete(n)))
        return rename_button + delete_button

    def check_valid_asset_name(self, name):
        if len(name) < 1:
            return 'Name cannot be empty'
        if len(name) > 32:
            return 'Name must be 32 characters or fewer'
        return None

    async def rename(self, name):
        """Show a dialog to rename an asset."""
        newname = await rename_asset(name, self.asset_type(),
                                     self.check_valid_asset_name,
                                     self.check_name_is_unused)
        if newname is not None:
            self.on_rename(name, newname)

    async def delete(self, name):
        if await confirm_remove_asset(name, self.asset_type()):
            self.on_delete(name)

    async def add(self):
        """Load a new asset from a file."""
        name, file_handle = await load_asset(self.asset_type(),
                                             self.check_valid_asset_name,
                                             self.check_name_is_unused)
        if name is not None:
            await self.on_add(name, file_handle)


class SoundsDialog(AssetDialog):
    """Dialog for managing sounds.

    For each sound in the row, the user can:
    - Play the sound
    - Delete the sound
    - Rename the sound

    The duration in seconds is also shown, calculated from metadata
    and is dynamically updated after the dialog is opened.
    """
    def __init__(self, app, top=100, left=200):
        super().__init__(app, 'Manage sounds', top=top, left=left)
        self.durations = {}  # Cache for sound durations
        self.populate_table()

    def asset_type(self):
        return 'sound'

    def helptext(self):
        return 'Sounds added here can be accessed in window.SOUNDS in your program.'

    def names(self):
        return self.app.get_sound_names()

    def additional_columns(self) -> list[str]:
        return ['Duration']

    def check_name_is_unused(self, name):
        return name not in self.app.sounds

    def on_rename(self, name, new_name):
        self.app.rename_sound(name, new_name)

    def on_delete(self, name):
        self.app.delete_sound(name)

    async def on_add(self, name, file_handle):
        data_url = await read_file_as_data_url(file_handle)
        if data_url is not None:
            self.app.add_sound(name, data_url)

    def row_cells(self, name):
        data_url = self.app.get_sound(name)

        name_cell = self.cell(name)
        size_cell = self.size_cell(data_url)
        duration_cell = self.cell('...', align='right')
        actions_cell = self.cell('', align='center')
        play_button = html.BUTTON("▶", style="margin-right: 5px;")
        play_button.title = "Play sound"
        play_button.bind("click", lambda evt, n=name: self.play_sound(n))

        actions_cell <= play_button + self.row_buttons(name)

        # Calculate duration asynchronously
        self.load_duration(name, data_url, duration_cell)

        return name_cell + size_cell + duration_cell + actions_cell

    def load_duration(self, name, data_url, duration_cell):
        """Load the duration of a sound and update the cell."""
        audio = window.Audio.new(data_url)

        def on_loaded(evt):
            duration = round(audio.duration, 1)
            self.durations[name] = duration
            duration_cell.textContent = f'{duration}s'

        def on_error(evt):
            duration_cell.textContent = 'Error'
            console.log(f'Error loading duration for {name}')

        audio.bind('loadedmetadata', on_loaded)
        audio.bind('error', on_error)

    def play_sound(self, name):
        """Play a sound."""
        audio = window.Audio.new(self.app.get_sound(name))
        try:
            audio.play()
        except Exception as e:
            console.log(f'Error playing sound {name}: {e}')


class ImageDialog(AssetDialog):
    """Dialog for managing images.

    For each image in the row, the user can:
    - See a thumbnail
    - Open in an interactive viewer
    - Delete the image
    - Rename the image

    The sizeis also shown, calculated from metadata
    and is dynamically updated after the image is loaded.
    """
    def __init__(self, app, top=100, left=200):
        super().__init__(app, 'Manage images', top=top, left=left)
        self.populate_table()

    def asset_type(self):
        return 'image'

    def helptext(self):
        return 'Images added here can be accessed in window.IMAGES in your program.'

    def names(self):
        return self.app.get_image_names()

    def additional_columns(self) -> list[str]:
        return ['Image size', 'Thumbnail']

    def check_name_is_unused(self, name):
        return name not in self.app.images

    def on_rename(self, name, new_name):
        self.app.rename_image(name, new_name)

    def on_delete(self, name):
        self.app.delete_image(name)

    async def on_add(self, name, file_handle):
        data_url = await read_file_as_data_url(file_handle)
        if data_url is not None:
            self.app.add_image(name, data_url)

    def row_cells(self, name):
        data_url = self.app.get_image(name)

        name_cell = self.cell(name)
        size_cell = self.size_cell(data_url)
        image_size_cell = self.cell('...', align='right')
        thumb_cell = self.cell('', align='right')
        thumb = html.IMG(
            src=data_url,
            style='cursor: pointer; width: 50px; height: 50px; object-fit: cover;')
        thumb.title = "View image"
        thumb_cell <= thumb
        thumb.bind('click', lambda e, n=name: self.open_viewer(n))
        actions_cell = self.cell('', align='center')
        actions_cell <= self.row_buttons(name)

        # Calculate image size asynchronously
        self.load_image_size(name, data_url, image_size_cell)

        return name_cell + size_cell + image_size_cell + thumb_cell + actions_cell

    def load_image_size(self, name, data_url, cell):
        """Load and display the dimensions of an image.

        Args:
            name: The image name
            data_url: The data URL of the image
            cell: The table cell to update with the dimensions
        """
        # Create a temporary image to get dimensions
        img = html.IMG(src=data_url)

        def on_load(evt):
            # Get dimensions
            width = img.naturalWidth
            height = img.naturalHeight

            # Format dimensions and update cell
            dimensions = f"{width}×{height}px"
            cell.textContent = dimensions

        def on_error(evt):
            cell.textContent = "Error"
            console.log(f"Error loading image dimensions for {name}")

        # Set up event handlers
        img.bind("load", on_load)
        img.bind("error", on_error)

    def open_viewer(self, name):
        """Open the image in the image viewer dialog."""
        ImageViewDialog(self.app, name)


class ImageViewDialog(Dialog):
    """Interactive image viewer dialog with zoom, pan, and pixel info features.

    Allows viewing images with:
    - Zoom in/out with mouse wheel or buttons
    - Pan by dragging
    - Display current cursor position in pixels
    - Show color at cursor position
    - Navigate between images with next/prev buttons
    """
    def __init__(self, app, image_name, top=50, left=50):
        self.app = app
        self.image_name = image_name
        self.image_url = app.get_image(image_name)
        self.zoom_scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.image_width = 0
        self.image_height = 0
        self.names = app.get_image_names()
        self.current_index = self.names.index(image_name)
        self.show_checkerboard = True  # Default to showing checkerboard
        self.hidden_canvas = None  # Will store original image for pixel sampling
        self.original_image_data = None  # Will store unscaled pixel data

        # Create a temporary image to get dimensions
        temp_img = html.IMG(src=self.image_url)

        def on_img_load(evt):
            self.image_width = temp_img.naturalWidth
            self.image_height = temp_img.naturalHeight
            self.update_title()

        temp_img.bind('load', on_img_load)

        # Initialize dialog but don't use any title update mechanism yet
        super().__init__(f"Image: {image_name}", ok_cancel=False, top=top, left=left, can_close=True)

        # Ensure the close button exists
        if not hasattr(self, 'close_button'):
            self.close_button = html.SPAN("&times;", Class="brython-dialog-close")
            self.title_bar <= self.close_button
            self.close_button.bind("click", self.close)

        self.init_ui()

    def update_title(self):
        """Update the dialog title with image name and dimensions."""
        if self.image_width and self.image_height:
            new_title = f"Image: {self.image_name} ({self.image_width}×{self.image_height})"
            # Update the text content of the title bar's first child (the title span)
            # but preserve the close button
            if hasattr(self, "title_bar") and self.title_bar.childNodes:
                self.title_bar.childNodes[0].textContent = new_title

    def init_ui(self):
        """Initialize the viewer interface with canvas and controls."""
        # Main container
        container = html.DIV(style="display: flex; flex-direction: column; gap: 10px; width: 900px; height: 600px;")

        # Controls bar
        controls = html.DIV(style="display: flex; align-items: center; gap: 10px; padding: 5px;")

        # Zoom controls
        zoom_out = html.BUTTON("🔍-", style="font-size: 14px;")
        zoom_in = html.BUTTON("🔍+", style="font-size: 14px;")
        reset_zoom = html.BUTTON("Reset View", style="margin-left: 10px;")

        zoom_out.bind("click", lambda evt: self.adjust_zoom(0.8))
        zoom_in.bind("click", lambda evt: self.adjust_zoom(1.2))
        reset_zoom.bind("click", lambda evt: self.reset_view())

        # Checkerboard toggle
        checker_div = html.DIV(style="display: flex; align-items: center; margin-left: 15px;")
        self.checker_checkbox = html.INPUT(type="checkbox", id="checker_toggle")
        self.checker_checkbox.checked = self.show_checkerboard
        checker_label = html.LABEL("Transparency grid", style="margin-left: 5px; font-size: 14px;")
        checker_label.attrs["for"] = "checker_toggle"
        checker_div <= self.checker_checkbox + checker_label

        self.checker_checkbox.bind("change", self.toggle_checkerboard)

        # Position and color info display
        self.info_display = html.SPAN("Position: - Color: -",
                                      style="margin-left: auto; font-family: monospace;")

        # Navigation buttons
        prev_btn = html.BUTTON("◀ Previous")
        next_btn = html.BUTTON("Next ▶")

        prev_btn.bind("click", lambda evt: self.navigate_images(-1))
        next_btn.bind("click", lambda evt: self.navigate_images(1))

        # Add all controls
        controls <= zoom_out + zoom_in + reset_zoom + checker_div + self.info_display + prev_btn + next_btn

        # Canvas container with border - use all remaining vertical space
        canvas_container = html.DIV(
            style="flex: 1; overflow: hidden; border: 1px solid #ccc; position: relative; background-color: #f0f0f0;")

        # Add components to container
        container <= controls + canvas_container

        # Add container to dialog
        self.panel <= container

        # Create the canvases after container is added to get proper sizing
        def setup_canvas():
            # Get the actual container height to properly size the canvas
            container_height = canvas_container.offsetHeight

            # Create canvas for image display
            self.canvas = html.CANVAS(width=900, height=container_height,
                                    style="cursor: crosshair; display: block;")
            canvas_container <= self.canvas

            # Create hidden canvas for accurate pixel reading
            self.hidden_canvas = html.CANVAS(width=900, height=container_height,
                                           style="display: none;")
            canvas_container <= self.hidden_canvas

            # Explicitly set title attribute to empty to disable tooltip
            self.canvas.title = ""

            # Add event listeners for canvas
            self.canvas.bind("wheel", self.on_wheel)
            self.canvas.bind("mousedown", self.on_mouse_down)
            self.canvas.bind("mousemove", self.on_mouse_move)
            self.canvas.bind("mouseup", self.on_mouse_up)
            self.canvas.bind("mouseleave", self.on_mouse_up)

            # Render the image
            self.load_image()

        # Slight delay to ensure DOM is updated and we can get accurate container size
        window.setTimeout(setup_canvas, 0)

    def load_image(self):
        """Load the current image and render it to the canvas."""
        img = html.IMG(src=self.image_url)
        img.title = ""  # Prevent tooltip

        def on_image_load(evt):
            self.image_width = img.naturalWidth
            self.image_height = img.naturalHeight

            # Create a hidden canvas at the native image size for accurate pixel reading
            self.prepare_image_data(img)

            self.update_title()
            self.render()

        img.bind("load", on_image_load)

    def prepare_image_data(self, img):
        """Prepare original unscaled image data for accurate pixel reading."""
        if not img:
            return

        # Create a canvas at native image size
        temp_canvas = html.CANVAS(width=img.naturalWidth, height=img.naturalHeight)
        temp_ctx = temp_canvas.getContext("2d", {"willReadFrequently": True})

        # Disable image smoothing
        temp_ctx.imageSmoothingEnabled = False

        # Draw the image at its natural size (1:1 pixels)
        temp_ctx.drawImage(img, 0, 0)

        # Store the entire image data for direct pixel access
        self.original_image_data = temp_ctx.getImageData(0, 0, img.naturalWidth, img.naturalHeight)

    def draw_to_hidden_canvas(self):
        """Draw only the image to a hidden canvas for display purposes."""
        if self.hidden_canvas is None:
            return

        ctx = self.hidden_canvas.getContext("2d", {"willReadFrequently": True})

        # Clear canvas
        ctx.clearRect(0, 0, self.hidden_canvas.width, self.hidden_canvas.height)

        # Disable image smoothing for crisp pixels
        ctx.imageSmoothingEnabled = False

        # Draw image with same transformations as main canvas
        ctx.save()

        # Move to center of canvas as origin
        ctx.translate(self.hidden_canvas.width / 2, self.hidden_canvas.height / 2)

        # Apply scale
        ctx.scale(self.zoom_scale, self.zoom_scale)

        # Apply pan offset
        ctx.translate(self.offset_x, self.offset_y)

        # Draw the image centered (no checkerboard)
        img = html.IMG(src=self.image_url)
        ctx.drawImage(img, -img.naturalWidth / 2, -img.naturalHeight / 2)

        ctx.restore()

    def get_exact_pixel(self, img_x, img_y):
        """Get pixel data directly from the original image data.

        This bypasses any scaling or interpolation for exact pixel values.

        Args:
            img_x, img_y: Integer pixel coordinates in the original image

        Returns:
            Tuple of (r, g, b, a) values for the pixel, or None if out of bounds
        """
        if not self.original_image_data:
            return None

        if img_x < 0 or img_x >= self.image_width or img_y < 0 or img_y >= self.image_height:
            return None

        # Calculate the index in the flat pixel array (each pixel is 4 values: r,g,b,a)
        idx = (img_y * self.image_width + img_x) * 4
        data = self.original_image_data.data

        if idx + 3 < len(data):
            return (data[idx], data[idx + 1], data[idx + 2], data[idx + 3])
        return None

    def render(self):
        """Render the image on the canvas with current scale and offset."""
        # Get canvas context
        ctx = self.canvas.getContext("2d", {"willReadFrequently": True})

        # Clear canvas
        ctx.clearRect(0, 0, self.canvas.width, self.canvas.height)

        # Disable image smoothing for crisp pixels when zoomed
        ctx.imageSmoothingEnabled = False

        # Draw image with transformations
        ctx.save()

        # Move to center of canvas as origin
        ctx.translate(self.canvas.width / 2, self.canvas.height / 2)

        # Apply scale
        ctx.scale(self.zoom_scale, self.zoom_scale)

        # Apply pan offset
        ctx.translate(self.offset_x, self.offset_y)

        # First draw checkerboard pattern just in image area if enabled
        if self.show_checkerboard and self.image_width and self.image_height:
            self.draw_transparency_checkerboard(ctx, -self.image_width / 2, -self.image_height / 2,
                                             self.image_width, self.image_height)

        # Draw the image centered
        img = html.IMG(src=self.image_url)
        # Prevent tooltip on image
        img.title = ""
        ctx.drawImage(img, -img.naturalWidth / 2, -img.naturalHeight / 2)

        ctx.restore()

        # Update the hidden canvas with the same view
        self.draw_to_hidden_canvas()

    def draw_transparency_checkerboard(self, ctx, x, y, width, height):
        """Draw a checkerboard pattern to indicate transparent areas.

        Args:
            ctx: Canvas context
            x, y: Top-left coordinates to start drawing
            width, height: Dimensions of the area to fill with checkerboard
        """
        # Save current transform state
        ctx.save()

        # Define checker size that scales inversely with zoom for consistent appearance
        base_checker_size = 8
        checker_size = base_checker_size / self.zoom_scale
        checker_size = max(4, min(checker_size, 16))  # Keep size reasonable

        # Calculate how many checkers we need
        cols = window.Math.ceil(width / checker_size)
        rows = window.Math.ceil(height / checker_size)

        # Define checker colors
        color1 = "#ffffff"  # White
        color2 = "#cccccc"  # Light gray

        # Draw checkerboard pattern only in image area
        for row in range(rows):
            for col in range(cols):
                # Alternate colors
                if (row + col) % 2 == 0:
                    ctx.fillStyle = color1
                else:
                    ctx.fillStyle = color2

                # Draw square at correct position
                ctx.fillRect(
                    x + col * checker_size,
                    y + row * checker_size,
                    checker_size,
                    checker_size
                )

        # Restore original transform
        ctx.restore()

    def adjust_zoom(self, factor):
        """Adjust the zoom by multiplying the current scale."""
        old_scale = self.zoom_scale
        self.zoom_scale *= factor

        # Limit zoom range
        self.zoom_scale = max(0.1, min(10, self.zoom_scale))

        # Render with new scale
        self.render()

    def reset_view(self):
        """Reset to original view."""
        self.zoom_scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.render()

    def on_wheel(self, evt):
        """Handle mouse wheel for zooming."""
        evt.preventDefault()

        # Determine zoom direction
        if evt.deltaY < 0:
            # Zoom in
            self.adjust_zoom(1.1)
        else:
            # Zoom out
            self.adjust_zoom(0.9)

    def on_mouse_down(self, evt):
        """Start dragging for panning."""
        self.dragging = True
        self.drag_start_x = evt.clientX
        self.drag_start_y = evt.clientY

        # Change cursor to grabbing
        self.canvas.style.cursor = "grabbing"

    def on_mouse_up(self, evt):
        """End dragging."""
        self.dragging = False

        # Restore cursor to crosshair
        self.canvas.style.cursor = "crosshair"

    def on_mouse_move(self, evt):
        """Handle mouse movement for panning and position tracking."""
        rect = self.canvas.getBoundingClientRect()
        canvas_x = evt.clientX - rect.left
        canvas_y = evt.clientY - rect.top

        if self.dragging:
            # Calculate drag distance
            dx = (evt.clientX - self.drag_start_x) / self.zoom_scale
            dy = (evt.clientY - self.drag_start_y) / self.zoom_scale

            # Update offset
            self.offset_x += dx
            self.offset_y += dy

            # Update drag start
            self.drag_start_x = evt.clientX
            self.drag_start_y = evt.clientY

            # Render with new offset
            self.render()
        else:
            # Calculate image coordinates
            center_x = self.canvas.width / 2
            center_y = self.canvas.height / 2

            # Calculate the pixel coordinates in the original image
            img_x = window.Math.round((canvas_x - center_x) / self.zoom_scale - self.offset_x + self.image_width / 2)
            img_y = window.Math.round((canvas_y - center_y) / self.zoom_scale - self.offset_y + self.image_height / 2)

            # Update position display if within image bounds
            if 0 <= img_x < self.image_width and 0 <= img_y < self.image_height:
                # Get precise pixel color directly from original image data
                pixel = self.get_exact_pixel(img_x, img_y)

                if pixel:
                    r, g, b, a = pixel

                    # Format as hex with alpha percentage
                    color_hex = f"#{r:02x}{g:02x}{b:02x}"
                    alpha_percent = window.Math.round(a / 255 * 100)

                    # Update info display with alpha
                    self.info_display.textContent = f"Pos: {img_x},{img_y} | Color: {color_hex} | Alpha: {alpha_percent}%"
                else:
                    self.info_display.textContent = f"Pos: {img_x},{img_y} | Color: [no data]"
            else:
                self.info_display.textContent = "Pos: outside image | Color: -"

    def navigate_images(self, direction):
        """Navigate to next or previous image."""
        # Calculate new index with wrap-around
        new_index = (self.current_index + direction) % len(self.names)

        # Update current image
        self.current_index = new_index
        self.image_name = self.names[new_index]
        self.image_url = self.app.get_image(self.image_name)

        # Reset view for new image
        self.reset_view()

        # Load and display new image
        self.load_image()

        # Update title
        self.update_title()

    def toggle_checkerboard(self, evt):
        """Toggle the checkerboard pattern for transparency."""
        self.show_checkerboard = self.checker_checkbox.checked
        self.render()


class App:
    def __init__(self):
        self.file_handle = None
        self.file_name = None # Save file name separate
        self.modules: dict[str, str] = {'main': INITIAL_PYTHON}
        self.modules_viewinfo: dict[str, ViewInfo] = {}
        self.sounds: dict[str, str] = {} # Name -> base64 encoded sound as a data URL
        self.images: dict[str, str] = {} # Name -> base64 encoded image as a data URL
        self.libraries: dict[str, str] = {} # Name -> contents of javascript library (cache)
        self.active_module = 'main'
        self.orig_modules = dict(self.modules)
        self.orig_body = INITIAL_HTML
        self.save_on_run = False
        self.show_save_on_run = True

        self.ui = UI(self)

        self.ui.set_contents_html(self.orig_body)
        self.update_ui(update_python_text=True)

    def anything_modified(self, current_body, current_python):
        self.modules[self.active_module] = current_python
        if current_body != self.orig_body:
            console.log('Mismatched body')
            return True
        if set(self.orig_modules.keys()) != set(self.modules.keys()):
            console.log('Module list mismatch')
            return True
        for k in self.modules:
            if self.orig_modules[k] != self.modules[k]:
                console.log(f'Module {k} mismatch')
                # console.log(f'Orig module {k}:')
                # console.log(self.orig_modules[k])
                # console.log(f'Current module {k}:')
                # console.log(self.modules[k])
                return True
        return False

    def has_file(self):
        return self.file_handle != None

    def update_ui(self, update_python_text=False):
        # Not complete - we don't keep track of active example
        if self.file_name is not None:
            self.ui.set_loaded_file(self.file_name)
        self.ui.set_module_list(self.modules.keys())
        self.ui.set_active_module(self.active_module)
        if update_python_text:
            self.ui.set_focus_python()
            viewinfo = self.modules_viewinfo.get(self.active_module, None)
            self.ui.set_contents_python(self.modules[self.active_module], viewinfo)
            # console.log(f'Updated ui with viewinfo: {viewinfo}')

    async def load_example(self, name):
        # Assumes overwrite check has already been completed
        # All examples have been loaded as part of examples.js into window.EXAMPLES_DATA
        # Find the example in window.EXAMPLES_DATA
        for category in window.EXAMPLES_DATA:
            for example in category['examples']:
                if example['id'] == name:
                    try:
                        if self.load_html(base64.b64decode(example['content']).decode('utf-8')):
                            self.file_handle = None
                            self.file_name = f'{name}.html'
                            self.reset_save_on_run()
                            self.ui.set_loaded_file(f'{name}.html')
                        else:
                            err(f'Parsing error when loading example {name}.')
                        return
                    except Exception as e:
                        console.log(str(e))
                        err(f'Unable to load example {name}.')
                        return
        err(f'Unable to find example {name} in loaded examples.')

    def reset_save_on_run(self):
        self.save_on_run = False
        self.show_save_on_run = True

    def set_save_on_run(self, save_on_run, dont_show_again):
        self.save_on_run = save_on_run
        self.show_save_on_run = not dont_show_again

    async def open_file(self, file_handle):
        f = await file_handle.getFile()
        contents = await f.text()
        if not self.load_html(contents):
            return
        # File load successful
        self.file_handle = file_handle
        self.file_name = file_handle.name
        console.log(f'Opened {file_handle.name}.')
        self.reset_save_on_run()
        self.ui.set_loaded_file(self.file_name)

    def load_html(self, contents):
        try:
            body, modules, sounds, images = self.split_html(contents)
        except Exception as e:
            console.log(e)
            err('Looks like this file was not saved by pywebedit. Unable to load.')
            return False
        # Save copies so we can detect when edited
        self.orig_body = body
        self.orig_modules = modules
        # Set up modules and active module
        self.modules = dict(modules)
        self.active_module = 'main'
        self.modules_viewinfo = {}
        # Save resources
        self.sounds = sounds
        self.images = images
        # Load successful
        self.ui.set_contents_html(body)
        self.update_ui(update_python_text=True)
        return True

    def split_html(self, contents):
        """Split out header, python scripts, sounds, images from saved html."""
        body_and_scripts = contents.split('<body onload="__brython_pre_then_code()">')[1]

        body, precode, *modfragments, script_and_foot = body_and_scripts.split(
            '<' + 'script type="text/python" id=')

        # Body has extra line - remove it
        body = '\n'.join(body.splitlines()[1:])

        # Extract sounds and images from precode
        sounds = {}
        images = {}
        if 'window.SOUNDS = {' in precode:
            sounds_dict_as_str = extract_between(precode, 'window.SOUNDS = {', '}')
            images_dict_as_str = extract_between(precode, 'window.IMAGES = {', '}')
            sounds = parse_str_str_dict(sounds_dict_as_str)
            images = parse_str_str_dict(images_dict_as_str)

        modules = {}
        lines = script_and_foot.strip().splitlines()
        script = '\n'.join(lines[1:-3])
        modules['main'] = script

        for fragment in modfragments:
            lines = fragment.splitlines()
            modname = lines[0].replace('"__pwe_', '').replace('">', '')
            modules[modname] = '\n'.join(lines[1:-2])

        return body, modules, sounds, images

    def run(self, html_body, python_code):
        html = self.build_html(html_body, python_code)
        if self.save_on_run:
            assert self.file_handle is not None
            aio.run(self.save_file(self.file_handle, html_body, python_code,
                                   self.modules_viewinfo[self.active_module], quiet=True))
        self.ui.run_html_in_new_window(html)

    async def fetchlib(self, libname):
        """Attempt to fetch and cache javascript library.

        Start with CDN (and the browser cache). If that doesn't work,
        try to fetch a local copy (which will fail if offline due to
        CORS).

        Returns True if successfully able to fetch and cache the library.
        """
        desc, globalvar, url = JSLIBS[libname]
        localurl = url[(url.rfind('/')+1):]
        for url_to_try in [url, localurl]:
            response = await aio.get(url, cache=True)
            # TODO: fix correct syntax here
            if response.status == 200:
                self.libraries[libname] = response.data
                return True
        return False

    async def fileloadlib(self, libname, lib_file_handle):
        """Loads library from a file handle."""
        f = await lib_file_handle.getFile()
        self.libraries[libname] = await f.text()
        return True

    def is_lib_cached(self, libname):
        return libname in self.libraries

    def build_html(self, html_body, python_code, libs_to_bundle=None):
        """Build the full html text, inserting the user editable sections into the template.

        Optionally inlines complete javascript libraries for complete standaloneness.
        """
        self.modules[self.active_module] = python_code

        console.log('Building html with libs_to_bundle:', libs_to_bundle)
        if libs_to_bundle is None:
            libs_to_bundle = []

        # Handle library bundling - need to respect the order for bython
        for lib in libs_to_bundle:
            assert lib in self.libraries
        libtxt = ''

        # Brython has a special case - it needs to be loaded first with an additional shim
        if 'brython' in libs_to_bundle:
            libtxt += SCRIPT_LOCAL_BRYTHON_SHIM
            libtxt += encode_js_for_html(self.libraries['brython']) + '\n'
            libs_to_bundle.remove('brython')
        else:
            libtxt += create_script_loader('brython') + '\n'

        # We also have to load the standard library no matter what, as our error handler currently relies on it
        if 'brython_stdlib' in libs_to_bundle:
            libtxt += encode_js_for_html(self.libraries['brython_stdlib']) + '\n'
            libs_to_bundle.remove('brython_stdlib')
        else:
            libtxt += create_script_loader('brython_stdlib') + '\n'

        libtxt += '\n'.join(encode_js_for_html(self.libraries[lib]) + '\n'
                            for lib in libs_to_bundle)

        # Convert modules to script blocks
        module_texts = []
        for module_name, module_code in self.modules.items():
            if module_name == 'main':
                continue
            tagmap = {'script':    '<' + 'script',
                      'endscript': '<' + '/script>',
                      'modulecode': module_code,
                      'moduleid': f'__pwe_{module_name}'}
            m = MODULE_TEMPLATE
            for key, value in tagmap.items():
                m = m.replace('%' + key + '%', value)
            module_texts.append(m)

        # Save embedded sounds and images
        sounds = "{" + ",\n".join(f"'{key}':'{val}'" for key,val in self.sounds.items()) + "}"
        images = "{" + ",\n".join(f"'{key}':'{val}'" for key,val in self.images.items()) + "}"

        # Note this is order dependent
        tagmap = {'libraries':       libtxt,
                  'brython_version': BRYTHON_VERSION,
                  'html_body':       html_body,
                  'python_code':     self.modules['main'],
                  'script':          '<' + 'script',
                  'endscript':       '<' + '/script>',
                  'modules':         ', '.join(f"'__pwe_{m}'" for m in self.modules if m != 'main'),
                  'modulescripts':   '\n\n'.join(module_texts),
                  'sounds':          sounds,
                  'images':          images}
        p = PAGE_TEMPLATE
        for key, value in tagmap.items():
            p = p.replace('%' + key + '%', value)

        return p

    async def save_file(self, file_handle, html_body, python_code, python_viewinfo,
                        libs_to_bundle=None, quiet=False):
        self.modules[self.active_module] = python_code
        self.modules_viewinfo[self.active_module] = python_viewinfo
        self.file_handle = file_handle
        self.file_name = file_handle.name
        full_html = self.build_html(html_body, python_code, libs_to_bundle)
        writable = await file_handle.createWritable()
        await writable.write(full_html)
        await writable.close()
        console.log(f'Wrote {self.file_name}')
        # Update known saved version
        self.orig_body = html_body
        self.orig_modules = dict(self.modules)
        self.update_ui(update_python_text=True)
        if not quiet and self.show_save_on_run:
            self.ui.show_save_on_run_dialog(self.save_on_run)

    def new_module(self, name, current_python_code, python_viewinfo):
        assert name not in self.modules
        self.modules[self.active_module] = current_python_code
        self.modules_viewinfo[self.active_module] = python_viewinfo
        self.active_module = name
        self.modules[name] = ''
        self.update_ui(update_python_text=True)

    async def import_module(self, name, file_handle, current_python_code):
        self.modules[self.active_module] = current_python_code
        f = await file_handle.getFile()
        contents = await f.text()
        self.modules[name] = contents.replace('\t', '    ')
        self.active_module = name
        console.log(f'Imported {file_handle.name} as {name}')
        self.update_ui(update_python_text=True)

    async def export_module(self, file_handle, current_python_code):
        self.modules[self.active_module] = current_python_code
        writable = await file_handle.createWritable()
        await writable.write(current_python_code)
        await writable.close()
        console.log(f'Exported module {self.active_module} as {file_handle.name}')
        self.update_ui(update_python_text=True)

    def rename_module(self, new_name):
        assert new_name not in self.modules
        assert self.active_module != 'main'
        old_name = self.active_module
        self.modules[new_name] = self.modules[old_name]
        del self.modules[old_name]
        self.active_module = new_name
        console.log(f'Module {old_name} renamed to {new_name}')
        self.update_ui(update_python_text=False)

    def remove_module(self):
        assert len(self.modules) > 1
        del self.modules[self.active_module]
        self.active_module = 'main'
        self.update_ui(update_python_text=True)

    def select_module(self, name, current_python_code, python_viewinfo):
        assert name in self.modules
        self.modules[self.active_module] = current_python_code
        self.modules_viewinfo[self.active_module] = python_viewinfo
        self.active_module = name
        self.update_ui(update_python_text=True)

    # Sound management methods
    def get_sound_names(self):
        """Get a list of all sound names."""
        return list(self.sounds.keys())

    def get_sound(self, name):
        """Get a sound by name."""
        return self.sounds.get(name)

    def add_sound(self, name, data_url):
        """Add a new sound. If name already in sounds, replace that sound."""
        self.sounds[name] = data_url
        self.ui.update_sound_dialog()

    def rename_sound(self, old_name, new_name):
        """Rename a sound."""
        assert old_name in self.sounds
        assert new_name not in self.sounds
        self.sounds[new_name] = self.sounds[old_name]
        del self.sounds[old_name]
        self.ui.update_sound_dialog()

    def delete_sound(self, name):
        """Delete a sound."""
        assert name in self.sounds
        del self.sounds[name]
        self.ui.update_sound_dialog()

    # Image management
    def get_image_names(self):
        """Get a list of all image names."""
        return list(self.images.keys())

    def get_image(self, name):
        """Get an image by name."""
        return self.images.get(name)

    def add_image(self, name, data_url):
        """Add a new image. If name already in images, replace that image."""
        self.images[name] = data_url
        self.ui.update_image_dialog()

    def rename_image(self, old_name, new_name):
        """Rename an image."""
        assert old_name in self.images
        assert new_name not in self.images
        self.images[new_name] = self.images[old_name]
        del self.images[old_name]
        self.ui.update_image_dialog()

    def delete_image(self, name):
        """Delete an image."""
        assert name in self.images
        del self.images[name]
        self.ui.update_image_dialog()


app = App()
