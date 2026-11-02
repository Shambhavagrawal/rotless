#!/usr/bin/env python3
"""Repo-level checks that the per-skill tests can't see. Standard library only; run from anywhere.

  python tests/check_repo.py

1. Relative links and #anchors in Markdown files resolve.
2. Paths a SKILL.md names in backticks (references/…, scripts/…, $C/scripts/…) exist in that skill.
3. The plugin manifests agree on name, version, license and author, marketplaces point at the repo root,
   the version is semver, and the Codex listing and icons fit their limits.
4. The only SKILL.md files are skills/<name>/SKILL.md (sample skills in test cases are SKILL.md.fixture).
5. No hooks anywhere, as the README promises.
6. Every skill has a trigger test set with should-trigger and should-not-trigger queries, and a Codex picker entry.
7. The field-notes footer is the same in every skill and in both templates, apart from the skill's own name,
   and its reminder goes through `keeper.py status`.
8. Every script or stylesheet an HTML page loads from the web is named in docs/privacy.md.

Ideas for 1 and 4-5 come from google/elephant-goldfish-model's unit tests (Apache-2.0).
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
problems = []


def files(pattern):
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.endswith("-workspace")]
        for f in filenames:
            p = Path(dirpath) / f
            if p.match(pattern):
                yield p


def rel(p):
    return p.relative_to(ROOT).as_posix()


def strip_code(text):
    text = re.sub(r"^[ \t]*```.*?^[ \t]*```", "", text, flags=re.S | re.M)
    return re.sub(r"`[^`\n]*`", "", text)


def slug(heading):
    """GitHub's anchor for a heading: lowercase, drop punctuation, spaces become hyphens."""
    h = re.sub(r"[`*_]", "", heading.strip().lower())
    h = re.sub(r"[^\w\- ]", "", h)
    return h.replace(" ", "-")


assert slug("Tracks & Workflow") == "tracks--workflow" and slug("Step 0: Brief") == "step-0-brief"


def anchors(md):
    return {slug(m.group(1)) for m in re.finditer(r"^#{1,6}\s+(.+?)\s*#*\s*$", strip_code(md.read_text(encoding="utf-8")), re.M)}


