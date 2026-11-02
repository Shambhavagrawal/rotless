#!/usr/bin/env python3
"""Validate a skill against the Agent Skills spec, then lint it for portability across agents.

Modified by rotless contributors (2026) from Anthropic's skill-creator quick_validate.py
(Apache-2.0): no PyYAML dependency, name must match its folder, metadata values must be
strings, plus non-fatal portability warnings (Claude-only tool names, paths and syntax).

  python quick_validate.py <skill_directory> [--strict]

Exit 0 when valid (warnings don't fail unless --strict), 1 otherwise.
"""
import json
import re
import sys
from pathlib import Path

EXCLUDED_DIR_PARTS = {'__pycache__', 'node_modules'}
ROOT_EXCLUDED_DIR_PARTS = {'evals'}
ALLOWED = {'name', 'description', 'license', 'allowed-tools', 'metadata', 'compatibility'}

# Claude-only wording that leaves other agents guessing. Each entry: (pattern, advice).
# A line that also names another agent or a generic alternative is fine, so those are skipped.
PORTABILITY = [
    (r"\$ARGUMENTS", "`$ARGUMENTS` is filled in by Claude Code only; say what it means in other agents"),
    (r"\b(WebSearch|WebFetch|TodoWrite|AskUserQuestion|NotebookEdit)\b", "Claude Code tool name; describe the capability (web search, ask the user…)"),
    (r"\b(Bash|Task|Skill|Agent) tool\b", "Claude Code tool name; say 'a shell', 'a subagent'…"),
    (r"\bclaude -p\b|\bclaude plugin\b", "Claude Code CLI only; give the other agents' equivalent or mark it optional"),
    (r"(?<![\w.])~?/?\.claude/(skills|commands|agents)", "Claude Code path; other agents use .agents/skills, ~/.codex/skills…"),
    (r"\bCLAUDE\.md\b", "Claude Code's instructions file; other agents read AGENTS.md / GEMINI.md"),
    (r"\bpresent_files\b|\bCowork\b|\bclaude\.ai\b", "Claude app feature; keep it to a clearly labelled optional note"),
]
OTHER_AGENTS = re.compile(r"codex|gemini|cursor|copilot|opencode|AGENTS\.md|other agents|any agent|e\.g\.|optional", re.I)


def unquote(v):
    """A YAML scalar as written: unescape double quotes the way YAML does (JSON-compatible) and '' in single quotes."""
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] == '"':
        try:
            return json.loads(v)
        except ValueError:
            return v[1:-1]
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1].replace("''", "'")
    return v


# YAML would read these as numbers, booleans, null, lists or maps, not strings
NON_STRING = re.compile(r'^(true|false|yes|no|on|off|null|~|[-+]?\d+(\.\d+)?|\[.*\]|\{.*\})$', re.I)


def counts_as_skill_md(rel):
    parts = rel.parts[:-1]
    return not any(p in EXCLUDED_DIR_PARTS for p in parts) and not (parts and parts[0] in ROOT_EXCLUDED_DIR_PARTS)


def parse_frontmatter(text):
    """Top-level keys of a YAML frontmatter block, without PyYAML. Values: str, or dict for mappings."""
    m = re.match(r'^---\r?\n(.*?)\r?\n---', text, re.S)
    if not m:
        return None, text
    fm, key = {}, None
    for line in m.group(1).splitlines():
        top = re.match(r'^([A-Za-z][\w-]*):\s*(.*)$', line)
        if top:
            key, val = top.group(1), top.group(2).strip()
            # only metadata is a mapping; any other key with its value on the next lines is a string
            # (a description line like 'Use this when: …' must not turn into a map; lesson L-2026-11-02-6)
            fm[key] = ({} if key == 'metadata' else '') if val == '' else val
        elif key is not None and line[:1] in (' ', '\t') and line.strip():
            sub = re.match(r'^\s+([\w.-]+):\s*(.*)$', line)
            if isinstance(fm[key], dict) and sub:
                fm[key][sub.group(1)] = sub.group(2).strip()
            elif isinstance(fm[key], str):
                fm[key] = (fm[key] + ' ' + line.strip()).strip()
    for k, v in fm.items():
        if isinstance(v, str):
            if v in ('>', '|', '>-', '|-'):
                fm[k] = ''
            fm[k] = unquote(re.sub(r'^([>|]-?)\s+', '', fm[k]).strip())
    return fm, text[m.end():]


