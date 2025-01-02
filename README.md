# pywebedit

Build python programs that can run in the browser, from your browser.


## Goals

- Run python programs on a classroom Chromebook, without having to
  install Linux, or anything
- Have a way to keep everything local, in-browser, standalone, so we
  don't even need web access (sites like [replit](https://replit.com/)
  are often blocked)
- Make sure python errors are reported to the screen, as opposed to
  the developer console (also often blocked)
- Allow distribution of resulting programs as standalone html files,
  which can be run directly from the browser, and shared using Google Drive


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

- Add text wrapping, because as of now it affects the editor width
  if lines go too long
- Add ability to have multiple python files
- Add examples as tutorials
- Add all examples from Brython website?
- Add examples using pixi.js (fast 2d rendering engine, basis for
  Phaser.js)
  - Or consider Phaser.js
- Add autosave?
- Fix bug: If example fails to load, incorrectly states that it wasn't
  encoded by pywebedit
- Add [indentation markers](https://github.com/replit/codemirror-indentation-markers)
