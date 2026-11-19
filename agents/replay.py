"""Load the recorded runs and check them again before the page or the scores use them.

A run folder (data/runs/<model>/<run>/) holds one file per session, audit.json with the chain and its head, and
morning.json with what the run was made under. check() finds every way a run could mislead:
- a session missing a field the page reads, or events out of order;
- a call that engine/policy.py, deciding again on the recorded facts under the policy the run used, doesn't decide the
  same way (verdict, rule and stop);
- a chain that doesn't verify against its head, or an event pointing at an audit entry that isn't there;
- a session that spent past its budget;
- a run made under a policy other than the one this build holds, which makes it stale.
The build stops on any of them. The sanitizer's scan of the files runs beside this, in the build and in the export.
"""
import hashlib
import json
from pathlib import Path

from engine import audit, policy

HERE = Path(__file__).resolve().parent.parent
RUNS = HERE.joinpath("data", "runs")
NEEDED = ("schema", "job", "run", "model", "recorded", "settings", "events", "end", "totals")


class Invalid(Exception):
    pass


def policy_hash(pol):
    """The hash of what decides a call, so a reworded label or reason never makes a run stale."""
    view = policy.decision_view(pol)
    return hashlib.sha256(json.dumps(view, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def load_run(folder):
    folder = Path(folder)
    sessions = {}
    for p in sorted(folder.glob("*.json")):
        if p.name in ("audit.json", "morning.json"):
            continue
        record = json.loads(p.read_text(encoding="utf-8"))
        sessions[record["job"]] = record
    chain = json.loads(folder.joinpath("audit.json").read_text(encoding="utf-8"))
    meta_path = folder.joinpath("morning.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    return {"folder": str(folder), "sessions": sessions, "audit": chain, "meta": meta}


def runs(root=None):
    """{(model id, run kind): run folder} for every recorded run."""
    root = Path(root or RUNS)
    out = {}
    if root.exists():
        for folder in sorted(root.glob("*/*")):
            if folder.joinpath("audit.json").exists():
                out[(folder.parent.name, folder.name)] = folder
    return out


def check(run, pol):
    problems = []
    entries = run["audit"].get("entries", [])
    v = audit.verify(entries, run["audit"].get("head"))
    if not v["ok"]:
        problems.append(f"the audit chain fails at entry {v['failed_at']} ({v['why']})")
    seqs = {e["seq"] for e in entries}
    if run["meta"].get("policy_hash") and run["meta"]["policy_hash"] != policy_hash(pol):
        problems.append("the run was made under a different policy, so it's stale")
    for job, s in run["sessions"].items():
        missing = [k for k in NEEDED if k not in s]
        if missing:
            problems.append(f"{job}: missing {', '.join(missing)}")
            continue
        if [e["seq"] for e in s["events"]] != list(range(1, len(s["events"]) + 1)):
            problems.append(f"{job}: the events are out of order")
        for e in s["events"]:
            if any(a not in seqs for a in e.get("audit", [])):
                problems.append(f"{job}: event {e['seq']} points at an audit entry that isn't in the chain")
            if e["kind"] == "call" and e.get("facts"):
                d = policy.decide(e["facts"], pol)
                if (d["verdict"], d["rule"], d["stop"]) != (e["verdict"], e["rule"], e["stop"]):
                    problems.append(f"{job}: call {e['seq']} was recorded as {e['verdict']} under {e['rule']}, and "
                                    f"the policy decides {d['verdict']} under {d['rule']}")
        if s["totals"].get("cost_micro", 0) > s["settings"].get("budget_micro", 0):
            problems.append(f"{job}: spent past its budget")
    return problems
