# pywebedit

Build python programs that can run in the browser, from your browser.

See the live version [here](https://robotfantastic.org/pywebedit/).


## Goals

- Run python programs on a classroom Chromebook, without having to
  install Linux, or anything
- Have a way to keep everything local, in-browser, standalone, so we
  don't even need web access (sites like [replit](https://replit.com/)
  are often blocked and [runpython](https://runpython.org))
- Make sure python errors are reported to the screen, as opposed to
  the developer console (also often blocked)
- Allow distribution of resulting programs as standalone html files,
  which can be run directly from the browser, and shared using Google
  Drive
- These files should also be able to be run fully offline using the same
  files as from the original download
- Maximize vertical space for coding on a Chromebook


## Approach

- Use [brython](https://www.brython.info/)
- Use [Codemirror 6](https://codemirror.net) for the editor components
- Inspired by [brython's editor
  example](https://www.brython.info/tests/editor.html?lang=en) and
  [urfdvw's Brython Editor](https://github.com/urfdvw/Brython-Editor)
- Use a fallback so that it can run using local copies of the main
  javascript libraries (both the editor and the generated webpages)
- Embed images and sound files to be truly portable, even offline
  (where you can't load non-image files)


## Implementation notes

- Mixing tabs and spaces results in confusing errors. For now, we
  replace all tabs with spaces on Run.
- Some CDNs are better than others for this project, in that they
  allow fetching resources from Origin: Null (like when you are
  running / testing locally). This is nice, so prefer them (unpkg).


## TODO

- Increase speed of export
  - Test out speed of non-chuncked encode approach
- Improve speed of loading
  - Check out Blob approach instead of directly embedding script
- Maybe "use" statements that load scripts in a useful way?
- Support export to github
- support save/load from google drive?
- Disable other buttons when help window is up
- Add console
- Fix keypresses on Windows
- Fix issue where mismatched tags in the body section will screw up
  code generation. Need to parse it?
- Fix behavior with long lines - editor grows, which may not be what
  we want
- Add [indentation markers](https://github.com/replit/codemirror-indentation-markers)
- Don't add the stdlib if the python doesn't require it
  - No, can't do this yet, as error handling depends on stdlib
- Consider using brython's browser.widgets.menu to make more complex
  menu interfaces
- Add all examples from Brython website?


## References

- Game libraries
  - pixi.js
      - https://waelyasmina.net/articles/pixi-js-tutorial-for-complete-beginners/
  - https://ggame.readthedocs.io/en/latest/introduction.html
  - phaser.js
- Sound:
  - https://tonejs.github.io/
  - https://buzz.jaysalvat.com/ for audio
  - pixi-sound.js
- For oauth server for github:
  - https://sphaerula.com/blog/posts/wsgi-and-cgi-apps-in-a-dreamhost-shared-hosting-account/
    - Seems that running python as cgi is still working and dead
      simple
    - And, from https://docs.python.org/2/howto/webservers.html shows
      how to enable nice debugging
