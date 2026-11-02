#!/usr/bin/env python3
"""Offline lesson checks for keeper.py (no network: gh calls are faked, subprocess runs stay local).

  python scripts/test_keeper.py [skill-dir]     # default: this skill; pass a snapshot to see it fail
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

skill = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp(prefix="rotless-keeper-test-"))
os.environ["SKILL_REGISTRY"] = str(tmp / "registry")  # never touch the real registry
spec = importlib.util.spec_from_file_location("keeper_under_test", skill / "scripts" / "keeper.py")
keeper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keeper)
fails = []

# L-2: `python`/`python3` in a check run the interpreter running keeper.py (hosts often have only one
# of the two names on PATH); simulate the worst case, no Python on PATH at all
old_path = os.environ.get("PATH", "")
os.environ["PATH"] = str(tmp)
rc, out, _ = keeper.run(["python3", "-c", "import sys; print(sys.executable)"])
os.environ["PATH"] = old_path
if rc != 0 or Path(out.strip()).resolve() != Path(sys.executable).resolve():
    fails.append(f"L-2: python3 must map to {sys.executable} (rc={rc}, got {out.strip()!r})")

# L-3: {skill} survives backslashes and spaces in the skill's path
sdir = tmp / "a skill dir"
sdir.mkdir()
res = keeper.chk_command({"id": "t", "run": 'python -c "import os,sys; sys.exit(0 if os.path.isdir(sys.argv[1]) else 3)" {skill}'}, sdir)
if res[0]["status"] != "OK":
    fails.append(f"L-3: {{skill}} was mangled: {res[0]['detail']}")

# L-4: a GraphQL call that fails as a whole is a WARN, not "every repo was deleted"; a real NOT_FOUND still FAILs
real_run = keeper.run
keeper.run = lambda cmd, cwd=None, timeout=180: (1, json.dumps({"errors": [{"type": "RATE_LIMITED", "message": "API rate limit exceeded"}]}), "")
out, _ = keeper.chk_repos([{"type": "github-repo", "repo": "octo/repo"}], {})
if any(r["status"] == "FAIL" for r in out):
    fails.append("L-4: a rate-limited GraphQL call reported repos as deleted")
if shutil.which("gh") and keeper.existing_repos(["octo/repo"]) != {"octo/repo"}:
    fails.append("L-4: existing_repos must keep candidates when GraphQL failed, not drop them")
keeper.run = lambda cmd, cwd=None, timeout=180: (1, json.dumps({"data": {"r0": None}, "errors": [{"type": "NOT_FOUND", "message": "x"}]}), "")
out, _ = keeper.chk_repos([{"type": "github-repo", "repo": "octo/gone"}], {})
if not any(r["status"] == "FAIL" for r in out):
    fails.append("L-4: a repo GraphQL reports NOT_FOUND must still FAIL")
keeper.run = real_run

# L-5: a claim quote with backticks matches the skill's text (both sides normalised the same way)
res = keeper.chk_claim({"id": "q", "quote": "Codex (`codex exec`)"}, [("SKILL.md", ["Verified: Codex (`codex exec`)."])], sdir)
if any("no longer in the skill" in r["detail"] for r in res):
    fails.append("L-5: a backticked quote was reported missing")

# L-6: a keeper.json you didn't mark as yours never gets its commands run
root = tmp / "skills"
mod = root / "rotless-skill-modernizer" / "scripts"
mod.mkdir(parents=True)
shutil.copy2(skill / "scripts" / "keeper.py", mod / "keeper.py")
third = root / "third-party"
third.mkdir()
marker = (tmp / "ran.txt").as_posix()
(third / "SKILL.md").write_text("---\nname: third-party\ndescription: x\n---\nbody\n", encoding="utf-8")
(third / "keeper.json").write_text(json.dumps({"skill": "third-party", "deps": [
    {"type": "command", "id": "x", "run": f"python -c \"open('{marker}', 'w').write('ran')\""}]}), encoding="utf-8")
env = {**os.environ, "SKILL_ROOTS": ""}


def k(*args):
    return subprocess.run([sys.executable, str(mod / "keeper.py"), *args], cwd=tmp, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


k("check", "--all")
if Path(marker).exists():
    fails.append("L-6: check --all ran a command from a skill not marked as yours")
else:
    r = k("check", "third-party")
    if Path(marker).exists() or r.returncode == 0:
        fails.append("L-6: check <skill> on a skill not marked as yours must refuse")
    elif k("own", "third-party").returncode != 0 or (k("check", "third-party") and not Path(marker).exists()):
        fails.append("L-6: after `own`, check must run the skill's commands")

# L-7: `lint` is an offline gate: a claim quote missing from the text fails it, a clean skill passes
lint = root / "linty"
lint.mkdir()
(lint / "SKILL.md").write_text("---\nname: linty\ndescription: x\n---\nThe sky is blue.\n", encoding="utf-8")
(lint / "keeper.json").write_text(json.dumps({"skill": "linty", "deps": [], "claims": [{"id": "c", "quote": "the sky is green"}]}), encoding="utf-8")
bad = k("lint", str(lint)).returncode
(lint / "keeper.json").write_text(json.dumps({"skill": "linty", "deps": [], "claims": [{"id": "c", "quote": "the sky is blue"}]}), encoding="utf-8")
good = k("lint", str(lint)).returncode
if bad == 0 or good != 0:
    fails.append(f"L-7: lint must fail on an orphaned claim quote and pass a clean skill (exit {bad}/{good})")

# L-8: a server outage (5xx, 429) is a WARN to rerun, not "the endpoint moved"; a 404 still FAILs
real_http = keeper.http
for code, want in ((503, "WARN"), (429, "WARN"), (404, "FAIL")):
    keeper.http = lambda *a, **k: (code, "")
    got = keeper.chk_http({"id": "h", "url": "https://example.invalid/api"}, None)[0]["status"]
    got_doc = keeper.chk_doc({"id": "d", "url": "https://example.invalid/doc"}, None)[0][0]["status"]
    if got != want or got_doc != want:
        fails.append(f"L-8: HTTP {code} must be {want} (api check gave {got}, doc check gave {got_doc})")
keeper.http = real_http

# L-9: extract() only reads shell commands: not markdown/text templates, tables, diagrams, comments or a|b flag values
ex = tmp / "extract-skill"
ex.mkdir()
fence = "`" * 3
(ex / "SKILL.md").write_text("\n".join([
    "---", "name: extract-skill", "description: x", "---",
    fence + "markdown", "| repo | role | last substantive commit | license |", "|---|---|---|---|", fence,
    fence, "idea ─► research ─► create", "your skill/      keeper.py", fence,
    fence + "bash", "gh search code foo   # relevance filter; homonyms drag in noise",
    "python notes.py add x --kind failure|correction|workaround", fence, ""]), encoding="utf-8")
clis = set(keeper.extract(ex)[0]["cli"])
if clis - {"gh", "python"}:
    fails.append(f"L-9: extract() took non-commands for CLIs: {sorted(clis - {'gh', 'python'})}")

# L-10: coverage() normalises claim quotes like chk_claim, so a backticked quote covers its limit
cov = keeper.coverage({"claims": [{"id": "l", "quote": "`search` 30/min"}]},
                      {"cli": {}, "sub": {}, "url": {}, "repo": {}, "version": {}, "limit": {"search 30/min": "SKILL.md:1"}}, offline=True)
if any(r["id"].startswith("gap:claim") for r in cov):
    fails.append("L-10: a backticked claim quote left its limit reported as untracked")

# L-11: claim and MCP checks treat a server outage as WARN with the status, not CHANGED or a parse error
real_http = keeper.http
keeper.http = lambda *a, **k: (503, '{"error": "unavailable"}')
cl = keeper.chk_claim({"id": "c", "quote": "the sky is blue", "check": {"http": "https://example.invalid", "jsonPath": "n", "equals": 1}},
                      [("SKILL.md", ["the sky is blue"])], tmp)
mc = keeper.chk_mcp({"id": "m", "url": "https://example.invalid/mcp", "expectTools": {"t": []}}, None)
if cl[0]["status"] != "WARN" or "503" not in cl[0]["detail"] or mc[0]["status"] != "WARN" or "503" not in mc[0]["detail"]:
    fails.append(f"L-11: a 503 must be WARN with the status (claim: {cl[0]['status']} {cl[0]['detail'][:60]!r}; mcp: {mc[0]['detail'][:60]!r})")
keeper.http = real_http

shutil.rmtree(tmp, ignore_errors=True)
if fails:
    print("FAIL\n" + "\n".join(fails))
    sys.exit(1)
print("ok: 10 keeper lessons hold")
