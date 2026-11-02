# Lessons from real use

Kept by rotless-skill-refiner. Each lesson has a check that failed on the old skill and passes now; every later change must keep these checks passing (`python scripts/test_harness.py`).

## L-2026-11-02-2: a shortened canary still means the skill loaded
- From: n-20261102144625-8f14 (failure) · verdict: refine
- Change: Start: `harness.saw_canary()` matches the first 6 hex characters of the run's token; tokens are 8 hex (scripts/harness.py; used by run_eval.py and probe)
- Check: scripts/test_harness.py L-2 (red on snapshot 20261102-144626, green after) + rotless.json command `lesson-runner-checks`
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

## L-2026-11-02-6: the validator reads multi-line descriptions and rejects non-string metadata
- From: external code review (Gemini), 2026-11-02 · verdict: fix
- Change: Start: only `metadata` is parsed as a mapping; metadata values that YAML would read as numbers, booleans, null, lists or maps are rejected with "quote it" (scripts/quick_validate.py)
- Check: scripts/test_harness.py L-6 (red on snapshot 20261102-175456, green after)
- Why: a description on the next line containing a colon became a map and the valid skill was rejected

## L-2026-11-02-7: quoted YAML values read back as written
- From: external code review (Gemini), 2026-11-02 · verdict: fix
- Change: Start: `unquote()` in utils.py and quick_validate.py unescapes double-quoted (JSON-compatible) and single-quoted values
- Check: scripts/test_harness.py L-7
- Why: a description with quotes written by `set_frontmatter` came back with literal backslashes

## L-2026-11-02-8: the canary instruction sits at the top of the body
- From: external code review (Gemini), 2026-11-02 · verdict: fix
- Change: Start: `make_workspace` inserts it right after the frontmatter and asks for the token even if the task can't finish (scripts/harness.py)
- Check: scripts/test_harness.py L-8
- Why: an agent stopped early by permissions or a turn limit may never reach the end of a long SKILL.md

## L-2026-11-02-9: small eval sets keep both splits
- From: external code review (Gemini), 2026-11-02 · verdict: fix
- Change: Start: with 2+ queries in a group, test and train each get at least one (scripts/run_eval.py)
- Check: scripts/test_harness.py L-9
- Why: `--holdout 0.2` on 2 queries per group gave an empty test split

## L-2026-11-02-10: the eval review page is filled safely
- From: external code review (Gemini), 2026-11-02 · verdict: fix
- Change: Start: `scripts/make_eval_review.py` HTML-escapes name and description and writes `<` as \u003c inside the script block, in one pass; SKILL.md step 7 uses it
- Check: scripts/test_harness.py L-10
- Why: replacing the placeholders by hand let a query containing `</script>` break the page

## L-2026-11-02-11: one frontmatter parser for the validator and the runners
- From: external code review (Gemini), round 3, 2026-11-02 · verdict: fix
- Change: Start: `parse_frontmatter()` and `unquote()` live in utils.py; quick_validate.py imports them; `parse_skill_md()` uses them | Stop: the separate line-by-line parser in utils.py
- Check: scripts/test_harness.py L-11 (red on snapshot 20261102-184045, green after)
- Why: after L-6 the validator accepted a description written on the next line, but `run_eval.py` and `make_eval_review.py` read it as empty

## L-2026-11-02-12: the validator accepts rotless.json and the old keeper.json
- From: rename decision, 2026-11-02 · verdict: fix
- Change: Start: `quick_validate` counts either name as a tracked manifest and suggests rotless.json when there is none
- Check: scripts/test_harness.py L-12 (red on snapshot 20261102-195834, green after)
- Why: the manifest was renamed from keeper.json to rotless.json; skills with the old name must not be told their dependencies are untracked

## L-2026-11-02-13: input skills ship as SKILL.md.fixture
- From: installing rotless as a Codex plugin, 2026-11-02 · verdict: fix
- Change: Start: `make_workspace` renames `*.fixture` files back after copying a case's input files (scripts/harness.py); Step 4 tells authors to name input skills `SKILL.md.fixture`; the refiner's test case and its place-files.sh follow it
- Check: scripts/test_harness.py L-13 (red on snapshot 20261102-202732, green after); the repo check also fails on any SKILL.md outside skills/<name>/
- Why: the plugin install copied `evals/.../files/toy-search/SKILL.md`, a sample skill, and tools that scan a repo for SKILL.md files could offer it as one of rotless's skills
