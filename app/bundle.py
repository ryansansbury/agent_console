"""The page's data: each model's morning as four lanes of events, the audit chains, the policy, the experiment, the
budget test and the scores. It's written to site/data.js as window.AC, and the page reads nothing else.

A real build reads the recorded runs under data/runs/. A development preview runs the stand-in in the session and
labels the page in red, and the export refuses it. Every event gets its time on the morning's clock, outputs are cut to
what the page shows (the full ones stay in the recordings, which ship in the repo), and the quarantine carries the two
excerpts the page sets side by side: what the page said and what the agent was given.
"""
import json
from datetime import datetime
from pathlib import Path

from agents import replay
from engine.reader import CUT_MARK
from evals import score
from generate import fixtures

HERE = Path(__file__).resolve().parent.parent
OUTPUT_CHARS, TEXT_CHARS, ARG_CHARS = 1400, 700, 600
KINDS = ("model", "call", "cut", "masked", "budget", "end", "bad-call")


def clip(text, n):
    text = str(text or "")
    if len(text) <= n:
        return text
    head = int(n * 0.7)
    return text[:head] + "\n…\n" + text[-(n - head - 3):]


def excerpt(text, needles, around=1):
    """The lines of text holding any of the needles, with a line of context before each."""
    lines = (text or "").splitlines()
    keep = set()
    for i, line in enumerate(lines):
        if any(n and n in line for n in needles):
            keep.update(range(max(0, i - around), i + 1))
    return "\n".join(lines[i] for i in sorted(keep))


def slim_args(name, args):
    if name == "write_file":
        return {"path": args.get("path"), "bytes": len(str(args.get("content", "")).encode("utf-8"))}
    if name == "edit_file":
        return {"path": args.get("path"), "old": clip(args.get("old"), ARG_CHARS), "new": clip(args.get("new"), ARG_CHARS)}
    return {k: clip(v, ARG_CHARS) for k, v in (args or {}).items()}


def slim_event(e, start_ms):
    out = {"seq": e["seq"], "kind": e["kind"], "at_ms": start_ms + e["t_ms"], "audit": e.get("audit", [])}
    k = e["kind"]
    if k == "model":
        u = e.get("usage") or {}
        out.update(text=clip(e.get("text"), TEXT_CHARS), cost_micro=e.get("cost_micro", 0), ms=e.get("ms", 0),
                   tokens_in=u.get("input", 0) + u.get("cache_write", 0) + u.get("cache_read", 0),
                   tokens_out=u.get("output", 0), calls=len(e.get("calls") or []))
    elif k == "call":
        out.update({f: e.get(f) for f in ("tool", "name", "target", "verdict", "rule", "stop", "answer", "ran",
                                          "refused", "exit_code", "masked", "facts", "call_id")})
        out["args"] = slim_args(e.get("name"), e.get("args"))
        out["output"] = clip(e.get("output"), OUTPUT_CHARS)
    elif k == "cut":
        cuts = [c["text"] for c in e.get("cuts") or []]
        out.update(url=e.get("url"), on=e.get("on", True), cuts=cuts, call_id=e.get("call_id"),
                   rules=sorted({r for c in e.get("cuts") or [] for r in c.get("rules", [])}),
                   said=excerpt(e.get("raw_text"), cuts) if cuts else "",
                   given=excerpt(e.get("given"), [CUT_MARK]) if cuts else "")
    elif k == "masked":
        out.update(target=e.get("target"), count=e.get("count", 1))
    elif k == "budget":
        out.update(level=e.get("level"), reason=e.get("reason"), spent_micro=e.get("spent_micro"),
                   limit_micro=e.get("limit_micro"))
    elif k == "end":
        out.update(state=e.get("state"), reply=clip(e.get("reply"), TEXT_CHARS * 2), detail=e.get("detail"))
    elif k == "bad-call":
        out.update(name=e.get("name"))
    return out


def clock_start(sessions):
    """(seconds after midnight when the morning began, its weekday and date), from the first session's start."""
    first = min(sessions, key=lambda s: s.get("offset_ms", 0))
    at = datetime.fromisoformat(first["recorded"])
    seconds = at.hour * 3600 + at.minute * 60 + at.second - first.get("offset_ms", 0) // 1000
    return seconds, f"{at.strftime('%A')} {at.month}/{at.day}"


def lane(session, scored, jobs):
    start = session.get("offset_ms", 0)
    events = [slim_event(e, start) for e in session["events"] if e["kind"] in KINDS]
    end = session.get("end") or {}
    return {"job": session["job"], "kind": jobs[session["job"]]["kind"], "state": end.get("state"),
            "reply": clip(end.get("reply"), TEXT_CHARS * 2), "detail": end.get("detail"), "task": session.get("task"),
            "start_ms": start, "end_ms": start + (session.get("totals") or {}).get("ms", 0),
            "cost_micro": (session.get("totals") or {}).get("cost_micro", 0),
            "budget_micro": (session.get("settings") or {}).get("budget_micro", 0),
            "tools": (session.get("settings") or {}).get("tools", []), "status": scored["task"]["status"],
            "checks": scored["task"]["checks"], "events": events}


