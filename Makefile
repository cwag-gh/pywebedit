all: pywebedit.html editor.bundle.min.js

.PHONY: server dist clean

WEBSERVER := $(shell cat webserver.txt)

clean:
	rm editor.bundle.min.js

pywebedit.html: pywebedit.py
	python utils/tagreplace.py -i $@ "<script type=\"text/python\">" "</script>" $<

dev.html: pywebedit.py
	python utils/tagreplace.py -i $@ "<script type=\"text/python\">" "</script>" $<

server:
	python -m http.server

editor.bundle.min.js: pywebeditor/package.json pywebeditor/editor.mjs pywebeditor/rollup.config.js
	cd pywebeditor && npm run build
	ls -al $@

# Download monolithic working single file
# TODO: bundle examples
dist:
    monolith $(WEBSERVER)/pywebedit/ -o dist/pywebedit.html