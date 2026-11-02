#!/usr/bin/env python3
"""Lesson checks for rotless-skill-creator's runners (lessons L-2026-11-02-2..4).

  python scripts/test_harness.py [skill-dir]     # default: this skill; pass a snapshot to see it fail

No agent CLI needed: agent runs are faked.
"""
import importlib.util
import shutil
import sys
import tempfile
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


harness = load("harness")
run_eval = load("run_eval")
run_case = load("run_case")
fails = []

# L-2: an agent that copies the canary shortened still counts as triggered; another run's canary doesn't
c = harness.new_canary()
short = c[:len("ROTLESS-CANARY-") + 6]
if not (hasattr(harness, "saw_canary") and harness.saw_canary(c, f"answer\n{short}\n")
        and not harness.saw_canary(c, "answer\n" + harness.new_canary())):
    fails.append("L-2: a shortened canary must count as triggered, a different canary must not")

# L-3: a run that exits non-zero keeps its stderr, so errors can be diagnosed
real_run = harness.run
harness.run = lambda agent, prompt, cwd, timeout=600, allow_writes=False: {
    "exit": 1, "stdout": "", "stderr": "rate limited: too many sessions", "seconds": 0.1}
src = Path(tempfile.mkdtemp(prefix="rotless-test-")) / "toy"
src.mkdir()
(src / "SKILL.md").write_text("---\nname: toy\ndescription: toy skill\n---\nbody\n", encoding="utf-8")
try:
    r = run_eval.one_run("codex", src, "toy-eval-x", None, "q", 5)
    if "rate limited" not in r.get("stderr", ""):
        fails.append("L-3: one_run must keep the stderr of a failed run")
finally:
    harness.run = real_run

# L-4: files the agent writes beside the skills folders (e.g. .agents/skill-registry) reach outputs;
# the installed skill copies don't
ws = Path(tempfile.mkdtemp(prefix="rotless-test-ws-"))
(ws / ".agents" / "skill-registry" / "notes").mkdir(parents=True)
(ws / ".agents" / "skill-registry" / "notes" / "toy.jsonl").write_text("{}\n", encoding="utf-8")
(ws / ".agents" / "skills" / "toy").mkdir(parents=True)
(ws / ".agents" / "skills" / "toy" / "SKILL.md").write_text("x", encoding="utf-8")
seen = {p.as_posix() for p in run_case.snapshot(ws)}
if ".agents/skill-registry/notes/toy.jsonl" not in seen or ".agents/skills/toy/SKILL.md" in seen:
    fails.append(f"L-4: outputs must include .agents/skill-registry files and exclude installed skills (saw {sorted(seen)})")

# L-5: errored runs don't count as "not triggered"; a query with no valid run is no data, not a pass
if not hasattr(run_eval, "summarise"):
    fails.append("L-5: run_eval.summarise(query, runs, split) missing")
else:
    q = {"query": "q", "should_trigger": False}
    err = {"triggered": False, "exit": 1, "stderr": "usage limit"}
    ok = {"triggered": True, "exit": 0}
    none = run_eval.summarise(q, [err, err], "train")
    mixed = run_eval.summarise({"query": "q", "should_trigger": True}, [ok, err], "train")
    if none["pass"] is not None or mixed["trigger_rate"] != 1.0 or mixed["pass"] is not True:
        fails.append(f"L-5: rates must use valid runs only and all-errored queries must be no data (got {none}, {mixed})")
    elif run_eval.score([none, mixed])["total"] != 1:
        fails.append("L-5: score must leave no-data queries out")

# L-6..L-10 come from an external code review (2026-11-02)
tmp6 = Path(tempfile.mkdtemp(prefix="rotless-test-l6-"))


def toy(name, frontmatter):
    d = tmp6 / name
    d.mkdir()
    (d / "SKILL.md").write_text(f"---\n{frontmatter}\n---\nbody\n", encoding="utf-8")
    return d


# L-6: the validator parses a description on the next line (even with a colon) and rejects non-string metadata
try:
    qv = load("quick_validate")
    ok, msg, _ = qv.validate_skill(toy("toy-a", "name: toy-a\ndescription:\n  Use this skill when: the user asks for X\nmetadata:\n  author: me"))
    if not ok:
        fails.append(f"L-6: a valid multi-line description was rejected: {msg}")
    for bad in ("metadata:\n  version: 1.0", "metadata:\n  tags: [a, b]", "metadata:\n  beta: true"):
        name = f"toy-{len(list(tmp6.iterdir()))}"
        ok, msg, _ = qv.validate_skill(toy(name, f"name: {name}\ndescription: x\n{bad}"))
        if ok:
            fails.append(f"L-6: non-string metadata passed: {bad.splitlines()[1].strip()}")
except Exception as e:
    fails.append(f"L-6: validator crashed: {type(e).__name__}: {e}")

# L-7: a double-quoted YAML description is unescaped, so text written by set_frontmatter reads back the same
try:
    utils = load("utils")
    d = toy("toy-q", "name: toy-q")
    (d / "SKILL.md").write_text(harness.set_frontmatter((d / "SKILL.md").read_text(encoding="utf-8"),
                                                        "description", 'Says "hi" to people'), encoding="utf-8")
    if utils.parse_skill_md(d)[1] != 'Says "hi" to people':
        fails.append(f"L-7: description read back as {utils.parse_skill_md(d)[1]!r}")
except Exception as e:
    fails.append(f"L-7: {type(e).__name__}: {e}")

# L-8: the canary instruction sits at the top of the body, so an agent stopped early still sees it
d = toy("toy-c", "name: toy-c\ndescription: x")
ws = harness.make_workspace(d, canary="ROTLESS-CANARY-abcdef12")
text = (ws / ".agents" / "skills" / "toy-c" / "SKILL.md").read_text(encoding="utf-8")
if text.index("ROTLESS-CANARY-abcdef12") > text.index("\nbody"):
    fails.append("L-8: the canary instruction must come before the skill body")
shutil.rmtree(ws, ignore_errors=True)

# L-9: --holdout on a small eval set still leaves both splits non-empty
items = [{"query": f"p{i}", "should_trigger": True} for i in range(2)] + [{"query": f"n{i}", "should_trigger": False} for i in range(2)]
tr, te = run_eval.split(items, 0.2, 7)
if not tr or not te:
    fails.append(f"L-9: holdout 0.2 on 4 queries gave train={len(tr)} test={len(te)}")

# L-10: filling the eval review page escapes what goes into the HTML and the <script> block
try:
    mer = load("make_eval_review")
    page = mer.render("<b>__SKILL_NAME_PLACEHOLDER__</b><p>__SKILL_DESCRIPTION_PLACEHOLDER__</p><script>const D = __EVAL_DATA_PLACEHOLDER__;</script>",
                      [{"query": "</script><i>x", "should_trigger": True}], "a<b", 'say "hi" <i>')
    if "</script><i>" in page or "<i>" in page.split("<script>")[0] or "a<b" in page:
        fails.append("L-10: raw HTML got into the review page")
except Exception as e:
    fails.append(f"L-10: {type(e).__name__}: {e}")
shutil.rmtree(tmp6, ignore_errors=True)

shutil.rmtree(src.parent, ignore_errors=True)
shutil.rmtree(ws, ignore_errors=True)
if fails:
    print("FAIL\n" + "\n".join(fails))
    sys.exit(1)
print("ok: 9 creator lessons hold")
