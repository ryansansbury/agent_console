"""Rotate the app's daily logs: anything past the retention window is uploaded to the archive and deleted.

    python3 -m scripts.rotate_logs [--dry-run]
"""
import argparse
import re
from datetime import date
from pathlib import Path

from scripts.settings import load_settings
from scripts.upload import Uploader

NAME = re.compile(r"^app-(\d{4}-\d{2}-\d{2})\.log$")


def log_files(log_dir):
    """(path, the day it covers) for every app log in log_dir, oldest first."""
    out = []
    for p in sorted(Path(log_dir).iterdir()):
        m = NAME.match(p.name)
        if m:
            out.append((p, date.fromisoformat(m.group(1))))
    return out


def rotate(log_dir, today, settings, uploader, dry_run=False):
    """Upload and delete every log older than the retention window. Returns what it did as (action, file name)."""
    retention = int(settings["RETENTION_DAYS"])
    done = []
    for path, day in log_files(log_dir):
        if (today - day).days > retention:
            if not dry_run:
                uploader.upload(path)
                path.unlink()
            done.append(("uploaded", path.name))
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rotate the app's daily logs.")
    ap.add_argument("--dry-run", action="store_true", help="say what would happen and change nothing")
    args = ap.parse_args(argv)
    settings = load_settings()
    uploader = Uploader(settings)
    for action, name in rotate(settings["LOG_DIR"], date.today(), settings, uploader, args.dry_run):
        print(f"{action} {name}")


if __name__ == "__main__":
    main()
