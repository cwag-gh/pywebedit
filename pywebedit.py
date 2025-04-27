# Main python code

from dataclasses import dataclass
from browser import document, window, bind, aio, console, html
from browser.widgets.dialog import InfoDialog, Dialog, EntryDialog
import base64

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

# Template for generated final page. Do not include script tags, which
# screws up the html in python in html. Use alternate replacement
# syntax (other than format()) to avoid syntax conflicts. Note the
# second level of indirection when defining the fallback script tags.
PAGE_TEMPLATE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
%script% type="text/javascript" src="https://cdn.jsdelivr.net/npm/brython@%brython_version%/brython.min.js">%endscript%
%script%> typeof brython === "undefined" && document.write('%script% src="brython.min.js">\\x3C/script>')%endscript%

%script% type="text/javascript" src="https://cdn.jsdelivr.net/npm/brython@%brython_version%/brython_stdlib.js">%endscript%
%script%> typeof __BRYTHON__.use_VFS === "undefined" && document.write('%script% src="brython_stdlib.js">\\x3C/script>')%endscript%

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


def add_option(select, title, value):
    if title is None:
        select <= html.HR()
    else:
        option = html.OPTION(title)
        option.attrs['value'] = value
        select <= option


@dataclass
class ViewInfo:
    """Holds the cursor and scroll state of an editor view."""
    scrolltop: int
    scrollleft: int
    cursor_anchor: int
    cursor_head: int


