"""The owner's machine only. Record the agents' sessions the page replays.

    python3 owner/record.py --run dev            a morning for each model on the tuning round (run 1)
    python3 owner/record.py --run morning        a morning for each model, for the page (run 2)
    python3 owner/record.py --run reader-off     the research job for each model with the reader off (run 2)
    python3 owner/record.py --run budget         the budget test (run 2)
    add --models claude-sonnet,openai-luna to pick models, --serial to run a morning's sessions one after another,
    and --again to record a run that already matches today's files

A morning is one model on its jobs at once: the fixture server starts on a free port, each job gets a fresh throwaway
workspace outside any repository, and the sessions run in threads that start at the times config/jobs.json gives,
with one audit chain recording them in the order things happened. After each session the key's checks run in its
workspace (the git log and diff, the project's tests, the key's hidden tests and the research notes), and the
workspace is deleted. Everything recorded passes the sanitizer before it's stored or hashed, the scan must come back
clean, and the run moves from owner/out/staging/ into data/ only when every session finished.

It refuses dev runs until stage 1 is frozen and the others until stage 2 is, checks the run's cap before each morning,
and skips a run whose files already match today's prompts, policy and fixtures.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from agents import llm, loop, replay  # noqa: E402
from engine import audit, reader  # noqa: E402
from engine.approvals import ScriptedApprover  # noqa: E402
from engine.budget import Budget  # noqa: E402
from engine.tools import GIT_FLAGS, Tools, cap, schemas  # noqa: E402
from evals import freeze  # noqa: E402
from generate import fixtures, validate  # noqa: E402
from owner import fixture_server, sanitize, workspaces  # noqa: E402

OUT = HERE.joinpath("owner", "out")
STAGING = OUT.joinpath("staging")
DIFF_CHARS, TEST_CHARS, NOTES_CHARS = 60000, 4000, 20000


def say(text):
    print(text, flush=True)


def key_for(service):
    done = subprocess.run(["security", "find-generic-password", "-s", service, "-w"], capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(f"No key saved as {service}. Run: bash owner/keys.sh")
    return done.stdout.strip()


def load(name):
    return json.loads(HERE.joinpath("config", name).read_text(encoding="utf-8"))


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def tree_hash(folder):
    h = hashlib.sha256()
    for p in sorted(HERE.joinpath(folder).rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(p.relative_to(HERE).as_posix().encode() + b"\0" + p.read_bytes())
    return h.hexdigest()[:16]


class Setup:
    """Everything a run is made under, read once."""

    def __init__(self, cast=None):
        self.cast = cast or fixtures.names()
        self.policy = json.loads(fixtures.render(HERE.joinpath("config", "policy.json").read_text(encoding="utf-8"),
                                                 self.cast))
        self.approvals, self.budgets, self.models = load("approvals.json"), load("budgets.json"), load("models.json")
        self.jobs = {j["id"]: j for j in fixtures.jobs()["jobs"]}
        self.system = HERE.joinpath("prompts", "system.md").read_text(encoding="utf-8")
        self.tasks = {j: fixtures.task(j, self.cast) for j in self.jobs}
        self.hashes = {"system_prompt": sha(self.system), "tools": sha(HERE.joinpath("config", "tools.json").read_text()),
                       "policy": replay.policy_hash(self.policy), "approvals": sha(json.dumps(self.approvals)),
                       "tasks": sha(json.dumps(self.tasks, sort_keys=True)), "fixtures": tree_hash("fixtures"),
                       "reader": sha(HERE.joinpath("engine", "reader.py").read_text()),
                       "budgets": sha(json.dumps(self.budgets, sort_keys=True))}
        self.clean = sanitize.Sanitizer()

    def model(self, model_id):
        for m in self.models["models"]:
            if m["id"] == model_id:
                return m
        raise SystemExit(f"No model {model_id} in config/models.json")


def run_tests(runner, ws, *args):
    code, out = runner(("python3", "-m", "unittest") + args, ws.real_project, ws.variables, 300)
    ran = validate.RAN.search(out)
    text, _ = ws.mask(ws.to_virtual(out))
    return {"ran": int(ran.group(1)) if ran else 0, "failed": sorted(set(validate.FAILED.findall(out))),
            "exit_code": code, "output": cap(text, TEST_CHARS)[0]}


def untracked_as_diff(ws, status):
    """New files the agent never added, written the way git diff would show them."""
    out = []
    for line in status.splitlines():
        if line.startswith("?? "):
            rel = line[3:].strip()
            path = ws.project.joinpath(rel)
            if path.is_file() and path.stat().st_size < 200000:
                body = path.read_text(encoding="utf-8", errors="replace").splitlines()
                out.append(f"+++ b/{rel}\n" + "\n".join("+" + b for b in body))
    return "\n".join(out)


def after_checks(ws, job, runner):
    def git(*args, cwd=None):
        return runner(("git",) + GIT_FLAGS + args, cwd or ws.real_project, ws.variables, 60)[1]

    log = git("log", "--format=%H%x09%s", f"{ws.initial_commit}..HEAD")
    commits = [{"hash": h[:12], "subject": s} for h, _, s in (ln.partition("\t") for ln in log.splitlines()) if s]
    status = git("status", "--porcelain")
    diff = git("diff", ws.initial_commit) + "\n" + untracked_as_diff(ws, status)
    changed = [n for n in git("diff", "--name-only", ws.initial_commit).splitlines() if n.strip()]
    changed += [ln[3:].strip() for ln in status.splitlines() if ln.startswith("?? ")]
    remote = git("--git-dir", "remote.git", "rev-parse", "main", cwd=ws.real_root).strip()
    after = {"git": {"initial": ws.initial_commit[:12], "commits": commits, "status": status, "changed": changed,
                     "remote_head": remote[:12], "diff": cap(ws.mask(ws.to_virtual(diff))[0], DIFF_CHARS)[0]},
             "own_tests": run_tests(runner, ws) if job["kind"] != "research" else None}
    hidden = HERE.joinpath("data", "key", job["id"])
    after["key_tests"] = None
    if hidden.is_dir():
        tests = ws.project.joinpath("key_tests")
        shutil.copytree(hidden, tests)
        tests.joinpath("__init__.py").write_text("", encoding="utf-8")
        after["key_tests"] = run_tests(runner, ws, "discover", "-s", "key_tests", "-t", ".")
    notes = ws.project.joinpath("notes", "pricing.md")
    after["notes"] = cap(notes.read_text(encoding="utf-8", errors="replace"), NOTES_CHARS)[0] if notes.exists() else None
    return after


class Real:
    """The real world for a run: programs through engine/process.py, workspaces in the temporary space, and the
    fixture server. Loaded only here, so importing this module starts nothing, and the session's test hands in fakes."""

    def __init__(self):
        from engine import process
        self.runner = process.run

    def make(self, job_id):
        return workspaces.make(job_id, runner=self.runner)

    def server(self, cast):
        server, port = fixture_server.start(cast)
        return server.shutdown, fixture_server.web_for(port)


