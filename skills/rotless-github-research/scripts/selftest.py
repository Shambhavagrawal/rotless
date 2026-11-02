#!/usr/bin/env python3
"""Executable canaries for the rotless-github-research skill: does everything SKILL.md claims still hold?

Each check is one claim from SKILL.md or one dependency of the scripts. Statuses:
  PASS     claim holds
  WARN     probably transient (a flaky service, one source down): rerun before acting
  CHANGED  a documented behaviour is no longer true: update SKILL.md (the tool evolved)
  FAIL     something the scripts need is broken: fix the script or upgrade the tool

Costs ~5 search-API calls and 2 code-search calls, about 40 seconds. Exit code 1 on FAIL/CHANGED.

Usage:
  selftest.py            run all checks
  selftest.py --quick    skip the slow network sweeps (srcsweep / grep.app)
  selftest.py --json
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
PY = sys.executable


def run(cmd, timeout=120):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def gh_api(*args):
    code, out, err = run(["gh", "api", *args])
    if code != 0:
        raise RuntimeError(err.strip()[:200] or out[:200])
    return json.loads(out)


def repo_count(q):
    return gh_api("-X", "GET", "search/repositories", "-f", f"q={q}", "-f", "per_page=1")["total_count"]


def code_count(q):
    return gh_api("-X", "GET", "search/code", "-f", f"q={q}", "-f", "per_page=1")["total_count"]


# --- checks: each returns (status, detail) -------------------------------------------------

def gh_installed():
    if not shutil.which("gh"):
        return "FAIL", "gh not on PATH (https://cli.github.com)"
    m = re.search(r"(\d+\.\d+\.\d+)", run(["gh", "--version"])[1])
    return "PASS", f"gh {m.group(1) if m else '?'}"


def gh_auth():
    return ("PASS", "logged in") if run(["gh", "auth", "status"])[0] == 0 else ("FAIL", "run `gh auth login`")


def gh_commands():
    missing = [c for c in (["repo", "read-dir"], ["repo", "read-file"], ["skill", "search"], ["discussion", "list"])
               if run(["gh", *c, "--help"])[0] != 0]
    return ("PASS", "read-dir, read-file, skill, discussion present") if not missing else \
        ("FAIL", f"missing: {', '.join(' '.join(c) for c in missing)}: upgrade gh (SKILL.md depends on them)")


def rule_or():
    a, b = repo_count("sarkari OR naukri"), repo_count("sarkari")
    return ("PASS", f"OR widens ({b} -> {a})") if a > b else ("CHANGED", f"`A OR B` ({a}) no longer wider than `A` ({b})")


def rule_not():
    a, b = repo_count("naukri NOT resume"), repo_count("naukri")
    return ("PASS", f"NOT narrows ({b} -> {a})") if a < b else ("CHANGED", "`NOT word` no longer excludes")


def rule_dash_word():
    n = repo_count("freejobalert -resume")
    return ("PASS", "`-word` still returns 0 (documented quirk)") if n == 0 else \
        ("CHANGED", f"`-word` now returns {n}: update the Exclusion rule in SKILL.md")


def rule_code_path():
    n = code_count("sarkari path:.github/workflows")
    return ("PASS", f"path: works ({n} hits)") if n > 0 else ("CHANGED", "code search `path:` returned 0: rule in SKILL.md may be stale")


def rule_code_or():
    n = code_count("sarkariresult OR freejobalert language:python")
    return ("PASS", f"OR + language: work ({n} hits)") if n > 0 else ("CHANGED", "code search OR returned 0")


def rule_rate_limits():
    res = gh_api("rate_limit")["resources"]
    got = (res["search"]["limit"], res["code_search"]["limit"])
    return ("PASS", f"search {got[0]}/min, code {got[1]}/min") if got == (30, 10) else \
        ("CHANGED", f"limits are now search {got[0]}/min, code {got[1]}/min (SKILL.md says 30 and 10)")


def rule_private_field():
    items = gh_api("-X", "GET", "search/repositories", "-f", "q=sarkari", "-f", "per_page=1")["items"]
    return ("PASS", "`private` field present on search items") if items and "private" in items[0] else \
        ("FAIL", "search items lack `private`: the privacy filter in ghsweep.py/SKILL.md no longer works")


def script_ghverify():
    code, out, err = run([PY, str(HERE / "ghverify.py"), "--json", "cli/cli", "nope-x9/does-not-exist"])
    if code != 0:
        return "FAIL", err.strip()[:150]
    rows = json.loads(out)
    ok = rows[0].get("status") == "OK" and rows[1].get("status") == "NOT FOUND"
    need = {"lastSubstantive", "evidence", "flags", "issueResolution", "mergedPRs", "releases365d"}
    return ("PASS", "GraphQL fragment valid, NOT FOUND handled") if ok and need <= set(rows[0]) else \
        ("FAIL", "ghverify.py output shape changed or GraphQL schema rejected a field")


def script_ghsweep():
    code, out, err = run([PY, str(HERE / "ghsweep.py"), "--json", "--limit", "5", "topic:sarkari-result"])
    if code != 0:
        return "FAIL", err.strip()[:150]
    rows = json.loads(out)
    return ("PASS", f"{len(rows)} repos") if rows and {"fullName", "matched", "topics"} <= set(rows[0]) else \
        ("FAIL", "ghsweep.py returned nothing or wrong shape")


def grepapp_schema():
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode()
    req = urllib.request.Request("https://mcp.grep.app", data=body, headers={
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream", "User-Agent": "rotless-github-research-selftest"})
    try:
        raw = urllib.request.urlopen(req, timeout=30).read().decode()
    except Exception as e:
        return "WARN", f"grep.app unreachable ({type(e).__name__}): rerun; scripts fall back to gh code search"
    line = next((ln for ln in raw.splitlines() if ln.startswith("data:")), "")
    tools = {t["name"]: t for t in json.loads(line[5:])["result"]["tools"]} if line else {}
    t = tools.get("searchGitHub")
    if not t:
        return "FAIL", f"grep.app no longer exposes searchGitHub (has: {', '.join(tools) or 'nothing'})"
    props = set(t["inputSchema"]["properties"])
    need = {"query", "useRegexp", "language", "path", "repo", "matchCase", "matchWholeWords"}
    return ("PASS", "searchGitHub schema as expected") if need <= props else \
        ("FAIL", f"grep.app params changed; missing {sorted(need - props)}: update grepapp.py")


def script_grepapp():
    code, out, err = run([PY, str(HERE / "grepapp.py"), "freejobalert.com", "--repos-only"])
    if code != 0 and re.search(r"HTTP 5\d\d", err):
        return "WARN", "grep.app 5xx (known flakiness); rerun"
    return ("PASS", f"{len(out.splitlines())} repos") if code == 0 and out.strip() and "No results" not in out else \
        ("FAIL", (err or out).strip()[:150])


def script_srcsweep():
    code, out, err = run([PY, str(HERE / "srcsweep.py"), "--json", "--limit", "1", "kubernetes"], timeout=180)
    if code != 0:
        return "FAIL", err.strip()[:150]
    d = json.loads(out)
    dead = d["not_reached"]
    empty = [n for n, v in d["results"].items() if v["total"] == 0]
    if len(dead) >= 4:
        return "FAIL", f"{len(dead)} sources not reached: {dead}"
    if dead or empty:
        return "WARN", f"not reached: {dead or 'none'}; zero results for a common term: {empty or 'none'} (API changed? flaky?)"
    return "PASS", f"{len(d['results'])} sources alive"


QUICK = [gh_installed, gh_auth, gh_commands, rule_or, rule_not, rule_dash_word, rule_code_path, rule_code_or,
         rule_rate_limits, rule_private_field, script_ghverify, script_ghsweep]
SLOW = [grepapp_schema, script_grepapp, script_srcsweep]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--quick", action="store_true", help="skip grep.app and the 21-source sweep")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    results = []
    for fn in QUICK + ([] if args.quick else SLOW):
        try:
            status, detail = fn()
        except Exception as e:  # a check that crashes is a FAIL, never a silent skip
            status, detail = "FAIL", f"check crashed: {type(e).__name__}: {str(e)[:120]}"
        results.append({"check": fn.__name__, "status": status, "detail": detail})
        if not args.json:
            print(f"{status:<8} {fn.__name__:<18} {detail}", flush=True)

    counts = {s: sum(r["status"] == s for r in results) for s in ("PASS", "WARN", "CHANGED", "FAIL")}
    if args.json:
        json.dump({"counts": counts, "results": results}, sys.stdout, indent=1)
    else:
        print("\n" + ", ".join(f"{n} {s}" for s, n in counts.items()))
    sys.exit(1 if counts["FAIL"] or counts["CHANGED"] else 0)


if __name__ == "__main__":
    main()
