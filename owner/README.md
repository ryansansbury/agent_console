# The owner's steps

Everything in this folder runs on the owner's own machine in a normal terminal because it starts programs, calls the models, opens a local server or drives a browser. Every command runs from the build folder.

## Before run 1

The vendors' names go in `config/names.json` after their check. The jobs in `fixtures/README.md` get a read before the first freeze.

## Run 1, the selftest and the tuning round

```
bash owner/bootstrap.sh
bash owner/keys.sh
bash owner/run.sh 1
```

The first script makes `.venv` with Homebrew's Python and installs nothing.

The second copies the two API keys into this project's own Keychain items and prints only their lengths. The Keychain may ask to allow access.

The third runs the selftest first. The selftest proves the real tools, git, the fixture server, the reader, the masking and the sanitizer with no model. It stops the run if anything fails. Then the run records a dev morning for each model in about 15 minutes.

A model whose morning wasn't kept (a model error or a held scan) runs again with the same command. The models already in the latest round are skipped while nothing they were made under has changed. The dev round also tries the budget test once on Sonnet's parser-lib when the test has a limit. The limit then meets a real model before stage 2 freezes it.

## Run 2, the recordings for the page

This one comes after the tuning round and the stage 2 freeze.

```
bash owner/run.sh 2
```

It does the rest in one go and takes about 30 minutes unattended. It checks the vendors' names in `config/names.json` and freezes stage 1 again on them. Then it runs the selftest on them and records a morning for each model. The research job's reader-off run and the budget test come next. Last it makes the real build and runs the browser check. The page shows the real clock. A morning start reads best for that reason.

Run 2 stops at the start when `config/names.json` is missing.

## Run 3, the screenshots

```
bash owner/screenshots.sh
```

It runs once for each review round.

## What each script does

- `selftest.py` runs the stand-in through the real tools in real throwaway workspaces and tries every call that has to be refused. It checks the programs' variables and the masking. Then it scans what it recorded and checks every workspace is gone.
- `record.py` records a run. Each job gets a fresh workspace in the system's temporary space while the sessions of a morning run at once. Every text passes the sanitizer before it's stored. A run moves into `data/` only when every session finished with a clean scan.
- `workspaces.py` makes and removes the workspaces. `fixture_server.py` serves the three vendors' pages on a free port. `sanitize.py` swaps out this machine's paths and names. Its scan then looks for any it missed. `stand_in.py` is the scripted stand-in for the model.
- `check_names.py` checks the vendors' names before stage 1 freezes on them. It holds them to the cast test's rules and to what the scorer needs. Then it runs the validator over the filled-in fixtures.
- `browser_check.py` drives Chrome through every view, state and tour step at four widths. It writes the screenshots, the layout check, the console's errors and the requests to `owner/out/`.

Nothing here prints a key. Nothing an agent does can reach this repo because every workspace sits outside it and is deleted when its session ends.
