all: dist

.PHONY: dist clean

clean:
	rm -rf dist

pywebedit.html: pywebedit.py
	python utils/tagreplace.py -i $@ "<script type=\"text/python\">" "</script>" $<

dev.html: pywebedit.py
	python utils/tagreplace.py -i $@ "<script type=\"text/python\">" "</script>" $<

dist/pywebeditor.min.js: pywebeditor/package.json pywebeditor/editor.mjs pywebeditor/rollup.config.js
	cd pywebeditor && npm run build
	ls -al $@

dist/brython.min.js:
	cd dist && curl -O https://cdn.jsdelivr.net/npm/brython@3.13.0/brython.min.js

dist/brython_stdlib.js:
	cd dist && curl -O https://cdn.jsdelivr.net/npm/brython@3.13.0/brython_stdlib.js

dist/pywebedit.zip: pywebedit.html dist/pywebeditor.min.js dist/brython.min.js dist/brython_stdlib.js
	cd dist && zip pywebedit.zip ../pywebedit.html brython.min.js brython_stdlib.js pywebeditor.min.js

dist: pywebedit.html dist/pywebedit.zip
	cp pywebedit.html dist/index.html