class UI:
    PICKER_ID = 'choosefile'

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
        for title, value in PYFILES[:-1]:
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

    async def _pick_file_to_open(self):
        try:
            file_handles = await window.showOpenFilePicker({
                'id': self.PICKER_ID}) # Use same id between pickers to save folder
            if len(file_handles) == 0:
                return None
        except AttributeError:
            self.erropen()
            return None
        return file_handles[0]

    async def on_open(self):
        """Pick a file, then load it."""
        file_handle = await self._pick_file_to_open()
        if file_handle is None:
            return
        await self.app.open_file(file_handle)

    async def on_save(self, force_picker=False):
        handle = self.app.file_handle
        if force_picker or not self.app.has_file():
            name = 'myprogram.html'
            if self.app.file_name is not None:
                name = self.app.file_name
            try:
                handle = await window.showSaveFilePicker({
                   'id': self.PICKER_ID, # Use same id between pickers to save folder
                   'suggestedName': name,
                   'types': [{'description': 'Text documents',
                              'accept': {'text/html': ['.html']}}]})
            except AttributeError:
                self.erropen()
                return
            except JavascriptError:
                # User cancelled
                return
        await self.app.save_file(handle, self.contents_html(),
                                 self.contents_python(), self.viewinfo_python())

    async def on_save_as(self):
        await self.on_save(force_picker=True)

    def _check_valid_module_name(self, name, with_existing_check=True):
        title = 'Invalid module name'
        if len(name) > 20:
            self.err('Module names must be no more than 20 letters.', title)
        elif name.startswith('__'):
            self.err('Module names must not start with two underscores.', title)
        elif not name.replace('_', '').isalnum():
            self.err('Module names must only include letters, numbers, and underscores.', title)
        elif with_existing_check and name in self.app.modules:
            self.err('Module name already exists.', title)
        else:
            return True
        return False

    def _check_newname(self, name):
        if self._check_valid_module_name(name):
            self.app.new_module(name, self.contents_python(), self.viewinfo_python())

    def _check_rename(self, name):
        if self._check_valid_module_name(name):
            self.app.rename_module(name)

    async def on_import(self):
        file_handle = await self._pick_file_to_open()
        if file_handle is None:
            return
        module_name = file_handle.name.replace('.py', '')
        if module_name in self.app.modules:
            def complete_import(name):
                if self._check_valid_module_name(name, with_existing_check=False):
                    aio.run(self.app.import_module(name, file_handle, self.contents_python()))

            self.inputdialog(
                'Warning...',
                f'Module "{module_name}" already exists.<br><br>'
                'Enter a new name, or just keep the same to overwrite the module.<br><br>'
                'Import module as:',
                onok=complete_import, value=module_name)
        else:
            await self.app.import_module(module_name, file_handle, self.contents_python())

    async def on_export(self):
        name = f'{self.app.active_module}.py'
        try:
            handle = await window.showSaveFilePicker({
               'id': self.PICKER_ID, # Use same id between pickers to save folder
               'suggestedName': name,
               'types': [{'description': 'Python files',
                          'accept': {'text/py': ['.py']}}]})
        except AttributeError:
            self.erropen()
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
            self.inputdialog('New module', 'Module name:', self._check_newname)
        elif module == '__import':
            aio.run(self.on_import())
        elif module == '__export':
            aio.run(self.on_export())
        elif module == '__rename':
            if self.app.active_module == 'main':
                self.err("Can't rename main module.")
                return
            self.inputdialog('Rename module', 'New name', self._check_rename)
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

    def on_add_images(self):
        """Show a dialog with a table of already included images, and a button to add more."""
        pass

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
        self.msg('Help', HELP, top=100, left=200)

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

    def inputdialog(self, title, prompt, onok, value=None):
        d = EntryDialog(title, prompt)
        if value is not None:
            d.entry.value = value

        @bind(d, 'entry')
        def entry(ev):
            value = d.value
            d.close()
            if value:
                onok(value)

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

    def msg(self, title, text, top=None, left=None):
        d = InfoDialog(title, text, ok='Ok', top=top, left=left)

    def err(self, text, title='Unfortunately...'):
        self.msg(title, text)

    def erropen(self):
        self.err('This browser does not support opening and saving local files. Try Chrome.')

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
        pyfiles = PYFILES[1:] if len(self.app.modules) > 1 else PYFILES[1:-1]
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

        # Create the dialog
        d = Dialog("Select libraries to include", ok_cancel=("Export", "Cancel"), top=100, left=200)

        # Define available libraries
        # Format: (library_name, default_checked, description, is_required)
        libraries = [
            ("brython.min.js", True, "Core Brython functionality (required)", True),
            ("brython_stdlib.js", True, "Brython standard library", False),
            ("pixi.min.js", False, "2D WebGL renderer", False),
            ("pixi-sound.js", False, "Sound extension for Pixi.js", False),
            ("three.min.js", False, "3D graphics library", False),
            # Add more libraries as needed
        ]

        # Create a container div for the library list
        container = html.DIV(style="max-height: 300px; overflow-y: auto;")

        # Add description
        description = html.P("Select which JavaScript libraries to include in your exported file:",
                             style="margin-bottom: 15px;")
        container <= description

        # Dictionary to keep track of checkboxes
        checkboxes = {}

        # Add each library as a checkbox option
        for lib_name, default_checked, lib_desc, is_required in libraries:
            # Create a div for each library
            lib_div = html.DIV(style="margin-bottom: 10px; display: flex; align-items: center;")

            # Create the checkbox
            checkbox = html.INPUT(type="checkbox", id=f"lib_{lib_name.replace('.', '_')}")
            checkbox.checked = default_checked
            checkbox.disabled = is_required  # Disable checkbox if library is required

            # Label with library name and description
            label_text = f"{lib_name}"
            if lib_desc:
                label_text += f" - {lib_desc}"
            label = html.LABEL(label_text, style="margin-left: 8px; flex: 1;")
            label.attrs["for"] = checkbox.id

            # Add elements to the div
            lib_div <= checkbox + label

            # Add the div to the container
            container <= lib_div

            # Store the checkbox reference
            checkboxes[lib_name] = checkbox

        # Add note about required libraries
        note = html.P("Note: Required libraries cannot be deselected.",
                      style="font-style: italic; margin-top: 15px; font-size: 0.9em;")
        container <= note

        # Add the container to the dialog
        d.panel <= container

        # Handle the OK button click
        @bind(d.ok_button, "click")
        def ok_click(evt):
            # Get the list of selected libraries
            selected_libs = [lib_name for lib_name, checkbox in checkboxes.items()
                            if checkbox.checked]

            # Close the dialog
            d.close()


