# infra-scripts

Small scripts the app servers run from cron. Right now that's log rotation.

`scripts/rotate_logs.py` keeps the app's daily logs (`logs/app-YYYY-MM-DD.log`) for the retention window, then uploads
each one to the archive bucket and deletes it. `rotate(log_dir, today, settings, uploader)` does the work, and `main()`
wires it to the real settings.

The settings come from `.env` beside the code on each server, which also holds the storage credentials, so it stays
out of git. `docs/OPERATIONS.md` is the runbook.

## Tests

```
python3 -m unittest
```
