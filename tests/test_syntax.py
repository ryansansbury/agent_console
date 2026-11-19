"""Every Python file in the project compiles, including the owner scripts the unit tests never run (the browser check,
the selftest and the recorder's real paths), so a typo or newer syntax shows up here before it shows up in a real run.
Compiling runs nothing."""
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SKIP = ("reference", ".cache", ".venv", "node_modules")


class Syntax(unittest.TestCase):
    def test_every_python_file_compiles(self):
        bad, count = [], 0
        for path in sorted(HERE.rglob("*.py")):
            rel = path.relative_to(HERE)
            if rel.parts[0] in SKIP or "__pycache__" in rel.parts:
                continue
            count += 1
            try:
                compile(path.read_text(encoding="utf-8"), str(rel), "exec")
            except SyntaxError as e:
                bad.append(f"{rel}:{e.lineno} {e.msg}")
        self.assertGreater(count, 40)
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
