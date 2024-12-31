import {EditorView, basicSetup} from "codemirror"
import {EditorState} from "@codemirror/state"
import {indentUnit} from "@codemirror/language"
import {python} from "@codemirror/lang-python"
import {html} from "@codemirror/lang-html"

// Explicitly assign to window to prevent tree-shaking
window.EditorView = EditorView;
window.EditorState = EditorState;
window.indentUnit = indentUnit;
window.basicSetup = basicSetup;
window.python = python;
window.html = html;
