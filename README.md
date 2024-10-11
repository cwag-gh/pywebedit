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
- Have the pywebedit be editable in... pywebedit!

## Approach

- Use [brython](https://www.brython.info/)
- Inspired by [brython's editor
  example](https://www.brython.info/tests/editor.html?lang=en) and
  [urfdvw's Brython Editor](https://github.com/urfdvw/Brython-Editor)
