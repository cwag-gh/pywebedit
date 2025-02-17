import {basicSetup} from "codemirror"
import {EditorState, Prec} from "@codemirror/state"
import {EditorView, keymap} from "@codemirror/view"
import {indentUnit} from "@codemirror/language"
import {indentWithTab} from "@codemirror/commands"
import {python} from "@codemirror/lang-python"
import {html} from "@codemirror/lang-html"

// Explicitly assign to window to prevent tree-shaking
window.basicSetup    = basicSetup;
window.EditorState   = EditorState;
window.Prec          = Prec;
window.EditorView    = EditorView;
window.keymap        = keymap;
window.indentUnit    = indentUnit;
window.indentWithTab = indentWithTab;
window.python        = python;
window.html          = html;
