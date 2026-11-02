#!/usr/bin/env python3
"""Verify many repos via batched GraphQL (25 repos/call): existence, renames, health, evidence.

Per repo it reports:
  - existence (NOT FOUND = hallucinated/deleted), renames/transfers (real name shown),
    archived, fork (+ upstream), empty, template
  - last commit AND last *substantive* commit (ignores chore/bump/deps/merge/typo/docs-only
    messages; pushedAt and raw last commit overstate activity)
  - issue resolution % (closed / all issues), merged PRs, people involved, org vs user,
    releases in the last 365 days
  - evidence of real engineering from the root tree: tests, CI (.github/workflows,
    not just .github), package manifest, SECURITY.md
  - warning flags: !velocity (stars/day since creation > 100: viral, hype or bought stars,
    needs context), !lowfork (>=1000 stars but forks/stars < 0.005), new (< 14 days old),
    stale Ny (no substantive commit for 2+ years; flagged, never demoted: an abandoned tool
    still proves the idea was built), noise? (tutorial/template/demo/boilerplate/dotfiles/awesome-list)

Requires the GitHub CLI (`gh`), logged in. Uses the GraphQL quota (5000 pts/hr), not search.

Usage:
  ghverify.py owner/repo https://github.com/owner2/repo2 ...
  ghverify.py - < repos.txt          # one repo per line (first token used)
  ghverify.py --json owner/repo ...
"""
import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys

BATCH = 25
FRAGMENT = """
fragment f on Repository {
  nameWithOwner url description stargazerCount forkCount pushedAt createdAt
  isArchived isFork isEmpty isTemplate
  owner { __typename }
  parent { nameWithOwner }
  primaryLanguage { name }
  mentionableUsers { totalCount }
  openIssues: issues(states: OPEN) { totalCount }
  closedIssues: issues(states: CLOSED) { totalCount }
  mergedPRs: pullRequests(states: MERGED) { totalCount }
  releases(first: 10, orderBy: {field: CREATED_AT, direction: DESC}) { nodes { publishedAt } }
  repositoryTopics(first: 10) { nodes { topic { name } } }
  root: object(expression: "HEAD:") { ... on Tree { entries { name type } } }
  workflows: object(expression: "HEAD:.github/workflows") { ... on Tree { entries { name } } }
  defaultBranchRef { target { ... on Commit {
    committedDate
    history(first: 30) { totalCount nodes { messageHeadline committedDate } }
  } } }
}"""

TRIVIAL = re.compile(
    r"^(merge\b|bump\b|chore|build\(deps|deps?[(:]|update (readme|dependencies|deps)|typo|fix typo|"
    r"docs?[(:]|readme|ci[(:]|style[(:]|format|lint|update \S+\.md|auto-?update|\[bot\]|version bump|release v?\d)",
    re.I)
MANIFESTS = {"package.json", "pyproject.toml", "setup.py", "requirements.txt", "go.mod", "Cargo.toml",
             "pom.xml", "build.gradle", "build.gradle.kts", "Gemfile", "composer.json", "mix.exs",
             "Package.swift", "pubspec.yaml", "CMakeLists.txt", "deno.json"}
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "testing", "e2e"}
NOISE = re.compile(r"(^|[-_.])(tutorial|course|boilerplate|starter|template|demo|example|examples|poc|"
                   r"learning|homework|assignment|dotfiles|awesome)([-_.]|$)", re.I)


def parse_repo(s):
    s = s.strip().removesuffix(".git").rstrip("/")
    m = re.search(r"(?:github\.com[/:])?([\w.-]+)/([\w.-]+)", s)
    return (m.group(1), m.group(2)) if m else None


def fetch(batch):
    parts = [f'r{i}: repository(owner: {json.dumps(o)}, name: {json.dumps(n)}) {{ ...f }}'
             for i, (o, n) in enumerate(batch)]
    query = "{ " + " ".join(parts) + " }" + FRAGMENT
    r = subprocess.run(["gh", "api", "graphql", "-f", f"query={query}"],
                       capture_output=True, text=True, encoding="utf-8")
    # NOT_FOUND repos make gh exit non-zero but stdout still carries the data.
    try:
        return json.loads(r.stdout).get("data") or {}
    except json.JSONDecodeError:
        sys.exit(f"GraphQL call failed: {r.stderr.strip()}")


def days_since(iso, now):
    return (now - dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))).days if iso else None


