# Lessons from real use

Kept by rotless-skill-refiner. Each lesson has a check that failed on the old skill and passes now; every later change must keep these checks passing.

## L-2026-11-02-1: launch CLIs installed as Windows shims
- From: n-20261102143209-0cd8 (failure) · verdict: refine
- Change: Start: `keeper.run()` resolves the command through PATH (`shutil.which`) before starting it (scripts/keeper.py, run)
- Check: `scripts/test_cli_shims.py` (red on snapshot 20261102-143209, green after) + keeper.json command `lesson-cli-shims`
- Why: on Windows, npm installs codex, gemini and npx as .CMD files; `check` reported "`codex exec` no longer exists" while codex worked fine

## L-2026-11-02-2: python and python3 in checks run this interpreter
- From: external code review (Gemini), 2026-11-02 · verdict: fix
- Change: Start: `run()` maps `python`/`python3` to `sys.executable` (scripts/keeper.py)
- Check: scripts/test_keeper.py L-2, with no Python on PATH (red on snapshot 20261102-175457, green after)
- Why: hosts with only `python3` failed every `python scripts/…` check with "not found"

## L-2026-11-02-3: {skill} survives backslashes and spaces
- From: external code review (Gemini), 2026-11-02 · verdict: fix
- Change: Start: `chk_command` substitutes `{skill}` after `shlex.split`
- Check: scripts/test_keeper.py L-3
- Why: shlex ate Windows backslashes and split paths containing spaces

## L-2026-11-02-4: a failed GraphQL call is a WARN, not "every repo was deleted"
- From: external code review (Gemini), 2026-11-02 · verdict: fix
- Change: Start: `gql()` returns the error; `chk_repos` warns and skips the batch, `existing_repos` keeps the candidates
- Check: scripts/test_keeper.py L-4; a real NOT_FOUND still FAILs
- Why: a rate limit returned no data and every watched repo was reported as gone

## L-2026-11-02-5: claim quotes with backticks match
- From: n-20261102143302-ca79 (failure) and external code review (Gemini), 2026-11-02 · verdict: fix
- Change: Start: `quote_where()` normalises quote and text the same way
- Check: scripts/test_keeper.py L-5
- Why: lines were stripped of `*` and backticks, quotes weren't, so a backticked quote never matched

## L-2026-11-02-6: only skills marked as yours get checks that run code
- From: external code review (Gemini), 2026-11-02 · verdict: fix (security)
- Change: Start: `<registry>/owned.json`; `init` and `own` add to it; `check` skips or refuses other skills with a keeper.json; first use migrates skills already checked
- Check: scripts/test_keeper.py L-6 (a third-party keeper.json's command never runs until `own`)
- Why: any installed skill shipping a keeper.json got its commands run by `check --all`

## L-2026-11-02-7: an offline lint gate
- From: external code review (Gemini), 2026-11-02 · verdict: fix
- Change: Start: `keeper.py lint`: manifests and eval sets parse, claim quotes present, no untracked references; no network, no skill code; runs in CI
- Check: scripts/test_keeper.py L-7
- Why: a PR could edit SKILL.md and orphan a claim quote or add an untracked CLI with nothing catching it before someone ran `check`
- Also: removed the `claude-md-flow-rule` claim, which checked the user's home folder and failed for anyone without the optional global rule

## L-2026-11-02-8: a server outage is a WARN, not "the endpoint moved"
- From: n-20261102180527-5772 (failure) · verdict: fix
- Change: Start: `transient()`; API and doc checks report 429 and 5xx as WARN "rerun later"; other 4xx still FAIL (scripts/keeper.py)
- Check: scripts/test_keeper.py L-8 (red on snapshot 20261102-175457, green after)
- Why: skills.sh flapped (200, 503, 503, 200) and `check` said the endpoint changed or moved

## L-2026-11-02-9: only shell gets parsed for commands
- From: external code review (Gemini), round 3, 2026-11-02 · verdict: fix
- Change: Start: `strip_examples()` blanks non-shell fences (markdown, text, json, python…) and ASCII diagrams; shell comments are dropped; a lone `|` splits only with spaces around it (scripts/keeper.py extract)
- Check: scripts/test_keeper.py L-9 (red on snapshot 20261102-184047, green after)
- Why: a markdown table template produced CLIs `repo`, `last`, `license`; `--kind a|b|c` produced `correction`, `workaround`. Harmless only while no such program is on PATH: a Linux host with `repo` or `last` installed would report false GAPs
- Note: the review predicted CI on ubuntu-latest would fail; the previous CI run passed there, so those programs weren't on that runner's PATH. The bug was real, the prediction wasn't

## L-2026-11-02-10: coverage normalises claim quotes like chk_claim
- From: external code review (Gemini), round 3, 2026-11-02 · verdict: fix
- Change: Start: `coverage()` compares `norm_text()` of quote and limit phrase
- Check: scripts/test_keeper.py L-10
- Why: a backticked quote passed `chk_claim` but left its limit reported as an untracked GAP

## L-2026-11-02-11: claim and MCP checks report outages as WARN with the status
- From: external code review (Gemini), round 3, 2026-11-02 · verdict: fix
- Change: Start: `chk_claim` http checks and `chk_mcp` use `transient()`; a non-200 MCP reply names its status instead of a parse error
- Check: scripts/test_keeper.py L-11
- Why: a 503 turned a claim into "CHANGED: no longer true (now: None)" and an MCP check into "KeyError: 'result'"
