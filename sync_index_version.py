#!/usr/bin/env python3
"""Sync index.html's version footer to generate.py's APP_VERSION.

index.html is intentionally kept outside the live app's regeneration
pipeline (it's landing-page content, deployed manually, not draft data --
see DEPLOY.md), so it can't inherit the version automatically the way the
three board pages do on every pick. This script is the deliberate
alternative: run it after bumping APP_VERSION in generate.py and it keeps
index.html in sync via a real substitution instead of a hand-typed edit
that's easy to get wrong or forget (which is exactly what happened once
already -- index.html was left one version behind after a change that
didn't touch its content).

index.html and generate.py can live on different git branches (board-repo:
index.html is on main, generate.py is on v2-live-app), so this can't always
just `import generate` -- it first tries that (works when both files sit in
the same plain directory, e.g. the sandbox test copies), and falls back to
reading APP_VERSION out of `git show v2-live-app:generate.py` without
needing that branch checked out, when run inside a git repo that has it.

Usage: python3 sync_index_version.py [path-to-index.html]
Defaults to index.html next to this script.
"""
import re
import sys
import os
import subprocess

def get_app_version(base_dir):
    try:
        sys.path.insert(0, base_dir)
        from generate import APP_VERSION
        return APP_VERSION
    except ImportError:
        pass

    try:
        content = subprocess.run(
            ["git", "-C", base_dir, "show", "v2-live-app:generate.py"],
            capture_output=True, text=True, check=True,
        ).stdout
        m = re.search(r'APP_VERSION\s*=\s*"([\d.]+)"', content)
        if m:
            return m.group(1)
    except subprocess.CalledProcessError:
        pass

    print("ERROR: could not determine APP_VERSION (no local generate.py and no "
          "v2-live-app:generate.py via git)", file=sys.stderr)
    sys.exit(1)

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    index_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base_dir, "index.html")

    app_version = get_app_version(base_dir)

    content = open(index_path).read()
    pattern = r"(TBML Draft Tool &middot; v)[\d.]+"
    new_content, n = re.subn(pattern, r"\g<1>" + app_version, content)

    if n == 0:
        print(f"ERROR: version footer pattern not found in {index_path}", file=sys.stderr)
        sys.exit(1)
    if n > 1:
        print(f"WARNING: {n} occurrences replaced (expected 1) in {index_path}", file=sys.stderr)

    if new_content == content:
        print(f"{index_path}: already at v{app_version}, no change")
    else:
        open(index_path, "w").write(new_content)
        print(f"{index_path}: synced to v{app_version}")

if __name__ == "__main__":
    main()
