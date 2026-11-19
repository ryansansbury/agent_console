"""The loop through every end state on a scripted backend and the fake runner, with the session's events and audit
entries checked along the way."""
import json
import tempfile
import unittest
from pathlib import Path

from agents import loop
from agents.llm import ModelError, Reply
from engine import audit
from engine.approvals import ScriptedApprover
from engine.budget import Budget
from engine.tools import Tools
from evals import key
from generate import fixtures
from owner import workspaces
from tests.fakes import FakeRunner

HERE = Path(__file__).resolve().parent.parent
SCRATCH = HERE.joinpath(".cache", "tmp")
CAST = {"vendors": [{"id": "v1", "name": "Alpha", "domain": "alpha.example"},
                    {"id": "v2", "name": "Beta", "domain": "beta.example"},
                    {"id": "v3", "name": "Gamma", "domain": "gamma.example"}],
        "outside_domain": "drop.example"}
POLICY = json.loads(fixtures.render(HERE.joinpath("config", "policy.json").read_text(encoding="utf-8"), CAST))
APPROVALS = json.loads(HERE.joinpath("config", "approvals.json").read_text(encoding="utf-8"))
LIMITS = {"tool_calls": 40, "model_calls": 30, "minutes": 15, "command_seconds": 60, "output_chars": 8000}
PRICE = {"in": 2.0, "out": 10.0, "cache_write": 1.25, "cache_read": 0.1}
PROTECTED = key.expectations()["protected_names"][0]


class Script:
    """Replies from a list, recording the messages each call saw."""

    def __init__(self, *turns, usage=None):
        self.turns, self.seen, self.n = list(turns), [], 0
        self.usage = usage or {"input": 100, "cache_write": 0, "cache_read": 0, "output": 50}

    def turn(self, system, messages, tools, max_tokens):
        self.seen.append({"messages": [dict(m) for m in messages], "max_tokens": max_tokens})
        turn = self.turns[min(self.n, len(self.turns) - 1)]
        self.n += 1
        if isinstance(turn, Exception):
            raise turn
        text, calls = turn[:2]
        stop = turn[2] if len(turn) > 2 else ("tool_use" if calls else "end_turn")
        return Reply(text=text, calls=[dict(c, id=c.get("id", f"c{self.n}-{i}")) for i, c in enumerate(calls)],
                     usage=dict(self.usage), stop_reason=stop, model="scripted", raw=None, ms=5)


def read(path):
    return {"name": "read_file", "args": {"path": path}}


def shell(command):
    return {"name": "shell", "args": {"command": command}}


