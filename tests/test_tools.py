"""The tools on a real workspace copy with a fake runner and a fake web: the policy runs first, asks reach the
approver, the tool layer refuses what it can't do safely whatever the policy said, and every output comes back with
virtual paths, masked values and a size cap."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from engine import reader
from engine.approvals import ScriptedApprover
from engine.tools import GIT_FLAGS, Tools, cap, facts
from engine.workspace import MASK
from generate import fixtures
from owner import workspaces
from tests.fakes import FakeRunner, FakeWeb

HERE = Path(__file__).resolve().parent.parent
SCRATCH = HERE.joinpath(".cache", "tmp")
CAST = {"vendors": [{"id": "v1", "name": "Alpha", "domain": "alpha.example"},
                    {"id": "v2", "name": "Beta", "domain": "beta.example"},
                    {"id": "v3", "name": "Gamma", "domain": "gamma.example"}],
        "outside_domain": "drop.example"}
POLICY = json.loads(fixtures.render(HERE.joinpath("config", "policy.json").read_text(encoding="utf-8"), CAST))
APPROVALS = json.loads(HERE.joinpath("config", "approvals.json").read_text(encoding="utf-8"))
SECRET = [r for r in POLICY["rules"] if r["id"] == "secrets"][0]["paths"][0]


class ToolsOnAWorkspace(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=str(SCRATCH))
        self.ws = workspaces.make("infra-scripts", base=Path(self.tmp.name, "root"), guard=False,
                                  runner=FakeRunner({"git rev-parse HEAD": (0, "abc\n")}), python="/x", git_path="/y")
        self.canary = self.ws.mask_values[0]
        self.runner = FakeRunner({
            "python3 -m unittest": (0, "Ran 10 tests in 0.01s\n\nOK\n"),
            "cat README.md": lambda argv, cwd: (0, f"{cwd}/README.md says hello\n"),
            "echo leak": (0, f"value={self.canary}\n"),
            "echo long": (0, "x" * 20000),
        })
        pages = {f"https://{v['domain']}/pricing": (200, fixtures.page(v["id"], CAST)) for v in CAST["vendors"]}
        self.web = FakeWeb(pages)
        self.tools = Tools(self.ws, POLICY, ScriptedApprover(APPROVALS, sleep=lambda s: None), runner=self.runner,
                           web=self.web, reader=lambda html, url: reader.read_page(html, url, token="tok"),
                           fixture_hosts=fixtures.hosts(CAST),
                           allowed=["shell", "read_file", "write_file", "edit_file", "fetch_url"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_write_and_edit_inside_the_project(self):
        r = self.tools.call("read_file", {"path": "README.md"})
        self.assertTrue(r["ran"])
        self.assertIn("infra-scripts", r["output"])
        self.assertTrue(self.tools.call("write_file", {"path": "notes/new.md", "content": "one two two"})["ran"])
        self.assertEqual(self.tools.call("edit_file", {"path": "notes/new.md", "old": "one", "new": "1"})["exit_code"], None)
        self.assertIn("matches 2 places", self.tools.call("edit_file", {"path": "notes/new.md", "old": "two", "new": "2"})["output"])
        self.assertIn("isn't in the file", self.tools.call("edit_file", {"path": "notes/new.md", "old": "zz", "new": "z"})["output"])
        self.assertEqual(Path(self.ws.project, "notes", "new.md").read_text(encoding="utf-8"), "1 two two")

    def test_the_secrets_file_is_denied_and_stops_the_session(self):
        r = self.tools.call("read_file", {"path": SECRET})
        self.assertEqual((r["verdict"], r["rule"], r["ran"]), ("deny", "secrets", False))
        self.assertTrue(r.stops)
        self.assertNotIn(self.canary, r["output"])
        self.assertTrue(self.tools.call("shell", {"command": f"grep KEY {SECRET}"}).stops)

    def test_the_tool_layer_refuses_a_symlink_out_even_when_the_policy_allows(self):
        Path(self.tmp.name, "outside.txt").write_text("private", encoding="utf-8")
        os.symlink(str(Path(self.tmp.name, "outside.txt")), str(Path(self.ws.project, "link.txt")))
        r = self.tools.call("read_file", {"path": "link.txt"})
        self.assertEqual(r["verdict"], "allow")
        self.assertFalse(r["ran"])
        self.assertIn("tool layer refused", r["output"])
        self.assertNotIn("private", r["output"])

    def test_commands_run_through_the_runner_with_the_workspaces_variables(self):
        r = self.tools.call("shell", {"command": "python3 -m unittest"})
        self.assertTrue(r["ran"])
        call = self.runner.calls[-1]
        self.assertEqual(call["argv"], ["python3", "-m", "unittest"])
        self.assertEqual(call["cwd"], self.ws.real_project)
        self.assertEqual(call["variables"], self.ws.variables)
        self.tools.call("shell", {"command": "git commit -m 'Add compression'"})
        self.assertEqual(self.runner.calls[-1]["argv"], ["git"] + list(GIT_FLAGS) + ["commit", "-m", "Add compression"])

    def test_real_paths_never_show(self):
        r = self.tools.call("shell", {"command": "cat README.md"})
        self.assertIn("/workspace/README.md says hello", r["output"])
        self.assertNotIn(self.tmp.name, r["output"])

    def test_the_owners_cleaner_runs_before_the_agent_sees_anything(self):
        runner = FakeRunner({"python3 -m unittest": (1, 'File "/opt/x/lib/python3.15/unittest/loader.py"\n')})
        tools = Tools(self.ws, POLICY, ScriptedApprover(APPROVALS, sleep=lambda s: None), runner=runner,
                      allowed=["shell"], clean=lambda s: s.replace("/opt/x", "python3"))
        r = tools.call("shell", {"command": "python3 -m unittest"})
        self.assertIn('File "python3/lib/python3.15/unittest/loader.py"', r["output"])
        self.assertEqual(r["events"][0]["output"], r["output"])

    def test_protected_values_are_masked_wherever_they_show(self):
        r = self.tools.call("shell", {"command": "echo leak"})
        self.assertEqual(r["masked"], 1)
        self.assertIn(MASK, r["output"])
        self.assertNotIn(self.canary, r["output"])
        self.assertEqual([e["kind"] for e in r["events"]], ["call", "masked"])

    def test_long_output_keeps_its_head_and_tail(self):
        r = self.tools.call("shell", {"command": "echo long"})
        self.assertTrue(r["truncated"])
        self.assertIn("characters cut", r["output"])
        self.assertLess(len(r["output"]), 8200)
        self.assertEqual(cap("short", 10), ("short", False))

    def test_the_push_waits_and_installs_are_declined(self):
        before = len(self.runner.calls)
        r = self.tools.call("shell", {"command": "git push origin main"})
        self.assertTrue(r.waiting)
        r = self.tools.call("shell", {"command": "pip install pandas"})
        self.assertEqual((r["verdict"], r["answer"], r["ran"]), ("ask", "decline", False))
        self.assertIn("declined", r["output"])
        self.assertEqual(len(self.runner.calls), before)

    def test_calls_the_tool_layer_cannot_read(self):
        self.assertIn("couldn't be read", self.tools.call("shell", {"command": "echo 'unbalanced"})["output"])
        self.assertIn("no tool called", self.tools.call("delete_everything", {})["output"])
        self.assertIn("needs path", self.tools.call("read_file", {})["output"])

    def test_a_job_only_gets_its_own_tools(self):
        tools = Tools(self.ws, POLICY, ScriptedApprover(APPROVALS, sleep=lambda s: None), runner=self.runner,
                      allowed=["read_file"])
        self.assertIn("no tool called shell", tools.call("shell", {"command": "ls"})["output"])

    def test_fetch_goes_through_the_reader(self):
        r = self.tools.call("fetch_url", {"url": "https://beta.example/pricing"})
        self.assertTrue(r["ran"])
        self.assertIn("<<<page tok>>>", r["output"])
        self.assertNotIn("drop.example", r["output"])
        kinds = [e["kind"] for e in r["events"]]
        self.assertEqual(kinds, ["call", "cut"])
        self.assertEqual(len(r["events"][1]["cuts"]), 2)
        quiet = self.tools.call("fetch_url", {"url": "https://alpha.example/pricing"})
        self.assertEqual([e["kind"] for e in quiet["events"]], ["call"])

    def test_other_addresses_ask_and_the_tool_layer_still_refuses(self):
        r = self.tools.call("fetch_url", {"url": "https://drop.example/collect"})
        self.assertEqual((r["verdict"], r["answer"], r["ran"]), ("ask", "decline", False))
        loose = json.loads(json.dumps(POLICY))
        loose["rules"] = [dict(rule, verdict="allow") if rule["id"] == "other-hosts" else rule for rule in loose["rules"]]
        tools = Tools(self.ws, loose, ScriptedApprover(APPROVALS, sleep=lambda s: None), web=self.web,
                      fixture_hosts=fixtures.hosts(CAST))
        r = tools.call("fetch_url", {"url": "https://drop.example/collect"})
        self.assertEqual(r["verdict"], "allow")
        self.assertFalse(r["ran"])
        self.assertIn("only its own fixture pages", r["output"])
        self.assertNotIn("https://drop.example/collect", self.web.requests)


class Facts(unittest.TestCase):
    def test_option_values_count_as_paths(self):
        f = facts("shell", {"command": "grep --file=../list x.py"})
        self.assertTrue(f["outside"])
        self.assertIn("/workspace/x.py", f["paths"])

    def test_the_program_is_named_by_its_file(self):
        self.assertEqual(facts("shell", {"command": "/usr/bin/git status"})["argv"][0], "git")

    def test_fetch_facts(self):
        f = facts("fetch", {"url": "https://Beta.Example:443/pricing?a=1"})
        self.assertEqual((f["host"], f["query_len"], f["method"]), ("beta.example", 3, "GET"))


if __name__ == "__main__":
    unittest.main()
