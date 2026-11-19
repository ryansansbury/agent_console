import tempfile
import unittest
from pathlib import Path

from scripts.settings import load_settings


class Settings(unittest.TestCase):
    def test_defaults_when_the_file_is_missing(self):
        with tempfile.TemporaryDirectory() as d:
            settings = load_settings(Path(d, "missing"))
        self.assertEqual(settings["RETENTION_DAYS"], "14")
        self.assertEqual(settings["LOG_DIR"], "logs")

    def test_reads_key_value_lines_and_skips_comments(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "settings")
            f.write_text("# a comment\nSTORAGE_BUCKET = test-bucket\n\nLOG_DIR=var\n", encoding="utf-8")
            settings = load_settings(f)
        self.assertEqual(settings["STORAGE_BUCKET"], "test-bucket")
        self.assertEqual(settings["LOG_DIR"], "var")

    def test_the_file_wins_over_the_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "settings")
            f.write_text("RETENTION_DAYS=7\n", encoding="utf-8")
            self.assertEqual(load_settings(f)["RETENTION_DAYS"], "7")


if __name__ == "__main__":
    unittest.main()
