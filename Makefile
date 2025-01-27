JS_DEPS = \
    https://raw.githack.com/brython-dev/brython/master/www/src/brython.js \
    https://raw.githack.com/brython-dev/brython/master/www/src/brython_stblib.js \
    https://cdnjs.cloudflare.com/ajax/libs/pixi.js/8.6.6/pixi.min.js
#    https://cdn.jsdelivr.net/npm/brython@3.13.0/brython.min.js \
#    https://cdn.jsdelivr.net/npm/brython@3.13.0/brython_stdlib.js \


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

pywebedit.html: pywebedit.py
	python utils/tagreplace.py -i $@ "<script type=\"text/python\">" "</script>" $<

dev.html: pywebedit.py
	python utils/tagreplace.py -i $@ "<script type=\"text/python\">" "</script>" $<

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

dist/pywebedit.zip: pywebedit.html dist/pywebeditor.min.js $(ALL_DIST_FILES)
	cd dist && zip pywebedit.zip ../pywebedit.html pywebeditor.min.js $(ALL_FILES)

dist: pywebedit.html dist/pywebedit.zip dev.html
	cp pywebedit.html dist/index.html
	cp dev.html dist/dev.html
