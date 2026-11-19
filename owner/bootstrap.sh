#!/bin/bash
# The owner's machine only, once, under a minute. Creates .venv from Homebrew's Python with nothing installed, since the
# build, the recorder and the selftest use only the standard library, and checks that git and node are there. The
# agents' commands run with this Python, so its version is the one the recordings name.
# Run from the build folder:   bash owner/bootstrap.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PY=""
for cand in /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if [ -x "$cand" ]; then
    PY="$cand"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "Installing Python with Homebrew..."
  brew install python
  PY="$(brew --prefix)/bin/python3"
fi
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { echo "Python 3.10 or newer is needed."; exit 1; }
if [ ! -x .venv/bin/python3 ]; then
  "$PY" -m venv .venv
fi
command -v git >/dev/null 2>&1 || { echo "git is missing. Install the Xcode command line tools, then run this again."; exit 1; }
command -v node >/dev/null 2>&1 || echo "node is missing, so the page checks in the tests will fail. Install it with: brew install node"
echo "Ready: Python $(.venv/bin/python3 -c 'import sys; print(sys.version.split()[0])'), $(git --version)"
echo "Next: bash owner/keys.sh"
