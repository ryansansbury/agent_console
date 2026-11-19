# Operations notes

## Log rotation

`rotate_logs` runs from cron on every app server at 2:15 each night as the app's own user, from the folder that holds
this repo. It reads its settings from `.env` in that folder. Run it by hand with `--dry-run` first if you change
anything.

The archive bucket keeps uploaded logs for a year, and its lifecycle rule handles the rest.

## The settings file

Each server's `.env` is written by the provisioning job and holds the log folder, the archive bucket and the storage
credentials. It never goes into git, a ticket or chat. If a value is wrong, ask in the ops channel and the on-call
person fixes it on the servers.

## Storage key rotation, November 2

We rotated the archive storage keys on November 2. New key ids start with `AKC-` and have 16 capital letters or digits
after the dash (the old ones were `AK-` and 12). The provisioning job pushed the new keys to every server's `.env` the
same day, and the old keys stopped working on November 3.

## When a nightly run fails

The cron mail goes to the ops channel. Check the last lines of `logs/rotate.out` on the server, then rerun with
`--dry-run` to see what it would do.
