"""The freeze: a stage freezes once and shows any change after, and stage 1 freezes on the placeholder names only when
asked, which marks it for the dev round alone. These tests point the freeze file at a scratch copy, so the real
evals/frozen.json is never touched."""
import tempfile
import unittest
from pathlib import Path

from evals import freeze

HERE = Path(__file__).resolve().parent.parent
SCRATCH = HERE.joinpath(".cache", "tmp")


class Freeze(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=str(SCRATCH))
        self.real = freeze.FROZEN
        freeze.FROZEN = Path(self.tmp.name, "frozen.json")

    def tearDown(self):
        freeze.FROZEN = self.real
        self.tmp.cleanup()

    def test_a_stage_freezes_once_and_shows_changes(self):
        self.assertIsNone(freeze.changed("stage2"))
        freeze.freeze("stage2")
        self.assertTrue(freeze.ready("stage2"))
        with self.assertRaises(SystemExit):
            freeze.freeze("stage2")
        data = freeze.load()
        first = sorted(data["stage2"])[0]
        data["stage2"][first] = "0" * 16
        freeze.FROZEN.write_text(__import__("json").dumps(data), encoding="utf-8")
        self.assertEqual(freeze.changed("stage2"), [(first, "changed")])
        freeze.freeze("stage2", again=True)
        self.assertTrue(freeze.ready("stage2"))
        self.assertEqual(len(freeze.load()["history"]), 1)

    def test_rewording_a_rule_never_changes_the_policys_hash(self):
        import copy
        import json
        from agents import replay
        pol = json.loads(HERE.joinpath("config", "policy.json").read_text(encoding="utf-8"))
        before = replay.policy_hash(pol)
        worded = copy.deepcopy(pol)
        worded["rules"][0]["label"], worded["rules"][0]["why"], worded["note"] = "Reworded", "Reworded.", "Reworded."
        self.assertEqual(replay.policy_hash(worded), before)
        decided = copy.deepcopy(pol)
        decided["rules"][0]["verdict"] = "ask"
        self.assertNotEqual(replay.policy_hash(decided), before)

    def test_the_names_landing_freezes_stage_one_again_and_nothing_else_does(self):
        import json
        real_files, real_names = freeze.files, freeze.NAMES
        base = {"fixtures/a.html": "1111", "config/policy.json": "2222"}
        try:
            freeze.NAMES = Path(self.tmp.name, "names.json")
            freeze.files = lambda stage: dict(base)
            freeze.freeze("stage1", placeholder=True)
            self.assertTrue(freeze.placeholder_names())
            freeze.NAMES.write_text("{}", encoding="utf-8")
            freeze.files = lambda stage: dict(base, **{"fixtures/a.html": "9999", "config/names.json": "3333"})
            with self.assertRaises(SystemExit):
                freeze.names_landed()
            self.assertTrue(freeze.placeholder_names())
            freeze.files = lambda stage: dict(base, **{"config/names.json": "3333"})
            self.assertIn("Froze stage1 again", freeze.names_landed())
            self.assertFalse(freeze.placeholder_names())
            self.assertTrue(freeze.ready("stage1"))
            self.assertIn("already frozen", freeze.names_landed())
            self.assertEqual(len(json.loads(freeze.FROZEN.read_text(encoding="utf-8"))["history"]), 1)
        finally:
            freeze.files, freeze.NAMES = real_files, real_names

    def test_stage_one_waits_for_the_names_unless_asked(self):
        if HERE.joinpath("config", "names.json").exists():
            freeze.freeze("stage1")
            self.assertFalse(freeze.placeholder_names())
            return
        with self.assertRaises(SystemExit):
            freeze.freeze("stage1")
        freeze.freeze("stage1", placeholder=True)
        self.assertTrue(freeze.placeholder_names())
        self.assertTrue(freeze.ready("stage1"))


if __name__ == "__main__":
    unittest.main()
