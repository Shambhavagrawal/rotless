#!/usr/bin/env python3
"""Offline lesson checks for rotless-github-research's scripts (no network, no gh calls).

  python scripts/test_offline.py [skill-dir]     # default: this skill; pass a snapshot to see it fail
"""
import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path

skill = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
scripts = skill / "scripts"
sys.path.insert(0, str(scripts))


def load(name):
    spec = importlib.util.spec_from_file_location(name, scripts / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


fails = []

# L-1: the MCP Registry gets the first word of the query, not the whole URL-encoded phrase
srcsweep = load("srcsweep")
urls = []
srcsweep.get = lambda url, headers=None: urls.append(url) or {"servers": []}
srcsweep.run_source("mcp", "repository discovery", 3)
if not urls or "search=repository&" not in urls[0]:
    fails.append(f"L-1: mcp must search the first word only (asked for {urls[:1]})")

# L-4: hf-papers is a search source; a paper's linked GitHub repo feeds --repos
srcsweep.get = lambda url, headers=None: [{"paper": {"id": "2605.09359", "title": "Skill-R1: Agent Skill Evolution",
                                                    "githubRepo": "https://github.com/octo/skill-r1", "upvotes": 3,
                                                    "publishedAt": "2026-05-10T00:00:00.000Z"}}]
_, res, err = srcsweep.run_source("hf-papers", "skill evolution", 3)
if err or not res or res[1][0]["repo"] != "https://github.com/octo/skill-r1" or not res[1][0]["url"].endswith("/papers/2605.09359"):
    fails.append(f"L-4: hf-papers must search papers and keep the linked repo (err={err}, got={res})")


# L-2: a GraphQL call that fails as a whole (rate limit, bad token) aborts instead of reporting every repo as NOT FOUND
ghverify = load("ghverify")


class Done:
    def __init__(self, out):
        self.stdout, self.stderr, self.returncode = out, "", 1


ghverify.subprocess.run = lambda *a, **k: Done(json.dumps({"errors": [{"type": "RATE_LIMITED", "message": "API rate limit exceeded"}]}))
try:
    got = ghverify.fetch([("octo", "repo")])
    fails.append(f"L-2: fetch returned {got!r} on a failed GraphQL call; it must stop with the error")
except SystemExit as e:
    if "rate limit" not in str(e).lower():
        fails.append(f"L-2: the abort message should carry GraphQL's error (got {e})")
ghverify.subprocess.run = lambda *a, **k: Done(json.dumps({"data": {"r0": None}, "errors": [{"type": "NOT_FOUND", "message": "x"}]}))
try:
    if ghverify.fetch([("octo", "gone")]) != {"r0": None}:
        fails.append("L-2: a plain NOT_FOUND must still come back as a missing repo")
except SystemExit:
    fails.append("L-2: a plain NOT_FOUND must not abort")

# L-3: --json carries the same [noise?] signal as the table
ghsweep = load("ghsweep")
ghsweep.shutil.which = lambda name: "gh"
ghsweep.run_query = lambda q, args: (1, [{"full_name": "someone/awesome-agents", "html_url": "u", "description": "list",
                                          "stargazers_count": 5, "pushed_at": "2026-01-01T00:00:00Z",
                                          "created_at": "2025-01-01T00:00:00Z", "language": None, "topics": [],
                                          "fork": False, "archived": False}])
sys.argv = ["ghsweep.py", "agents", "--json"]
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    ghsweep.main()
rows = json.loads(buf.getvalue())
if not rows or rows[0].get("noise") is not True:
    fails.append(f"L-3: --json rows need a noise flag (got keys {sorted(rows[0]) if rows else []})")

if fails:
    print("FAIL\n" + "\n".join(fails))
    sys.exit(1)
print("ok: 4 research-script lessons hold")
