#    https://cdn.jsdelivr.net/npm/brython@3.13.1/brython.min.js \
#    https://cdn.jsdelivr.net/npm/brython@3.13.1/brython_stdlib.js \

JS_DEPS = \
    https://raw.githack.com/brython-dev/brython/master/www/src/brython.js \
    https://raw.githack.com/brython-dev/brython/master/www/src/brython_stdlib.js \
    https://unpkg.com/pixi.js@8.9.2/dist/pixi.min.js \
    https://unpkg.com/@pixi/sound@6.0.1/dist/pixi-sound.js \
    https://cdnjs.cloudflare.com/ajax/libs/three.js/100/three.min.js

CSS_DEPS = \
    https://cdn.jsdelivr.net/npm/@picocss/pico@1/css/pico.min.css

# Extract just the filenames for local use
JS_FILES = $(notdir $(JS_DEPS))
JS_FILES_NO_BRYTHON = $(filter-out brython.js, $(notdir $(JS_DEPS))) brython.min.js
CSS_FILES = $(notdir $(CSS_DEPS))
# Allow option to retrieve brython.js, but bundle brython.min.js
ALL_FILES = $(JS_FILES_NO_BRYTHON) $(CSS_FILES)

# Full paths in dist for dependencies
JS_DIST_FILES = $(addprefix dist/,$(JS_FILES_NO_BRYTHON))
CSS_DIST_FILES = $(addprefix dist/,$(CSS_FILES))
ALL_DIST_FILES = $(JS_DIST_FILES) $(CSS_DIST_FILES)

all: dist

.PHONY: dist clean

clean:
	rm -rf dist

dist/pywebedit.html: pywebedit.py pywebedit.html_template
	mkdir -p dist
	python utils/tagreplace.py pywebedit.html_template "<script type=\"text/python\">" "</script>" pywebedit.py -o $@

dist/dev.html: pywebedit.py dev.html_template
	mkdir -p dist
	python utils/tagreplace.py dev.html_template "<script type=\"text/python\">" "</script>" pywebedit.py -o $@

dist/pywebeditor.min.js: pywebeditor/package.json pywebeditor/editor.mjs pywebeditor/rollup.config.js
	mkdir -p dist
	cd pywebeditor && npm run build
	ls -al $@

dist/examples.js: examples.py
	mkdir -p dist
	python examples.py $@

# Generic rule for downloading JS files
dist/%.js:
	mkdir -p dist
	cd dist && curl -O $(filter %/$(notdir $@),$(JS_DEPS))

# Specific rule for minifying brython if you are getting the development version.
# Install terser with npm install terser -g
dist/brython.min.js: dist/brython.js
	terser dist/brython.js --compress -o dist/brython.min.js

# Generic rule for downloading CSS files
dist/%.css:
	mkdir -p dist
	cd dist && curl -O $(filter %/$(notdir $@),$(CSS_DEPS))

dist/pywebedit.zip: dist/pywebedit.html dist/pywebeditor.min.js dist/examples.js $(ALL_DIST_FILES)
	cd dist && zip pywebedit.zip pywebedit.html pywebeditor.min.js examples.js $(ALL_FILES)

dist/index.html: dist/pywebedit.html
	cd dist && cp pywebedit.html index.html

dist: dist/index.html dist/dev.html dist/pywebedit.zip
