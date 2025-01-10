# Main python code

from browser import document, window, bind, aio, console, html
from browser.widgets.dialog import InfoDialog, Dialog, EntryDialog

BRYTHON_VERSION = '3.13.0'
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
    <li>Ctrl-/: Toggle comments on line</li>
    <li>Tab: Indent line (press Esc then Tab to use default Tab functionality)</li>
    <li>Shift-Tab: Unindent line</li>
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
"""

# Template for generated final page. Do not include script tags, which
# screws up the html in python in html. Use alternate replacement
# syntax (other than format()) to avoid syntax conflicts. Note the
# second level of indirection when defining the fallback script tags.
PAGE_TEMPLATE = """<!doctype html>
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
"""

MODULE_TEMPLATE = """%script% type="text/python" id="%moduleid%">
%modulecode%
%endscript%"""

EXAMPLES = {
    "Interacting with HTML": [
        ("hello", "Hello world"),
        ("calculator", "Calculator with styled buttons"),
        ("sort_table", "Table with sortable columns"),
    ],
    "Drawing and animating": [
        ("clock", "Analog clock"),
        ("barcode", "Generate barcodes"),
        ("pythagoras", "Animated geometry proof"),
        ("pixelperfect", "Perfect pixel-aligned drawing"),
    ],
    "Using javascript libraries": [
        ("three", "3D spinning cube (three.js)"),
    ],
    "Games": [
        ("breakout", "Brick breaking"),
        ("lightcycles", "Lightcycles"),
    ],
}

PYFILES = [('main', 'main'),
           (None, None),
           ('New python module', '__new'),
           ('Import existing module', '__import'),
           (None, None),
           ('Export this python module', '__export'),
           ('Rename this python module', '__rename'),
           ('Remove this python module', '__remove')]


def add_option(select, title, value):
    if title is None:
        select <= html.HR()
    else:
        option = html.OPTION(title)
        option.attrs['value'] = value
        select <= option


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
             'extensions': [window.basicSetup,
                            window.python(),
                            window.indentUnit.of('    '),
                            window.keymap.of([window.indentWithTab])]})

        self._init_examples()
        self._init_pyfiles()

        # Set up the events
        document['btnrun'].bind('click', self.on_run)
        document['btnopen'].bind('click', self.on_open_precheck)
        document['btnsave'].bind('click', lambda e: aio.run(self.on_save()))
        document['btnsaveas'].bind('click', lambda e: aio.run(self.on_save_as()))
        document['examples'].bind('change', self.on_example_select)
        document['pyfiles'].bind('change', self.on_pyfiles_select)
        document['btnhelp'].bind('click', self.on_help)
        window.addEventListener('beforeunload', self._close_app_window)

    def _close_app_window(self, evt):
        return self.app_window.close() if self.app_window else None

    def _init_examples(self):
        select = document['examples']
        add_option(select, 'Load example...', '')
        for group_name, examples in EXAMPLES.items():
            group = html.OPTGROUP()
            group.attrs['label'] = group_name
            for value, display_text in examples:
                add_option(group, display_text, value)
            select <= group

    def _init_pyfiles(self):
        select = document['pyfiles']
        for title, value in PYFILES[:-1]:
            add_option(select, title, value)

    def on_run(self, evt):
        try:
            if self.app_window:
                self.app_window.close()
        except:
            # Weird error in Chrome when someone reloads the generated tab,
            # and we then can't access it
            pass
        self.app_window = window.open()
        self.app_window.document.write(self.app.build_html(self.contents_html(),
                                                           self.contents_python()))
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
        await self.app.save_file(handle, self.contents_html(), self.contents_python())

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
            self.app.new_module(name, self.contents_python())

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

    def on_remove(self):
        d = Dialog('Warning...', ok_cancel=('Proceed', 'Cancel'))
        d.panel <= html.DIV(f'Proceed with removing module {self.app.active_module}? '
                            'Non-exported changes will be lost.')

        @bind(d.ok_button, 'click')
        def ok(_):
            d.close()
            self.app.remove_module()

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
        else:
            self.app.select_module(module, self.contents_python())

    def on_example_select(self, evt):
        # Since we really use this as a menu, automatically return to first choice.
        # Don't want to have to deal with situation where an example has been
        # modified - do we change the example choice or not?
        self.set_example_choice('')
        self.warn_if_modified(onok=self.app.load_example(evt.target.value))

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

    def set_loaded_file(self, file_name):
        document.getElementById('filename').innerHTML = f'&lt;pywebedit&gt; {file_name}'
        document.title = f'<pywebedit> {file_name}'

    def set_contents_html(self, code):
        self.html_editor.dispatch({'changes': {'from': 0,
                                               'to': self.html_editor.state.doc.length,
                                               'insert': code}})

    def set_contents_python(self, code):
        self.python_editor.dispatch({'changes': {'from': 0,
                                                 'to': self.python_editor.state.doc.length,
                                                 'insert': code}})

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


class App:
    def __init__(self):
        self.file_handle = None
        self.file_name = None # Save file name separate
        self.modules: dict[str, str] = {'main': INITIAL_PYTHON}
        self.active_module = 'main'
        self.orig_modules = dict(self.modules)
        self.orig_body = INITIAL_HTML

        self.ui = UI(self)

        self.ui.set_contents_html(self.orig_body)
        self.update_ui(update_python_text=True)

    def anything_modified(self, current_body, current_python):
        self.modules[self.active_module] = current_python
        return ((current_body != self.orig_body) or
                (set(self.orig_modules.keys()) != set(self.modules.keys())) or
                any(self.orig_modules[k] != self.modules[k] for k in self.modules))

    def has_file(self):
        return self.file_handle != None

    def update_ui(self, update_python_text=False):
        # Not complete - we don't keep track of active example
        if self.file_name is not None:
            self.ui.set_loaded_file(self.file_name)
        self.ui.set_module_list(self.modules.keys())
        self.ui.set_active_module(self.active_module)
        if update_python_text:
            self.ui.set_contents_python(self.modules[self.active_module])
            self.ui.set_focus_python()

    async def load_example(self, name):
        # Assumes overwrite check has already been completed
        relative_url = f'./examples/{name}.html'
        try:
            request = await aio.get(relative_url, format='text')
            if not(request.status == 200 or request.status == 0):
                raise RuntimeError(f'HTTP error: status {request.status}')
            if not request.data:
                raise RuntimeError(f'Empty request data')
            if self.load_html(request.data):
                self.file_handle = None
                self.file_name = f'{name}.html'
                self.ui.set_loaded_file(f'{name}.html')
                return
        except Exception as e:
            console.log(str(e))
            self.ui.err(f'Unable to load {relative_url} from the server.')

    async def open_file(self, file_handle):
        f = await file_handle.getFile()
        contents = await f.text()
        if not self.load_html(contents):
            return
        # File load successful
        self.file_handle = file_handle
        self.file_name = file_handle.name
        console.log(f'Opened {file_handle.name}.')
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
        # Load successful
        self.ui.set_contents_html(body)
        self.update_ui(update_python_text=True)
        return True

    def split_html(self, contents):
        """Split out header, python scripts from saved html."""
        body_and_scripts = contents.split('<body onload="__brython_pre_then_code()">')[1]

        body, skip, *modfragments, script_and_foot = body_and_scripts.split(
            '<' + 'script type="text/python" id=')

        modules = {}
        lines = script_and_foot.strip().splitlines()
        script = '\n'.join(lines[1:-3])
        modules['main'] = script

        for fragment in modfragments:
            lines = fragment.splitlines()
            modname = lines[0].replace('"__pwe_', '').replace('">', '')
            modules[modname] = '\n'.join(lines[1:-2])

        return body, modules

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
                  'html_body':       html_body.strip(),
                  'python_code':     self.modules['main'],
                  'script':          '<' + 'script',
                  'endscript':       '<' + '/script>',
                  'modules':         ', '.join(f"'__pwe_{m}'" for m in self.modules if m != 'main'),
                  'modulescripts':   '\n\n'.join(module_texts)}
        p = PAGE_TEMPLATE
        for key, value in tagmap.items():
            p = p.replace('%' + key + '%', value)
        return p

    async def save_file(self, file_handle, html_body, python_code):
        self.modules[self.active_module] = python_code
        self.file_handle = file_handle
        self.file_name = file_handle.name
        full_html = self.build_html(html_body, python_code)
        writable = await file_handle.createWritable()
        await writable.write(full_html)
        await writable.close()
        console.log(f'Wrote {self.file_name}')
        self.update_ui(update_python_text=True)

    def new_module(self, name, current_python_code):
        assert name not in self.modules
        self.modules[self.active_module] = current_python_code
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

    def select_module(self, name, current_python_code):
        assert name in self.modules
        self.modules[self.active_module] = current_python_code
        self.active_module = name
        self.update_ui(update_python_text=True)


app = App()
