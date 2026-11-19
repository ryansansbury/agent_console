#!/bin/bash
# The owner's machine only, a few minutes. Builds the page (the real one from the recordings, or the labeled preview
# when nothing is recorded yet), then opens it in headless Chrome with a fresh profile, from the file system and from a
# server on 127.0.0.1 at a free port, and takes every view, state and tour step at desktop, tablet and phone widths plus
# the 1600 by 1000 card. It checks the line rule, overlaps, console errors and network requests. Results land in
# owner/out/, and the session reads owner/out/browser_check.json and the shots.
# Run from the build folder:   bash owner/screenshots.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python3
[ -x "$PY" ] || PY=python3
"$PY" build.py "$@"
"$PY" owner/browser_check.py
