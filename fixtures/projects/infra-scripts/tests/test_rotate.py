import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from scripts.rotate_logs import rotate
from scripts.upload import Uploader

TODAY = date(2026, 11, 9)
SETTINGS = {"RETENTION_DAYS": "30", "STORAGE_KEY_ID": "AK-TESTKEY00001", "STORAGE_BUCKET": "test-bucket"}


class Rotate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        for age in (0, 10, 30, 31, 45):
            day = TODAY - timedelta(days=age)
            self.dir.joinpath(f"app-{day.isoformat()}.log").write_text(f"log for {day}\n", encoding="utf-8")
        self.dir.joinpath("notes.txt").write_text("not a log\n", encoding="utf-8")
        self.dir.joinpath("app-latest.log").write_text("not a dated log\n", encoding="utf-8")
        self.sent = []
        self.uploader = Uploader(SETTINGS, send=lambda bucket, path: self.sent.append(path.name))

    def tearDown(self):
        self.tmp.cleanup()

    def names(self):
        return sorted(p.name for p in self.dir.iterdir())

    def test_old_logs_are_uploaded_and_deleted(self):
        rotate(self.dir, TODAY, SETTINGS, self.uploader)
        self.assertEqual(self.sent, ["app-2026-09-25.log", "app-2026-10-09.log"])
        self.assertNotIn("app-2026-09-25.log", self.names())
        self.assertIn("app-2026-10-10.log", self.names())

    def test_a_dry_run_changes_nothing(self):
        before = self.names()
        done = rotate(self.dir, TODAY, SETTINGS, self.uploader, dry_run=True)
        self.assertEqual(self.names(), before)
        self.assertEqual(self.sent, [])
        self.assertEqual(len(done), 2)

    def test_other_files_are_left_alone(self):
        rotate(self.dir, TODAY, SETTINGS, self.uploader)
        self.assertIn("notes.txt", self.names())
        self.assertIn("app-latest.log", self.names())

    def test_it_reports_what_it_did(self):
        done = rotate(self.dir, TODAY, SETTINGS, self.uploader)
        self.assertEqual(done, [("uploaded", "app-2026-09-25.log"), ("uploaded", "app-2026-10-09.log")])


if __name__ == "__main__":
    unittest.main()
