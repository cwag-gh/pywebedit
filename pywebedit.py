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

# Template for generated final page. Do not include script
# tags, which screws up the html in python in html. Use
# alternate replacement syntax (other than format()) to
# avoid syntax conflicts.
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

window.brython({'debug': 1, 'ids': ["pythoncode"]})
%endscript%

%script% type="text/python" id="pythoncode">
%python_code%
%endscript%
</body>
</html>
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


# Main state variables
html_editor = window.EditorView(
    {'parent': document['html_editor'],
     'extensions': [window.basicSetup,
                    window.html(),
                    window.indentUnit.of("    "),
                    window.keymap.of([window.indentWithTab])]})
python_editor = window.EditorView(
    {'parent': document['python_editor'],
     'extensions': [window.basicSetup,
                    window.python(),
                    window.indentUnit.of("    "),
                    window.keymap.of([window.indentWithTab])]})

app_window = None
file_handle = None
file_name = None
orig_code = INITIAL_PYTHON
orig_body = INITIAL_HTML


def editor_contents_set(editor, code):
    editor.dispatch({'changes': {'from': 0,
                                 'to': editor.state.doc.length,
                                 'insert': code}})


def editor_contents_get(editor):
    return editor.state.doc.toString()


def add_examples():
    select = document["examples"]

    # Create and add a default option
    default_option = html.OPTION("Load example...")
    default_option.attrs["value"] = ""
    select <= default_option

    # Iterate through the example groups
    for group_name, examples in EXAMPLES.items():
        # Create optgroup
        group = html.OPTGROUP()
        group.attrs["label"] = group_name

        # Add options to the group
        for value, display_text in examples:
            option = html.OPTION(display_text)
            option.attrs["value"] = value
            group <= option

        # Add the group to the select
        select <= group


async def load_example(name):
    try:
        relative_url = f'./examples/{name}.html'
        request = await aio.get(relative_url, format='text')
        if request.status == 200 or request.status == 0:
            # TODO: check overwrite of modified data
            if load_html(request.data):
                set_loaded_file_and_title(None, f'{name}.html')
                return
        else:
            raise RuntimeError(f"HTTP error: status {request.status}")
    except Exception as e:
        console.log(str(e))
        # TODO: Fallback to choosing folder to load local example
        d = InfoDialog("Unfortunately...",
                       f"Unable to load {relative_url} from the server.",
                       ok="Ok")
    # For all unsuccessful cases, set the combo box back to default
    document["examples"].value = ''


@bind(document['examples'], 'change')
def on_example_select(evt):
    if anything_modified():
        d = Dialog("Warning...", ok_cancel=('Proceed', 'Cancel'))
        style = dict(textAlign="center", paddingBottom="1em")
        d.panel <= html.DIV("Code changes will be lost. Proceed anyway? Or "
                            "cancel (so you can then save first)?")

        @bind(d.ok_button, "click")
        def ok(_):
            aio.run(load_example(evt.target.value))
            d.close()
    else:
        aio.run(load_example(evt.target.value))


@bind(document['btnhelp'], 'click')
def on_help(_):
    d = InfoDialog("Help", HELP, ok="Ok")


def replace_all_tabs():
    """Replaces all tabs with spaces in the python editor."""
    editor_contents_set(python_editor, editor_contents_get(python_editor).replace('\t', '    '))


@bind(document['btnrun'], 'click')
def on_run(_):
    global app_window
    try:
        if app_window:
            app_window.close()
    except:
        # Weird error in Chrome when someone reloads the generated tab,
        # and we then can't access it
        pass
    replace_all_tabs()
    app_window = window.open()
    app_window.document.write(build_html())
    app_window.document.close()

    # Download to a file - user has to click on it, but works
    # blob = window.Blob.new([build_html()], {'type': 'text/html' })
    # a = document.createElement('a')
    # a.href = window.URL.createObjectURL(blob)
    # a.download = 'generated.html'
    # a.click()


@bind(document['btnopen'], 'click')
def on_open(_):
    # Need this intermediate to run async functions
    aio.run(open_file())


async def pick_file_for_saving():
    return await _pick_file(True)


async def pick_existing_file():
    return await _pick_file(False)


