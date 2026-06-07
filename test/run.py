#!/usr/bin/env python3
"""One entry point for the pywebedit test harness.

  Tier 1 (logic) -- zero dependencies, runs on any Python.
  Tier 2 (e2e)   -- needs Playwright; skips cleanly if it isn't installed.

Usage (from anywhere):
    test/.venv/bin/python test/run.py              # both tiers
    test/.venv/bin/python test/run.py --logic-only # Tier 1 only (no deps)
    test/.venv/bin/python test/run.py --e2e-only   # Tier 2 only
    test/.venv/bin/python test/run.py --build       # `make` dist/ first, then run
    python test/run.py --logic-only                 # Tier 1 on a bare interpreter

Exit code is 0 only if every selected test passed (skips don't fail the run).
"""

import argparse
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)


def _load(module_names):
    sys.path.insert(0, HERE)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in module_names:
        suite.addTests(loader.loadTestsFromModule(__import__(name)))
    return suite


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--logic-only", action="store_true", help="run only Tier 1 (zero-dependency) tests")
    group.add_argument("--e2e-only", action="store_true", help="run only Tier 2 (browser) tests")
    ap.add_argument("--build", action="store_true", help="run `make` in the repo root to (re)build dist/ first")
    ap.add_argument("-q", "--quiet", action="store_true", help="less verbose test output")
    args = ap.parse_args()

    if args.build:
        print("==> Building dist/ via make ...")
        subprocess.check_call(["make"], cwd=REPO_ROOT)

    modules = []
    if not args.e2e_only:
        modules.append("test_logic")
    if not args.logic_only:
        modules.append("test_e2e")

    print(f"==> Running: {', '.join(modules)}")
    suite = _load(modules)
    result = unittest.TextTestRunner(verbosity=1 if args.quiet else 2).run(suite)

    # Helpful nudge if the browser tier was skipped wholesale.
    skip_reasons = " ".join(reason for _, reason in result.skipped)
    if "playwright" in skip_reasons.lower():
        print(
            "\nNote: Tier 2 was skipped because Playwright isn't installed.\n"
            "      Install it into the isolated env with:\n"
            "        uv pip install --python test/.venv/bin/python playwright\n"
            "        test/.venv/bin/python -m playwright install chromium"
        )
    if "dist/" in skip_reasons:
        print("\nNote: Tier 2 was skipped because dist/ isn't built. Run: make  (or: python test/run.py --build)")

    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