class SoundsDialog(Dialog):
    """Dialog for managing sounds.

    Shows a list of sounds as rows in a table. For each sound in the row, the user can:
    - Play the sound
    - Delete the sound
    - Rename the sound
    These functions are shown as small buttons in the row.
    The sound size is shown in the row, in kB, as well as the duration in seconds. The duration
    is calculated from metadata and is dynamically updated after the dialog is opened.

    The user can also add a new sound, which will be added to the table.
    """
    def __init__(self, app, top=100, left=200):
        super().__init__("Manage sounds", ok_cancel=False, top=top, left=left)
        self.app = app
        self.sound_table = None
        self.durations = {}  # Cache for sound durations
        self.init_ui()
        self.populate_table()

    def init_ui(self):
        """Initialize the dialog UI with a table for sounds and an add button."""
        container = html.DIV(style="width: 500px;")

        # Add button at the top
        add_button = html.BUTTON("Add sound", style="margin-bottom: 10px;")
        add_button.bind("click", lambda evt: self.add_sound())
        container.appendChild(add_button)

        # Create table for sounds
        self.sound_table = html.TABLE(style="width: 100%; border-collapse: collapse;")
        self.sound_table.appendChild(html.TR(
            html.TH("Name", style="text-align: left;") +
            html.TH("Size", style="text-align: right;") +
            html.TH("Duration", style="text-align: right;") +
            html.TH("Actions", style="text-align: center;")
        ))

        container.appendChild(self.sound_table)
        self.panel <= container

    def populate_table(self):
        """Fill the table with sound entries."""
        # Clear existing rows except header
        if self.sound_table and len(self.sound_table.childNodes) > 1:
            while len(self.sound_table.childNodes) > 1:
                self.sound_table.removeChild(self.sound_table.lastChild)

        # Add a row for each sound
        for name in self.app.get_sound_names():
            self.add_row(name, self.app.get_sound(name))

    def add_row(self, name, data_url):
        """Add a row to the table for a sound."""
        if not self.sound_table:
            return

        # Calculate size in kB
        # Remove the data:audio/* prefix to get the raw base64
        base64_data = data_url.split(',')[1]
        size_kb = round(len(base64_data) * 3 / 4 / 1024, 1)  # Approximate size in kB

        # Create row with name, size, and action buttons
        row = html.TR(style="border-bottom: 1px solid #ddd;")

        # Name cell
        name_cell = html.TD(name, style="padding: 5px;")

        # Size cell
        size_cell = html.TD(f"{size_kb} kB", style="text-align: right; padding: 5px;")

        # Duration cell - initially empty, will be populated later
        duration_cell = html.TD("...", style="text-align: right; padding: 5px;")

        # Actions cell with play, rename, and delete buttons
        actions_cell = html.TD(style="text-align: center; padding: 5px;")

        # Play button
        play_button = html.BUTTON("▶", style="margin-right: 5px;")
        play_button.bind("click", lambda evt, n=name: self.play_sound(n))

        # Rename button
        rename_button = html.BUTTON("✏️", style="margin-right: 5px;")
        rename_button.bind("click", lambda evt, n=name: self.rename_sound(n))

        # Delete button
        delete_button = html.BUTTON("🗑️")
        delete_button.bind("click", lambda evt, n=name: self.delete_sound(n))

        actions_cell <= play_button + rename_button + delete_button

        # Add cells to row
        row <= name_cell + size_cell + duration_cell + actions_cell

        # Add row to table
        self.sound_table.appendChild(row)

        # Calculate duration asynchronously
        self.load_duration(name, data_url, duration_cell)

    def load_duration(self, name, data_url, duration_cell):
        """Load the duration of a sound and update the cell."""
        audio = window.Audio.new(data_url)

        def on_loaded(evt):
            duration = round(audio.duration, 1)
            self.durations[name] = duration
            duration_cell.textContent = f"{duration}s"

        def on_error(evt):
            duration_cell.textContent = "Error"
            console.log(f"Error loading duration for {name}")

        audio.bind("loadedmetadata", on_loaded)
        audio.bind("error", on_error)

    def play_sound(self, name):
        """Play a sound."""
        audio = window.Audio.new(self.app.get_sound(name))
        try:
            audio.play()
        except Exception as e:
            console.log(f'Error playing sound {name}: {e}')

    def add_sound(self):
        """Open a file picker to select a sound file.

        If name already exists, open additional dialog to either replace or rename."""
        input_elem = html.INPUT(type="file", accept="audio/*")

        def on_change(evt):
            if input_elem.files.length == 0:
                return

            file = input_elem.files[0]
            file_name = file.name.split('/')[-1].split('\\')[-1]
            name = file_name.split('.')[0]

            reader = window.FileReader.new()

            def on_load(evt):
                data_url = reader.result

                # Check if sound name already exists
                if name in self.app.get_sound_names():
                    # Create a dialog to ask what to do
                    d = Dialog("Sound name exists", ok_cancel=False)
                    d.panel <= html.DIV(f"A sound named '{name}' already exists. What would you like to do?")

                    # Create buttons container
                    buttons_div = html.DIV(style="margin-top: 15px; display: flex; justify-content: space-between;")

                    # Replace button
                    replace_btn = html.BUTTON("Replace existing sound", style="margin-right: 10px;")

                    @bind(replace_btn, "click")
                    def on_replace(evt):
                        d.close()
                        self.handle_replace_sound(name, data_url)

                    # Rename button
                    rename_btn = html.BUTTON("Use a different name")

                    @bind(rename_btn, "click")
                    def on_rename(evt):
                        d.close()
                        self.handle_rename_sound(name, data_url)

                    # Cancel button
                    cancel_btn = html.BUTTON("Cancel", style="margin-left: 10px;")

                    @bind(cancel_btn, "click")
                    def on_cancel(evt):
                        d.close()

                    # Add buttons to container
                    buttons_div <= replace_btn + rename_btn + cancel_btn

                    # Add buttons container to dialog
                    d.panel <= buttons_div
                else:
                    # No conflict, add directly
                    self.app.add_sound(name, data_url)

            reader.bind("load", on_load)
            reader.readAsDataURL(file)

        input_elem.bind("change", on_change)
        input_elem.click()

    def handle_replace_sound(self, name, data_url):
        """Handle replacing an existing sound."""
        # Delete the existing sound first
        self.app.delete_sound(name)
        # Then add the new sound with the same name
        self.app.add_sound(name, data_url)

    def handle_rename_sound(self, original_name, data_url):
        """Handle renaming a new sound."""
        # Create suggestion for new name
        base_name = original_name
        counter = 1
        suggestion = f"{base_name}_{counter}"

        # Find a name that doesn't exist
        while suggestion in self.app.get_sound_names():
            counter += 1
            suggestion = f"{base_name}_{counter}"

        # Show dialog to get new name
        d = EntryDialog("Rename sound", f"New name for sound ('{original_name}' already exists):")
        d.entry.value = suggestion

        @bind(d, "entry")
        def on_entry(evt):
            new_name = d.value
            d.close()

            if not new_name:
                return

            if new_name in self.app.get_sound_names():
                self.show_error(f"Sound name '{new_name}' also exists. Please choose another name.")
                # Recursive call to try again
                self.handle_rename_sound(original_name, data_url)
            else:
                # Add with the new name
                self.app.add_sound(new_name, data_url)

    def rename_sound(self, name):
        """Show a dialog to rename a sound."""
        # Create dialog to get new name
        d = EntryDialog("Rename sound", "New name:")
        d.entry.value = name

        @bind(d, "entry")
        def on_entry(evt):
            new_name = d.value
            d.close()
            if new_name and new_name != name:
                self.app.rename_sound(name, new_name)

    def delete_sound(self, name):
        """Delete a sound after confirmation."""
        d = Dialog("Confirm deletion", ok_cancel=("Delete", "Cancel"))
        d.panel <= html.DIV(f"Are you sure you want to delete sound '{name}'?")

        @bind(d.ok_button, "click")
        def on_confirm(evt):
            # Delete the sound
            self.app.delete_sound(name)
            d.close()

    def show_error(self, message):
        """Show an error dialog."""
        d = InfoDialog("Error", message, ok="OK")


