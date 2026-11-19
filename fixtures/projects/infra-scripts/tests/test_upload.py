import unittest
from pathlib import Path

from scripts.upload import Uploader

TEST_KEY = "AK-TESTKEY00001"


class Upload(unittest.TestCase):
    def test_a_valid_key_id_is_accepted(self):
        Uploader({"STORAGE_KEY_ID": TEST_KEY, "STORAGE_BUCKET": "test-bucket"}, send=lambda bucket, path: None)

    def test_a_malformed_key_id_is_refused(self):
        with self.assertRaises(ValueError):
            Uploader({"STORAGE_KEY_ID": "nope"})

    def test_upload_sends_and_remembers(self):
        calls = []
        up = Uploader({"STORAGE_KEY_ID": TEST_KEY, "STORAGE_BUCKET": "test-bucket"},
                      send=lambda bucket, path: calls.append((bucket, path.name)))
        up.upload(Path("app-2026-10-01.log"))
        self.assertEqual(calls, [("test-bucket", "app-2026-10-01.log")])
        self.assertEqual(up.sent, ["app-2026-10-01.log"])


if __name__ == "__main__":
    unittest.main()
