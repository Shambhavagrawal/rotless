#!/usr/bin/env python3
"""Trigger test: does a skill's description make a fresh agent load it for the right queries?

Part of rotless-skill-creator. Replaces Anthropic's Claude-only run_eval.py: runs on any agent
CLI in harness.AGENTS and detects triggering with a canary token, not with event parsing.

  python run_eval.py --eval-set trigger-eval.json --skill-path <skill> --agent codex
  python run_eval.py ... --description "candidate description" --holdout 0.4 --out result.json

The eval set is a JSON list of {"query": "...", "should_trigger": true|false}. A query passes
when its trigger rate over --runs is >= 0.5 for should_trigger, < 0.5 otherwise.
"""
import argparse
import json
import random
import shutil
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402
from utils import parse_skill_md  # noqa: E402


def split(items, holdout, seed):
    """Stratified train/test split so both sides keep positives and negatives."""
    if holdout <= 0:
        return items, []
    rnd = random.Random(seed)
    train, test = [], []
    for flag in (True, False):
        group = [i for i in items if bool(i["should_trigger"]) == flag]
        rnd.shuffle(group)
        k = round(len(group) * holdout)
        if len(group) >= 2:  # a small set still gets a test and a train side (lesson L-2026-11-02-9)
            k = min(max(k, 1), len(group) - 1)
        test += group[:k]
        train += group[k:]
    return train, test


def one_run(agent, skill, as_name, description, query, timeout):
    canary = harness.new_canary()
    ws = harness.make_workspace(skill, as_name=as_name, description=description, canary=canary)
    try:
        r = harness.run(agent, query, ws, timeout)
    finally:
        shutil.rmtree(ws, ignore_errors=True)
    out = {"triggered": harness.saw_canary(canary, r["stdout"]), "exit": r["exit"], "seconds": r["seconds"]}
    if r["exit"] != 0:  # keep why it failed (lesson L-2026-11-02-3)
        out["stderr"] = (r["stderr"] or r["stdout"])[-300:]
    return out


def summarise(q, runs, split_name):
    """One query's result. Rates use runs that completed; errored runs (usage limits, crashes) are not
    'not triggered'. With no completed run the query is no data (pass None). Lesson L-2026-11-02-5."""
    valid = [r for r in runs if r["exit"] == 0]
    rate = sum(r["triggered"] for r in valid) / len(valid) if valid else None
    return {"query": q["query"], "should_trigger": bool(q["should_trigger"]),
            "trigger_rate": None if rate is None else round(rate, 2),
            "pass": None if rate is None else (rate >= 0.5) == bool(q["should_trigger"]),
            "valid_runs": len(valid), "errors": len(runs) - len(valid),
            "error_samples": [r.get("stderr", "") for r in runs if r["exit"] != 0][:2], "split": split_name}


def score(rows):
    no_data = sum(1 for r in rows if r["pass"] is None)
    rows = [r for r in rows if r["pass"] is not None]
    tp = sum(1 for r in rows if r["should_trigger"] and r["pass"])
    fn = sum(1 for r in rows if r["should_trigger"] and not r["pass"])
    fp = sum(1 for r in rows if not r["should_trigger"] and not r["pass"])
    tn = sum(1 for r in rows if not r["should_trigger"] and r["pass"])
    n = len(rows) or 1
    return {"accuracy": round((tp + tn) / n, 3), "recall": round(tp / (tp + fn), 3) if tp + fn else None,
            "precision": round(tp / (tp + fp), 3) if tp + fp else None, "passed": tp + tn, "total": len(rows),
            "no_data": no_data}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eval-set", required=True)
    ap.add_argument("--skill-path", required=True)
    ap.add_argument("--agent", required=True, choices=sorted(harness.AGENTS))
    ap.add_argument("--description", help="test this description instead of the one in SKILL.md")
    ap.add_argument("--runs", type=int, default=3, help="runs per query (default 3)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--holdout", type=float, default=0.0, help="fraction held out as a test split, e.g. 0.4")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", help="write the full result JSON here")
    a = ap.parse_args()

    skill = Path(a.skill_path).resolve()
    name, desc, _ = parse_skill_md(skill)
    description = a.description if a.description is not None else desc
    items = json.loads(Path(a.eval_set).read_text(encoding="utf-8"))
    train, test = split(items, a.holdout, a.seed)
    as_name = f"{name}-eval-{uuid.uuid4().hex[:6]}"  # unique, so an installed copy can't be mistaken for it

    for p in harness.installed_copies(name):
        print(f"[warn] {name} is also installed at {p}; the agent may load that copy instead, "
              "which shows up as a missed trigger", file=sys.stderr)

    jobs = [(i, q) for i, q in enumerate(train + test) for _ in range(a.runs)]
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        results = list(ex.map(lambda j: one_run(a.agent, skill, as_name, description, j[1]["query"], a.timeout), jobs))

    rows = []
    for idx, q in enumerate(train + test):
        runs = [r for (i, _), r in zip(jobs, results) if i == idx]
        rows.append(summarise(q, runs, "train" if idx < len(train) else "test"))

    out = {"agent": a.agent, "skill": name, "description": description, "runs_per_query": a.runs,
           "train": score([r for r in rows if r["split"] == "train"]),
           "test": score([r for r in rows if r["split"] == "test"]) if test else None,
           "results": rows}
    positives = [r for r in rows if r["should_trigger"]]
    if positives and all(r["trigger_rate"] == 0 for r in positives):
        out["warning"] = ("no should-trigger query triggered at all: check the agent loads project skills "
                          f"(python harness.py probe --agent {a.agent}) before blaming the description")
    if any(r["errors"] for r in rows):
        out["warning_errors"] = (f"{sum(r['errors'] for r in rows)} run(s) exited non-zero and are left out of the rates; "
                                 f"{sum(r['pass'] is None for r in rows)} quer(ies) have no completed run (see error_samples)")

    text = json.dumps(out, indent=2, ensure_ascii=False)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