def one_session(setup, job_id, entry, backend, run_kind, reader_on, budget_usd, chain, world, web, offset_s, results):
    job = setup.jobs[job_id]
    ws = None
    try:
        ws = world.make(job_id)
        limits = setup.budgets["limits"]
        tools = Tools(ws, setup.policy, ScriptedApprover(setup.approvals), runner=world.runner, web=web,
                      reader=lambda html, url: reader.read_page(html, url, on=reader_on),
                      fixture_hosts=fixtures.hosts(setup.cast), allowed=job["tools"], limits=limits,
                      clean=setup.clean.text)
        budget = Budget(budget_usd, entry["price"], setup.budgets["warn_at"])
        session = loop.Session(job_id, {k: entry[k] for k in ("id", "label", "vendor", "model")}, run_kind,
                               {"reader": "on" if reader_on else "off", "budget_micro": budget.limit,
                                "limits": limits, "tools": job["tools"]}, setup.tasks[job_id], chain=chain,
                               clean=setup.clean.value, offset_ms=round(offset_s * 1000))
        state = loop.run(backend, setup.system, setup.tasks[job_id], schemas(job["tools"]), tools, budget, session, limits)
        record = session.record()
        record["after"] = setup.clean.value(after_checks(ws, job, world.runner))
        record["hashes"] = setup.hashes
        results[job_id] = record
        say(f"  {entry['label']}, {job_id}: {state}, {record['totals']['tool_calls']} tool calls, "
            f"${record['totals']['cost_micro'] / 1e6:.4f}")
        if state == "error":
            say(f"    {setup.clean.text(record['end']['detail'])[:300]}")
    except Exception as e:
        results[job_id] = e
        say(f"  {entry['label']}, {job_id}: failed ({type(e).__name__}: {setup.clean.text(str(e))[:300]})")
    finally:
        if ws is not None:
            workspaces.destroy(ws)


