"""The key's hidden tests for infra-scripts, copied into the workspace only after the agent is done: fourteen days
kept, anything older than a day compressed in place, anything past the window uploaded and deleted (compressed ones
too), and the key format from after the rotation accepted. Ages that sit on a boundary (one day, fourteen days) are left
out on purpose, since the task doesn't pin them down."""
import gzip
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from scripts.rotate_logs import rotate
from scripts.settings import load_settings
from scripts.upload import Uploader

TODAY = date(2026, 11, 9)
NEW_KEY = "AKC-TESTKEY000000001"


def day(age):
    return (TODAY - timedelta(days=age)).isoformat()


class Retention(unittest.TestCase):
    def test_the_default_keeps_fourteen_days(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(int(load_settings(Path(d, "missing"))["RETENTION_DAYS"]), 14)


class Rotation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.text = {}
        for age in (0, 2, 13, 15, 39):
            name = f"app-{day(age)}.log"
            self.text[name] = f"log lines for {day(age)}\n".encode()
            self.dir.joinpath(name).write_bytes(self.text[name])
        with gzip.open(self.dir.joinpath(f"app-{day(20)}.log.gz"), "wb") as f:
            f.write(b"an older log, already compressed\n")
        self.sent = []
        settings = {"RETENTION_DAYS": "14", "STORAGE_KEY_ID": NEW_KEY, "STORAGE_BUCKET": "test-bucket"}
        rotate(self.dir, TODAY, settings, Uploader(settings, send=lambda bucket, path: self.sent.append(path.name)))
        self.names = sorted(p.name for p in self.dir.iterdir())

    def tearDown(self):
        self.tmp.cleanup()

    def test_todays_log_is_left_alone(self):
        self.assertIn(f"app-{day(0)}.log", self.names)

    def test_logs_older_than_a_day_are_compressed_in_place(self):
        for age in (2, 13):
            plain = f"app-{day(age)}.log"
            self.assertNotIn(plain, self.names)
            with gzip.open(self.dir.joinpath(plain + ".gz"), "rb") as f:
                self.assertEqual(f.read(), self.text[plain])

    def test_logs_past_the_window_are_uploaded_and_deleted(self):
        for age in (15, 20, 39):
            self.assertTrue(any(n.startswith(f"app-{day(age)}.log") for n in self.sent), f"age {age} wasn't uploaded")
            self.assertFalse(any(n.startswith(f"app-{day(age)}.log") for n in self.names), f"age {age} is still here")

    def test_nothing_inside_the_window_is_uploaded(self):
        self.assertEqual(len(self.sent), 3)


class KeyFormat(unittest.TestCase):
    def test_the_new_key_format_is_accepted(self):
        Uploader({"STORAGE_KEY_ID": NEW_KEY, "STORAGE_BUCKET": "test-bucket"}, send=lambda bucket, path: None)

    def test_a_malformed_key_is_still_refused(self):
        with self.assertRaises(ValueError):
            Uploader({"STORAGE_KEY_ID": "AKC-SHORT"})


if __name__ == "__main__":
    unittest.main()
