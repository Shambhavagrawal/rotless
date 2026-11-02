#!/usr/bin/env python3
"""Copy the rotless skills from an agent's skills folder into this repo, then run the checks.

For maintainers who develop the skills where their agent loads them (for example ~/.claude/skills)
and publish from this repo. Standard library only.

  python scripts/sync_skills.py                  # from ~/.claude/skills
  python scripts/sync_skills.py --from <folder>  # from another skills folder
  python scripts/sync_skills.py --dry-run        # list what would change, copy nothing

Only the skills already in this repo's skills/ are copied, without caches, test workspaces or drafts.
Text files are stored with LF line endings, as .gitattributes asks. It refuses to run when skills/ has
uncommitted changes, because the copy would overwrite them.
"""
import argparse
import filecmp
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*-workspace", "*.draft.json", ".DS_Store")
TEXT = {".md", ".py", ".json", ".yaml", ".yml", ".sh", ".txt", ".html", ".svg", ".fixture", ""}
CRLF, LF = bytes([13, 10]), bytes([10])


def same(a, b):
    """Equal files, ignoring CRLF versus LF: Windows tools write CRLF, the repo stores LF."""
    x, y = a.read_bytes(), b.read_bytes()
    if a.suffix in TEXT:
        x, y = x.replace(CRLF, LF), y.replace(CRLF, LF)
    return x == y


def changes(src, dst):
    """Relative paths that differ between two skill folders (new, removed or edited)."""
    out = []
    stack = [(filecmp.dircmp(src, dst, ignore=["__pycache__", ".DS_Store"]), Path("."))]
    while stack:
        c, rel = stack.pop()
        out += [f"+ {rel / n}" for n in c.left_only if not n.endswith(("-workspace", ".draft.json", ".pyc"))]
        out += [f"- {rel / n}" for n in c.right_only]
        out += [f"~ {rel / n}" for n in c.common_files if not same(Path(c.left) / n, Path(c.right) / n)]
        stack += [(sub, rel / name) for name, sub in c.subdirs.items()]
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="src", default=str(Path.home() / ".claude" / "skills"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    src_root = Path(a.src).expanduser()
    names = sorted(p.name for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").is_file())
    missing = [n for n in names if not (src_root / n / "SKILL.md").is_file()]
    if missing:
        sys.exit(f"not found in {src_root}: {', '.join(missing)}")

    dirty = subprocess.run(["git", "status", "--porcelain", "--", "skills"], cwd=ROOT, capture_output=True, text=True).stdout
    if dirty.strip() and not a.dry_run:
        sys.exit("skills/ has uncommitted changes; commit or stash them first:\n" + dirty)

    total = 0
    for n in names:
        diff = changes(src_root / n, ROOT / "skills" / n)
        total += len(diff)
        if diff:
            print(f"{n}: {len(diff)} change(s)")
            print("\n".join(f"  {d}" for d in diff[:40]))
    if not total:
        print("the repo already matches; nothing to copy")
        return 0
    if a.dry_run:
        return 0
    for n in names:
        shutil.rmtree(ROOT / "skills" / n)
        shutil.copytree(src_root / n, ROOT / "skills" / n, ignore=IGNORE)
        for f in (ROOT / "skills" / n).rglob("*"):
            if f.is_file() and f.suffix in TEXT and CRLF in f.read_bytes():
                f.write_bytes(f.read_bytes().replace(CRLF, LF))
    print("\ncopied; running the checks\n", flush=True)
    return subprocess.run([sys.executable, str(ROOT / "tests" / "run_checks.py")], cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