# 1. links
for md in files("*.md"):
    if "/files/" in rel(md):  # test-case input files are data
        continue
    for target in re.findall(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", strip_code(md.read_text(encoding="utf-8"))):
        if re.match(r"[a-z]+:", target) or any(c in target for c in "<{") or target.startswith("mailto"):
            continue
        path, _, frag = target.partition("#")
        dest = md if not path else (md.parent / path)
        if path and not dest.exists():
            dest = ROOT / path  # a plain path written from the repo root
        if not dest.exists():
            problems.append(f"{rel(md)}: broken link {target}")
        elif frag and dest.suffix == ".md" and frag not in anchors(dest):
            problems.append(f"{rel(md)}: link {target} points at a heading that doesn't exist")

# 2. paths named in SKILL.md
PATH_REF = re.compile(r"`(?:\$[A-Z]/)?((?:references|scripts|assets|agents|evals)/[\w./-]+)`")
# files of the skill being worked on, which a rotless skill names in its instructions; they aren't its own
TARGET_SKILL_FILES = {"references/prior-art.md", "references/prior-art.new.md", "references/lessons.md"}
for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
    for ref in PATH_REF.findall(skill_md.read_text(encoding="utf-8")):
        ref = ref.rstrip("/")
        if ref in TARGET_SKILL_FILES or ref.startswith("evals/"):
            continue
        if not (skill_md.parent / ref).exists():
            problems.append(f"{rel(skill_md)}: names `{ref}`, which doesn't exist in the skill")

# 3. manifests agree
def load(p):
    try:
        return json.loads((ROOT / p).read_text(encoding="utf-8"))
    except FileNotFoundError:
        problems.append(f"missing {p}")
        return {}


root = load("plugin.json")
claims = {"plugin.json": (root.get("name"), root.get("version")),
          ".claude-plugin/plugin.json": (load(".claude-plugin/plugin.json").get("name"), load(".claude-plugin/plugin.json").get("version")),
          ".codex-plugin/plugin.json": (load(".codex-plugin/plugin.json").get("name"), load(".codex-plugin/plugin.json").get("version"))}
for p in load(".claude-plugin/marketplace.json").get("plugins", []):
    claims[".claude-plugin/marketplace.json"] = (p.get("name"), p.get("version"))
for p in load(".agents/plugins/marketplace.json").get("plugins", []):
    claims[".agents/plugins/marketplace.json"] = (p.get("name"), root.get("version"))
for f, (name, version) in claims.items():
    if (name, version) != (root.get("name"), root.get("version")):
        problems.append(f"{f}: name/version {name} {version} differ from plugin.json ({root.get('name')} {root.get('version')})")
if not re.fullmatch(r"\d+\.\d+\.\d+", str(root.get("version"))):
    problems.append(f"plugin.json: version {root.get('version')!r} isn't MAJOR.MINOR.PATCH")
claude_p, codex_p = load(".claude-plugin/plugin.json"), load(".codex-plugin/plugin.json")
for f, m in ((".claude-plugin/plugin.json", claude_p), (".codex-plugin/plugin.json", codex_p)):
    for key in ("license", "author"):
        if m.get(key) != root.get(key):
            problems.append(f"{f}: {key} {m.get(key)!r} differs from plugin.json ({root.get(key)!r})")
for f in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
    for p in load(f).get("plugins", []):
        if p.get("source") != "./":
            problems.append(f"{f}: plugin {p.get('name')} must point source at the repo root (\"./\")")


def icon_ok(where, path):
    """Listing icons: the file exists, is under 5 MB, and an SVG is square."""
    p = ROOT / path
    if not p.is_file():
        problems.append(f"{where}: icon {path} doesn't exist")
        return
    if p.stat().st_size > 5 * 1024 * 1024:
        problems.append(f"{where}: icon {path} is over 5 MB")
    if p.suffix == ".svg":
        vb = re.search(r'viewBox="\s*[\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)"', p.read_text(encoding="utf-8"))
        if not vb or vb.group(1) != vb.group(2):
            problems.append(f"{where}: icon {path} must be a square SVG with a viewBox")


# Codex listing limits (as enforced by google/elephant-goldfish-model's harness tests)
ui = codex_p.get("interface", {})
for key, limit in (("displayName", 30), ("shortDescription", 30), ("longDescription", 4000), ("developerName", 80)):
    if not ui.get(key) or len(ui[key]) > limit:
        problems.append(f".codex-plugin/plugin.json: interface.{key} must be 1-{limit} characters")
caps = ui.get("capabilities", [])
if not caps or len(caps) > 20 or any(len(c) > 120 for c in caps):
    problems.append(".codex-plugin/plugin.json: interface.capabilities needs 1-20 entries of at most 120 characters")
for key in ("composerIcon", "logo"):
    icon_ok(f".codex-plugin/plugin.json {key}", ui.get(key, "").lstrip("./"))
icon_ok(".claude-plugin (default icon)", ".claude-plugin/icon.png")
for d in sorted(p for p in (ROOT / "skills").iterdir() if (p / "agents" / "openai.yaml").is_file()):
    y = (d / "agents" / "openai.yaml").read_text(encoding="utf-8")
    vals = dict(re.findall(r'^\s+(\w+):\s*"([^"]*)"', y, re.M))
    if not 1 <= len(vals.get("display_name", "")) <= 30 or not 1 <= len(vals.get("short_description", "")) <= 64:
        problems.append(f"{rel(d)}/agents/openai.yaml: display_name 1-30 and short_description 1-64 characters")
    for key in ("icon_small", "icon_large"):
        if key in vals:
            icon_ok(f"{rel(d)}/agents/openai.yaml {key}", f"{rel(d)}/{vals[key].lstrip('./')}")

# 4. only real skills are named SKILL.md
for p in files("SKILL.md"):
    parts = Path(rel(p)).parts
    if not (len(parts) == 3 and parts[0] == "skills"):
        problems.append(f"{rel(p)}: only skills/<name>/SKILL.md may be named SKILL.md; name sample skills SKILL.md.fixture")

# 5. no hooks
for p in list(files("hooks.json")) + [d for d in ROOT.rglob("hooks") if d.is_dir() and ".git" not in d.parts]:
    problems.append(f"{rel(p)}: rotless promises no hooks")
for m in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", "plugin.json"):
    if "hooks" in load(m):
        problems.append(f"{m}: declares hooks; rotless promises none")

# 6. trigger tests and Codex picker entry per skill
for d in sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir()):
    te = d / "evals" / "trigger-eval.json"
    try:
        items = json.loads(te.read_text(encoding="utf-8"))
        kinds = {bool(i.get("should_trigger")) for i in items}
        if kinds != {True, False}:
            problems.append(f"{rel(te)}: needs both should-trigger and should-not-trigger queries")
    except FileNotFoundError:
        problems.append(f"{rel(d)}: no evals/trigger-eval.json")
    if not (d / "agents" / "openai.yaml").is_file():
        problems.append(f"{rel(d)}: no agents/openai.yaml (Codex picker entry)")

