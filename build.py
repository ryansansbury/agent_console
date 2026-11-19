"""Build the Agent Console page from the recorded sessions.

    python3 build.py              the real page from data/runs/, or the preview when nothing is recorded yet
    python3 build.py --preview    the development preview from the scripted stand-in, labeled in red

The real build loads every recorded run and checks it again (the chain, every call re-decided by the policy, the
budgets, and the run made under today's policy), scores it against the key, and writes site/data.js, site/index.html
and site/code.js, plus evals/scores.json. It stops if a stage changed since it was frozen, if the sanitizer's scan finds
anything from this machine in a recording, if a word from the never list, another demo's name or a real company from
the avoid list reaches anything that ships, or if the copy lint flags the page's words or the policy's labels. Standard
library only, so it runs on any Python from 3.9 on.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from agents import replay  # noqa: E402
from app import bundle, code_view, never, page, readme, words  # noqa: E402
from evals import freeze  # noqa: E402

SITE = HERE.joinpath("site")
FONTS = ("inter-latin.woff2", "jetbrains-mono-latin.woff2", "Inter-LICENSE.txt", "JetBrainsMono-OFL.txt")
SHIPS = ("index.html", "app.css", "app.js", "policy.js", "audit.js", "data.js", "code.js")
LINT = HERE.joinpath("tools", "lint_copy.py")
WEIGHT = 1_000_000
# The docs that ship, each read by the copy lint as a page of its own.
LINTED = ("README.md", "docs/DECISIONS.md", "fixtures/README.md", "owner/README.md")


def lint(paths, page=False):
    """The copy lint in strict mode, when the private tool is here. The public repo doesn't carry it, so a clean clone
    builds without it. With page set, the files are read as one page and a phrase of five words may show up once."""
    if not LINT.exists():
        return []
    extra = ["--repeats"] if page else []
    done = subprocess.run([sys.executable, str(LINT), "--strict"] + extra + [str(p) for p in paths],
                          capture_output=True, text=True, cwd=str(HERE))
    if done.returncode == 0:
        return []
    return [line for line in done.stdout.splitlines() if line.strip()][:20]


def policy_words(pol):
    """The policy's labels and reasons as a file the lint can read, since they show on the page."""
    path = HERE.joinpath(".cache", "tmp", "policy_words.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(f"{r['why']}" for r in pol["rules"]) + "\n", encoding="utf-8")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the Agent Console page.")
    ap.add_argument("--preview", action="store_true", help="the scripted stand-in's preview, labeled")
    a = ap.parse_args(argv)
    t0 = time.time()
    w = words.load()
    missing = [f for f in FONTS if not SITE.joinpath("fonts", f).exists()]
    if missing:
        sys.exit(f"Stopped: site/fonts/ is missing {', '.join(missing)}.")
    preview = a.preview or not replay.runs()
    if not preview:
        for stage in ("stage1", "stage2"):
            if not freeze.ready(stage):
                sys.exit(f"Stopped: {stage} isn't frozen, or something in it changed since. Run python3 "
                         f"evals/freeze.py --check to see what.")
    try:
        data = bundle.build(w, preview=preview)
    except replay.Invalid as e:
        sys.exit(f"Stopped: {e}")
    sizes = {"data.js": bundle.write(data, SITE.joinpath("data.js"))}
    SITE.joinpath("index.html").write_text(page.render(w, data), encoding="utf-8")
    sizes["code.js"] = code_view.write(code_view.collect(), SITE.joinpath("code.js"))
    if not preview:
        from owner import sanitize
        problems = sanitize.scan(sanitize.recordings())
        if problems:
            sys.exit("Stopped by the sanitizer's scan: " + "; ".join(problems))
        scores = {"route": data["route"], "rows": data["rows"], "experiment": data["experiment"],
                  "budget_test": data["budget_test"]}
        HERE.joinpath("evals", "scores.json").write_text(json.dumps(scores, indent=1) + "\n", encoding="utf-8")
        readme.write(data)
    shipped = [SITE.joinpath(f) for f in SHIPS] + [HERE.joinpath("WORDS.md"), HERE.joinpath("config", "names.json"),
                                                   HERE.joinpath("README.md")]
    problems = never.scan(shipped)
    if problems:
        sys.exit("Stopped: " + "; ".join(problems))
    docs = sorted(HERE.joinpath("docs").glob("*.md")) + [HERE.joinpath("README.md"), HERE.joinpath("fixtures", "README.md"),
                                                          HERE.joinpath("owner", "README.md")]
    problems = never.scan(docs)
    if problems:
        sys.exit("Stopped: " + "; ".join(problems))
    flagged = lint([HERE.joinpath("WORDS.md"), policy_words(data["policy"])], page=True)
    for rel in LINTED:
        if HERE.joinpath(rel).exists():
            flagged += lint([HERE.joinpath(rel)], page=True)
    if flagged:
        sys.exit("Stopped by the copy lint:\n" + "\n".join(flagged))
    weight = sum(SITE.joinpath(f).stat().st_size for f in SHIPS if f != "code.js")
    if weight > WEIGHT:
        print(f"Note: the page weighs {weight / 1e6:.2f} MB without the code view, over the {WEIGHT / 1e6:.0f} MB aim.")
    kind = "the preview from the stand-in" if preview else "the page from the recordings"
    print(f"Built {kind} in {time.time() - t0:.2f} s ({weight / 1000:.0f} KB, the code view {sizes['code.js'] / 1000:.0f} KB).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
