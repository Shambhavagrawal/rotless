# Lessons from real use

rotless-skill-refiner records its own lessons here. Each lesson has a check that failed on the old skill and passes now; every later change must keep these checks passing (`python scripts/notes.py selftest`, run in CI).

## L-2026-11-02-1: JSON-style secrets are redacted
- From: external code review (Gemini), round 3, 2026-11-02 · verdict: fix
- Change: Start: the key=value secret pattern allows a quote between key and colon and stops values at `,;}])` (scripts/notes.py SECRETS)
- Check: notes.py selftest (the new assertion failed on the old pattern, passes now)
- Why: evidence pasted as JSON (`{"token": "…"}`) kept the secret, because the old pattern needed the colon right after the key

## L-2026-11-02-2: snapshots never collide or copy repo internals
- From: external code review (Gemini), round 3, 2026-11-02 · verdict: fix
- Change: Start: a second snapshot in the same second gets a `-2` suffix; `.git`, `.venv`, `node_modules`, `*.pyc` and `*.skill` are skipped
- Check: notes.py selftest (two snapshots in one second; no `.git` in the copy)
- Why: two snapshots in one second raised FileExistsError, and copying `.git` packs (read-only on Windows) breaks later cleanup

## L-2026-11-02-3: notes survive a plugin install and update
- From: README audit, 2026-11-02 · verdict: fix
- Change: Start: `registry()` uses an existing `skill-registry/` next to the skills folder, else `~/.skill-registry`; `roots()` includes every agent's user skills folder (scripts/notes.py), the same rule as rotless-skill-modernizer
- Check: rotless-skill-modernizer's test_keeper.py L-12 checks notes.py and keeper.py agree in a plugin-cache layout (red on snapshot 20261102-194958, green after)
- Why: in a plugin install, notes would have been written into the plugin cache and lost on the next update
