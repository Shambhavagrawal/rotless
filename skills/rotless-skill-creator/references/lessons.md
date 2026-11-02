# Lessons from real use

Kept by rotless-skill-refiner. Each lesson has a check that failed on the old skill and passes now; every later change must keep these checks passing (`python scripts/test_harness.py`).

## L-2026-11-02-2: a shortened canary still means the skill loaded
- From: n-20261102144625-8f14 (failure) · verdict: refine
- Change: Start: `harness.saw_canary()` matches the first 6 hex characters of the run's token; tokens are 8 hex (scripts/harness.py; used by run_eval.py and probe)
- Check: scripts/test_harness.py L-2 (red on snapshot 20261102-144626, green after) + keeper.json command `lesson-runner-checks`
- Why: Codex printed `ROTLESS-CANARY-63b55b6b` for a 10-character token; an exact match scored a real trigger as a miss

## L-2026-11-02-3: failed runs keep their stderr
- From: n-20261102144625-24b2 (missing) · verdict: refine
- Change: Start: `one_run` keeps the last 300 characters of stderr when a run exits non-zero; results list `error_samples` (scripts/run_eval.py)
- Check: scripts/test_harness.py L-3
- Why: 3 of 18 runs errored with 6 parallel Codex sessions and nothing said why

## L-2026-11-02-4: outputs include what the agent wrote beside the skills folders
- From: n-20261102144626-c981 (missing) · verdict: refine
- Change: Start: `run_case.snapshot()` skips only the installed skill copies, not whole `.agents/`, `.claude/`… trees (scripts/run_case.py)
- Check: scripts/test_harness.py L-4
- Why: a with-skill run logged a field note into `.agents/skill-registry`, but outputs/ showed only the reply, so the grader couldn't see it

## L-2026-11-02-5: errored runs are no data, not "not triggered"
- From: n-20261102145308-b18c (failure) · verdict: refine
- Change: Start: `run_eval.summarise()` rates triggers over completed runs only; a query with none is no data (pass null) and `score()` leaves it out, reporting `no_data` (scripts/run_eval.py)
- Check: scripts/test_harness.py L-5 (red on snapshot 20261102-145308, green after)
- Why: when Codex hit its usage limit, 8 of 12 runs errored and the old scoring reported accuracy 1.0, because never-run negatives "passed"
