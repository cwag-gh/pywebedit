# pywebedit

Build python programs that can run in the browser, from your browser.

## Goals

- Run python programs on a classroom chromebook, without having to
  install Linux, or anything
- Keep everything local, in-browser, standalone, so we don't even need web
  access (sites like [replit](https://replit.com/) are often blocked)
- Make sure python errors are reported to the screen, as opposed to
  the developer console (also often blocked)
- Allow distribution of resulting programs as standalone html files
- Have the pywebedit be editable in... pywebedit! Eventually...

## Approach

- Use [brython](https://www.brython.info/)
- Inspired by [brython's editor
  example](https://www.brython.info/tests/editor.html?lang=en) and
  [urfdvw's Brython Editor](https://github.com/urfdvw/Brython-Editor)
- Use monolith to download then reupload a standalone version

## TODO

- Add all examples from Brython website
  - Add them to pywebedit/examples
  - First, try to get it from the website. If that doesn't work,
    fall back to letting the user choose the folder of local directories
- Add examples using pixi.js (fast 2d rendering engine, basis for
  Phaser.js)
  - Or consider Phaser.js
- Strip tabs (or at least highlight?) in python code editor
- Find / replace
- Toggle Header, Body, Code regions
- Add autosave
- If example fails to load, then program shouldn't end in a half
  loaded state
- Codemirror:
  - Add [indentation markers](https://github.com/replit/codemirror-indentation-markers)