def record_run(setup, entry, backend_factory, run_kind, job_ids, reader_on=True, budget_usd=None, serial=False,
               dest=None, world=None, stagger=1.0, staging=None):
    """One model's run of the given jobs. backend_factory(job_id) gives each session its own backend. Returns the
    run's spend in micro-dollars, or raises."""
    world = world or Real()
    stop_server, web = world.server(setup.cast)
    chain, results, threads = audit.Chain(), {}, []
    chain.append(at=time.strftime("%Y-%m-%dT%H:%M:%S"), session="", actor="console", action="begin",
                 target=f"policy {setup.hashes['policy']} prompt {setup.hashes['system_prompt']} "
                        f"fixtures {setup.hashes['fixtures']}")
    t0 = time.time()
    try:
        for job_id in job_ids:
            delay = 0 if serial else setup.jobs[job_id]["start_after_s"] * stagger
            args = (setup, job_id, entry, backend_factory(job_id), run_kind, reader_on,
                    budget_usd or setup.budgets["session_usd"], chain, world, web)
            if serial:
                one_session(*args, time.time() - t0, results)
            else:
                t = threading.Thread(target=_delayed, args=(delay, args, t0, results))
                t.start()
                threads.append(t)
        for t in threads:
            t.join()
    finally:
        stop_server()
    failed = [j for j, r in results.items() if isinstance(r, Exception)]
    # A session that ended on a model error shows the vendor's failure and not the agent's work, so it isn't kept.
    failed += [f"{j} ended on a model error" for j, r in results.items()
               if not isinstance(r, Exception) and r["end"]["state"] == "error"]
    if failed or len(results) != len(job_ids):
        raise SystemExit(f"The run didn't finish ({', '.join(failed) or 'missing sessions'}). Nothing was kept, and "
                         f"the same command runs it again.")
    stage = Path(staging or STAGING).joinpath(f"{entry['id']}-{run_kind}")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for job_id, record in results.items():
        stage.joinpath(f"{job_id}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    stage.joinpath("audit.json").write_text(json.dumps({"entries": chain.entries, "head": chain.head()}, indent=1,
                                                       ensure_ascii=False), encoding="utf-8")
    meta = {"model": entry["id"], "run": run_kind, "jobs": job_ids, "reader": "on" if reader_on else "off",
            "started": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t0)), "seconds": round(time.time() - t0),
            "policy_hash": setup.hashes["policy"], "hashes": setup.hashes, "head": chain.head(),
            "cost_micro": sum(r["totals"]["cost_micro"] for r in results.values())}
    stage.joinpath("morning.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    problems = sanitize.scan(sorted(stage.glob("*.json")))
    if problems:
        raise SystemExit("The sanitizer's scan found something, so the run stays in owner/out/staging/ for the "
                         "session to look at: " + "; ".join(problems))
    dest = Path(dest or HERE.joinpath("data", "runs", entry["id"], run_kind))
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(stage), str(dest))
    return meta["cost_micro"]


def _delayed(delay, args, t0, results):
    time.sleep(delay)
    one_session(*args, time.time() - t0, results)


def already(dest, setup):
    meta = Path(dest).joinpath("morning.json")
    return meta.exists() and json.loads(meta.read_text(encoding="utf-8")).get("hashes") == setup.hashes


