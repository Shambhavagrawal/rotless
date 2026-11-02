# Lessons from real use

Kept by rotless-skill-refiner. Each lesson has a check that failed on the old skill and passes now; every later change must keep these checks passing.

## L-2026-11-02-1: launch CLIs installed as Windows shims
- From: n-20261102143209-0cd8 (failure) · verdict: refine
- Change: Start: `keeper.run()` resolves the command through PATH (`shutil.which`) before starting it (scripts/keeper.py, run)
- Check: `scripts/test_cli_shims.py` (red on snapshot 20261102-143209, green after) + rotless.json command `lesson-cli-shims`
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
- Change: Start: `<registry>/owned.json`; `init` and `own` add to it; `check` skips or refuses other skills with a rotless.json; first use migrates skills already checked
- Check: scripts/test_keeper.py L-6 (a third-party rotless.json's command never runs until `own`)
- Why: any installed skill shipping a rotless.json got its commands run by `check --all`

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
- Note: the review predicted that CI on ubuntu-latest would fail, but the previous CI run passed there because those programs weren't on that runner's PATH

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

## L-2026-11-02-12: works from a plugin install: finds your skills, keeps state outside the install folder
- From: README audit, 2026-11-02 · verdict: fix
- Change: Start: `keeper.py` also searches every agent's user skills folder (`USER_SKILL_DIRS`); the registry is an existing `skill-registry/` next to the skills folder, else `~/.skill-registry`, never the install folder. rotless-skill-refiner's notes.py uses the same rule
- Check: scripts/test_keeper.py L-12 (red on snapshot 20261102-194957, green after): a plugin-cache layout keeps state in ~/.skill-registry and finds ~/.claude/skills; notes.py agrees; an existing registry keeps being used
- Why: installed as a Claude Code plugin, the registry landed in the plugin cache (wiped on update) and your own skills in ~/.claude/skills were invisible to `check --all` and `list`
- Follow-up: the check compared a short (8.3) Windows temp path with keeper's resolved long path and failed on GitHub's Windows runners (RUNNER~1); it now compares resolved paths. Reproduced locally with a short-named TEMP before fixing.

## L-2026-11-02-13: the manifest is rotless.json; keeper.json still works
- From: rename decision, 2026-11-02 · verdict: fix
- Change: Start: `manifest()` reads `rotless.json`, else the old `keeper.json`; `init` writes `rotless.draft.json`; `check` and `lint` suggest renaming an old-name file | the four rotless skills renamed theirs
- Check: scripts/test_keeper.py L-13 (red on snapshot 20261102-195832, green after): new and old names both lint and check, the old name gets the hint, init writes the new draft name
- Why: "keeper" was the skill's old name (skill-keeper); the file travels into every skill built with rotless, so its name should say where it comes from

## L-2026-11-02-14: new repos in a skill's space stay listed until reviewed
- From: the user's design review, 2026-11-02 · verdict: fix
- Change: Start: `chk_search` keeps unreviewed repos out of "seen", so they're reported NEW in every check, with a hint to research them with rotless-github-research; `ack <skill> search:<name>` marks them reviewed (`accept_search`). `fix` now offers that research.
- Check: scripts/test_keeper.py L-14 (red on snapshot 20261102-212306, green after)
- Why: a check marked every new repo as seen the moment it reported it, so one ignored report meant the repo was never shown again and nobody looked at what could be borrowed

## L-2026-11-02-15: skills remind you when they haven't been updated or checked for a while
- From: the user's design review, 2026-11-02 · verdict: fix
- Change: Start: `rotless.json` records `updated` (new `keeper.py updated` command; `init` sets it) and `checked` (a clean `check` sets it); `freshness()` uses `remindAfterDays`, 15 by default; `status` and `list` name skills that are due; the field-notes footer asks the agent to offer a check at the end of a task when its skill is due
- Check: scripts/test_keeper.py L-15 (red on snapshot 20261102-212306, green after)
- Why: checks run only on demand, and nothing reminded anyone to ask; `status` only knew the last check run and used a fixed 7 days

## L-2026-11-02-16: only skills you own remind you
- From: external code review (Gemini), round 4, 2026-11-02 · verdict: fix
- Change: Start: the field-notes footer (every rotless skill, both templates) runs `keeper.py status` once per session and offers a check only when `status` lists the skill as due, and never in a reply that must stay machine-readable. Stop: reading `rotless.json` and comparing dates after every task
- Check: tests/check_repo.py check 7 (fails while any footer lacks `keeper.py status`; red on the old footers, green after)
- Why: `status` already lists only owned skills, but the footer didn't use it, so 15 days after install everyone would be asked to modernize rotless's own skills, which the modernizer then refuses; it also cost a file read after every task
