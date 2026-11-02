#!/usr/bin/env python3
"""Search code across ~1M public GitHub repos via grep.app's public MCP endpoint.

It needs no install and no auth, and works whether or not the grep MCP server is added to your agent.

Usage:
  grepapp.py "sarkariresult.com"
  grepapp.py "(sarkariresult|freejobalert)[.]com" --regex --lang Python --lang JavaScript
  grepapp.py "cron" --path .github/workflows/ --repos-only
  grepapp.py "import scrapy" --repo someorg/

Regex notes: prefix `(?s)` to span lines, `(?i)` for case-insensitive. Broad
regexes with no rare literal in them (e.g. `requests\\.get\\(`) time out (HTTP 504):
anchor on a rare string (a domain, a unique identifier) and add --lang/--path.
Returns at most ~10 files per query, so run several narrow queries, not one wide one.
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://mcp.grep.app"


def search(args):
    arguments = {"query": args.query}
    if args.regex:
        arguments["useRegexp"] = True
    if args.case:
        arguments["matchCase"] = True
    if args.words:
        arguments["matchWholeWords"] = True
    if args.lang:
        arguments["language"] = args.lang
    if args.repo:
        arguments["repo"] = args.repo
    if args.path:
        arguments["path"] = args.path

    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "searchGitHub", "arguments": arguments},
    }).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "rotless-github-research-skill/1.0",
    })
    raw = ""
    for attempt in (1, 2):  # grep.app intermittently 504s; one retry usually clears it
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as e:
            if attempt == 2 or e.code not in (500, 502, 503, 504):
                hint = " (query too broad: anchor on a rarer literal, add --lang/--path)" if e.code in (500, 502, 504) else ""
                sys.exit(f"grep.app HTTP {e.code}{hint}")

    # Response is SSE: one or more "data: {...}" lines.
    for line in raw.splitlines():
        if line.startswith("data:"):
            msg = json.loads(line[5:])
            if "error" in msg:
                sys.exit(f"grep.app error: {msg['error']}")
            return [c["text"] for c in msg["result"]["content"] if c.get("type") == "text"]
    sys.exit("grep.app: unexpected response:\n" + raw[:500])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("query")
    p.add_argument("--regex", action="store_true", help="treat query as regex")
    p.add_argument("--case", action="store_true", help="case sensitive")
    p.add_argument("--words", action="store_true", help="match whole words")
    p.add_argument("--lang", action="append", help="language filter, repeatable (Python, JavaScript, TypeScript, TSX, YAML, Markdown...)")
    p.add_argument("--repo", help="repo or org prefix filter, e.g. 'vercel/' or 'facebook/react'")
    p.add_argument("--path", help="partial path filter, e.g. '.github/workflows/' or 'requirements.txt'")
    p.add_argument("--repos-only", action="store_true", help="print unique repos + matching paths only, no snippets")
    args = p.parse_args()

    hits = search(args)
    if not hits or hits[0].startswith("No results"):
        print("No results.")
        return

    if not args.repos_only:
        print("\n\n".join(hits))
        return

    repos = {}
    for h in hits:
        repo = re.search(r"^Repository: (.+)$", h, re.M)
        path = re.search(r"^Path: (.+)$", h, re.M)
        if repo:
            repos.setdefault(repo.group(1).strip(), []).append(path.group(1).strip() if path else "?")
    for repo, paths in repos.items():
        print(f"{repo}\t{', '.join(paths)}")


if __name__ == "__main__":
    main()
