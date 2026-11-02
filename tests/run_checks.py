#!/usr/bin/env python3
"""Run every offline check: what CI runs, what a release requires, what contributors run first.

  python tests/run_checks.py

No network and no agent CLI. Live checks (keeper.py check, the creator's test runs) stay local.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").is_file())
OUT = Path(tempfile.mkdtemp(prefix="rotless-release-check-")) / "dist"
CHECKS = [
    ["tests/check_repo.py"],
    ["skills/rotless-skill-refiner/scripts/notes.py", "selftest"],
    ["skills/rotless-skill-creator/scripts/test_harness.py"],
    ["skills/rotless-skill-modernizer/scripts/test_cli_shims.py"],
    ["skills/rotless-skill-modernizer/scripts/test_keeper.py"],
    ["skills/rotless-github-research/scripts/test_offline.py"],
    ["skills/rotless-skill-modernizer/scripts/keeper.py", "lint", *SKILLS],
    *[["skills/rotless-skill-creator/scripts/quick_validate.py", s, "--strict"] for s in SKILLS],
    ["scripts/build_release.py", "--out", str(OUT)],
]

failed = 0
for cmd in CHECKS:
    r = subprocess.run([sys.executable, *cmd], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    last = (r.stdout.strip().splitlines() or r.stderr.strip().splitlines() or [""])[-1]
    label = " ".join(c if not c.startswith(str(OUT)) else "<tmp>" for c in cmd)
    print(f"{'ok  ' if r.returncode == 0 else 'FAIL'}  {label}: {last[:120]}")
    if r.returncode:
        failed += 1
        print("\n".join("      " + line for line in (r.stdout + r.stderr).strip().splitlines()[-15:]))
print(f"\n{len(CHECKS) - failed} of {len(CHECKS)} checks passed")
sys.exit(1 if failed else 0)