def analyse(asked, d, now):
    head = ((d.get("defaultBranchRef") or {}).get("target") or {})
    history = head.get("history") or {}
    substantive = next((c["committedDate"] for c in history.get("nodes", [])
                        if not TRIVIAL.search(c["messageHeadline"].strip())), None)
    root = {e["name"] for e in ((d.get("root") or {}).get("entries") or [])}
    root_lower = {n.lower() for n in root}
    topics = [t["topic"]["name"] for t in d["repositoryTopics"]["nodes"]]
    stars, forks = d["stargazerCount"], d["forkCount"]
    age = max(days_since(d["createdAt"], now) or 1, 1)
    open_i, closed_i = d["openIssues"]["totalCount"], d["closedIssues"]["totalCount"]
    rel_365 = sum(1 for r in d["releases"]["nodes"]
                  if r["publishedAt"] and (days_since(r["publishedAt"], now) or 0) <= 365)

    evidence = []
    if root_lower & TEST_DIRS or any(n.startswith(("test_", "pytest", "jest.config", "vitest.config")) for n in root_lower):
        evidence.append("tests")
    if (d.get("workflows") or {}).get("entries"):
        evidence.append("ci")
    if root & MANIFESTS:
        evidence.append("manifest")
    if "security.md" in root_lower:
        evidence.append("security.md")

    flags = []
    if d["nameWithOwner"].lower() != asked.lower():
        flags.append(f"renamed->{d['nameWithOwner']}")
    if d["isArchived"]:
        flags.append("archived")
    if d["isFork"]:
        flags.append(f"fork of {(d.get('parent') or {}).get('nameWithOwner', '?')}")
    if d["isEmpty"]:
        flags.append("EMPTY")
    if d["isTemplate"]:
        flags.append("template")
    if stars / age > 100:
        flags.append(f"!velocity {stars / age:.0f}/day")
    if stars >= 1000 and forks / stars < 0.005:
        flags.append("!lowfork")
    if age < 14:
        flags.append("new")
    stale_days = days_since(substantive or head.get("committedDate"), now)
    if stale_days is not None and stale_days > 730 and not d["isArchived"]:
        # flagged, never demoted: an abandoned tool is still proof the idea was built
        flags.append(f"stale {stale_days // 365}y")
    if NOISE.search(d["nameWithOwner"].split("/")[1]) or any(NOISE.search(t) for t in topics):
        flags.append("noise?")

    return {
        "asked": asked, "status": "OK", "repo": d["nameWithOwner"], "url": d["url"],
        "owner": "org" if d["owner"]["__typename"] == "Organization" else "user",
        "stars": stars, "forks": forks, "created": d["createdAt"][:10],
        "lastCommit": (head.get("committedDate") or "")[:10],
        "lastSubstantive": (substantive or "")[:10] or ("none in last 30" if history.get("nodes") else ""),
        "commits": history.get("totalCount", 0), "people": d["mentionableUsers"]["totalCount"],
        "openIssues": open_i, "closedIssues": closed_i,
        "issueResolution": round(100 * closed_i / (open_i + closed_i)) if open_i + closed_i else None,
        "mergedPRs": d["mergedPRs"]["totalCount"], "releases365d": rel_365,
        "language": (d.get("primaryLanguage") or {}).get("name"),
        "evidence": evidence, "flags": flags, "topics": topics, "description": d.get("description") or "",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("repos", nargs="+", help="owner/repo or GitHub URLs; '-' reads stdin")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if not shutil.which("gh"):
        sys.exit("gh CLI not found. Install: https://cli.github.com then `gh auth login`.")

    raw = []
    for a in args.repos:
        raw += [line.split()[0] for line in sys.stdin if line.strip()] if a == "-" else [a]
    wanted, seen = [], set()
    for s in raw:
        pr = parse_repo(s)
        if pr and pr not in seen:
            seen.add(pr)
            wanted.append(pr)

    now = dt.datetime.now(dt.timezone.utc)
    out = []
    for start in range(0, len(wanted), BATCH):
        batch = wanted[start:start + BATCH]
        data = fetch(batch)
        for i, (o, n) in enumerate(batch):
            d = data.get(f"r{i}")
            out.append(analyse(f"{o}/{n}", d, now) if d else {"asked": f"{o}/{n}", "status": "NOT FOUND"})

    if args.json:
        json.dump(out, sys.stdout, indent=1)
        return

    print("repo | ★ | last commit / last substantive | created | commits | people | issues open/closed (resolved%) | "
          "merged PRs | rel/yr | lang | evidence | flags | description")
    for r in out:
        if r["status"] != "OK":
            print(f"NOT FOUND | {r['asked']}")
            continue
        res = f"{r['issueResolution']}%" if r["issueResolution"] is not None else "-"
        print(f"{r['repo']} ({r['owner']}) | {r['stars']} | {r['lastCommit']} / {r['lastSubstantive'] or '-'} | "
              f"{r['created']} | {r['commits']} | {r['people']} | {r['openIssues']}/{r['closedIssues']} ({res}) | "
              f"{r['mergedPRs']} | {r['releases365d']} | {r['language'] or '-'} | "
              f"{','.join(r['evidence']) or 'NONE'} | {', '.join(r['flags']) or '-'} | {r['description'][:70]}")
    missing = sum(r["status"] != "OK" for r in out)
    if missing:
        print(f"\n{missing} repo(s) not found: drop them or recheck the name.")


if __name__ == "__main__":
    main()
