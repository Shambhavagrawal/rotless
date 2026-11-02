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

## L-2026-11-02-14: a trigger test stops once the skill loads
- From: external code review (Gemini), round 4, 2026-11-02 · verdict: fix · verdict: optimize
- Change: Start: with a canary, `make_workspace` replaces the test copy's body with one line: print the token and stop, without tools or the task. Stop: L-8's "even if you can't finish the task" note above the real body (scripts/harness.py)
- Check: scripts/test_harness.py L-14 (red on snapshot r11-snap, green after); live: `harness.py probe --agent claude` replied with the token alone in 13.8 s
- Why: agents choose a skill from its name and description, so the body changes nothing being measured; running the whole task took up to 300 s per query and used up the Codex quota

## L-2026-11-02-15: the review server answers only its own page
- From: external code review (Gemini), round 4, 2026-11-02 · verdict: fix
- Change: Start: `ReviewHandler._own_page()` requires Host to be 127.0.0.1 or localhost on the server's port, and Origin, when sent, to match; other requests get 403 (eval-viewer/generate_review.py)
- Check: scripts/test_harness.py L-15 (red on snapshot r11-snap, green after: a POST from another site was answered 200 and wrote feedback.json)
- Why: any page open in the browser could POST to 127.0.0.1:3117 and put instructions in feedback.json, which the agent reads as the user's review

## L-2026-11-02-16: the viewer never kills another program
- From: external code review (Gemini), round 4, 2026-11-02 · verdict: fix
- Change: Stop: `_kill_port()` (lsof + SIGTERM on whatever held the port). Continue: falling back to a free port
- Check: scripts/test_harness.py L-16 (red on snapshot r11-snap, green after)
- Why: it could end an unrelated process that happened to use port 3117, and printed a warning on Windows, which has no lsof

## L-2026-11-02-17: run_case sees every change to the input files
- From: external code review (Gemini), round 4, 2026-11-02 · verdict: fix
- Change: Start: `snapshot()` keeps (mtime in ns, size); `changes()` returns changed and deleted files; deleted ones go to `deleted-files.txt` beside outputs/ (scripts/run_case.py)
- Check: scripts/test_harness.py L-17 (red on snapshot r11-snap, green after)
- Why: a rewrite within the clock's resolution kept the same float mtime and was missed, and deleted files were never reported to the graders

## L-2026-11-02-18: the review pages load no fonts and name no single agent
- From: external code review (Gemini), round 4, 2026-11-02 · verdict: fix
- Change: Start: system font stacks in eval-viewer/viewer.html and assets/eval_review.html; "your agent session" in the two lines that said Claude Code; docs/privacy.md names the one remaining load (SheetJS, pinned with a hash)
- Check: scripts/test_harness.py L-18 (red on snapshot r11-snap, green after); tests/check_repo.py check 8 (every page's external script or stylesheet is in docs/privacy.md)
- Why: the pages called fonts.googleapis.com on every open, which docs/privacy.md didn't mention, and NOTICE claimed the wording was already agent-neutral

## L-2026-11-02-19: trigger tests on Claude skip the user's own skills
- From: running the 20-query trigger sets on this machine, 2026-11-02 · verdict: fix
- Change: Start: `AGENTS["claude"]["isolate"] = ["--setting-sources", "project"]`; `run_eval.py` runs with `isolate=True` and only warns about installed copies on agents without it (scripts/harness.py, scripts/run_eval.py)
- Check: scripts/test_harness.py L-19 (red on snapshot r11-snap, green after); live: `claude -p --setting-sources project` listed no user-level skills
- Why: an installed copy with the same description competes with the renamed test copy, and when the agent picks it the run counts as a missed trigger

## L-2026-11-02-20: a block description with blank lines is replaced whole
- From: external code review (Gemini), round 4, 2026-11-02 · verdict: fix
- Change: Start: `set_frontmatter` also takes blank lines that are followed by more indented lines of the same value (scripts/harness.py)
- Check: scripts/test_harness.py L-20 (red on snapshot r11-snap, green after)
- Why: a `description: |` with two paragraphs kept its second paragraph after the key was replaced, which left broken YAML in the test copy