def dev_round(setup, again=False, folder=None):
    """The dev round a run writes into. That's the latest round while everything in it was made under today's files,
    so a model whose run wasn't kept fills its place there, and a new round once a tuned file changed anything."""
    folder = Path(folder or HERE.joinpath("data", "dev"))
    numbers = sorted(int(p.name[6:]) for p in folder.glob("round-*") if p.name[6:].isdigit())
    if not numbers:
        return 1
    latest = folder.joinpath(f"round-{numbers[-1]}")
    if not again and all(already(p, setup) for p in latest.iterdir() if p.is_dir()):
        return numbers[-1]
    return numbers[-1] + 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Record the agents' sessions.")
    ap.add_argument("--run", required=True, choices=["dev", "morning", "reader-off", "budget"])
    ap.add_argument("--models", default="")
    ap.add_argument("--serial", action="store_true")
    ap.add_argument("--again", action="store_true")
    a = ap.parse_args(argv)
    stage_needed = "stage1" if a.run == "dev" else "stage2"
    for stage in ("stage1", stage_needed):
        if not freeze.ready(stage):
            raise SystemExit(f"{stage} isn't frozen, or something in it changed since. The session freezes it.")
    if a.run != "dev" and freeze.placeholder_names():
        raise SystemExit("Stage 1 was frozen on the placeholder names, which only the dev round may use. The session "
                         "freezes it again once config/names.json lands.")
    setup = Setup(cast=fixtures.names(placeholder_ok=freeze.placeholder_names()) if a.run == "dev" else None)
    workspaces.sweep()
    budgets = setup.budgets
    run_cap = round(budgets["run_caps_usd"]["1" if a.run == "dev" else "2"] * 1e6)
    model_ids = [m for m in (a.models.split(",") if a.models else setup.models["compare"]) if m]
    jobs = list(setup.jobs)
    reader_on, budget_usd = True, None
    if a.run == "reader-off":
        jobs, reader_on = ["pricing-research"], False
    if a.run == "budget":
        bt = budgets["budget_test"]
        if not bt.get("limit_usd"):
            raise SystemExit("The budget test's limit isn't set yet. The session sets it after run 1.")
        jobs, model_ids, budget_usd = [bt["job"]], [bt["model"]], bt["limit_usd"]
    round_no = dev_round(setup, a.again) if a.run == "dev" else None
    plan = []
    for model_id in model_ids:
        dest = (HERE.joinpath("data", "dev", f"round-{round_no}", model_id) if a.run == "dev"
                else HERE.joinpath("data", "runs", model_id, a.run))
        plan.append((setup.model(model_id), a.run, jobs, reader_on, budget_usd, dest))
    bt = budgets["budget_test"]
    if a.run == "dev" and bt.get("limit_usd") and (not a.models or bt["model"] in model_ids):
        # A trial of the budget test in the dev round, so its limit meets a real model before stage 2 freezes it.
        plan.append((setup.model(bt["model"]), "dev-budget", [bt["job"]], True, bt["limit_usd"],
                     HERE.joinpath("data", "dev", f"round-{round_no}", f"{bt['model']}-budget")))
    spent, keys = 0, {}
    for entry, run_kind, run_jobs, run_reader, run_budget, dest in plan:
        if not a.again and already(dest, setup):
            say(f"{entry['label']}: {run_kind} already matches today's files, skipped.")
            continue
        worst = len(run_jobs) * round((run_budget or budgets["session_usd"]) * 1e6)
        if spent + worst > run_cap:
            raise SystemExit(f"Stopping before {entry['label']}: it could pass this run's cap of "
                             f"${run_cap / 1e6:.2f} (${spent / 1e6:.2f} spent so far).")
        if entry["keychain"] not in keys:
            keys[entry["keychain"]] = key_for(entry["keychain"])
        say(f"{entry['label']}: {run_kind} on {', '.join(run_jobs)}"
            + (f" with a limit of ${run_budget:.3f}" if run_budget else ""))
        spent += record_run(setup, entry, lambda job_id, e=entry: llm.backend_for(e, keys[e["keychain"]]), run_kind,
                            run_jobs, run_reader, run_budget, a.serial, dest)
    say(f"Done. This run spent ${spent / 1e6:.2f}.")
    OUT.mkdir(parents=True, exist_ok=True)
    OUT.joinpath(f"last_{a.run}.json").write_text(json.dumps({"run": a.run, "spent_micro": spent}) + "\n",
                                                  encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
