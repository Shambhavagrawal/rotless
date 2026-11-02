# Lessons from real use

Kept by rotless-skill-refiner. Each lesson has a check that failed on the old skill and passes now; every later change must keep these checks passing.

## L-2026-11-02-1: launch CLIs installed as Windows shims
- From: n-20261102143209-0cd8 (failure) · verdict: refine
- Change: Start: `keeper.run()` resolves the command through PATH (`shutil.which`) before starting it (scripts/keeper.py, run)
- Check: `scripts/test_cli_shims.py` (red on snapshot 20261102-143209, green after) + keeper.json command `lesson-cli-shims`
- Why: on Windows, npm installs codex, gemini and npx as .CMD files; `check` reported "`codex exec` no longer exists" while codex worked fine
