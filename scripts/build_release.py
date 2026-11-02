#!/usr/bin/env python3
"""Build the files attached to a GitHub release. Standard library only.

  python scripts/build_release.py --out dist [--tag v0.1.0]

Writes into --out (which must be empty or new):
  rotless-<version>.zip   the whole plugin, for apps that install a plugin from a file
  <skill>.skill           one per skill, built by rotless-skill-creator's package_skill (no evals/)
  SHA256SUMS              checksums of the files above
  RELEASE_NOTES.md        this version's section of CHANGELOG.md

With --tag, it fails unless the tag is v<the version in plugin.json>. It then checks its own output.
The release workflow and the checksums idea follow google/elephant-goldfish-model (Apache-2.0).
"""
import argparse
import contextlib
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_FILES = ["plugin.json", ".claude-plugin", ".codex-plugin", ".agents", "skills", "assets", "docs",
                "README.md", "LICENSE", "CHANGELOG.md"]
SKIP_PARTS = {"__pycache__", ".DS_Store"}


def skipped(rel):
    return any(p in SKIP_PARTS or p.endswith("-workspace") for p in rel.parts) or rel.suffix in (".pyc", ".skill")


def plugin_zip(path):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for entry in PLUGIN_FILES:
            src = ROOT / entry
            for f in ([src] if src.is_file() else sorted(p for p in src.rglob("*") if p.is_file())):
                rel = f.relative_to(ROOT)
                if not skipped(rel):
                    z.write(f, rel.as_posix())


def skill_files(out):
    creator = ROOT / "skills" / "rotless-skill-creator"
    sys.path.insert(0, str(creator))
    from scripts.package_skill import package_skill  # the creator's own packager, reused as is
    built = []
    for d in sorted(p for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").is_file()):
        with contextlib.redirect_stdout(io.StringIO()):
            made = package_skill(d, out)
        if not made:
            sys.exit(f"packaging {d.name} failed (run quick_validate.py on it)")
        built.append(Path(made))
    return built


def release_notes(version):
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(rf"^## {re.escape(version)}\b.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        sys.exit(f"CHANGELOG.md has no section for {version}")
    return m.group(1).strip() + "\n"


def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag")
    a = ap.parse_args()
    version = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))["version"]
    if a.tag and a.tag != f"v{version}":
        sys.exit(f"tag {a.tag} doesn't match plugin.json version {version} (expected v{version})")
    out = Path(a.out)
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} isn't empty; give a new folder so old files can't slip into the release")
    out.mkdir(parents=True, exist_ok=True)

    plugin = out / f"rotless-{version}.zip"
    plugin_zip(plugin)
    skills = skill_files(out)
    assets = [plugin] + skills
    (out / "SHA256SUMS").write_text("".join(f"{sha256(p)}  {p.name}\n" for p in assets), encoding="utf-8", newline="\n")
    (out / "RELEASE_NOTES.md").write_text(release_notes(version), encoding="utf-8", newline="\n")

    # check what was built
    problems = []
    with zipfile.ZipFile(plugin) as z:
        names = set(z.namelist())
    for need in ["plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json", "LICENSE"]:
        if need not in names:
            problems.append(f"{plugin.name} lacks {need}")
    for s in skills:
        with zipfile.ZipFile(s) as z:
            inner = z.namelist()
        name = s.stem
        if f"{name}/SKILL.md" not in inner:
            problems.append(f"{s.name} lacks {name}/SKILL.md")
        if any(n.startswith(f"{name}/evals/") for n in inner):
            problems.append(f"{s.name} includes evals/")
        if f"skills/{name}/SKILL.md" not in names:
            problems.append(f"{plugin.name} lacks skills/{name}/SKILL.md")
    if len(skills) != 4:
        problems.append(f"expected 4 skills, built {len(skills)}")
    if problems:
        sys.exit("release check failed:\n" + "\n".join(f"- {p}" for p in problems))
    print(f"built rotless {version}: {plugin.name}, {', '.join(s.name for s in skills)}, SHA256SUMS, RELEASE_NOTES.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
