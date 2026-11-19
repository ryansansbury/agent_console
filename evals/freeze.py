"""Freeze the jobs and the key, then the prompts and the scoring, so nothing scored is tuned after the fact.

    python3 evals/freeze.py stage1      before run 1: the fixtures, the tasks, the key, the names, the policy, the
                                        approvals, the jobs file, the reader and the policy engine
    python3 evals/freeze.py stage2      after tuning, before run 2: the system prompt, the tool schemas, the budgets
                                        and the code that scores
    python3 evals/freeze.py --check     list anything changed since it was frozen, and exit 1 if so

Each stage writes its hashes into evals/frozen.json once. Freezing a stage again needs --again, and the old hashes
move to "history" with the time, so a change after the fact shows. The recorder refuses run 1 until stage 1 and run 2
until stage 2, and build.py checks both before it shows a score. Standard
library only.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent.parent
FROZEN = HERE.joinpath("evals", "frozen.json")
NAMES = HERE.joinpath("config", "names.json")
STAGES = {
    "stage1": ["fixtures/**/*", "prompts/jobs/*.md", "data/key/**/*", "config/names.json", "config/policy.json",
               "config/approvals.json", "config/jobs.json", "engine/reader.py", "engine/policy.py"],
    "stage2": ["prompts/system.md", "config/tools.json", "config/budgets.json", "evals/score.py", "evals/key.py"],
}
SKIP = ("__pycache__", ".DS_Store")
DOCS = ("fixtures/README.md",)


def sha(path):
    """A file's hash. The policy's is taken over what decides a call, so its labels and reasons stay editable copy."""
    if path.name == "policy.json" and path.parent.name == "config":
        from engine.policy import decision_view
        view = decision_view(json.loads(path.read_text(encoding="utf-8")))
        return hashlib.sha256(json.dumps(view, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def files(stage):
    out = {}
    for pattern in STAGES[stage]:
        for p in sorted(HERE.glob(pattern)):
            rel = p.relative_to(HERE).as_posix()
            if p.is_file() and not any(s in rel for s in SKIP) and rel not in DOCS:
                out[rel] = sha(p)
    return out


def load():
    return json.loads(FROZEN.read_text(encoding="utf-8")) if FROZEN.exists() else {}


def now():
    return datetime.now(ZoneInfo("America/Los_Angeles")).isoformat(timespec="seconds")


def placeholder_names():
    """True when stage 1 was frozen before the cleared names landed, which only the dev round may run on."""
    return bool(load().get("placeholder_names"))


def freeze(stage, again=False, placeholder=False):
    data = load()
    if stage in data and not again:
        raise SystemExit(f"{stage} is already frozen at {data.get('at', {}).get(stage)}. Use --again to refreeze, and "
                         f"the old hashes go to history.")
    names_in = NAMES.exists()
    if stage == "stage1" and not names_in and not placeholder:
        raise SystemExit("Stage 1 holds the vendors' names, and config/names.json hasn't landed yet. "
                         "--placeholder-names freezes it for the dev round alone.")
    if stage == "stage1":
        data["placeholder_names"] = not names_in
    current = files(stage)
    if not current:
        raise SystemExit("Nothing to freeze.")
    if stage in data:
        data.setdefault("history", []).append({"stage": stage, "at": data.get("at", {}).get(stage),
                                               "replaced": now(), stage: data[stage]})
    data[stage] = current
    data.setdefault("at", {})[stage] = now()
    FROZEN.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return data


def changed(stage):
    """What differs from the frozen hashes for a stage, as (path, why). None when the stage isn't frozen."""
    data = load()
    if stage not in data:
        return None
    then, current = data[stage], files(stage)
    out = []
    for name in sorted(set(then) | set(current)):
        if name not in current:
            out.append((name, "removed"))
        elif name not in then:
            out.append((name, "added"))
        elif then[name] != current[name]:
            out.append((name, "changed"))
    return out


def ready(stage):
    """True when the stage is frozen and nothing in it has changed."""
    c = changed(stage)
    return c is not None and not c


def names_landed():
    """Freeze stage 1 again on the cleared names, when it was frozen on the placeholders and the names file is the one
    change since. Anything else that changed in stage 1 stops it. Returns the line to print."""
    data = load()
    if "stage1" not in data:
        raise SystemExit("Stage 1 isn't frozen yet.")
    c = changed("stage1")
    if not data.get("placeholder_names"):
        if not c:
            return "Stage 1 is already frozen on the cleared names."
        raise SystemExit("Stage 1 changed since it was frozen on the cleared names: "
                         + ", ".join(f"{why} {name}" for name, why in c))
    if c != [("config/names.json", "added")]:
        raise SystemExit("Stage 1 freezes again on the names only when the names file is the one change since the "
                         "placeholder freeze. Changed: " + (", ".join(f"{why} {name}" for name, why in c) or "nothing"))
    data = freeze("stage1", again=True)
    return f"Froze stage1 again on the cleared names at {data['at']['stage1']}: {len(data['stage1'])} hashes."


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("stage", nargs="?", choices=sorted(STAGES))
    ap.add_argument("--again", action="store_true", help="refreeze a stage, keeping the old hashes in history")
    ap.add_argument("--check", action="store_true", help="list changes since each stage was frozen")
    ap.add_argument("--placeholder-names", action="store_true",
                    help="freeze stage 1 before the cleared names land, for the dev round alone")
    ap.add_argument("--names-landed", action="store_true",
                    help="freeze stage 1 again on the cleared names when they are the one change since")
    a = ap.parse_args(argv)
    if a.names_landed:
        print(names_landed())
        return 0
    if a.check or not a.stage:
        bad = False
        for stage in sorted(STAGES):
            c = changed(stage)
            if c is None:
                print(f"{stage}: not frozen yet")
                continue
            print(f"{stage}: frozen {load()['at'][stage]}, {'unchanged' if not c else f'{len(c)} changed'}")
            for name, why in c:
                print(f"  {why}: {name}")
                bad = True
        return 1 if bad else 0
    data = freeze(a.stage, a.again, a.placeholder_names)
    note = " on the placeholder names, for the dev round alone" if a.stage == "stage1" and data.get("placeholder_names") else ""
    print(f"Froze {a.stage} at {data['at'][a.stage]}{note}: {len(data[a.stage])} hashes in evals/frozen.json")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    sys.exit(main())