class Loop(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=str(SCRATCH))
        self.ws = workspaces.make("infra-scripts", base=Path(self.tmp.name, "root"), guard=False,
                                  runner=FakeRunner({"git rev-parse HEAD": (0, "abc\n")}), python="/x", git_path="/y")
        self.runner = FakeRunner({"python3 -m unittest": (0, "Ran 10 tests\n\nOK\n")})
        self.tools = Tools(self.ws, POLICY, ScriptedApprover(APPROVALS, sleep=lambda s: None), runner=self.runner,
                           allowed=["shell", "read_file", "write_file", "edit_file"])

    def tearDown(self):
        self.tmp.cleanup()

    def go(self, backend, budget=None, limits=None, clean=None):
        self.session = loop.Session("infra-scripts", {"id": "m", "label": "M"}, "test", {"budget_micro": 1000000},
                                    "the task", clean=clean)
        return loop.run(backend, "system", "the task", [], self.tools, budget or Budget(1.0, PRICE), self.session,
                        limits or LIMITS)

    def kinds(self):
        return [e["kind"] for e in self.session.events]

    def test_done(self):
        state = self.go(Script(("Running.", [shell("python3 -m unittest")]), ("All done.", [])))
        self.assertEqual(state, "done")
        self.assertEqual(self.kinds(), ["model", "call", "model", "end"])
        self.assertEqual(self.session.end_state["reply"], "All done.")
        self.assertTrue(audit.verify(self.session.chain.entries)["ok"])
        call = self.session.events[1]
        self.assertTrue(call["audit"] and all(a <= len(self.session.chain.entries) for a in call["audit"]))

    def test_waiting_at_the_push(self):
        self.assertEqual(self.go(Script(("", [shell("git push origin main")]))), "waiting")
        entries = self.session.chain.entries
        self.assertEqual([(e["actor"], e["verdict"]) for e in entries[-3:-1]], [("agent", "ask"), ("script", "wait")])

    def test_the_secrets_file_stops_it_before_the_next_call(self):
        backend = Script(("", [read("README.md"), read(PROTECTED), read("scripts/upload.py")]))
        self.assertEqual(self.go(backend), "stopped-denial")
        reads = [e["args"]["path"] for e in self.session.events if e["kind"] == "call"]
        self.assertEqual(reads, ["README.md", PROTECTED])

    def test_the_budget_stops_it_and_no_call_follows(self):
        backend = Script(*[("", [shell("python3 -m unittest")])] * 10,
                         usage={"input": 2000, "cache_write": 0, "cache_read": 0, "output": 800})
        state = self.go(backend, budget=Budget(0.05, PRICE))
        self.assertEqual(state, "stopped-budget")
        levels = [e["level"] for e in self.session.events if e["kind"] == "budget"]
        self.assertEqual(levels, ["warn", "stop"])
        stop = [e["seq"] for e in self.session.events if e.get("level") == "stop"][0]
        self.assertFalse([e for e in self.session.events if e["kind"] == "model" and e["seq"] > stop])
        self.assertLessEqual(self.session.totals["cost_micro"], 50000)

    def test_the_warning_rides_along_with_the_next_results(self):
        backend = Script(*[("", [shell("python3 -m unittest")])] * 3 + [("Done.", [])],
                         usage={"input": 1000, "cache_write": 0, "cache_read": 0, "output": 100})
        self.assertEqual(self.go(backend, budget=Budget(0.1, PRICE, warn_at=0.05)), "done")
        notes = [m.get("note") for seen in backend.seen for m in seen["messages"] if m["role"] == "tool"]
        self.assertEqual(notes.count(loop.WARN_NOTE), 2)
        self.assertEqual([e["level"] for e in self.session.events if e["kind"] == "budget"], ["warn"])

    def test_the_last_reply_the_money_pays_for_carries_the_warning(self):
        backend = Script(*[("", [shell("python3 -m unittest")])] * 10,
                         usage={"input": 2000, "cache_write": 0, "cache_read": 0, "output": 800})
        self.assertEqual(self.go(backend, budget=Budget(0.03, PRICE)), "stopped-budget")
        budget = [e for e in self.session.events if e["kind"] == "budget"]
        self.assertEqual([(e["level"], e["reason"]) for e in budget], [("warn", "last"), ("stop", None)])
        self.assertEqual(len(backend.seen), 2)
        self.assertEqual(backend.seen[1]["messages"][-1]["note"], loop.LAST_NOTE)
        self.assertLessEqual(self.session.totals["cost_micro"], 30000)

    def test_a_reply_cut_at_its_length_limit_runs_none_of_its_calls(self):
        write = {"name": "write_file", "args": {"path": "notes.md", "content": "half a fi"}}
        backend = Script(("", [write], "max_tokens"), ("Done.", []))
        self.assertEqual(self.go(backend), "done")
        self.assertFalse(self.ws.project.joinpath("notes.md").exists())
        self.assertEqual([e["reason"] for e in self.session.events if e["kind"] == "bad-call"], ["cut"])
        results = [m for m in backend.seen[1]["messages"] if m["role"] == "tool"][0]["results"]
        self.assertEqual(results[0]["output"], loop.CUT_OUTPUT)

    def test_the_limits(self):
        self.assertEqual(self.go(Script(("", [shell("ls")] * 3)), limits=dict(LIMITS, tool_calls=2)), "step-cap")
        self.assertEqual(self.go(Script(("", [shell("ls")])), limits=dict(LIMITS, model_calls=2)), "turn-cap")

    def test_an_api_failure_ends_it(self):
        self.assertEqual(self.go(Script(ModelError("Anthropic answered 500"))), "error")
        self.assertIn("500", self.session.end_state["detail"])

    def test_arguments_that_are_not_json(self):
        backend = Script(("", [{"name": "shell", "args": {}, "bad_args": "{\"command\": "}]), ("Done.", []))
        self.assertEqual(self.go(backend), "done")
        self.assertIn("bad-call", self.kinds())
        results = [m for m in backend.seen[1]["messages"] if m["role"] == "tool"][0]["results"]
        self.assertTrue(results[0]["error"])

    def test_everything_recorded_passes_the_cleaner(self):
        clean = lambda v: json.loads(json.dumps(v).replace("README", "R-E-A-D-M-E")) if not isinstance(v, str) \
            else v.replace("README", "R-E-A-D-M-E")
        self.go(Script(("", [read("README.md")]), ("Done.", [])), clean=clean)
        text = json.dumps(self.session.record()) + json.dumps(self.session.chain.entries)
        self.assertNotIn("README", text)
        self.assertTrue(audit.verify(self.session.chain.entries)["ok"])

    def test_estimates_err_high(self):
        self.assertGreaterEqual(loop.estimate_tokens("x" * 300), 100)


if __name__ == "__main__":
    unittest.main()
