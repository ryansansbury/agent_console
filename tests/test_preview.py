"""The stand-in's preview morning, made in the session with the canned shell and the in-memory web, passes the same
checks the build puts every real run through: the chain verifies, every call is decided again the same way, nothing
unsafe happened, every assertion holds, the reader cut the planted note, and the sanitizer's scan is clean."""
import json
import unittest
from pathlib import Path

from agents import replay
from evals import score
from generate import fixtures
from owner import sanitize, stand_in

HERE = Path(__file__).resolve().parent.parent


class Preview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cast = fixtures.names(placeholder_ok=True)
        cls.sessions, cls.chain = stand_in.preview(cls.cast)
        cls.policy = json.loads(fixtures.render(HERE.joinpath("config", "policy.json").read_text(encoding="utf-8"),
                                                cls.cast))

    def test_each_job_ends_where_the_stand_in_steers_it(self):
        self.assertEqual({s["job"]: s["end"]["state"] for s in self.sessions},
                         {"parser-lib": "done", "billing-export": "waiting", "pricing-research": "done",
                          "infra-scripts": "stopped-denial"})

    def test_the_build_checks_pass(self):
        run = {"sessions": {s["job"]: s for s in self.sessions},
               "audit": {"entries": self.chain.entries, "head": self.chain.head()}, "meta": {}}
        self.assertEqual(replay.check(run, self.policy), [])

    def test_safe_and_quarantined(self):
        for s in self.sessions:
            scored = score.score_session(s, self.cast)
            self.assertEqual(scored["unsafe"], [], s["job"])
            self.assertTrue(all(a["ok"] for a in scored["assertions"]), s["job"])
            if s["job"] == "pricing-research":
                self.assertTrue(scored["injection"]["cut"])
                self.assertEqual(scored["injection"]["followed"], [])

    def test_nothing_leaks(self):
        text = json.dumps(self.sessions, ensure_ascii=False) + json.dumps(self.chain.entries, ensure_ascii=False)
        self.assertEqual(sanitize.scan_text(text), [])


if __name__ == "__main__":
    unittest.main()
