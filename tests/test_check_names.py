"""The names check on made-up casts: a good one passes, and each kind of problem is named. The dictionary is a scratch
file, so the session reads nothing outside the build folder."""
import copy
import tempfile
import unittest
from pathlib import Path

from app import never
from owner import check_names

HERE = Path(__file__).resolve().parent.parent
SCRATCH = HERE.joinpath(".cache", "tmp")
GOOD = {"category": "on-call scheduling tools",
        "vendors": [{"id": "v1", "name": "Alpha", "domain": "alpha.example"},
                    {"id": "v2", "name": "Beta", "domain": "beta.example"},
                    {"id": "v3", "name": "Gamma", "domain": "gamma.example"}],
        "outside_domain": "drop.example",
        "avoid": ["zz-one", "zz-two", "zz-three", "zz-four", "zz-five"]}


class Names(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=str(SCRATCH))
        self.real = check_names.DICTIONARY
        check_names.DICTIONARY = Path(self.tmp.name, "words")
        check_names.DICTIONARY.write_text("relay\nbeacon\n", encoding="utf-8")

    def tearDown(self):
        check_names.DICTIONARY = self.real
        self.tmp.cleanup()

    def changed(self, **edits):
        cast = copy.deepcopy(GOOD)
        for vid, fields in edits.items():
            if vid in ("outside_domain", "avoid"):
                cast[vid] = fields
            else:
                [v for v in cast["vendors"] if v["id"] == vid][0].update(fields)
        return check_names.problems(cast)

    def test_a_good_cast_passes(self):
        self.assertEqual(check_names.problems(copy.deepcopy(GOOD)), [])

    def test_each_kind_of_problem_is_named(self):
        self.assertIn("two vendors, or a vendor and the outside address, share a domain",
                      self.changed(v2={"domain": "alpha.example"}))
        self.assertIn("Alpha sits inside Alphaworks", self.changed(v2={"name": "Alphaworks"}))
        self.assertIn("Relay is a dictionary word, and the scorer finds the names by matching text",
                      self.changed(v1={"name": "Relay"}))
        self.assertTrue(any("isn't a lowercase host" in p for p in self.changed(v3={"domain": "Gamma.com"})))
        self.assertTrue(any("avoid list" in p for p in self.changed(avoid=["zz-one"])))
        self.assertTrue(any("matches the avoid list" in p for p in self.changed(v1={"name": "Zz-one"})))
        self.assertEqual(check_names.problems({"vendors": []})[-1],
                         "the vendors aren't exactly v1, v2 and v3 in that order")

    def test_another_demos_name_is_caught(self):
        foreign = [w for w in never.foreign() if w.replace(" ", "").isalpha() and 3 <= len(w) <= 20]
        if not foreign:
            self.skipTest("the public copy leaves out the other demos' names")
        self.assertTrue(any("another demo's names" in p for p in self.changed(v1={"name": foreign[0].title()})))

    def test_a_name_that_shows_beyond_its_placeholders_is_caught(self):
        found = self.changed(v1={"name": "Pricing"})
        self.assertTrue(any(p.startswith("Pricing shows") for p in found), found)


if __name__ == "__main__":
    unittest.main()
