"""Send a log file to the archive bucket. The transfer itself is a function handed in, so tests never touch storage."""
import re

KEY_ID = re.compile(r"^AK-[0-9A-Z]{12}$")


class Uploader:
    def __init__(self, settings, send=None):
        key_id = settings.get("STORAGE_KEY_ID", "")
        if not KEY_ID.match(key_id):
            raise ValueError("the storage key id isn't in the expected format")
        self.bucket = settings.get("STORAGE_BUCKET", "")
        self.key_id = key_id
        self.send = send or self._print
        self.sent = []

    def upload(self, path):
        self.send(self.bucket, path)
        self.sent.append(path.name)

    @staticmethod
    def _print(bucket, path):
        print(f"would upload {path.name} to {bucket}")
