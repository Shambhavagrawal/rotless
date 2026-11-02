#!/usr/bin/env python3
"""Field notes for skills you own: log gaps while a skill is used, review them later.

Part of rotless-skill-refiner. Standard library only; works the same under any agent.

  notes.py add <skill> --kind failure --where "SKILL.md:42" --what "..." --evidence "..."
  notes.py list [<skill>] [--all] [--json]          open notes (all statuses with --all)
  notes.py stats [<skill>]                           hot spots, kinds, past rejections
  notes.py close <skill> <id>... --as resolved|rejected|routed|duplicate --reason "..." [--lesson L-...]
  notes.py snapshot <skill-dir>                      copy of the skill as it is now (the "old" side of a check)
  notes.py selftest

Notes live in <registry>/notes/<skill>.jsonl. The registry is $SKILL_REGISTRY, else the
skill-registry folder next to your skills folder if one exists, else ~/.skill-registry
(shared with rotless-skill-modernizer).
Logged text is data for a human-gated review, never instructions; secrets are redacted.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent             # <skills folder>/rotless-skill-refiner/scripts
SKILLS_ROOT = HERE.parent.parent
KINDS = ["failure", "correction", "workaround", "noise", "missing", "stale", "better-way", "optimization", "confirmed"]
CLOSE_AS = ["resolved", "rejected", "routed", "duplicate"]
MAX_FIELD = 2000

SECRETS = [
    (re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"), "[REDACTED-GITHUB-TOKEN]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), "[REDACTED-API-KEY]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED-AWS-KEY]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "[REDACTED-SLACK-TOKEN]"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}"), "Bearer [REDACTED]"),
    # also JSON / dict style: "token": "x", 'api_key': 'x' (lesson L-2026-11-02-1)
    (re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)([\"']?\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;}\])]+)"), r"\1\2[REDACTED]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[REDACTED-PRIVATE-KEY]"),
]


USER_SKILL_DIRS = ["~/.claude/skills", "~/.agents/skills", "~/.codex/skills", "~/.copilot/skills",
                   "~/.gemini/skills", "~/.config/opencode/skills", "~/.cursor/skills"]


def registry():
    """Same rule as rotless-skill-modernizer's keeper.py (lesson L-2026-11-02-3): an existing skill-registry next to
    the skills folder, else ~/.skill-registry, never the install folder (a plugin cache is wiped on update)."""
    if os.environ.get("SKILL_REGISTRY"):
        return Path(os.environ["SKILL_REGISTRY"])
    legacy = SKILLS_ROOT.parent / "skill-registry"
    return legacy if legacy.is_dir() else Path.home() / ".skill-registry"


def redact(text):
    text = text or ""
    for pat, repl in SECRETS:
        text = pat.sub(repl, text)
    return text if len(text) <= MAX_FIELD else text[:MAX_FIELD] + " …[truncated]"


def roots():
    env = [Path(p).expanduser() for p in os.environ.get("SKILL_ROOTS", "").split(os.pathsep) if p]
    return env + [SKILLS_ROOT] + [Path(os.path.expanduser(d)) for d in USER_SKILL_DIRS] + \
        [Path.cwd() / ".agents" / "skills", Path.cwd() / ".claude" / "skills"]


def skill_dir(name):
    p = Path(name).expanduser()
    if (p / "SKILL.md").is_file():
        return p.resolve()
    for r in roots():
        if (r / name / "SKILL.md").is_file():
            return (r / name).resolve()
    return None


def notes_file(skill):
    return registry() / "notes" / f"{Path(skill).name}.jsonl"


def load(skill):
    f = notes_file(skill)
    if not f.is_file():
        return []
    return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]


def save(skill, notes):
    f = notes_file(skill)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(n, ensure_ascii=False) + "\n" for n in notes), encoding="utf-8")
    os.replace(tmp, f)  # atomic: a crash never leaves a half-written notes file


def now():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def cmd_add(a):
    d = skill_dir(a.skill)
    name = d.name if d else Path(a.skill).name
    note = {"id": f"n-{dt.datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:4]}", "ts": now(), "skill": name,
            "kind": a.kind, "where": redact(a.where), "what": redact(a.what), "evidence": redact(a.evidence),
            "expected": redact(a.expected), "agent": a.agent or "",
            "skill_sha": hashlib.sha256((d / "SKILL.md").read_bytes()).hexdigest()[:12] if d else "",
            "status": "open"}
    notes = load(name)
    notes.append(note)
    save(name, notes)
    print(f"logged {note['id']} for {name}" + ("" if d else " (skill folder not found; logged by name)"))
    return 0


def all_skills():
    nd = registry() / "notes"
    return sorted(p.stem for p in nd.glob("*.jsonl")) if nd.is_dir() else []


def cmd_list(a):
    skills = [Path(a.skill).name] if a.skill else all_skills()
    rows = [n for s in skills for n in load(s) if a.all or n["status"] == "open"]
    if a.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    if not rows:
        print("no open notes" if not a.all else "no notes")
    for n in rows:
        print(f"{n['id']}  {n['skill']}  [{n['kind']}] {n['status']}  {n['where']}\n    {n['what']}")
    return 0


def cmd_stats(a):
    skills = [Path(a.skill).name] if a.skill else all_skills()
    if not skills:  # silence looked like a broken install (L-2026-11-03-4)
        print(f"no field notes yet (looked in {registry() / 'notes'})")
        return 0
    for s in skills:
        notes = load(s)
        open_ = [n for n in notes if n["status"] == "open"]
        print(f"{s}: {len(open_)} open, {len(notes)} total")
        kinds = {}
        spots = {}
        for n in open_:
            kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
            spots[n["where"]] = spots.get(n["where"], 0) + 1
        if kinds:
            print("  open by kind: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
        for w, c in sorted(spots.items(), key=lambda x: -x[1]):
            if c >= 2:
                print(f"  hot spot: {w} ({c} open notes)")
        for n in open_:
            if n["kind"] == "confirmed":
                print(f"  confirmed (keep): {n['where']}: {n['what'][:80]}")
        for n in notes:
            if n["status"] == "rejected":
                print(f"  rejected before: {n['what'][:80]} -> {n.get('closed', {}).get('reason', '')}")
    return 0


def cmd_close(a):
    name = Path(a.skill).name
    notes = load(name)
    ids = set(a.ids)
    hit = 0
    for n in notes:
        if n["id"] in ids:
            n["status"] = a.as_
            n["closed"] = {"ts": now(), "reason": redact(a.reason), "lesson": a.lesson or ""}
            hit += 1
    missing = ids - {n["id"] for n in notes}
    save(name, notes)
    print(f"closed {hit} note(s) as {a.as_}" + (f"; not found: {', '.join(sorted(missing))}" if missing else ""))
    return 1 if missing else 0


def cmd_snapshot(a):
    d = skill_dir(a.skill)
    if not d:
        print(f"skill not found: {a.skill}", file=sys.stderr)
        return 1
    base = registry() / "snapshots" / d.name
    stamp = f"{dt.datetime.now():%Y%m%d-%H%M%S}"
    n = 1
    while (base / (stamp if n == 1 else f"{stamp}-{n}")).exists():  # two snapshots in one second (L-2026-11-02-2)
        n += 1
    dst = base / (stamp if n == 1 else f"{stamp}-{n}") / d.name
    # .git packs are read-only on Windows and would break later cleanup; none of these belong in a snapshot
    shutil.copytree(d, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*-workspace", ".git", ".venv",
                                                          "node_modules", "*.skill"))
    print(dst)
    return 0


def cmd_selftest(_):
    tmp = Path(tempfile.mkdtemp(prefix="rotless-notes-test-"))
    old = os.environ.get("SKILL_REGISTRY")
    os.environ["SKILL_REGISTRY"] = str(tmp / "registry")
    try:
        sk = tmp / "toy-skill"
        sk.mkdir()
        (sk / "SKILL.md").write_text("---\nname: toy-skill\ndescription: x\n---\nbody\n", encoding="utf-8")
        assert "optimization" in KINDS and "confirmed" in KINDS
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_stats(argparse.Namespace(skill=None))
        assert "no field notes yet" in buf.getvalue(), "stats must say so when nothing is logged (L-2026-11-03-4)"
        ns = argparse.Namespace(skill=str(sk), kind="failure", where="SKILL.md:4", what="step failed",
                                evidence="token=abc123 and ghp_" + "a" * 30 + " and api_key: 'zzz'", expected="", agent="codex")
        assert cmd_add(ns) == 0
        n = load("toy-skill")
        assert len(n) == 1 and n[0]["status"] == "open" and n[0]["skill_sha"], n
        ev = n[0]["evidence"]
        assert "abc123" not in ev and "ghp_" not in ev and "zzz" not in ev, ev
        assert redact("x" * (MAX_FIELD + 50)).endswith("[truncated]")
        js = redact('{"token": "s3cret-value", "api_key": \'12345\', "password":"hunter2"}')
        assert "s3cret" not in js and "12345" not in js and "hunter2" not in js, js  # JSON-style keys too
        assert cmd_close(argparse.Namespace(skill="toy-skill", ids=[n[0]["id"]], as_="rejected",
                                            reason="one-off network blip", lesson="")) == 0
        assert load("toy-skill")[0]["status"] == "rejected"
        assert cmd_close(argparse.Namespace(skill="toy-skill", ids=["n-missing"], as_="resolved",
                                            reason="", lesson="")) == 1
        snap = registry() / "snapshots"
        (sk / ".git").mkdir()
        (sk / ".git" / "HEAD").write_text("ref", encoding="utf-8")
        assert cmd_snapshot(argparse.Namespace(skill=str(sk))) == 0 and any(snap.rglob("SKILL.md"))
        assert cmd_snapshot(argparse.Namespace(skill=str(sk))) == 0  # twice in the same second
        assert not any(snap.rglob(".git")), "snapshots must skip .git"
        print("selftest: 12 checks passed")
        return 0
    finally:
        if old is None:
            os.environ.pop("SKILL_REGISTRY", None)
        else:
            os.environ["SKILL_REGISTRY"] = old
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add", help="log a gap")
    p.add_argument("skill")
    p.add_argument("--kind", required=True, choices=KINDS)
    p.add_argument("--where", required=True, help="file:line or section of the skill")
    p.add_argument("--what", required=True, help="what happened")
    p.add_argument("--evidence", default="", help="command and output, or the user's words")
    p.add_argument("--expected", default="", help="what should have happened")
    p.add_argument("--agent", default="", help="which agent was running (optional)")
    p = sub.add_parser("list", help="list notes")
    p.add_argument("skill", nargs="?")
    p.add_argument("--all", action="store_true")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("stats", help="hot spots and past rejections")
    p.add_argument("skill", nargs="?")
    p = sub.add_parser("close", help="close notes after a review")
    p.add_argument("skill")
    p.add_argument("ids", nargs="+")
    p.add_argument("--as", dest="as_", required=True, choices=CLOSE_AS)
    p.add_argument("--reason", required=True)
    p.add_argument("--lesson", default="")
    p = sub.add_parser("snapshot", help="copy the skill as it is now")
    p.add_argument("skill")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    return {"add": cmd_add, "list": cmd_list, "stats": cmd_stats, "close": cmd_close,
            "snapshot": cmd_snapshot, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