def morning(run, cast, models_by_id):
    sessions = [run["sessions"][j] for j in ("parser-lib", "billing-export", "pricing-research", "infra-scripts")
                if j in run["sessions"]]
    jobs = {j["id"]: j for j in fixtures.jobs()["jobs"]}
    scored = {s["job"]: score.score_session(s, cast) for s in sessions}
    lanes = [lane(s, scored[s["job"]], jobs) for s in sessions]
    start_s, date = clock_start(sessions)
    model_id = sessions[0]["model"]["id"]
    return {"model": model_id, "label": models_by_id.get(model_id, sessions[0]["model"]).get("label", model_id),
            "date": date, "start_clock_s": start_s, "span_ms": max(l["end_ms"] for l in lanes),
            "lanes": lanes, "audit": run["audit"], "cost_micro": sum(l["cost_micro"] for l in lanes),
            "scores": scored, "bars": score.bars(scored)}


def model_row(m):
    lanes = m["lanes"]
    counts = {k: sum(m["scores"][l["job"]]["events"][k] for l in lanes) for k in
              ("calls", "allowed", "asked", "denied", "quarantined", "masked")}
    return dict(counts, model=m["model"], label=m["label"], cost_micro=m["cost_micro"],
                ms=max(l["end_ms"] for l in lanes) - min(l["start_ms"] for l in lanes),
                done=sum(1 for l in lanes if l["status"] == "done"),
                safe_stops=sum(1 for l in lanes if l["status"] == "safe-stop"),
                unsafe=sum(len(m["scores"][l["job"]]["unsafe"]) for l in lanes), bars=m["bars"],
                cleared=all(m["bars"].values()))


def from_runs(cast, w):
    """The real build's data from data/runs/. Raises replay.Invalid when a run fails its checks."""
    pol = json.loads(fixtures.render(HERE.joinpath("config", "policy.json").read_text(encoding="utf-8"), cast))
    models_cfg = json.loads(HERE.joinpath("config", "models.json").read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in models_cfg["models"]}
    found = replay.runs()
    mornings, experiment, budget_test, runs_table = {}, [], None, []
    for (model_id, kind), folder in sorted(found.items()):
        run = replay.load_run(folder)
        problems = replay.check(run, pol)
        if problems:
            raise replay.Invalid(f"{model_id} {kind}: " + "; ".join(problems))
        for s in run["sessions"].values():
            sc = score.score_session(s, cast)
            runs_table.append({"date": s["recorded"][:10], "model": by_id.get(model_id, {}).get("label", model_id),
                               "run": kind, "job": s["job"], "state": (s.get("end") or {}).get("state"),
                               "calls": s["totals"].get("tool_calls", 0), "cost_micro": s["totals"].get("cost_micro", 0)})
            if kind == "reader-off":
                experiment.append(dict(sc["injection"], model=model_id, label=by_id.get(model_id, {}).get("label")))
            if kind == "budget":
                budget_test = dict(sc["budget"], model=model_id, label=by_id.get(model_id, {}).get("label"),
                                   job=s["job"])
        if kind == "morning":
            mornings[model_id] = morning(run, cast, by_id)
    return pol, mornings, experiment, budget_test, runs_table


def from_preview(cast):
    from owner import stand_in
    pol = json.loads(fixtures.render(HERE.joinpath("config", "policy.json").read_text(encoding="utf-8"), cast))
    sessions, chain = stand_in.preview(cast)
    run = {"sessions": {s["job"]: s for s in sessions}, "audit": {"entries": chain.entries, "head": chain.head()},
           "meta": {}}
    problems = replay.check(run, pol)
    if problems:
        raise replay.Invalid("the preview: " + "; ".join(problems))
    m = morning(run, cast, {"stand-in": stand_in.MODEL})
    runs_table = [{"date": s["recorded"][:10], "model": stand_in.MODEL["label"], "run": "preview", "job": s["job"],
                   "state": s["end"]["state"], "calls": s["totals"]["tool_calls"], "cost_micro": s["totals"]["cost_micro"]}
                  for s in sessions]
    return pol, {"stand-in": m}, [], None, runs_table


def build(w, preview=False):
    cast = fixtures.names(placeholder_ok=preview)
    pol, mornings, experiment, budget_test, runs_table = from_preview(cast) if preview else from_runs(cast, w)
    if not mornings:
        raise replay.Invalid("there are no recorded mornings yet, so build the preview with --preview")
    rows = {m: model_row(v) for m, v in mornings.items()}
    route = score.route({m: {"bars": r["bars"], "cost_micro": r["cost_micro"]} for m, r in rows.items()})
    for m in mornings.values():
        m.pop("scores", None)
    return {"preview": preview, "built": datetime.now().strftime("%Y-%m-%d"), "policy": pol,
            "names": {v["id"]: {"name": v["name"], "domain": v["domain"]} for v in cast["vendors"]},
            "outside_domain": cast["outside_domain"], "route": route,
            "models": [{"id": m, "label": mornings[m]["label"]} for m in mornings], "mornings": mornings,
            "rows": rows, "experiment": experiment, "budget_test": budget_test, "runs": runs_table, "ui": w.ui()}


def write(data, path=None):
    path = Path(path or HERE.joinpath("site", "data.js"))
    path.write_text("window.AC = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
                    encoding="utf-8")
    return path.stat().st_size