# 7. one field-notes footer: identical in every skill and in both templates, apart from the skill's name
def footer_text(text):
    """The footer with the skill's two self-references (its notes command and its reminder line) made generic."""
    text = re.sub(r"notes\.py add \S+", "notes.py add <skill-name>", text)
    text = re.sub(r"\"[\w<>-]+ hasn't been updated", "\"<skill-name> hasn't been updated", text)
    return re.sub(r"[ \t]+\n", "\n", text).strip()


footers = {}
for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
    t = skill_md.read_text(encoding="utf-8")
    footers[rel(skill_md)] = footer_text(t[t.rindex("## Field notes"):])
for tpl in ("rotless-skill-creator", "rotless-skill-refiner"):
    t = (ROOT / "skills" / tpl / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"```markdown\n(\s*## Field notes\n.*?)\n\s*```", t, re.S)
    if m:
        block = "\n".join(line[3:] if line.startswith("   ") else line for line in m.group(1).splitlines())
        footers[f"skills/{tpl}/SKILL.md (template)"] = footer_text(block)
    else:
        problems.append(f"skills/{tpl}/SKILL.md: footer template not found")
for f, v in footers.items():
    # the reminder goes through `keeper.py status`, which lists only skills the user owns (lesson L-2026-11-02-16)
    if "keeper.py status" not in v:
        problems.append(f"{f}: the field-notes footer must ask `keeper.py status`, so skills you didn't write never remind you")
if len(set(footers.values())) > 1:
    base = max(set(footers.values()), key=list(footers.values()).count)  # the version most copies agree on
    problems += [f"{f}: field-notes footer differs from the others" for f, v in footers.items() if v != base]

# 8. every file a page loads from the web is named in docs/privacy.md
privacy = (ROOT / "docs" / "privacy.md").read_text(encoding="utf-8")
for page in files("*.html"):
    for url in re.findall(r"<(?:script|link)\b[^>]*\b(?:src|href)=\"(https?://[^\"]+)\"", page.read_text(encoding="utf-8")):
        host = re.match(r"https?://([^/]+)", url).group(1)
        if host not in privacy:
            problems.append(f"{rel(page)}: loads {host}, which docs/privacy.md doesn't mention")

if problems:
    print("FAIL\n" + "\n".join(f"- {p}" for p in problems))
    sys.exit(1)
print("ok: links, skill paths, manifests, SKILL.md placement, no hooks, trigger tests, footers, page loads")
