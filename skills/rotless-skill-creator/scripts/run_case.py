#!/usr/bin/env python3
"""Run one test case in a fresh headless agent session, with or without the skill.

Part of rotless-skill-creator (new file). Use it when your agent can't spawn subagents, or when
you want runs on a different agent than the one you're talking to.

  python run_case.py --agent codex --case <skill>/evals/flags-negative-quantity \
      --skill-path <skill> --out <workspace>/iteration-1/flags-negative-quantity/with_skill
  python run_case.py --agent codex --case ... --out .../without_skill        # baseline: no --skill-path

Writes <out>/outputs/ (the reply as response.md, plus every file the run created or changed)
and <out>/timing.json. --allow-writes lets the run create files, inside its workspace only;
agents without a workspace-scoped write mode refuse it.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402


def read_prompt(case_dir):
    text = (case_dir / "prompt.md").read_text(encoding="utf-8")
    m = re.match(r"^---\r?\n.*?\r?\n---\r?\n?", text, re.S)  # settings block: only the CLI uses it
    return text[m.end():].strip() if m else text.strip()


def snapshot(ws):
    # skip only the installed skill copies; anything else under .agents/, .claude/… (e.g. a notes
    # registry next to the skills folder) is evidence the graders need. Lesson L-2026-11-02-4.
    skip = {Path(d).parts for d in harness.SKILL_DIRS}
    # size too, and nanoseconds: a rewrite within the clock's resolution keeps the same mtime (L-2026-11-02-17)
    return {p.relative_to(ws): (p.stat().st_mtime_ns, p.stat().st_size) for p in ws.rglob("*")
            if p.is_file() and p.relative_to(ws).parts[:2] not in skip}


def changes(before, after):
    """(changed or new files, deleted files), as sorted relative paths."""
    return sorted(p for p in after if before.get(p) != after[p]), sorted(set(before) - set(after))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", required=True, choices=sorted(harness.AGENTS))
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--case", help="evals/<case-name> folder (prompt.md, optional files/)")
    g.add_argument("--prompt", help="prompt text, for a quick run without a case folder")
    ap.add_argument("--skill-path", help="install this skill; omit for the baseline run")
    ap.add_argument("--out", required=True, help="run directory; outputs/ and timing.json go here")
    ap.add_argument("--allow-writes", action="store_true")
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()

    case = Path(a.case) if a.case else None
    prompt = read_prompt(case) if case else a.prompt
    files = case / "files" if case and (case / "files").is_dir() else None
    ws = harness.make_workspace(a.skill_path, files_dir=files)
    before = snapshot(ws)
    try:
        r = harness.run(a.agent, prompt, ws, a.timeout, allow_writes=a.allow_writes)
        out = Path(a.out)
        outputs = out / "outputs"
        outputs.mkdir(parents=True, exist_ok=True)
        (outputs / "response.md").write_text(r["stdout"], encoding="utf-8")
        changed, deleted = changes(before, snapshot(ws))
        for rel in changed:
            dst = outputs / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ws / rel, dst)
        if deleted:  # graders need to see what the agent removed, too
            (out / "deleted-files.txt").write_text("\n".join(p.as_posix() for p in deleted) + "\n", encoding="utf-8")
        # tokens aren't reported the same way by every CLI, so they stay null here
        (out / "timing.json").write_text(json.dumps({"total_tokens": None, "duration_ms": int(r["seconds"] * 1000),
                                                     "total_duration_seconds": r["seconds"], "agent": a.agent,
                                                     "exit": r["exit"]}, indent=2), encoding="utf-8")
    finally:
        shutil.rmtree(ws, ignore_errors=True)
    print(json.dumps({"out": str(out), "exit": r["exit"], "seconds": r["seconds"]}))
    return 0 if r["exit"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
