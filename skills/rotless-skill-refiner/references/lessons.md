# Lessons from real use

Kept by rotless-skill-refiner (this file is its own ledger). Each lesson has a check that failed on the old skill and passes now; every later change must keep these checks passing (`python scripts/notes.py selftest`, run in CI).

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
