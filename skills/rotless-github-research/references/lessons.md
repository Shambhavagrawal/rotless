# Lessons from real use

Kept by rotless-skill-refiner. Each lesson has a check that failed on the old skill and passes now; every later change must keep these checks passing (`python scripts/test_offline.py`, run in CI).

## L-2026-11-02-1: the MCP Registry gets one word, not an encoded phrase
- From: external code review (Gemini), 2026-11-02 · verdict: fix
- Change: Start: `srcsweep.mcp()` decodes the query before taking its first word (scripts/srcsweep.py)
- Check: scripts/test_offline.py L-1 (red on snapshot 20261102-175456, green after)
- Why: `run_source` URL-encodes the query, so `split()` never split and the registry got `repository%20discovery`

## L-2026-11-02-2: a failed GraphQL call stops instead of calling every repo NOT FOUND
- From: external code review (Gemini), 2026-11-02 · verdict: fix
- Change: Start: `ghverify.fetch()` exits with GraphQL's message on any error other than NOT_FOUND (scripts/ghverify.py)
- Check: scripts/test_offline.py L-2 (red on snapshot, green after); a plain NOT_FOUND still reports the repo as missing
- Why: a rate limit or bad token returned `{"errors": …}` with no data, and every repo in the batch was reported deleted

## L-2026-11-02-3: --json carries the noise flag
- From: external code review (Gemini), 2026-11-02 · verdict: fix
- Change: Start: each row gets `noise` before the JSON branch (scripts/ghsweep.py)
- Check: scripts/test_offline.py L-3
- Why: agents reading `--json` lost the `[noise?]` signal the table shows

## L-2026-11-02-4: papers are a search source, and their code repos feed --repos
- From: n-20261102143313-1e11 (missing) · verdict: fix
- Change: Start: `hf-papers` in srcsweep.py (Hugging Face paper search; a paper's `githubRepo` goes in `repo`, so `--repos | ghverify.py -` verifies the code behind a paper); SKILL.md and README say 21 sources
- Check: scripts/test_offline.py L-4 (red on snapshot 20261102-185023, green after); live: "skill evolution" gave 120 papers and repos such as Zhouyaner/Eviskill
- Why: rotless.json monitored the papers endpoint and sources.md documented it, but `--sources hf-papers` failed with "unknown source"
