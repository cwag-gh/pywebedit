JS_DEPS = \
    https://cdn.jsdelivr.net/npm/brython@3.13.1/brython.min.js \
    https://cdn.jsdelivr.net/npm/brython@3.13.1/brython_stdlib.js \
    https://pixijs.download/v8.9.1/pixi.min.js \
    https://unpkg.com/@pixi/sound@6.0.1/dist/pixi-sound.js

CSS_DEPS = \
    https://cdn.jsdelivr.net/npm/@picocss/pico@1/css/pico.min.css

# Extract just the filenames for local use
JS_FILES = $(notdir $(JS_DEPS))
CSS_FILES = $(notdir $(CSS_DEPS))
ALL_FILES = $(JS_FILES) $(CSS_FILES)

# Full paths in dist for dependencies
JS_DIST_FILES = $(addprefix dist/,$(JS_FILES))
CSS_DIST_FILES = $(addprefix dist/,$(CSS_FILES))
ALL_DIST_FILES = $(JS_DIST_FILES) $(CSS_DIST_FILES)

all: dist

.PHONY: dist clean

clean:
	rm -rf dist

dist/pywebedit.html: pywebedit.py pywebedit.html_template
	python utils/tagreplace.py pywebedit.html_template "<script type=\"text/python\">" "</script>" pywebedit.py -o $@

dist/dev.html: pywebedit.py dev.html_template
	python utils/tagreplace.py dev.html_template "<script type=\"text/python\">" "</script>" pywebedit.py -o $@

dist/pywebeditor.min.js: pywebeditor/package.json pywebeditor/editor.mjs pywebeditor/rollup.config.js
	cd pywebeditor && npm run build
	ls -al $@

# Generic rule for downloading JS files
dist/%.js:
	mkdir -p dist
	cd dist && curl -O $(filter %/$(notdir $@),$(JS_DEPS))

# Generic rule for downloading CSS files
dist/%.css:
	mkdir -p dist
	cd dist && curl -O $(filter %/$(notdir $@),$(CSS_DEPS))

dist/pywebedit.zip: dist/pywebedit.html dist/pywebeditor.min.js $(ALL_DIST_FILES)
	cd dist && zip pywebedit.zip pywebedit.html pywebeditor.min.js $(ALL_FILES)

dist/index.html: dist/pywebedit.html
	cd dist && cp pywebedit.html index.html

dist: dist/index.html dist/dev.html dist/pywebedit.zip

