#!/usr/bin/env python3
"""Run one fresh, headless agent session per call, on any supported agent CLI.

Part of rotless-skill-creator (new file, not from Anthropic's skill-creator).

Why: trigger tests and test-case runs need a *fresh* agent that sees the skill the way a
real user's agent would. Each agent has its own headless mode and its own project skills
folder, so this module knows the command for each and installs the skill under test into
every known project skills folder of a throwaway workspace.

Trigger detection works the same on every agent: the installed copy carries a canary
instruction, so if the agent loads the skill, the canary token shows up in its reply, and
nothing has to parse an agent's own event format.

  python harness.py agents                      # which agent CLIs are installed
  python harness.py probe --agent codex         # does this agent load project skills headlessly?
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

# Headless command per agent. The prompt goes on stdin where the CLI supports it (no shell
# quoting issues on Windows), otherwise as the last argument.
#   write: flags that let a test-case run create files *only inside the workspace*. None means the
#   CLI has no scoped option (only allow-everything flags), so file-writing runs on that agent go
#   through subagents or in-session runs instead. Never map this to an allow-all flag.
#   verified: headless skill loading confirmed with `harness.py probe` (date, CLI version).
AGENTS = {
    "claude":   {"bin": "claude",       "args": ["-p", "--output-format", "text"], "stdin": True,
                 "write": ["--permission-mode", "acceptEdits"], "verified": "2026-11-02 claude 2.1.316",
                 # trigger tests: skip the user's own skills, so an installed copy can't answer for the test copy
                 "isolate": ["--setting-sources", "project"]},
    "codex":    {"bin": "codex",        "args": ["exec", "--skip-git-repo-check", "--ephemeral", "-"], "stdin": True,
                 "write": ["-s", "workspace-write"], "verified": "2026-11-02 codex-cli 0.166.0"},
    "copilot":  {"bin": "copilot",      "args": ["-s", "-p"], "stdin": False, "write": None, "verified": None},
    "gemini":   {"bin": "gemini",       "args": ["-p"], "stdin": False, "write": None, "verified": None},
    "opencode": {"bin": "opencode",     "args": ["run"], "stdin": False, "write": None, "verified": None},
    "cursor":   {"bin": "cursor-agent", "args": ["-p"], "stdin": False, "write": None, "verified": None},
}

# Project-level skills folders the agents read. Installing into all of them means we don't
# need to know which one a given agent version uses.
SKILL_DIRS = [".claude/skills", ".agents/skills", ".github/skills", ".gemini/skills",
              ".opencode/skills", ".cursor/skills"]

# User-level folders, used to warn when an installed copy of the same skill could answer
# instead of the copy under test.
USER_SKILL_DIRS = ["~/.claude/skills", "~/.agents/skills", "~/.codex/skills", "~/.copilot/skills",
                   "~/.gemini/skills", "~/.config/opencode/skills", "~/.cursor/skills"]


def binary(agent):
    spec = AGENTS.get(agent)
    return shutil.which(spec["bin"]) if spec else None


def installed():
    return [a for a in AGENTS if binary(a)]


def set_frontmatter(text, key, value):
    """Replace a top-level `key:` line in SKILL.md frontmatter (single-line value)."""
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    if not m:
        raise ValueError("SKILL.md has no frontmatter")
    fm = m.group(1)
    new_line = f"{key}: {json.dumps(value, ensure_ascii=False)}"
    # includes folded continuation lines, and blank lines between paragraphs of a block value (L-2026-11-02-20)
    pat = re.compile(rf"^{re.escape(key)}:.*(?:\r?\n(?:[ \t]*\r?\n)*[ \t]+\S.*)*", re.M)
    fm2 = pat.sub(lambda _: new_line, fm, count=1) if pat.search(fm) else fm + "\n" + new_line
    return text[:m.start(1)] + fm2 + text[m.end(1):]


def make_workspace(skill_dir=None, as_name=None, description=None, canary=None, files_dir=None):
    """Throwaway workspace. Optionally installs a copy of skill_dir (renamed to as_name, with an
    overridden description and a canary line) into every project skills folder, and copies
    files_dir's contents in as the task's input files."""
    ws = Path(tempfile.mkdtemp(prefix="rotless-ws-"))
    if files_dir:
        shutil.copytree(files_dir, ws, dirs_exist_ok=True)
        # input files that are themselves skills ship as SKILL.md.fixture, so tools that scan a repo for
        # skills don't list them; give them their real name back here (lesson L-2026-11-02-13)
        for f in list(ws.rglob("*.fixture")):
            f.rename(f.with_name(f.name[:-len(".fixture")]))
    if skill_dir:
        skill_dir = Path(skill_dir)
        name = as_name or skill_dir.name
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        text = set_frontmatter(text, "name", name)
        if description is not None:
            text = set_frontmatter(text, "description", description)
        if canary:
            # A trigger test. Agents choose a skill from its name and description, so the body only has to show
            # the token; doing the whole task would measure nothing and use up quota (L-2026-11-02-14).
            m = re.match(r"^---\r?\n.*?\r?\n---\r?\n?", text, re.S)
            text = text[:m.end()] + (f"\n<!-- test run -->\nThis is an automated trigger test. Reply with this exact token "
                                     f"on a line of its own and stop there, without calling tools or doing the task: {canary}\n")
        for d in SKILL_DIRS:
            dst = ws / d / name
            shutil.copytree(skill_dir, dst, ignore=shutil.ignore_patterns("evals", "__pycache__", "*-workspace"))
            (dst / "SKILL.md").write_text(text, encoding="utf-8")
    return ws


def run(agent, prompt, cwd, timeout=600, allow_writes=False, isolate=False):
    """One fresh headless session. Returns {exit, stdout, stderr, seconds}. isolate: leave out the user's own
    skills where the agent can (trigger tests; lesson L-2026-11-02-19)."""
    spec = AGENTS[agent]
    exe = binary(agent)
    if not exe:
        raise RuntimeError(f"{agent} CLI ({spec['bin']}) not found on PATH")
    if allow_writes and spec["write"] is None:
        raise RuntimeError(f"{agent} has no workspace-scoped write mode; run this case with a subagent or in-session")
    cmd = [exe] + spec["args"] + (spec["write"] if allow_writes else []) + ((spec.get("isolate") or []) if isolate else [])
    if not spec["stdin"]:
        cmd.append(prompt)
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}  # allow a nested claude -p
    t0 = time.time()
    try:
        r = subprocess.run(cmd, input=prompt if spec["stdin"] else None, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=str(cwd), env=env, timeout=timeout)
        out = {"exit": r.returncode, "stdout": r.stdout, "stderr": r.stderr[-4000:]}
    except subprocess.TimeoutExpired as e:
        out = {"exit": 124, "stdout": (e.stdout or "") if isinstance(e.stdout, str) else "", "stderr": "timed out"}
    out["seconds"] = round(time.time() - t0, 1)
    return out


def installed_copies(name):
    """User-level installs of a skill with this name (they can trigger instead of the test copy)."""
    hits = []
    for d in USER_SKILL_DIRS:
        p = Path(os.path.expanduser(d)) / name / "SKILL.md"
        if p.is_file():
            hits.append(str(p.parent))
    return hits


def new_canary():
    return f"ROTLESS-CANARY-{uuid.uuid4().hex[:8]}"


def saw_canary(canary, text):
    """True if the reply carries this run's canary. Agents sometimes copy the token shortened, so the
    first 6 hex characters are enough (unique per run). Lesson L-2026-11-02-2."""
    return f"ROTLESS-CANARY-{canary.rsplit('-', 1)[1][:6]}" in text


def probe(agent, timeout=300):
    """Install a throwaway skill about a made-up topic and ask about it: True if the agent loaded it."""
    canary = new_canary()
    src = Path(tempfile.mkdtemp(prefix="rotless-probe-")) / "zorblax-protocol"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text(
        "---\nname: zorblax-protocol\ndescription: Explains the Zorblax handshake protocol. Use whenever the user "
        "asks anything about Zorblax or the Zorblax handshake.\n---\n\n# Zorblax protocol\n\nThe Zorblax handshake "
        "has three steps: ping, glimmer, settle.\n", encoding="utf-8")
    ws = make_workspace(src, canary=canary)
    try:
        r = run(agent, "What are the steps of the Zorblax handshake? Use the zorblax-protocol skill.", ws, timeout)
    finally:
        shutil.rmtree(ws, ignore_errors=True)
        shutil.rmtree(src.parent, ignore_errors=True)
    return saw_canary(canary, r["stdout"]), r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("agents", help="list supported agents and which are installed")
    p = sub.add_parser("probe", help="check that an agent loads project skills in headless mode")
    p.add_argument("--agent", required=True, choices=sorted(AGENTS))
    p.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()
    if a.cmd == "agents":
        for name, spec in AGENTS.items():
            print(f"{name:9} {binary(name) or '-':60} verified: {spec['verified'] or 'not yet (run probe)'}")
        return 0
    ok, r = probe(a.agent, a.timeout)
    print(json.dumps({"agent": a.agent, "loads_project_skills": ok, "exit": r["exit"], "seconds": r["seconds"],
                      "reply_tail": r["stdout"][-300:], "stderr_tail": r["stderr"][-300:]}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
