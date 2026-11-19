"""Settings for the log scripts: the KEY=VALUE file each server keeps beside the code, over the defaults below."""
from pathlib import Path

DEFAULTS = {"LOG_DIR": "logs", "RETENTION_DAYS": "30"}
SETTINGS_FILE = ".env"


def load_settings(path=SETTINGS_FILE):
    settings = dict(DEFAULTS)
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                settings[key.strip()] = value.strip()
    return settings
