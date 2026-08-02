# Note: Brython 3.14 introduced a regression, something to do with lazy imports
# that prevents local loading (turns imports into AJAX calls maybe)

# Brython sources:
#    https://raw.githack.com/brython-dev/brython/master/www/src/brython.js \
#    https://cdn.jsdelivr.net/npm/brython@3.13.2/brython.min.js \
#    https://cdn.jsdelivr.net/npm/brython@3.13.2/brython_stdlib.js \
#    https://cdnjs.cloudflare.com/ajax/libs/brython/3.14.0/brython.min.js \
#    https://cdnjs.cloudflare.com/ajax/libs/brython/3.14.0/brython_stdlib.min.js \
#    https://raw.githack.com/brython-dev/brython/master/www/src/brython.js \
#    https://raw.githack.com/brython-dev/brython/master/www/src/brython_stdlib.js \

# Build/test scripts are stdlib-only, but need Python 3.10+ (pywebedit.py uses
# PEP 604 `str | None`). uv fetches the interpreter on demand; no venv required.
PY_VERSION = 3.13
PY ?= uv run --no-project --python $(PY_VERSION) python

JS_DEPS = \
    https://cdn.jsdelivr.net/npm/brython@3.13.2/brython.min.js \
    https://cdn.jsdelivr.net/npm/brython@3.13.2/brython_stdlib.js \
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
	$(PY) utils/tagreplace.py pywebedit.html_template "<script type=\"text/python\">" "</script>" pywebedit.py -o $@

dist/dev.html: pywebedit.py dev.html_template
	mkdir -p dist
	$(PY) utils/tagreplace.py dev.html_template "<script type=\"text/python\">" "</script>" pywebedit.py -o $@

dist/pywebeditor.min.js: pywebeditor/package.json pywebeditor/editor.mjs pywebeditor/rollup.config.js
	mkdir -p dist
	cd pywebeditor && npm run build
	ls -al $@

dist/examples.js: examples.py
	mkdir -p dist
	$(PY) examples.py $@

# Generic rule for downloading JS files
dist/%.js:
	mkdir -p dist
	cd dist && curl -O $(filter %/$(notdir $@),$(JS_DEPS))

# # Specific rule for minifying brython if you are getting the development version.
# # Install terser with npm install terser -g
# dist/brython.min.js: dist/brython.js
#  	terser dist/brython.js --compress -o dist/brython.min.js

# Generic rule for downloading CSS files
dist/%.css:
	mkdir -p dist
	cd dist && curl -O $(filter %/$(notdir $@),$(CSS_DEPS))

dist/pywebedit.zip: dist/pywebedit.html dist/pywebeditor.min.js dist/examples.js $(ALL_DIST_FILES)
	cd dist && zip pywebedit.zip pywebedit.html pywebeditor.min.js examples.js $(ALL_FILES)

dist/index.html: dist/pywebedit.html
	cd dist && cp pywebedit.html index.html

dist: dist/index.html dist/dev.html dist/pywebedit.zip

# ---- Tests ----------------------------------------------------------------
# Tier 1 (logic) needs only Python 3.10+. Tier 2 (browser, via Playwright)
# needs the isolated env below, plus a built dist/. See test/ and the README.

TEST_VENV = test/.venv
TEST_PY   = $(TEST_VENV)/bin/python

.PHONY: test test-logic test-setup

# Full suite (logic + browser). Builds dist/ and the test env on demand.
test: dist $(TEST_VENV)
	$(TEST_PY) test/run.py

# Only the zero-dependency logic tests -- no Playwright, no dist/ needed.
test-logic:
	$(PY) test/run.py --logic-only

# Create the isolated test virtualenv and install Playwright + its browser.
test-setup: $(TEST_VENV)

$(TEST_VENV): test/pyproject.toml
	uv venv $(TEST_VENV) --python $(PY_VERSION)
	uv pip install --python $(TEST_PY) playwright
	$(TEST_PY) -m playwright install chromium
	touch $(TEST_VENV)