def validate_skill(skill_path):
    skill_path = Path(skill_path)
    skill_md = skill_path / 'SKILL.md'
    if not skill_md.exists():
        return False, "SKILL.md not found", []
    extra = [p for p in skill_path.rglob('SKILL.md') if counts_as_skill_md(p.relative_to(skill_path))
             and p.resolve() != skill_md.resolve()]
    if extra:
        return False, (f"Found nested SKILL.md files ({', '.join(str(p.relative_to(skill_path)) for p in extra)}). "
                       "A skill has exactly one, at <folder>/SKILL.md; rename supporting docs (references/<topic>.md) "
                       "or split them into separate skills."), []

    content = skill_md.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)
    if fm is None:
        return False, "No YAML frontmatter found (SKILL.md must start with ---)", []
    unexpected = set(fm) - ALLOWED
    if unexpected:
        return False, (f"Unexpected key(s) in SKILL.md frontmatter: {', '.join(sorted(unexpected))}. Allowed properties "
                       f"are: {', '.join(sorted(ALLOWED))}. Agent-specific fields break other agents; put extra data "
                       "under metadata (string values)."), []
    for req in ('name', 'description'):
        if not fm.get(req):
            return False, f"Missing '{req}' in frontmatter", []

    name = fm['name'].strip()
    if not re.match(r'^[a-z0-9-]+$', name):
        return False, f"Name '{name}' should be kebab-case (lowercase letters, digits and hyphens only)", []
    if name.startswith('-') or name.endswith('-') or '--' in name:
        return False, f"Name '{name}' cannot start/end with a hyphen or contain consecutive hyphens", []
    if len(name) > 64:
        return False, f"Name is too long ({len(name)} characters, maximum 64)", []
    if name != skill_path.resolve().name:
        return False, f"Name '{name}' must match the skill's folder name '{skill_path.resolve().name}'", []

    desc = fm['description'].strip()
    if '<' in desc or '>' in desc:
        return False, "Description cannot contain angle brackets (< or >)", []
    if len(desc) > 1024:
        return False, f"Description is too long ({len(desc)} characters, maximum 1024)", []
    comp = fm.get('compatibility', '')
    if isinstance(comp, str) and len(comp) > 500:
        return False, f"Compatibility is too long ({len(comp)} characters, maximum 500)", []
    if 'metadata' in fm and not isinstance(fm['metadata'], dict):
        return False, "metadata must be a mapping of string keys to string values", []
    for k, v in (fm.get('metadata') or {}).items():
        if v == '' or (NON_STRING.match(v) and v[:1] not in ('"', "'")):
            return False, (f"metadata.{k} must be a string (the spec allows string values only): "
                           f"quote it, e.g. {k}: \"{v}\""), []

    warnings = []
    if not (skill_path / "keeper.json").is_file():
        warnings.append("no keeper.json: the CLIs, APIs, docs and limits this skill relies on aren't tracked; "
                        "run rotless-skill-modernizer init <skill> (rotless-skill-creator step 8)")
    lines = body.splitlines()
    if len(lines) > 500:
        warnings.append(f"SKILL.md body is {len(lines)} lines; keep it under 500 and move detail to references/")
    offset = content[:len(content) - len(body)].count('\n')
    for i, line in enumerate(lines, start=offset + 1):
        if OTHER_AGENTS.search(line):
            continue
        for pat, advice in PORTABILITY:
            if re.search(pat, line):
                warnings.append(f"SKILL.md:{i}: {advice}: {line.strip()[:90]}")
                break
    return True, "Skill is valid!", warnings


def main(argv):
    args = [x for x in argv[1:] if x != '--strict']
    if len(args) != 1:
        print("Usage: python quick_validate.py <skill_directory> [--strict]")
        return 1
    valid, message, warnings = validate_skill(args[0])
    print(message)
    for w in warnings:
        print(f"  portability: {w}")
    if valid and warnings and '--strict' in argv:
        return 1
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
