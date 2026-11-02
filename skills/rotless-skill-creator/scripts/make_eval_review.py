#!/usr/bin/env python3
"""Fill assets/eval_review.html with an eval set, safely (lesson L-2026-11-02-10).

Part of rotless-skill-creator (new file). The skill name and description go into HTML text, so they're
HTML-escaped; the eval set goes into a <script> block, so `<` is written as \\u003c and a query containing
</script> can't end the block. One substitution pass: inserted text is never scanned for placeholders again.

  python scripts/make_eval_review.py --eval-set trigger-eval.json --skill-path <skill> --out review.html
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import parse_skill_md  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "eval_review.html"


def render(template, items, name, description):
    values = {"EVAL_DATA": json.dumps(items, ensure_ascii=False).replace("<", "\\u003c"),
              "SKILL_NAME": html.escape(name), "SKILL_DESCRIPTION": html.escape(description)}
    return re.sub(r"__(EVAL_DATA|SKILL_NAME|SKILL_DESCRIPTION)_PLACEHOLDER__", lambda m: values[m.group(1)], template)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eval-set", required=True)
    ap.add_argument("--skill-path", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    name, description, _ = parse_skill_md(Path(a.skill_path))
    items = json.loads(Path(a.eval_set).read_text(encoding="utf-8"))
    Path(a.out).write_text(render(TEMPLATE.read_text(encoding="utf-8"), items, name, description), encoding="utf-8")
    print(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
