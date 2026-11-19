import gzip
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from scripts.rotate_logs import rotate
from scripts.upload import Uploader

TODAY = date(2026, 11, 9)
SETTINGS = {"RETENTION_DAYS": "14", "STORAGE_KEY_ID": "AKC-TESTKEY000000001", "STORAGE_BUCKET": "test-bucket"}


def day(age):
    return (TODAY - timedelta(days=age)).isoformat()


class Rotate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        for age in (0, 1, 5, 14, 15, 30):
            self.dir.joinpath(f"app-{day(age)}.log").write_text(f"log for {day(age)}\n", encoding="utf-8")
        self.dir.joinpath("notes.txt").write_text("not a log\n", encoding="utf-8")
        self.sent = []
        self.uploader = Uploader(SETTINGS, send=lambda bucket, path: self.sent.append(path.name))

    def tearDown(self):
        self.tmp.cleanup()

    def names(self):
        return sorted(p.name for p in self.dir.iterdir())

    def test_logs_past_fourteen_days_are_uploaded_and_deleted(self):
        rotate(self.dir, TODAY, SETTINGS, self.uploader)
        self.assertEqual(self.sent, [f"app-{day(30)}.log", f"app-{day(15)}.log"])
        self.assertFalse(any(day(15) in n or day(30) in n for n in self.names()))

    def test_logs_older_than_a_day_are_compressed(self):
        rotate(self.dir, TODAY, SETTINGS, self.uploader)
        for age in (5, 14):
            with gzip.open(self.dir.joinpath(f"app-{day(age)}.log.gz"), "rt", encoding="utf-8") as f:
                self.assertEqual(f.read(), f"log for {day(age)}\n")
        self.assertIn(f"app-{day(0)}.log", self.names())
        self.assertIn(f"app-{day(1)}.log", self.names())

    def test_a_dry_run_changes_nothing(self):
        before = self.names()
        done = rotate(self.dir, TODAY, SETTINGS, self.uploader, dry_run=True)
        self.assertEqual(self.names(), before)
        self.assertEqual(self.sent, [])
        self.assertEqual(len(done), 4)

    def test_other_files_are_left_alone(self):
        rotate(self.dir, TODAY, SETTINGS, self.uploader)
        self.assertIn("notes.txt", self.names())


if __name__ == "__main__":
    unittest.main()