class App:
    def __init__(self):
        self.file_handle = None
        self.file_name = None # Save file name separate
        self.modules: dict[str, str] = {'main': INITIAL_PYTHON}
        self.modules_viewinfo: dict[str, ViewInfo] = {}
        self.sounds: dict[str, str] = {} # Name -> base64 encoded sound as a data URL
        self.images: dict[str, str] = {} # Name -> base64 encoded image as a data URL
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
                            self.ui.err(f'Parsing error when loading example {name}.')
                        return
                    except Exception as e:
                        console.log(str(e))
                        self.ui.err(f'Unable to load example {name}.')
                        return
        self.ui.err(f'Unable to find example {name} in loaded examples.')

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
            body, modules = self.split_html(contents)
        except Exception as e:
            console.log(e)
            self.ui.err('Looks like this file was not saved by pywebedit. Unable to load.')
            return False
        # Save copies so we can detect when edited
        self.orig_body = body
        self.orig_modules = modules
        # Set up modules and active module
        self.modules = dict(modules)
        self.active_module = 'main'
        self.modules_viewinfo = {}
        # Load successful
        self.ui.set_contents_html(body)
        self.update_ui(update_python_text=True)
        return True

    def split_html(self, contents):
        """Split out header, python scripts from saved html."""
        body_and_scripts = contents.split('<body onload="__brython_pre_then_code()">')[1]

        body, skip, *modfragments, script_and_foot = body_and_scripts.split(
            '<' + 'script type="text/python" id=')

        # Body has extra line - remove it
        body = '\n'.join(body.splitlines()[1:])

        modules = {}
        lines = script_and_foot.strip().splitlines()
        script = '\n'.join(lines[1:-3])
        modules['main'] = script

        for fragment in modfragments:
            lines = fragment.splitlines()
            modname = lines[0].replace('"__pwe_', '').replace('">', '')
            modules[modname] = '\n'.join(lines[1:-2])

        return body, modules

    def run(self, html_body, python_code):
        html = self.build_html(html_body, python_code)
        if self.save_on_run:
            assert self.file_handle is not None
            aio.run(self.save_file(self.file_handle, html_body, python_code,
                                   self.modules_viewinfo[self.active_module], quiet=True))
        self.ui.run_html_in_new_window(html)

    def build_html(self, html_body, python_code):
        """Build the full html text, inserting the user editable sections into the template."""
        self.modules[self.active_module] = python_code
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

        tagmap = {'brython_version': BRYTHON_VERSION,
                  'html_body':       html_body,
                  'python_code':     self.modules['main'],
                  'script':          '<' + 'script',
                  'endscript':       '<' + '/script>',
                  'modules':         ', '.join(f"'__pwe_{m}'" for m in self.modules if m != 'main'),
                  'modulescripts':   '\n\n'.join(module_texts)}
        p = PAGE_TEMPLATE
        for key, value in tagmap.items():
            p = p.replace('%' + key + '%', value)
        return p

    async def save_file(self, file_handle, html_body, python_code, python_viewinfo, quiet=False):
        self.modules[self.active_module] = python_code
        self.modules_viewinfo[self.active_module] = python_viewinfo
        self.file_handle = file_handle
        self.file_name = file_handle.name
        full_html = self.build_html(html_body, python_code)
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
        """Add a new sound."""
        if name not in self.sounds:
            self.sounds[name] = data_url
            self.ui.update_sound_dialog()
            return name
        else:
            # This should only be called from our dialog handler where we already confirmed replacement
            # is desired, so we just replace the existing sound
            self.sounds[name] = data_url
            self.ui.update_sound_dialog()
            return name

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

        return False


app = App()
