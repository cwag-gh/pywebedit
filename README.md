# pywebedit

Build python programs that can run in the browser, from your browser.

See the live version [here](https://robotfantastic.org/pywebedit/).


## Goals

- Run python programs on a classroom Chromebook, without having to
  install Linux, or anything
- Have a way to keep everything local, in-browser, standalone, so we
  don't even need web access (sites like [replit](https://replit.com/)
  are often blocked)
- Make sure python errors are reported to the screen, as opposed to
  the developer console (also often blocked)
- Allow distribution of resulting programs as standalone html files,
  which can be run directly from the browser, and shared using Google
  Drive
- Maximize vertical space for coding on a Chromebook


## Approach

- Use [brython](https://www.brython.info/)
- Use [Codemirror 6](https://codemirror.net) for the editor components
- Inspired by [brython's editor
  example](https://www.brython.info/tests/editor.html?lang=en) and
  [urfdvw's Brython Editor](https://github.com/urfdvw/Brython-Editor)
- Use a fallback so that it can run using local copies of the main
  javascript libraries (both the editor and the generated webpages)


## Implementation notes

- Mixing tabs and spaces results in confusing errors. For now, we
  replace all tabs with spaces on Run.


## TODO

- Fix behavior with long lines - editor grows, which may not be what
  we want
- Add ability to have multiple python files
- Add examples as tutorials
  - Variations on input
- Add all examples from Brython website?
- Add examples using pixi.js (fast 2d rendering engine, basis for
  Phaser.js)
  - Or consider Phaser.js
- Add autosave?
- Fix bug: If example fails to load, incorrectly states that it wasn't
  encoded by pywebedit
- Add [indentation markers](https://github.com/replit/codemirror-indentation-markers)
- Don't add the stdlib if the python doesn't require it
