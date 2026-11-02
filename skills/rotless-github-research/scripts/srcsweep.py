#!/usr/bin/env python3
"""Search ~21 non-GitHub sources at once for prior art, in parallel, no auth.

Package registries (npm, crates.io, Packagist, Hex, NuGet, Maven Central, RubyGems, Hackage,
Docker Hub, ArtifactHub, AUR, Open VSX), other forges (GitLab, Codeberg), agent ecosystems
(MCP Registry, skills.sh), Hugging Face (models/datasets/spaces/papers) and Hacker News.

Ends with a source ledger: which sources were searched and which were NOT reached (with
the error), so "nothing found" is never stated for a source that actually failed.
Not covered (no search API): PyPI (use web search `site:pypi.org <q>`), Homebrew, pkg.go.dev.

Usage:
  srcsweep.py "github repository discovery"
  srcsweep.py "kubernetes log viewer" --limit 6 --sources npm,crates,dockerhub,openvsx
  srcsweep.py "sarkari" --repos | python ghverify.py -     # GitHub repos found in the results
  srcsweep.py "prior art" --json

Tips: 1-3 word queries work best (all registries AND the terms). Run it with several wordings.
"""
import argparse
import concurrent.futures as cf
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

UA = "rotless-github-research-skill/1.0"
GH = re.compile(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/#?\"' ]|$)", re.I)
NOT_OWNERS = {"topics", "orgs", "users", "features", "marketplace", "sponsors", "settings", "search", "apps",
              "collections", "trending", "enterprise", "about", "pricing", "login", "explore", "notifications",
              "issues", "pulls", "codespaces", "organizations", "site", "security", "customer-stories", "readme"}


def gh_repo(text):
    """"owner/repo" from the first GitHub repo link in text; GitHub's own pages (topics, orgs…) don't count."""
    for m in GH.finditer(text or ""):
        if m.group(1).lower() not in NOT_OWNERS:
            return f"{m.group(1)}/{m.group(2)}"
    return None


def get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def item(name, desc=None, url="", repo="", extra=""):
    return {"name": name, "desc": (desc or "").replace("\n", " ")[:90], "url": url, "repo": repo or "", "extra": extra}


def npm(q, n):
    d = get(f"https://registry.npmjs.org/-/v1/search?text={q}&size={n}")
    return d["total"], [item(o["package"]["name"], o["package"].get("description"),
                             (o["package"].get("links") or {}).get("npm", ""), (o["package"].get("links") or {}).get("repository", ""),
                             f"v{o['package']['version']} {o['package']['date'][:10]}") for o in d["objects"]]


def crates(q, n):
    d = get(f"https://crates.io/api/v1/crates?q={q}&per_page={n}")
    return d["meta"]["total"], [item(c["name"], c.get("description"), f"https://crates.io/crates/{c['name']}",
                                     c.get("repository"), f"{c['downloads']} dl, upd {c['updated_at'][:10]}") for c in d["crates"]]


def packagist(q, n):
    d = get(f"https://packagist.org/search.json?q={q}&per_page={n}")
    return d["total"], [item(r["name"], r.get("description"), r["url"], r.get("repository"),
                             f"{r.get('downloads', 0)} dl") for r in d["results"]]


def hex_(q, n):
    d = get(f"https://hex.pm/api/packages?search={q}&sort=recent_downloads")[:n]
    return len(d), [item(r["name"], (r.get("meta") or {}).get("description"), r["html_url"],
                         next((v for v in ((r.get("meta") or {}).get("links") or {}).values() if "github.com" in v), ""),
                         f"upd {r['updated_at'][:10]}") for r in d]


def nuget(q, n):
    d = get(f"https://azuresearch-usnc.nuget.org/query?q={q}&take={n}")
    return d["totalHits"], [item(r["id"], r.get("description"), f"https://www.nuget.org/packages/{r['id']}",
                                 r.get("projectUrl"), f"{r.get('totalDownloads', 0)} dl") for r in d["data"]]


def maven(q, n):
    d = get(f"https://search.maven.org/solrsearch/select?q={q}&rows={n}&wt=json")["response"]
    return d["numFound"], [item(r["id"], "", f"https://central.sonatype.com/artifact/{r['g']}/{r['a']}", "",
                                f"v{r['latestVersion']}") for r in d["docs"]]


def rubygems(q, n):
    d = get(f"https://rubygems.org/api/v1/search.json?query={q}")[:n]
    return len(d), [item(r["name"], r.get("info"), r.get("project_uri", ""), r.get("source_code_uri") or r.get("homepage_uri"),
                         f"{r.get('downloads', 0)} dl") for r in d]


def hackage(q, n):
    d = get(f"https://hackage.haskell.org/packages/search?terms={q}")[:n]
    return len(d), [item(r["name"], "", f"https://hackage.haskell.org/package/{r['name']}") for r in d]


def dockerhub(q, n):
    d = get(f"https://hub.docker.com/v2/search/repositories/?query={q}&page_size={n}")
    return d["count"], [item(r["repo_name"], r.get("short_description"), f"https://hub.docker.com/r/{r['repo_name']}", "",
                             f"{r.get('star_count', 0)}★ {r.get('pull_count', 0)} pulls") for r in d["results"]]


def artifacthub(q, n):
    d = get(f"https://artifacthub.io/api/v1/packages/search?ts_query_web={q}&limit={n}")
    return len(d.get("packages") or []), [item(p["name"], p.get("description"),
                                               f"https://artifacthub.io/packages/search?ts_query_web={urllib.parse.quote(p['name'])}", "",
                                               f"{p.get('stars', 0)}★") for p in (d.get("packages") or [])]


def aur(q, n):
    d = get(f"https://aur.archlinux.org/rpc/v5/search/{q}")
    return d["resultcount"], [item(r["Name"], r.get("Description"), f"https://aur.archlinux.org/packages/{r['Name']}",
                                   r.get("URL"), f"{r.get('NumVotes', 0)} votes") for r in d["results"][:n]]


def openvsx(q, n):
    d = get(f"https://open-vsx.org/api/-/search?query={q}&size={n}")
    return d["totalSize"], [item(f"{e['namespace']}.{e['name']}", e.get("description"),
                                 f"https://open-vsx.org/extension/{e['namespace']}/{e['name']}", "",
                                 f"{e.get('downloadCount', 0)} dl") for e in d["extensions"]]


def gitlab(q, n):
    d = get(f"https://gitlab.com/api/v4/projects?search={q}&per_page={n}&order_by=star_count&sort=desc")
    return len(d), [item(p["path_with_namespace"], p.get("description"), p["web_url"], "",
                         f"{p.get('star_count', 0)}★ act {p['last_activity_at'][:10]}") for p in d]


def codeberg(q, n):
    d = get(f"https://codeberg.org/api/v1/repos/search?q={q}&limit={n}&sort=stars&order=desc")["data"]
    return len(d), [item(r["full_name"], r.get("description"), r["html_url"], "",
                         f"{r.get('stars_count', 0)}★ upd {r['updated_at'][:10]}") for r in d]


def mcp(q, n):
    # one distinctive word works best; names repeat per version so dedupe. `github` alone matches every io.github.* namespace.
    # q arrives URL-encoded (run_source quotes it); decode before taking the first word (lesson L-2026-11-02-1)
    first = urllib.parse.quote(urllib.parse.unquote(q).split()[0])
    d = get(f"https://registry.modelcontextprotocol.io/v0/servers?search={first}&limit=100")["servers"]
    seen, out = set(), []
    for s in d:
        s = s["server"]
        if s["name"] in seen:
            continue
        seen.add(s["name"])
        out.append(item(s["name"], s.get("description"), (s.get("repository") or {}).get("url", ""), (s.get("repository") or {}).get("url", "")))
    return len(out), out[:n]


def skills(q, n):
    d = get(f"https://skills.sh/api/search?q={q}")["skills"][:n]
    return len(d), [item(f"{s['source']}/{s['skillId']}", s.get("description"), f"https://github.com/{s['source']}",
                         f"https://github.com/{s['source']}") for s in d]


def hf(kind):
    def run(q, n):
        d = get(f"https://huggingface.co/api/{kind}?search={q}&limit={n}")
        return len(d), [item(m["id"], "", f"https://huggingface.co/{'' if kind == 'models' else kind + '/'}{m['id']}", "",
                             f"{m.get('downloads', 0)} dl {m.get('likes', 0)}♥") for m in d]
    return run


def hf_papers(q, n):
    # papers are prior art too; a paper's linked repo goes in `repo`, so --repos hands it to ghverify (lesson L-2026-11-02-4)
    d = get(f"https://huggingface.co/api/papers/search?q={q}")  # no size parameter: relevance order, so take the top n
    return len(d), [item(p["paper"]["id"], p["paper"].get("title"), f"https://huggingface.co/papers/{p['paper']['id']}",
                         p["paper"].get("githubRepo") or "",
                         f"{p['paper'].get('upvotes', 0)} upvotes {(p['paper'].get('publishedAt') or '')[:10]}") for p in d[:n]]


def hn(q, n):
    d = get(f"https://hn.algolia.com/api/v1/search?query={q}&tags=story&hitsPerPage={n}")
    return d["nbHits"], [item(h["title"], "", f"https://news.ycombinator.com/item?id={h['objectID']}",
                              h.get("url") or "", f"{h.get('points', 0)} pts {h['created_at'][:10]}") for h in d["hits"]]


SOURCES = {"npm": npm, "crates": crates, "packagist": packagist, "hex": hex_, "nuget": nuget, "maven": maven,
           "rubygems": rubygems, "hackage": hackage, "dockerhub": dockerhub, "artifacthub": artifacthub, "aur": aur,
           "openvsx": openvsx, "gitlab": gitlab, "codeberg": codeberg, "mcp": mcp, "skills": skills,
           "hf-models": hf("models"), "hf-datasets": hf("datasets"), "hf-spaces": hf("spaces"), "hf-papers": hf_papers, "hn": hn}


def run_source(name, q, n):
    err = "unknown error"
    for attempt in (1, 2):
        try:
            return name, SOURCES[name](urllib.parse.quote(q, safe=""), n), None  # "CI/CD" must not split a path
        except Exception as e:  # network, HTTP, shape changes: report as not reached, never crash the sweep
            err = f"HTTP {e.code}" if isinstance(e, urllib.error.HTTPError) else f"{type(e).__name__}: {str(e)[:50]}"
            if attempt == 1 and isinstance(e, urllib.error.HTTPError) and e.code not in (429, 500, 502, 503, 504):
                break
    return name, None, err


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=4, help="results shown per source")
    p.add_argument("--sources", help="comma list; default all: " + ",".join(SOURCES))
    p.add_argument("--repos", action="store_true", help="print only GitHub owner/repo found in results, one per line")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    names = [s.strip() for s in args.sources.split(",")] if args.sources else list(SOURCES)
    bad = [s for s in names if s not in SOURCES]
    if bad:
        sys.exit(f"unknown source(s): {', '.join(bad)}. Valid: {', '.join(SOURCES)}")

    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(lambda s: run_source(s, args.query, args.limit), names))

    ok = {n: r for n, r, e in results if r}
    failed = {n: e for n, r, e in results if e}

    if args.repos:
        seen = []
        for total, items in ok.values():
            for it in items:
                r = gh_repo(it["repo"]) or gh_repo(it["url"])
                if r and r not in seen:
                    seen.append(r)
        print("\n".join(seen))
        return
    if args.json:
        json.dump({"query": args.query, "results": {n: {"total": t, "items": i} for n, (t, i) in ok.items()}, "not_reached": failed},
                  sys.stdout, indent=1)
        return

    for n in names:
        if n not in ok:
            continue
        total, items = ok[n]
        print(f"\n## {n}: {total} match{'es' if total != 1 else ''}")
        for it in items:
            print(f"  {it['name']}  [{it['extra']}]  {it['desc']}  {it['repo'] or it['url']}")
    print("\nSOURCE LEDGER")
    print("  searched (" + str(len(ok)) + "): " + ", ".join(f"{n}={ok[n][0]}" for n in names if n in ok))
    if failed:
        print("  NOT REACHED (" + str(len(failed)) + "): " + ", ".join(f"{n} ({e})" for n, e in failed.items()))
    print("  not covered: PyPI (web search site:pypi.org), Homebrew, pkg.go.dev")


if __name__ == "__main__":
    main()
