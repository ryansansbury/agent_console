"""The README's results: written between the markers and nowhere else, and every sentence the build writes there passes
the copy lint, checked here on sample data with every branch taken."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app import readme

HERE = Path(__file__).resolve().parent.parent
SCRATCH = HERE.joinpath(".cache", "tmp")
LINT = HERE.joinpath("tools", "lint_copy.py")
ROW = {"label": "Model A", "done": 3, "safe_stops": 1, "unsafe": 0, "asked": 2, "denied": 1, "quarantined": 1,
       "cost_micro": 412345, "ms": 431000}
DATA = {"route": "a", "rows": {"a": ROW, "b": dict(ROW, label="Model B", safe_stops=0, cost_micro=9000, ms=50000)},
        "experiment": [{"model": "a", "label": "Model A", "followed": [], "flagged": True, "attempts": [], "caught": True},
                       {"model": "b", "label": "Model B", "followed": ["x"], "flagged": False,
                        "attempts": [{"ran": False}], "caught": True}],
        "budget_test": {"model": "a", "label": "Model A", "job": "parser-lib", "limit_micro": 40000,
                        "spent_micro": 38000, "ok": True},
        "mornings": {"a": {"label": "Model A", "audit": {"head": "a" * 64}},
                     "b": {"label": "Model B", "audit": {"head": "b" * 64}}}}


class Readme(unittest.TestCase):
    def test_only_the_results_change(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(SCRATCH)) as d:
            path = Path(d, "README.md")
            path.write_text(f"# Title\n\nBefore.\n\n{readme.START}\nold\n{readme.END}\n\nAfter.\n", encoding="utf-8")
            self.assertTrue(readme.write(DATA, path))
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# Title\n\nBefore.\n\n"))
            self.assertTrue(text.endswith(f"{readme.END}\n\nAfter.\n"))
            self.assertNotIn("\nold\n", text)
            self.assertIn("Model A (opens the page)", text)
            self.assertIn("a" * 64, text)
            if LINT.exists():
                done = subprocess.run([sys.executable, str(LINT), "--strict", str(path)], capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stdout)

    def test_no_markers_no_write(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(SCRATCH)) as d:
            path = Path(d, "README.md")
            path.write_text("# Title\n", encoding="utf-8")
            self.assertFalse(readme.write(DATA, path))


if __name__ == "__main__":
    unittest.main()
