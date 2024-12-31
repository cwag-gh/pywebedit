import {EditorView, basicSetup} from "codemirror"
import {python} from "@codemirror/lang-python"
//import {javascript} from "@codemirror/lang-javascript"
import {html} from "@codemirror/lang-html"

// Explicitly assign to window to prevent tree-shaking
window.EditorView = EditorView;
window.basicSetup = basicSetup;
window.python = python;
window.html = html;

// let editor1 = new EditorView({
//   extensions: [basicSetup, python()],
//   parent: document.body
// })
//
// let editor2 = new EditorView({
//   extensions: [basicSetup, html()],
//   parent: document.body
// })

// export class PythonEditor {
//     constructor(parentElement, initialCode = '') {
//         // Create editor view
//         this.view = new EditorView({
//             extensions: [basicSetup, python()],
//             parent: parentElement
//         });
//     }
//
//     // Get current code content
//     getCode() {
//         return this.view.state.doc.toString();
//     }
//
//     // Set new code content
//     setCode(newCode) {
//         this.view.dispatch({
//             changes: {
//                 from: 0,
//                 to: this.view.state.doc.length,
//                 insert: newCode
//             }
//         });
//     }
//
//     // Destroy the editor instance
//     destroy() {
//         this.view.destroy();
//     }
// }
//
//
// export class HTMLEditor {
//     constructor(parentElement, initialCode = '') {
//         // Create editor view
//         this.view = new EditorView({
//             extensions: [basicSetup, html()],
//             parent: parentElement
//         });
//     }
//
//     // Get current code content
//     getCode() {
//         return this.view.state.doc.toString();
//     }
//
//     // Set new code content
//     setCode(newCode) {
//         this.view.dispatch({
//             changes: {
//                 from: 0,
//                 to: this.view.state.doc.length,
//                 insert: newCode
//             }
//         });
//     }
//
//     // Destroy the editor instance
//     destroy() {
//         this.view.destroy();
//     }
// }