async def _pick_file(for_saving):
    global file_handle, file_name
    try:
        if for_saving:
            name = 'myprogram.html'
            if file_name is not None:
                name = file_name
            handle = await window.showSaveFilePicker({
               'id': 'choosefile', # Use same id between pickers to save folder
               'suggestedName': name,
               'types': [{'description': 'Text documents',
                          'accept': {'text/html': ['.html']}}]})
            # TODO: check for success
            file_handle = handle
            file_name = file_handle.name
            return True
        else:
            file_handles = await window.showOpenFilePicker({
               'id': 'choosefile'}) # Use same id between pickers to save folder
            if len(file_handles) > 0:
                file_handle = file_handles[0]
                file_name = file_handle.name
                return True
    except AttributeError:
        # TODO: should be able to handle local saving using download to a file approach
        d = InfoDialog("Unfortunately...",
                       "This browser does not support opening and saving local files. Try Chrome.",
                       ok="Ok")
    return False


def set_loaded_file_and_title(handle=None, title=None):
    """Single function to set what has been loaded - a file or an example"""
    global file_handle, file_name
    file_handle = handle
    file_name = title
    if file_name is None:
        if file_handle is None:
            # Reset
            file_name = ''
        else:
            file_name = file_handle.name
    # Set the UI of the title
    document.getElementById('filename').innerHTML = f'&lt;pywebedit&gt; {file_name}'
    document.title = f'<pywebedit> {file_name}'


async def open_file():
    """Pick a file, then load it."""
    global file_handle
    success = await pick_existing_file()
    if not success:
        return
    f = await file_handle.getFile()
    contents = await f.text()
    load_html(contents)
    console.log(f'Opened {file_handle.name}.')
    set_loaded_file_and_title(file_handle, file_handle.name)


def load_html(contents):
    """Update the UI given the actual html contents as a string."""
    global orig_body, orig_code
    try:
        body, script = split_html(contents)
    except Exception as e:
        console.log(e)
        d = InfoDialog("Error",
                       "Looks like this file was not saved by pywebedit. Unable to load.",
                       ok="Ok")
        return False
    editor_contents_set(html_editor, body)
    editor_contents_set(python_editor, script)
    # Save copies so we can detect when edited
    orig_body = body
    orig_code = script
    console.log(f'Set body {len(body)} chars, python {len(script)} chars.')
    return True


def anything_modified():
    return not(orig_body == editor_contents_get(html_editor) and
               orig_code == editor_contents_get(python_editor))


def split_html(contents):
    """Split out header, python script out of saved html."""
    body_and_script = contents.split('<body onload="__brython_pre_then_code()">')[1]
    body = body_and_script.split('<' + 'script type="text/python" id="brythonpre">')[0].strip()
    script_and_foot = body_and_script.split('<' + 'script type="text/python" id="pythoncode">')[1]
    script = script_and_foot.split('<' + '/script>')[0].strip()
    return body, script


def build_html():
    """Build the full html text, inserting the user editable sections into the template."""
    tagmap = {'brython_version': BRYTHON_VERSION,
              'html_body':       editor_contents_get(html_editor),
              'python_code':     editor_contents_get(python_editor),
              'script':          '<' + 'script',
              'endscript':       '<' + '/script>'}
    p = PAGE_TEMPLATE
    for key, value in tagmap.items():
        p = p.replace('%' + key + '%', value)
    return p


# def save_data_to_file(data, filename, type):
#     blob = window.Blob
#     file = blob.new([data], {'type': type})
#     if window.navigator.msSaveOrOpenBlob: # IE10+
#         window.navigator.msSaveOrOpenBlob(file, filename)
#     else: # Others
#         a = document.createElement('a')
#         url = window.URL.createObjectURL(file)
#         a.href = url
#         a.download = filename
#         document.body.appendChild(a)
#         a.click()
#         def remove_url():
#             document.body.removeChild(a)
#             window.URL.revokeObjectURL(url)
#         window.setTimeout(remove_url, 0)


async def write_file(contents):
    global file_handle
    assert file_handle is not None
    writable = await file_handle.createWritable()
    await writable.write(contents)
    await writable.close()


@bind(document['btnsave'], 'click')
def on_save(_):
    replace_all_tabs()
    aio.run(save_file(False))


@bind(document['btnsaveas'], 'click')
def on_save_as(_):
    replace_all_tabs()
    aio.run(save_file(True))


async def save_file(with_picker):
    global file_handle, file_name
    if file_handle is None or with_picker:
        success = await pick_file_for_saving()
        if not success:
            return
    # A bit lame - this re-sets what is already there just to update the UI
    set_loaded_file_and_title(file_handle, file_name)
    await write_file(build_html())


# Auto close child window if main window is closed
window.addEventListener('beforeunload', lambda e: app_window.close() if app_window else None)

add_examples()
editor_contents_set(html_editor, INITIAL_HTML)
editor_contents_set(python_editor, INITIAL_PYTHON)
