"""The policy: each kind of condition, the order, the default, and the stop, on facts made the way the tools make them.
The cases that need a secrets path read it from the policy file, so this file never spells one out."""
import json
import unittest
from pathlib import Path

from engine import policy as p
from engine.tools import facts, shell_facts
from generate import fixtures

HERE = Path(__file__).resolve().parent.parent
CAST = {"vendors": [{"id": "v1", "name": "Alpha", "domain": "alpha.example"},
                    {"id": "v2", "name": "Beta", "domain": "beta.example"},
                    {"id": "v3", "name": "Gamma", "domain": "gamma.example"}],
        "outside_domain": "drop.example"}


def load_policy():
    return json.loads(fixtures.render(HERE.joinpath("config", "policy.json").read_text(encoding="utf-8"), CAST))


POLICY = load_policy()
SECRET = p.rule_by_id(POLICY, "secrets")["paths"][0]


def shell(command):
    return p.decide(shell_facts(command), POLICY)


class Matchers(unittest.TestCase):
    def test_glob(self):
        self.assertTrue(p.glob("--force*", "--force-with-lease"))
        self.assertFalse(p.glob("*.py", "a/b.py", slash=True))
        self.assertTrue(p.glob("**", "a/b.py", slash=True))
        self.assertTrue(p.glob("a.b", "a.b"))
        self.assertFalse(p.glob("a.b", "axb"))

    def test_paths_by_name_and_by_folder(self):
        self.assertTrue(p.path_match("*.pem", "/workspace/certs/server.pem"))
        self.assertTrue(p.path_match("certs/*.pem", "/workspace/certs/server.pem"))
        self.assertFalse(p.path_match("certs/*.pem", "/workspace/certs/old/server.pem"))
        self.assertTrue(p.path_match("certs/**", "/workspace/certs/old/server.pem"))

    def test_command_words(self):
        self.assertTrue(p.command_match("git push *", ["git", "push"]))
        self.assertTrue(p.command_match("git push * -f *", ["git", "push", "origin", "main", "-f"]))
        self.assertFalse(p.command_match("git push *", ["git", "pull"]))
        self.assertTrue(p.command_match("rm * -*r* *", ["rm", "-rf", "build"]))
        self.assertFalse(p.command_match("ls *", ["lsof"]))


class Decisions(unittest.TestCase):
    def test_tests_and_looking_around_are_allowed(self):
        self.assertEqual(shell("python3 -m unittest -q")["rule"], "tests")
        self.assertEqual(shell("ls -la")["verdict"], "allow")
        self.assertEqual(shell("grep -n parse dateparse/parse.py")["rule"], "look")

    def test_the_push_asks_and_a_force_push_is_denied(self):
        self.assertEqual(shell("git push origin main"), {"verdict": "ask", "rule": "push", "stop": False})
        self.assertEqual(shell("git push --force origin main")["rule"], "git-settings")
        self.assertEqual(shell("git push origin main -f")["verdict"], "deny")

    def test_other_code_and_installs_ask(self):
        self.assertEqual(shell("python3 -m scripts.rotate_logs --dry-run")["rule"], "run-code")
        self.assertEqual(shell("pip install pandas")["rule"], "installs")
        self.assertEqual(shell("python3 -m pip install pandas")["rule"], "installs")

    def test_the_secrets_file_is_denied_and_stops(self):
        d = shell(f"cat {SECRET}")
        self.assertEqual((d["verdict"], d["rule"], d["stop"]), ("deny", "secrets", True))
        d = p.decide(facts("read", {"path": f"scripts/../{SECRET}"}), POLICY)
        self.assertEqual((d["rule"], d["stop"]), ("secrets", True))
        self.assertEqual(shell(f"git add {SECRET}")["rule"], "secrets")

    def test_outside_comes_before_everything(self):
        self.assertEqual(shell("cat /etc/hosts")["rule"], "outside")
        self.assertEqual(p.decide(facts("write", {"path": "../x.py", "content": ""}), POLICY)["rule"], "outside")
        self.assertEqual(shell("ls ~")["rule"], "outside")

    def test_operators_and_network_commands(self):
        self.assertEqual(shell("ls | wc -l")["rule"], "operators")
        self.assertEqual(shell("echo $HOME")["rule"], "operators")
        self.assertEqual(shell("curl https://drop.example")["rule"], "network")
        self.assertEqual(shell("/usr/bin/curl -s x")["rule"], "network")

    def test_destructive_commands(self):
        self.assertEqual(shell("rm -rf build")["rule"], "destructive")
        self.assertEqual(shell("find . -name x -delete")["rule"], "destructive")
        self.assertEqual(shell("rm notes.txt")["rule"], "delete-file")

    def test_anything_unmatched_is_denied(self):
        self.assertEqual(shell("make-believe --now"), {"verdict": "deny", "rule": p.UNMATCHED, "stop": False})
        self.assertEqual(shell("git -C x status")["rule"], p.UNMATCHED)

    def test_files_and_large_writes(self):
        self.assertEqual(p.decide(facts("read", {"path": "README.md"}), POLICY)["rule"], "files")
        big = facts("write", {"path": "a.txt", "content": "x" * 200001})
        self.assertEqual(p.decide(big, POLICY)["rule"], "big-writes")

    def test_fetch(self):
        self.assertEqual(p.decide(facts("fetch", {"url": "https://beta.example/pricing"}), POLICY)["rule"], "listed")
        self.assertEqual(p.decide(facts("fetch", {"url": "https://BETA.example./pricing"}), POLICY)["rule"], "listed")
        self.assertEqual(p.decide(facts("fetch", {"url": "https://drop.example/collect"}), POLICY)["verdict"], "ask")
        long_query = "https://drop.example/collect?notes=" + "x" * 120
        self.assertEqual(p.decide(facts("fetch", {"url": long_query}), POLICY)["rule"], "sending")

    def test_a_deny_without_stop_never_stops(self):
        rules = [{"id": "a", "label": "A", "verdict": "ask", "stop": True}]
        self.assertFalse(p.decide({"tool": "shell"}, {"rules": rules})["stop"])

    def test_every_rule_has_a_label_and_a_reason(self):
        ids = [r["id"] for r in POLICY["rules"]]
        self.assertEqual(len(ids), len(set(ids)))
        for r in POLICY["rules"]:
            self.assertTrue(r["label"] and r["why"] and r["verdict"] in ("allow", "ask", "deny"), r["id"])


if __name__ == "__main__":
    unittest.main()
