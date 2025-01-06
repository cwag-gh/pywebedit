# Main python code

from browser import document, window, bind, aio, console, html
from browser.widgets.dialog import InfoDialog, Dialog


BRYTHON_VERSION = '3.13.0'
PYWEBEDIT_VERSION = '0.1.0'


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
"""

MODULE_TEMPLATE = """
%script% type="text/python" id="%moduleid%">
%
%endscript%
"""

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

PYFILES = [('main.py', 'main'),
           (None, None),
           ('New python module', '__new'),
           ('Import existing module', '__import'),
           (None, None),
           ('Export this python module', '__export'),
           ('Rename this python module', '__rename'),
           ('Remove this python module', '__remove')] # TODO: only add when there is more than one


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

        self.set_contents_html(INITIAL_HTML)
        self.set_contents_python(INITIAL_PYTHON)

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
        for title, value in PYFILES:
            add_option(select, title, value)

    def on_run(self, evt):
        try:
            if self.app_window:
                self.app_window.close()
        except:
            # Weird error in Chrome when someone reloads the generated tab,
            # and we then can't access it
            pass
        self.replace_all_tabs()
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

    async def on_open(self):
        """Pick a file, then load it."""
        try:
            file_handles = await window.showOpenFilePicker({
                'id': self.PICKER_ID}) # Use same id between pickers to save folder
            if len(file_handles) == 0:
                return
        except AttributeError:
            self.erropen()
            return
        await self.app.open_file(file_handles[0])

    async def on_save(self, force_picker=False):
        self.replace_all_tabs()
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
            except DOMException:
                # User cancelled
                return
        await self.app.save_file(handle, self.contents_html(), self.contents_python())

    async def on_save_as(self):
        await self.on_save(force_picker=True)

    def on_pyfiles_select(self, evt):
        evt.target.value

    def on_example_select(self, evt):
        self.warn_if_modified(onok=self.app.load_example(evt.target.value))

    def on_help(self, evt):
        self.msg('Help', HELP)

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

    def msg(self, title, text):
        d = InfoDialog(title, text, ok='Ok')

    def err(self, text):
        self.msg('Unfortunately...', text)

    def erropen(self):
        self.err('This browser does not support opening and saving local files. Try Chrome.')

#    def anything_modified(self):
#        return not(self.app.orig_body == self.contents_html() and
#                   self.app.orig_code == self.contents_python())

    def contents_html(self):
        return self.html_editor.state.doc.toString()

    def contents_python(self):
        return self.python_editor.state.doc.toString()

    def replace_all_tabs(self):
        """Replaces all tabs with spaces in the python editor."""
        self.set_contents_python(self.contents_python().replace('\t', '    '))

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

    ## def set_module_list(self, names):
    ##     do this
    ##     PYFILES[1:]


class App:
    def __init__(self):
        self.file_handle = None
        self.file_name = None # Save file name separate
        self.modules: dict[str, str] = {} # Store the code for all python modules
        self.active_module = 'main'
        self.orig_modules = {'main': INITIAL_PYTHON}
        self.orig_body = INITIAL_HTML

        self.ui = UI(self)

    def anything_modified(self, current_body, current_python):
        self.modules[self.active_module] = current_python
        return ((current_body != self.orig_body) or
                (set(self.orig_modules.keys()) != set(self.modules.keys())) or
                any(self.orig_modules[k] != self.modules[k] for k in self.modules))

    def has_file(self):
        return self.file_handle != None

    def update_ui(self, update_python_text=False):
        # Not complete - we don't keep track of active example
        self.ui.set_loaded_file(self.file_name)
        self.ui.set_module_list(self.modules.keys())
        self.ui.set_active_module(self.active_module)
        if update_python_text:
            self.ui.set_contents_python(self.modules[self.active_module])

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
        # For all unsuccessful cases, set the combo box back to default
        self.ui.set_example_choice('')

    async def open_file(self, file_handle):
        f = await file_handle.getFile()
        contents = await f.text()
        if not self.load_html(contents):
            return
        # File load successful
        self.file_handle = file_handle
        self.file_name = file_handle.name
        console.log(f'Opened {file_handle.name}.')
        self.ui.set_loaded_file(file_handle.name)

    def load_html(self, contents):
        try:
            body, script = self.split_html(contents)
        except Exception as e:
            console.log(e)
            self.ui.err('Looks like this file was not saved by pywebedit. Unable to load.')
            return False
        # Save copies so we can detect when edited
        self.orig_body = body
        self.orig_code = script
        # Load successful
        self.ui.set_contents_html(body)
        self.ui.set_contents_python(script)
        return True

    def split_html(self, contents):
        """Split out header, python script out of saved html."""
        body_and_script = contents.split('<body onload="__brython_pre_then_code()">')[1]
        body = body_and_script.split(
            '<' + 'script type="text/python" id="brythonpre">')[0].strip()
        script_and_foot = body_and_script.split(
            '<' + 'script type="text/python" id="pythoncode">')[1]
        script = script_and_foot.split('<' + '/script>')[0].strip()
        return body, script

    def build_html(self, html_body, python_code):
        """Build the full html text, inserting the user editable sections into the template."""
        module_texts = []
        for module in self.modules:
            if module == 'main':
                continue
            tagmap = {'script':    '<' + 'script',
                      'endscript': '<' + '/script>',
                      'moduleid': f'__pwe_{module}'}
            m = MODULE_TEMPLATE
            for key, value in tagmap.items():
                m = m.replace('%' + key + '%', value)
            module_texts.append(m)

        tagmap = {'brython_version': BRYTHON_VERSION,
                  'html_body':       html_body,
                  'python_code':     python_code,
                  'script':          '<' + 'script',
                  'endscript':       '<' + '/script>',
                  'modules':         ', '.join(m for m in self.modules if m != 'main'),
                  'modulescripts':   '\n\n'.join(module_texts)}
        p = PAGE_TEMPLATE
        for key, value in tagmap.items():
            p = p.replace('%' + key + '%', value)
        return p

    async def save_file(self, file_handle, html_body, python_code):
        self.file_handle = file_handle
        self.file_name = file_handle.name
        full_html = self.build_html(html_body, python_code)
        writable = await file_handle.createWritable()
        await writable.write(full_html)
        await writable.close()
        console.log(f'Wrote {self.file_name}')
        self.update_ui()

    def new_module(self, name, current_python_code):
        assert name not in self.modules
        self.modules[self.active_module] = current_python_code
        self.active_module = name
        self.modules[name] = ''
        self.update_ui(update_python_text=True)

    async def import_module(self, file_handle, current_python_code):
        self.modules[self.active_module] = current_python_code
        f = await file_handle.getFile()
        contents = await f.text()
        name = file_handle.name.replace('.py', '')
        self.modules[name] = contents.replace('\t', '    ')
        self.active_module = name
        console.log(f'Imported {file_handle.name}.')
        self.update_ui(update_python_text=True)

    async def export_module(self, file_handle, current_python_code):
        self.modules[self.active_module] = current_python_code
        writable = await file_handle.createWritable()
        await writable.write(current_python_code)
        await writable.close()
        console.log(f'Exported module {self.active_module} as {self.file_name}')

    def rename_module(self, new_name):
        assert new_name not in self.modules
        assert self.active_module != 'main'
        old_name = self.active_module
        self.modules[new_name] = self.modules[old_name]
        del self.modules[old_name]
        self.active_module = new_name
        self.update_ui(update_python_text=False)

    def remove_module(self):
        assert len(self.modules) > 1
        del self.modules[self.active_module]
        self.active_module = 'main'
        self.update_ui(update_python_text=True)


app = App()
