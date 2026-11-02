#!/usr/bin/env python3
"""Run many GitHub repo searches, dedupe, and print one table sorted by last push.

Uses the raw search API through `gh api` (not `gh search repos`), so the full
GitHub query syntax works inside each query: OR, -exclusions, "exact phrases",
and every qualifier (topic:, language:, user:, org:, stars:>N, created:, pushed:,
in:name,description,readme,topics, fork:true, archived:false, size:).
Also reports each query's total match count and the most common topics among
the hits (feed those back in as topic: queries).

Requires the GitHub CLI (`gh`), logged in. Search API limit: 30 requests/min;
the script waits and retries once if it hits that. Responses are cached 1h.

Usage:
  ghsweep.py "sarkari OR naukri" "freejobalert" "topic:government-jobs"
  ghsweep.py --pushed ">2025-01-01" --min-stars 1 "admit card scraper" "naukri bot -resume"
  ghsweep.py --in name,description,readme "exam notification"
  ghsweep.py --json "query1" "query2" > repos.json
"""
import argparse
import collections
import json
import re
import shutil
import subprocess
import sys
import time


NOISE = re.compile(r"(^|[-_.])(tutorial|course|boilerplate|starter|template|demo|example|examples|poc|"
                   r"learning|homework|assignment|dotfiles|awesome)([-_.]|$)", re.I)


def run_query(q, args):
    full = q
    if args.pushed:
        full += f" pushed:{args.pushed}"
    if args.in_:
        full += f" in:{args.in_}"
    if args.include_forks:
        full += " fork:true"
    cmd = ["gh", "api", "-X", "GET", "search/repositories", "--cache", "1h",
           "-f", f"q={full}", "-f", f"per_page={min(args.limit, 100)}"]
    if args.sort:
        cmd += ["-f", f"sort={args.sort}"]
    for attempt in (1, 2):
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if r.returncode == 0:
            data = json.loads(r.stdout)
            return data.get("total_count", 0), data.get("items", [])
        if attempt == 1 and "rate limit" in r.stderr.lower():
            print("[info] search rate limit hit, waiting 60s", file=sys.stderr)
            time.sleep(61)
            continue
        break
    print(f"[warn] query failed: {full!r}: {r.stderr.strip()}", file=sys.stderr)
    return 0, []


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("queries", nargs="+")
    p.add_argument("--limit", type=int, default=50, help="results per query (max 100)")
    p.add_argument("--sort", choices=["stars", "forks", "updated", "help-wanted-issues"], help="default: best match")
    p.add_argument("--pushed", help="last-push filter, e.g. '>2025-01-01'")
    p.add_argument("--in", dest="in_", help="where to match: name,description,readme,topics")
    p.add_argument("--must", help="regex: keep only repos whose name/description/topics match it "
                                  "(cuts homonym noise, e.g. --must 'github|repo|agent' when 'prior art' drags in patent tools)")
    p.add_argument("--exclude", help="regex: drop repos whose name/description/topics match it (e.g. 'patent|trading')")
    p.add_argument("--min-stars", type=int, default=0)
    p.add_argument("--include-forks", action="store_true")
    p.add_argument("--keep-archived", action="store_true")
    p.add_argument("--order", choices=["pushed", "stars", "hits"], default="pushed",
                   help="table order; 'hits' = found by the most queries first (best relevance signal)")
    p.add_argument("--top", type=int, default=60, help="print only the first N rows, 0 = all (totals and topics still use all)")
    p.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = p.parse_args()

    if not shutil.which("gh"):
        sys.exit("gh CLI not found. Install: https://cli.github.com then `gh auth login`.")

    seen, totals = {}, []
    for q in args.queries:
        total, items = run_query(q, args)
        totals.append((q, total, len(items)))
        for r in items:
            if r.get("private"):  # authenticated search also returns private repos the account can see
                continue
            name = r["full_name"]
            if name in seen:
                seen[name]["matched"].append(q)
                continue
            seen[name] = {
                "fullName": name, "url": r["html_url"], "description": r.get("description") or "",
                "stars": r["stargazers_count"], "pushedAt": r["pushed_at"], "createdAt": r["created_at"],
                "language": r.get("language"), "topics": r.get("topics", []),
                "isFork": r["fork"], "isArchived": r["archived"], "matched": [q],
            }

    def text(r):
        return f"{r['fullName']} {r['description']} {' '.join(r['topics'])}"

    must = re.compile(args.must, re.I) if args.must else None
    exclude = re.compile(args.exclude, re.I) if args.exclude else None
    candidates = [r for r in seen.values()
                  if r["stars"] >= args.min_stars and (args.keep_archived or not r["isArchived"])]
    rows = [r for r in candidates
            if (not must or must.search(text(r))) and not (exclude and exclude.search(text(r)))]
    if len(rows) < len(candidates):
        print(f"[info] --must/--exclude dropped {len(candidates) - len(rows)} of {len(candidates)} repos", file=sys.stderr)
    keys = {"pushed": lambda r: r["pushedAt"],
            "stars": lambda r: r["stars"],
            "hits": lambda r: (len(r["matched"]), r["stars"])}
    rows.sort(key=keys[args.order], reverse=True)

    if args.json:
        json.dump(rows, sys.stdout, indent=1)
        return

    print("query totals (total matches on GitHub / fetched):")
    for q, total, got in totals:
        more = "  <- more exist: narrow it or slice by created:/pushed: dates" if total > got else ""
        print(f"  {total:>6} / {got:<3} {q}{more}")
    shown = rows[:args.top] if args.top else rows
    print(f"\n{len(rows)} unique repos" + (f", showing top {len(shown)} by {args.order}" if len(shown) < len(rows) else "") + "\n")
    print("pushed     | stars | repo | lang | hits | description")
    for r in shown:
        flags = (" [fork]" if r["isFork"] else "") + (" [archived]" if r["isArchived"] else "")
        if NOISE.search(r["fullName"].split("/")[1]) or any(NOISE.search(t) for t in r["topics"]):
            flags += " [noise?]"
        print(f"{r['pushedAt'][:10]} | {r['stars']:>5} | {r['fullName']}{flags} | "
              f"{r['language'] or '-'} | {len(r['matched'])} | {r['description'].replace(chr(10), ' ')[:100]}")

    topics = collections.Counter(t for r in rows for t in r["topics"])
    if topics:
        print("\ncommon topics (try as topic:<name> queries):")
        print("  " + ", ".join(f"{t} ({n})" for t, n in topics.most_common(20)))


if __name__ == "__main__":
    main()
