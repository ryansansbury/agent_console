#!/bin/bash
# The owner's machine only. The recordings in two runs, with a stop for the session between them. Each is safe to
# start again, since a finished run that matches today's files is skipped and an unfinished one keeps nothing.
#
#   bash owner/run.sh 1   the selftest (no model, a few minutes), then a dev morning for each model (about 15
#                         minutes). The selftest has to pass before any model is called. A model already in the
#                         latest dev round under today's files is skipped, so a rerun records only what's missing.
#                         Once the budget test has a limit, the round also tries it once on Sonnet's parser-lib.
#   bash owner/run.sh 2   after the session freezes stage 2, everything else in one go (about 30 minutes): the
#                         vendors' names when they're missing (a private step on the owner's machine), their check,
#                         stage 1 frozen again on them, the selftest on them, a morning for each model, the research
#                         job with the reader off, the budget test, the real build, and the browser check
#
# Run from the build folder:   bash owner/run.sh 1
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python3
[ -x "$PY" ] || { echo "Run bash owner/bootstrap.sh first."; exit 1; }
say() { printf '\n== %s\n' "$*"; }

case "${1:-}" in
  1)
    say "The selftest, with no model"
    "$PY" owner/selftest.py
    say "A dev morning for each model"
    "$PY" owner/record.py --run dev
    printf '\nRun 1 is done. Tell the session "run 1 done."\n'
    ;;
  2)
    if [ ! -f config/names.json ]; then
      if [ -f tools/get_names.py ]; then
        say "The vendors' names, from the private names step"
        "$PY" tools/get_names.py
      else
        echo "config/names.json is missing, and run 2 needs it."
        exit 1
      fi
    fi
    say "The names' check"
    "$PY" owner/check_names.py
    say "Stage 1 on the names"
    "$PY" evals/freeze.py --names-landed
    say "The selftest on the names, with no model"
    "$PY" owner/selftest.py
    say "A morning for each model"
    "$PY" owner/record.py --run morning
    say "The research job with the reader off"
    "$PY" owner/record.py --run reader-off
    say "The budget test"
    "$PY" owner/record.py --run budget
    say "The real build"
    "$PY" build.py
    say "The browser check"
    "$PY" owner/browser_check.py || echo "The browser check found things for the session to fix."
    printf '\nRun 2 is done. Tell the session "run 2 done."\n'
    ;;
  *)
    echo "Usage: bash owner/run.sh 1|2"
    exit 1
    ;;
esac
