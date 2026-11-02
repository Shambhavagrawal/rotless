#!/usr/bin/env python3
"""Lesson check L-2026-11-02-1: keeper.run() must launch CLIs installed as shims.

On Windows, npm installs CLIs (codex, gemini, npx) as .CMD files, which subprocess can't start
by bare name. This creates a fake CLI on PATH and asserts keeper.run() finds it.

  python scripts/test_cli_shims.py [skill-dir]     # default: this skill; pass a snapshot to see it fail
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

skill = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("keeper_under_test", skill / "scripts" / "keeper.py")
keeper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keeper)

tmp = Path(tempfile.mkdtemp(prefix="rotless-shim-"))
if os.name == "nt":
    (tmp / "rotless-fake-cli.cmd").write_text("@echo fake-cli 1.2.3\r\n", encoding="utf-8")
else:
    f = tmp / "rotless-fake-cli"
    f.write_text("#!/bin/sh\necho fake-cli 1.2.3\n", encoding="utf-8")
    f.chmod(0o755)
os.environ["PATH"] = str(tmp) + os.pathsep + os.environ.get("PATH", "")

rc, out, err = keeper.run(["rotless-fake-cli", "--version"])
assert rc == 0 and "fake-cli 1.2.3" in out, f"keeper.run could not launch a shim CLI: rc={rc} err={err!r}"
print("ok: keeper.run launches shim CLIs")
