"""Shared utilities for skill-creator scripts."""

import json
import re
from pathlib import Path


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


def parse_skill_md(skill_path: Path) -> tuple[str, str, str]:
    """(name, description, full_content), read with the same parser quick_validate uses, so the runners
    and the validator never disagree about a description (lesson L-2026-11-02-11)."""
    content = (skill_path / "SKILL.md").read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(content)
    if fm is None:
        raise ValueError("SKILL.md has no frontmatter (it must start with ---)")
    name, desc = fm.get("name", ""), fm.get("description", "")
    return (name if isinstance(name, str) else ""), (desc if isinstance(desc, str) else ""), content
