#!/usr/bin/env python3
"""rotless-skill-modernizer: keep the skills YOU author true to the outside world they describe.

A skill you write refers to things that change without telling you: CLIs and their subcommands,
APIs and their response shapes, MCP servers and their tool schemas, repos you cite, packages,
docs pages, limits and flags stated in the text. Each authored skill carries a `keeper.json`
manifest listing them; this engine checks them and reports only what changed.

  keeper.py init  <skill>            draft keeper.json from what SKILL.md + references/ mention
  keeper.py check <skill>... | --all run every check; print + save a digest; exit 1 if action needed
  keeper.py ack   <skill> [ID ...]   accept current upstream values as the new baseline (e.g. a new CLI version you verified)
  keeper.py list                     your skills (folders with keeper.json) and their last result
  keeper.py status                   one offline line for hooks

<skill> is a skill name or a path. Names are looked up in: $SKILL_ROOTS (os.pathsep-separated), the
skills folder this script is installed in (works in any harness: Claude Code, Codex, Antigravity…),
and ./.claude/skills, ./.agents/skills. Only skills with a keeper.json are ever checked: third-party
skills belong to their authors. Never writes to a skill folder except `ack` (keeper.json) and `init`
(keeper.draft.json). State, digests, history: a local git repo, the skill-registry folder next to the
skills folder if one exists there, otherwise ~/.skill-registry (override with $SKILL_REGISTRY).
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

HOME = pathlib.Path.home()
HERE = pathlib.Path(__file__).resolve().parent      # <skills folder>/rotless-skill-modernizer/scripts
SKILLS_ROOT = HERE.parent.parent                     # the folder this harness loads skills from
# where agents keep user-level skills (the same list as rotless-skill-creator's harness.py)
USER_SKILL_DIRS = ["~/.claude/skills", "~/.agents/skills", "~/.codex/skills", "~/.copilot/skills",
                   "~/.gemini/skills", "~/.config/opencode/skills", "~/.cursor/skills"]


def default_registry():
    """State must survive reinstalls: keep an existing skill-registry next to the skills folder, otherwise use
    ~/.skill-registry, never the install folder (a plugin cache is wiped on update). Lesson L-2026-11-02-12;
    rotless-skill-refiner's notes.py uses the same rule."""
    legacy = SKILLS_ROOT.parent / "skill-registry"
    return legacy if legacy.is_dir() else HOME / ".skill-registry"


REGISTRY = pathlib.Path(os.environ.get("SKILL_REGISTRY") or default_registry())
ROOTS = list(dict.fromkeys(
    [pathlib.Path(p).expanduser().resolve() for p in os.environ.get("SKILL_ROOTS", "").split(os.pathsep) if p]
    + [SKILLS_ROOT] + [pathlib.Path(os.path.expanduser(d)).resolve() for d in USER_SKILL_DIRS]
    + [pathlib.Path.cwd() / d / "skills" for d in (".claude", ".agents")]))
UA = "rotless-skill-modernizer/1.0"
PY = sys.executable
STATUS_ORDER = {"FAIL": 0, "CHANGED": 1, "LEARN": 2, "NEW": 3, "GAP": 4, "WARN": 5, "INFO": 6, "OK": 7, "BASELINE": 8}


# ------------------------------------------------------------------ helpers -------------------

def run(cmd, cwd=None, timeout=180):
    # Resolve through PATH first: on Windows, CLIs installed as .CMD/.BAT shims (npm: codex, gemini, npx)
    # can't be started by bare name. Lesson L-2026-11-02-1, checked by scripts/test_cli_shims.py.
    if cmd[0] in ("python", "python3"):  # this interpreter: hosts often have only one of the names (lesson L-2026-11-02-2)
        cmd = [PY] + list(cmd[1:])
    else:
        cmd = [shutil.which(cmd[0]) or cmd[0]] + list(cmd[1:])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return 127, "", f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"


def gh_json(path, *extra):
    code, out, err = run(["gh", "api", path, *extra])
    if code != 0:
        raise RuntimeError((err or out).strip()[-200:] or "gh api failed")
    return json.loads(out)


def http(url, body=None, headers=None, timeout=30):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"User-Agent": UA, "Accept": "application/json, text/event-stream",
                                          **({"Content-Type": "application/json"} if body is not None else {}), **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def ver(s):
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", s or "")
    return tuple(int(x or 0) for x in m.groups()) if m else None


def json_path(data, path):
    """Dotted path with [] wildcards: 'objects[].package.name'. Returns list of values (empty if absent)."""
    vals = [data]
    for part in re.findall(r"[^.\[\]]+|\[\]", path):
        nxt = []
        for v in vals:
            if part == "[]":
                nxt += v if isinstance(v, list) else []
            elif isinstance(v, dict) and part in v:
                nxt.append(v[part])
        vals = nxt
    return vals


def sse_json(text):
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:])
    return json.loads(text)


def find_skill(name, include_synced=False):
    """Locate an installed skill by name. include_synced also searches claude.ai-synced copies
    (<root>/synced/<account>/<name>), newest first; those are other people's skills, read-only."""
    for root in ROOTS:
        if (root / name / "SKILL.md").is_file():
            return (root / name).resolve(), 1
    if include_synced:
        copies = sorted((p for root in ROOTS for p in root.glob(f"synced/*/{name}") if (p / "SKILL.md").is_file()),
                        key=lambda p: (p / "SKILL.md").stat().st_mtime, reverse=True)
        if copies:
            return copies[0].resolve(), len(copies)
    return None, 0


def resolve_skill(name):
    p = pathlib.Path(name).expanduser()
    if (p / "SKILL.md").is_file():
        return p.resolve()
    for root in ROOTS:
        if (root / name / "SKILL.md").is_file():
            return (root / name).resolve()
    sys.exit(f"skill not found: {name} (looked in {', '.join(str(r) for r in ROOTS)})")


def manifest_skills():
    """Every skill folder with a keeper.json. Not proof of authorship: installed skills can ship one."""
    out = []
    for root in ROOTS:
        if root.is_dir():
            out += [d.resolve() for d in sorted(root.iterdir()) if (d / "keeper.json").is_file()]
    return list(dict.fromkeys(out))


def owned_names():
    """Skills the user marked as their own (<registry>/owned.json). Only these get checks, because checks run
    the commands in keeper.json; a third-party skill shipping a keeper.json must not get code execution just by
    being installed (lesson L-2026-11-02-6). First use migrates: skills checked before count as owned."""
    f = REGISTRY / "owned.json"
    names = load_json(f, None)
    if names is None:
        st = REGISTRY / "state"
        names = sorted(p.stem for p in st.glob("*.json")) if st.is_dir() else []
        if names:
            save_json(f, names)
    return set(names)


def mark_owned(name):
    save_json(REGISTRY / "owned.json", sorted(owned_names() | {name}))


def owned_skills():
    owned = owned_names()
    return [d for d in manifest_skills() if d.name in owned]


def load_json(p, default):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_json(p, data):
    p = pathlib.Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def result(cid, status, detail, hint=None, where=None, value=None):
    return {"id": cid, "status": status, "detail": detail, "hint": hint, "where": where, "value": value}


# ------------------------------------------------------------------ checkers ------------------
# Each returns a list of results. `prev` is this check's saved state (or None on first run).

def chk_cli(d, prev, skill_dir):
    name = d["name"]
    cid = d.get("id") or f"cli:{name}"
    if not shutil.which(name):
        return [result(cid, "FAIL", f"`{name}` is not installed", d.get("install"))]
    out = []
    code, so, se = run(shlex.split(d.get("versionCmd") or f"{name} --version"))
    installed = ver(so + se)
    tested = ver(d.get("tested"))
    for sub in d.get("needs", []):
        # many CLIs (gh, claude) exit 0 and print the PARENT's help for an unknown subcommand,
        # so a subcommand exists only if its own help names it ("USAGE gh repo read-dir …")
        c, so, se = run([name, *sub.split(), "--help"])
        if c != 0 or f"{name} {sub}".lower() not in re.sub(r"\s+", " ", so + se).lower():
            out.append(result(f"{cid}:{sub}", "FAIL", f"`{name} {sub}` no longer exists",
                              f"SKILL.md tells readers to use `{name} {sub}`: find the replacement and edit the skill"))
    latest = None
    if d.get("upstream", "").startswith("github:"):
        try:
            rel = gh_json(f"repos/{d['upstream'][7:]}/releases/latest")
            latest = rel["tag_name"]
        except Exception as e:
            out.append(result(cid, "WARN", f"could not read latest release: {e}"))
    lv = ver(latest)
    if latest and lv and tested and lv > tested:
        kind = "major" if lv[0] != tested[0] else "minor" if lv[1] != tested[1] else "patch"
        out.append(result(cid, "CHANGED", f"`{name}` {latest} released ({kind}); this skill was verified on {d['tested']}",
                          f"upgrade, run the skill's checks, then `keeper.py ack <skill> {cid}`", value=latest.lstrip("v")))
    if installed and tested and installed < tested:
        out.append(result(cid, "WARN", f"installed `{name}` {'.'.join(map(str, installed))} is older than the verified {d['tested']}"))
    if not out:
        out.append(result(cid, "OK", f"`{name}` {'.'.join(map(str, installed)) if installed else '?'} installed; "
                                     f"{len(d.get('needs', []))} subcommand(s) present; latest {latest or '?'}"))
    return out


TRIVIAL = re.compile(
    r"^(merge\b|bump\b|chore|build\(deps|deps?[(:]|update (readme|dependencies|deps)|typo|fix typo|docs?[(:]|readme|ci[(:]|"
    r"style[(:]|format|lint|update \S+\.md|auto-?update|\[bot\]|version bump|release v?\d|"
    r"(update|upgrade|bump) \S+ (dependency|dependencies|to v?\d))", re.I)


def headline(c):
    return c["commit"]["message"].splitlines()[0].strip()


def upstream_since(repo, old, new):
    """What changed in a cited repo between the commit we last reviewed and now: (info, error)."""
    try:
        cmp = gh_json(f"repos/{repo}/compare/{old}...{new}")
    except RuntimeError as e:
        return None, str(e)
    commits = cmp.get("commits", [])
    return {"total": cmp.get("total_commits", len(commits)),
            "meaningful": [c for c in commits if not TRIVIAL.search(headline(c))],
            "files": {f["filename"]: f for f in cmp.get("files", [])},
            "renamedFrom": {f["previous_filename"]: f for f in cmp.get("files", []) if f.get("previous_filename")},
            "url": cmp.get("html_url") or f"https://github.com/{repo}/compare/{old[:12]}...{new[:12]}"}, None


def borrowed_file_commits(repo, path, since_iso):
    try:
        cs = gh_json(f"repos/{repo}/commits?path={urllib.parse.quote(path)}&since={since_iso}&per_page=10")
        return [f"{c['commit']['committer']['date'][:10]} {headline(c)[:80]}" for c in cs]
    except RuntimeError:
        return []


def chk_repos(deps, state):
    """Batch GraphQL for all github-repo deps. First sight: baseline (and check that every borrowed
    `files` path exists). Afterwards: renames, archives, deletions, releases, and what changed since
    the commit last reviewed (`seenSha`): meaningful commits and changes to the borrowed files are
    reported as LEARN until acked; trivial-only changes (deps, chore, merge, typo) advance silently."""
    out, new_state = [], {}
    names = [d["repo"] for d in deps]
    for i in range(0, len(names), 25):
        chunk = names[i:i + 25]
        q = "{ " + " ".join(
            f'r{j}: repository(owner: {json.dumps(n.split("/")[0])}, name: {json.dumps(n.split("/")[1])}) '
            f'{{ nameWithOwner isArchived stargazerCount latestRelease {{ tagName url }} '
            f'defaultBranchRef {{ target {{ ... on Commit {{ oid committedDate }} }} }} }}' for j, n in enumerate(chunk)) + " }"
        data, err = gql(q)
        if err:
            out.append(result("repos", "WARN", f"GraphQL failed, these repos were not checked this run: {err[:120]}"))
            continue
        for j, n in enumerate(chunk):
            d = next(x for x in deps if x["repo"] == n)
            cid, role = d.get("id") or f"repo:{n}", d.get("role", "")
            r, prev = data.get(f"r{j}"), state.get(d.get("id") or f"repo:{n}")
            if not r:
                out.append(result(cid, "FAIL", f"{n} no longer exists (deleted or private)",
                                  f"SKILL.md cites it ({role}): remove or replace the reference"))
                continue
            head = ((r.get("defaultBranchRef") or {}).get("target") or {})
            now = {"name": r["nameWithOwner"], "archived": r["isArchived"], "stars": r["stargazerCount"],
                   "release": (r.get("latestRelease") or {}).get("tagName"),
                   "lastCommit": (head.get("committedDate") or "")[:10], "sha": head.get("oid"),
                   "seenSha": (prev or {}).get("seenSha"), "seenDate": (prev or {}).get("seenDate")}
            new_state[cid] = now
            # verify every borrowed path not yet confirmed (new, edited, or failing last time); remember the good ones
            verified = [f for f in (prev or {}).get("files", []) if f in d.get("files", [])]
            for f in d.get("files", []):
                if f in verified:
                    continue
                try:
                    gh_json(f"repos/{now['name']}/contents/{urllib.parse.quote(f)}?ref={now['sha']}")
                    verified.append(f)
                except RuntimeError:
                    out.append(result(f"{cid}:{f}", "FAIL", f"borrowed file `{f}` not found in {now['name']}",
                                      "fix the path in keeper.json (or the file moved before we started watching)"))
            now["files"] = verified
            if now["name"].lower() != n.lower():
                out.append(result(cid, "CHANGED", f"{n} is now {now['name']} (renamed/transferred)",
                                  "update the name in SKILL.md and keeper.json"))
            if now["archived"]:
                out.append(result(cid, "CHANGED" if not (prev or {}).get("archived") else "WARN",
                                  f"{now['name']} is archived (last commit {now['lastCommit']})",
                                  f"SKILL.md cites it ({role}): say it's archived or drop it"))
            if prev is not None and now["release"] and now["release"] != prev.get("release"):
                out.append(result(cid + ":release", "INFO", f"{now['name']} released {now['release']}",
                                  f"skim the notes if the skill borrows from it ({role})"))
            if not now["seenSha"]:  # first sight (or state from before commit tracking): baseline here
                now["seenSha"], now["seenDate"] = now["sha"], head.get("committedDate")
                if not any(x["id"].startswith(cid) for x in out):
                    out.append(result(cid, "BASELINE", f"{now['name']} recorded at {now['sha'][:7]} ({now['stars']}★, "
                                                       f"{len(d.get('files', []))} borrowed file(s) watched)"))
                continue
            if now["sha"] == now["seenSha"]:
                if not any(x["id"].startswith(cid) for x in out):
                    out.append(result(cid, "OK", f"{now['name']}: no new commits since {str(now['seenSha'])[:7]}"))
                continue
            ch, err = upstream_since(now["name"], now["seenSha"], now["sha"])
            if err or ch is None:  # e.g. history rewritten: we can't diff, so re-baseline and say so
                out.append(result(cid, "INFO", f"{now['name']}: can't compare {str(now['seenSha'])[:7]}...{now['sha'][:7]} ({(err or '')[:60]}); baseline reset"))
                now["seenSha"], now["seenDate"] = now["sha"], head.get("committedDate")
                continue
            hits = 0
            for f in d.get("files", []):
                if f in ch["renamedFrom"]:
                    hits += 1
                    out.append(result(f"{cid}:{f}", "CHANGED", f"borrowed file `{f}` was renamed to `{ch['renamedFrom'][f]['filename']}`",
                                      "update the path in keeper.json; re-read it if the skill still mirrors it", value=now["sha"]))
                elif f in ch["files"]:
                    hits += 1
                    fc = ch["files"][f]
                    if fc["status"] == "removed":
                        out.append(result(f"{cid}:{f}", "CHANGED", f"borrowed file `{f}` was removed from {now['name']}",
                                          "drop it from keeper.json; check whether the idea moved elsewhere", value=now["sha"]))
                    else:
                        log = borrowed_file_commits(now["name"], f, now["seenDate"] or "")
                        out.append(result(f"{cid}:{f}", "LEARN", f"borrowed file `{f}` changed (+{fc.get('additions', 0)} −{fc.get('deletions', 0)}): "
                                                                  + ("; ".join(log[:3]) or "see diff"),
                                          f"read the diff; borrow what improved: {ch['url']}", value=now["sha"]))
            if ch["meaningful"]:
                heads = "; ".join(f"{headline(c)[:70]}" for c in ch["meaningful"][:4])
                out.append(result(cid, "LEARN", f"{now['name']}: {len(ch['meaningful'])} meaningful commit(s) since {str(now['seenSha'])[:7]} "
                                                f"({ch['total']} total): {heads}" + (" …" if len(ch["meaningful"]) > 4 else ""),
                                  f"skim for ideas worth borrowing ({role}); diff: {ch['url']}", value=now["sha"]))
            elif not hits:
                out.append(result(cid, "OK", f"{now['name']}: {ch['total']} trivial commit(s) (deps/chore/merge) since "
                                             f"{str(now['seenSha'])[:7]}, auto-acknowledged"))
                now["seenSha"], now["seenDate"] = now["sha"], head.get("committedDate")
    return out, new_state


def transient(status):
    """A server outage or rate limit says nothing about the endpoint moving (lesson L-2026-11-02-8)."""
    return status == 429 or status >= 500


def chk_http(d, prev):
    cid = d.get("id") or f"http:{d['url'][:60]}"
    exp = d.get("expect", {})
    try:
        status, body = http(d["url"], d.get("body"), d.get("headers"))
    except Exception as e:
        return [result(cid, "WARN", f"unreachable: {type(e).__name__}: {str(e)[:80]}", "rerun; if it persists the endpoint moved")]
    if status != exp.get("status", 200) and transient(status):
        return [result(cid, "WARN", f"HTTP {status} from {d['url']}: the server is down or rate-limiting", "rerun later")]
    if status != exp.get("status", 200):
        return [result(cid, "FAIL", f"HTTP {status} (expected {exp.get('status', 200)}) from {d['url']}",
                       "the endpoint changed or moved: find the new one and edit the skill/scripts")]
    missing = []
    if exp.get("jsonPaths"):
        try:
            data = sse_json(body)
            missing = [p for p in exp["jsonPaths"] if not json_path(data, p)]
        except Exception:
            return [result(cid, "FAIL", "response is no longer JSON", "the API changed shape")]
    if missing:
        return [result(cid, "FAIL", f"response lacks {', '.join(missing)}", "the API changed shape: update the parser and the skill text")]
    return [result(cid, "OK", f"HTTP {status}, shape as expected")]


def chk_mcp(d, prev):
    cid = d.get("id") or f"mcp:{d['url']}"
    try:
        status, body = http(d["url"], {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        if status != 200:
            return [result(cid, "WARN" if transient(status) else "FAIL", f"tools/list: HTTP {status} from {d['url']}",
                           "rerun later" if transient(status) else "the server moved or changed: find its new URL")]
        tools = {t["name"]: t for t in sse_json(body)["result"]["tools"]}
    except Exception as e:
        return [result(cid, "WARN", f"tools/list failed: {type(e).__name__}: {str(e)[:80]}", "rerun; flaky servers happen")]
    out = []
    for tool, params in (d.get("expectTools") or {}).items():
        if tool not in tools:
            out.append(result(cid, "FAIL", f"MCP server no longer exposes `{tool}` (has: {', '.join(list(tools)[:8])})",
                              "the skill/scripts call it: update them"))
            continue
        have = set((tools[tool].get("inputSchema") or {}).get("properties", {}))
        gone = [p for p in params if p not in have]
        if gone:
            out.append(result(cid, "FAIL", f"`{tool}` lost parameter(s) {gone}", "update the calls in the skill/scripts"))
    return out or [result(cid, "OK", f"{len(tools)} tools; expected schema present")]


def chk_package(d, prev):
    eco, name = d["ecosystem"], d["name"]
    cid = d.get("id") or f"pkg:{eco}:{name}"
    urls = {"npm": f"https://registry.npmjs.org/{name}/latest", "pypi": f"https://pypi.org/pypi/{name}/json",
            "crates": f"https://crates.io/api/v1/crates/{name}"}
    try:
        status, body = http(urls[eco])
        j = json.loads(body)
        latest = {"npm": lambda: j["version"], "pypi": lambda: j["info"]["version"], "crates": lambda: j["crate"]["max_version"]}[eco]()
    except Exception as e:
        return [result(cid, "WARN", f"could not read {eco} {name}: {str(e)[:80]}")]
    tested = d.get("tested")
    lv, tv = ver(latest), ver(tested)
    if lv and tv and lv > tv:
        return [result(cid, "CHANGED", f"{eco} {name} {latest} released (verified on {tested})",
                       f"re-verify, then `keeper.py ack <skill> {cid}`", value=latest)]
    return [result(cid, "OK", f"{eco} {name} latest {latest}")]


def chk_doc(d, prev):
    cid = d.get("id") or f"doc:{d['url'][:60]}"
    try:
        status, body = http(d["url"], headers={"Accept": "text/html,text/plain,*/*"})
    except Exception as e:
        return [result(cid, "WARN", f"unreachable: {str(e)[:80]}")], prev
    if transient(status):
        return [result(cid, "WARN", f"HTTP {status}: the server is down or rate-limiting", "rerun later")], prev
    if status >= 400:
        return [result(cid, "FAIL", f"HTTP {status}: the doc page moved", "find its new URL; check what the skill summarised from it")], prev
    text = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", body)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    h = hashlib.sha256(text.encode()).hexdigest()[:16]
    if prev is None:
        return [result(cid, "BASELINE", f"content fingerprint recorded ({len(text)} chars)")], {"hash": h, "chars": len(text)}
    if h != prev.get("hash"):
        return [result(cid, "CHANGED", f"doc page changed ({prev.get('chars')} -> {len(text)} chars)",
                       "re-read it and check what the skill says about it; then `ack`", value=h)], prev | {"pending": h, "pendingChars": len(text)}
    return [result(cid, "OK", "doc page unchanged")], prev


def chk_skill(d):
    """Another skill this one relies on (e.g. rotless-github-research for searches, skill-creator for authoring).
    `files` must exist; `mustContain` phrases must still appear in its SKILL.md: our handoff
    instructions name its steps, so a renamed step makes our instructions stale."""
    cid = d.get("id") or f"skill:{d['name']}"
    base, copies = find_skill(d["name"], include_synced=True)
    if not base:
        return [result(cid, "FAIL", f"skill `{d['name']}` is not installed", d.get("install"))]
    missing = [f for f in d.get("files", []) if not (base / f).is_file()]
    text = (base / "SKILL.md").read_text(encoding="utf-8", errors="replace").lower()
    gone = [p for p in d.get("mustContain", []) if p.lower() not in text]
    where = f" ({base.parent.name[-8:]}/{base.name}, newest of {copies} synced copies)" if copies > 1 else ""
    out = []
    if missing:
        out.append(result(cid, "FAIL", f"skill `{d['name']}` lacks {', '.join(missing)}{where}", "it changed: update how this skill calls it"))
    if gone:
        out.append(result(cid, "CHANGED", f"skill `{d['name']}` no longer mentions {gone}{where}",
                          "our instructions refer to those steps: re-read it and update the handoff text"))
    return out or [result(cid, "OK", f"skill `{d['name']}` present{where}"
                                     + (f"; {len(d.get('mustContain', []))} handoff phrase(s) still there" if d.get("mustContain") else ""))]


def chk_command(d, skill_dir):
    """Only for skills you own: run their own self-test. Understands selftest-style JSON
    ({"results":[{"check","status","detail"}]}) or plain exit codes."""
    cid = d.get("id") or f"cmd:{d['run'][:40]}"
    # substitute after splitting: shlex would eat Windows backslashes and split paths with spaces (lesson L-2026-11-02-3)
    cmd = [tok.replace("{skill}", str(skill_dir)) for tok in shlex.split(d["run"])]
    code, so, se = run(cmd, cwd=skill_dir, timeout=d.get("timeout", 300))
    try:
        res = json.loads(so)["results"]
    except Exception:
        return [result(cid, "OK" if code == 0 else "FAIL", f"exit {code}" + (f": {(se or so).strip()[-160:]}" if code else ""))]
    bad = [r for r in res if r["status"] not in ("PASS", "OK")]
    if not bad:
        return [result(cid, "OK", f"all {len(res)} self-checks pass")]
    return [result(f"{cid}:{r['check']}", {"FAIL": "FAIL", "CHANGED": "CHANGED"}.get(r["status"], "WARN"), r["detail"],
                   "a documented behaviour changed: fix the rule in SKILL.md" if r["status"] == "CHANGED" else None) for r in bad]


def chk_search(d, prev):
    """Landscape: saved repo searches via the rotless-github-research skill; reports repos not seen before."""
    cid = d.get("id") or f"search:{d['name']}"
    gr, _ = find_skill("rotless-github-research")
    sweep = gr / "scripts" / "ghsweep.py" if gr else None
    if not sweep or not sweep.is_file():
        return [result(cid, "WARN", "needs the rotless-github-research skill (ghsweep.py) for landscape searches")], prev
    cutoff = (dt.date.today() - dt.timedelta(days=d.get("windowDays", 180))).isoformat()
    cmd = [PY, str(sweep), "--json", "--limit", "50", "--pushed", f">{cutoff}", "--min-stars", str(d.get("minStars", 0))]
    if d.get("must"):
        cmd += ["--must", d["must"]]
    if d.get("exclude"):
        cmd += ["--exclude", d["exclude"]]
    code, so, se = run(cmd + d["queries"])
    try:
        rows = json.loads(so)
    except json.JSONDecodeError:
        return [result(cid, "WARN", f"search failed: {se.strip()[:120]}")], prev
    names = {r["fullName"] for r in rows}
    if prev is None:
        return [result(cid, "BASELINE", f"{len(names)} repos recorded as known")], {"seen": sorted(names)}
    new = sorted((r for r in rows if r["fullName"] not in set(prev["seen"])), key=lambda r: (len(r["matched"]), r["stars"]), reverse=True)
    st = {"seen": sorted(names | set(prev["seen"]))}
    if not new:
        return [result(cid, "OK", "no new repos")], st
    lines = "; ".join(f"{r['fullName']} ({r['stars']}★) {r['description'][:60]}" for r in new[:8])
    return [result(cid, "NEW", f"{len(new)} new repo(s): {lines}" + (" …" if len(new) > 8 else ""),
                   "look at them with the rotless-github-research skill; borrow ideas or cite them, then they stay 'seen'")], st


def skill_texts(skill_dir):
    files = [skill_dir / "SKILL.md"] + (sorted((skill_dir / "references").glob("*.md")) if (skill_dir / "references").is_dir() else [])
    return [(f.relative_to(skill_dir).as_posix(), f.read_text(encoding="utf-8", errors="replace").splitlines()) for f in files]


def norm_text(s):
    return re.sub(r"\s+", " ", re.sub(r"[*`]", "", s.lower()))


def quote_where(quote, texts):
    """file:line of a claim's quote; quote and text are normalised the same way (lesson L-2026-11-02-5)."""
    q = norm_text(quote)
    return next((f"{rel}:{i + 1}" for rel, lines in texts for i, ln in enumerate(lines) if q in norm_text(ln)), None)


def chk_claim(c, texts, skill_dir):
    cid = f"claim:{c['id']}"
    where = quote_where(c["quote"], texts)
    if not where:  # the text was edited away: the claim is stale, whatever its check says
        return [result(cid, "WARN", f"quoted text no longer in the skill: “{c['quote']}”",
                       "the skill was edited: update the claim's quote (or delete the claim) in keeper.json")]
    out = []
    chk = c.get("check") or {}
    try:
        if "gh" in chk:
            vals = json_path(gh_json(chk["gh"]), chk["jsonPath"])
        elif "http" in chk:
            status, body = http(chk["http"])
            if transient(status):  # an outage proves nothing about the claim (lesson L-2026-11-02-11)
                return out + [result(cid, "WARN", f"HTTP {status} from {chk['http']}: the server is down or rate-limiting", "rerun later", where)]
            vals = json_path(sse_json(body), chk["jsonPath"])
        elif "run" in chk:
            code, so, se = run(shlex.split(chk["run"]), cwd=skill_dir)
            vals = [code] if "exit" in chk else re.findall(chk.get("regex", ".+"), so + se)
        else:
            return out + [result(cid, "WARN", "claim has no check yet (draft)", "add a check or delete the claim", where)]
    except Exception as e:
        return out + [result(cid, "WARN", f"check could not run: {str(e)[:100]}", None, where)]
    v = vals[0] if vals else None
    if "equals" in chk:
        ok = v == chk["equals"]
    elif "exit" in chk:
        ok = v == chk["exit"]
    elif "min" in chk:
        ok = v is not None and v >= chk["min"]
    else:
        ok = bool(vals)
    if ok:
        return out + [result(cid, "OK", f"holds: “{c['quote']}”", None, where)]
    return out + [result(cid, "CHANGED", f"no longer true: “{c['quote']}” (now: {v!r})",
                         "edit that line of SKILL.md, then update the claim's expected value", where, v)]


# ------------------------------------------------------------------ check command -------------

def check_skill(skill_dir):
    man = load_json(skill_dir / "keeper.json", {})
    name = skill_dir.name
    state_file = REGISTRY / "state" / f"{name}.json"
    state = load_json(state_file, {})
    results = []
    deps = man.get("deps", [])
    texts = skill_texts(skill_dir)
    for d in deps:
        t = d.get("type")
        try:
            if t == "cli":
                results += chk_cli(d, state.get(d.get("id") or f"cli:{d['name']}"), skill_dir)
            elif t == "http":
                results += chk_http(d, None)
            elif t == "mcp":
                results += chk_mcp(d, None)
            elif t == "package":
                results += chk_package(d, None)
            elif t == "doc":
                cid = d.get("id") or f"doc:{d['url'][:60]}"
                r, st = chk_doc(d, state.get(cid))
                results += r
                if st is not None:
                    state[cid] = st
            elif t == "command":
                results += chk_command(d, skill_dir)
            elif t == "skill":
                results += chk_skill(d)
        except Exception as e:  # one broken check never hides the others
            results.append(result(d.get("id") or t, "WARN", f"check crashed: {type(e).__name__}: {str(e)[:100]}"))
    repo_deps = [d for d in deps if d.get("type") == "github-repo"]
    if repo_deps:
        r, st = chk_repos(repo_deps, state)
        results += r
        state.update(st)
    for s in (man.get("landscape") or {}).get("searches", []):
        cid = s.get("id") or f"search:{s['name']}"
        r, st = chk_search(s, state.get(cid))
        results += r
        if st is not None:
            state[cid] = st
    for c in man.get("claims", []):
        results += chk_claim(c, texts, skill_dir)
    try:
        results += coverage(man, extract(skill_dir)[0])
    except Exception as e:
        results.append(result("coverage", "WARN", f"coverage scan crashed: {type(e).__name__}: {str(e)[:100]}"))
    for r in results:  # remember values that `ack` can accept
        if r["value"] is not None and r["status"] in ("CHANGED", "INFO", "LEARN"):
            state.setdefault("_pending", {})[r["id"]] = r["value"]
    state["_lastRun"] = dt.datetime.now().isoformat(timespec="seconds")
    state["_lastSummary"] = {s: sum(r["status"] == s for r in results) for s in STATUS_ORDER}
    save_json(state_file, state)
    return man, results


def render(name, man, results):
    v = man.get("verified") or {}
    L = [f"# {name}: keeper check {dt.date.today().isoformat()}",
         f"_last verified by its author: {v.get('date', 'never')}{(' · ' + v['note']) if v.get('note') else ''}_", ""]
    groups = [("Fix the skill", ("FAIL", "CHANGED")), ("Worth learning from (upstream commits since last review)", ("LEARN",)),
              ("Not tracked in keeper.json (update the manifest)", ("GAP",)),
              ("New in the landscape", ("NEW",)), ("Worth a look", ("WARN", "INFO")),
              ("Baseline recorded (first run)", ("BASELINE",)), ("OK", ("OK",))]
    for title, sts in groups:
        rs = sorted((r for r in results if r["status"] in sts), key=lambda r: STATUS_ORDER[r["status"]])
        if not rs:
            continue
        L.append(f"## {title} ({len(rs)})")
        for r in rs:
            extra = "".join(f" — {x}" for x in (r["where"], r["hint"]) if x)
            L.append(f"- {r['status']} `{r['id']}`: {r['detail']}{extra}" if title != "OK" else f"- `{r['id']}`: {r['detail']}")
        L.append("")
    return "\n".join(L)


def commit_registry(msg):
    if not shutil.which("git"):
        return
    git = ["git", "-C", str(REGISTRY), "-c", "user.name=rotless-skill-modernizer", "-c", "user.email=rotless-skill-modernizer@localhost"]
    if not (REGISTRY / ".git").exists():
        run(git + ["init", "-q"])
    run(git + ["add", "-A"])
    run(git + ["commit", "-q", "-m", msg])


def cmd_check(args):
    if args.all:
        dirs = owned_skills()
        foreign = [d.name for d in manifest_skills() if d.name not in owned_names()]
        if foreign:
            print(f"skipped, not marked as yours: {', '.join(foreign)} (their checks would run the commands in their "
                  "keeper.json; if you wrote one, run `keeper.py own <name>`)")
    else:
        dirs = [resolve_skill(s) for s in args.skills]
        for d in dirs:
            if (d / "keeper.json").is_file() and d.name not in owned_names():
                sys.exit(f"{d.name} is not marked as yours, and checking it runs the commands in its keeper.json. "
                         f"If you wrote it: keeper.py own {d.name}")
    if not dirs:
        sys.exit("no skills with keeper.json found (run `keeper.py init <skill>` first)")
    needs_action = False
    for d in dirs:
        if not (d / "keeper.json").is_file():
            print(f"{d.name}: no keeper.json; skipping (run `keeper.py init {d.name}`)")
            continue
        man, results = check_skill(d)
        report = render(d.name, man, results)
        if open_notes(d.name):
            report += (f"\n\n## Field notes from use ({open_notes(d.name)} open)\nNot drift: lessons logged while the skill was used. "
                       f"Review them with rotless-skill-refiner (`notes.py list {d.name}`, then its retro).")
        print(report)
        (REGISTRY / "digests").mkdir(parents=True, exist_ok=True)
        (REGISTRY / "digests" / f"{d.name}-{dt.date.today().isoformat()}.md").write_text(report + "\n", encoding="utf-8")
        s = {k: sum(r["status"] == k for r in results) for k in STATUS_ORDER}
        needs_action |= bool(s["FAIL"] or s["CHANGED"])
        commit_registry(f"check {d.name}: " + ", ".join(f"{v} {k}" for k, v in s.items() if v))
    sys.exit(1 if needs_action else 0)


# ------------------------------------------------------------------ ack ------------------------

def cmd_ack(args):
    d = resolve_skill(args.skill)
    man = load_json(d / "keeper.json", {})
    if not man:
        sys.exit(f"{d.name} has no keeper.json")
    state_file = REGISTRY / "state" / f"{d.name}.json"
    state = load_json(state_file, {})
    pending = state.get("_pending", {})
    ids = args.ids or list(pending)
    done = []
    for cid in ids:
        val = pending.get(cid)
        base = cid.split(":")[0] + ":" + cid.split(":")[1] if cid.count(":") >= 1 else cid
        for dep in man.get("deps", []):
            did = dep.get("id") or {"cli": f"cli:{dep.get('name')}", "package": f"pkg:{dep.get('ecosystem')}:{dep.get('name')}"}.get(dep.get("type"))
            if did in (cid, base) and val is not None and dep.get("type") in ("cli", "package"):
                dep["tested"] = str(val)
                done.append(f"{did}: tested -> {val}")
        if cid.startswith("doc:") and cid in state and state[cid].get("pending"):
            state[cid] = {"hash": state[cid]["pending"], "chars": state[cid].get("pendingChars")}
            done.append(f"{cid}: new content accepted")
        key = cid if cid in state else base  # file-level ids ("repo:o/r:path") ack their repo
        if val is not None and isinstance(state.get(key), dict) and "seenSha" in state[key]:
            st = state[key]
            st["seenSha"] = val
            st["seenDate"] = f"{st.get('lastCommit') or dt.date.today().isoformat()}T00:00:00Z"
            # one ack covers the repo and all its borrowed files: drop their other pending entries too
            for other in [k for k in pending if k == key or k.startswith(key + ":")]:
                if other != cid:
                    pending.pop(other, None)
            done.append(f"{key}: upstream changes reviewed up to {str(val)[:7]}")
        pending.pop(cid, None)
    if args.note or done:
        man["verified"] = {"date": dt.date.today().isoformat(), "note": args.note or "; ".join(done)}
    save_json(d / "keeper.json", man)
    save_json(state_file, state)
    commit_registry(f"ack {d.name}: {'; '.join(done) or args.note or 'noted'}")
    if done:
        print("\n".join(done))
    print(f"verified stamp: {man.get('verified')}" if (args.note or done) else "nothing pending to accept")


# ------------------------------------------------------------------ text scanning (init + coverage)

URL = re.compile(r"https?://[^\s)`'\"<>\]|{]+(?![<{])")
INLINE_SUB = re.compile(r"`(gh|claude|npx)\s+([a-z][\w-]*)(?:\s+([a-z][\w-]*))?")
REPO = re.compile(r"`([A-Za-z0-9][\w.-]*/[\w.-]+)`")
VERSIONED = re.compile(r"\b(gh|git|node|python|npm|claude)\s+v?(\d+\.\d+(?:\.\d+)?)\b", re.I)
LIMIT = re.compile(r"(?:[\w/-]+[ \t]+){0,4}[(\"“]?\d+\s*(?:/|per\s)(?:min|minute|hour|hr|day|s)\b", re.I)
# Fenced blocks that aren't shell: data and templates, or diagrams. Blanked before parsing, line numbers kept
# (lesson L-2026-11-02-9: a markdown table became CLIs `repo`, `last`, `license`).
FENCED = re.compile(r"^[ \t]*```[ \t]*([\w+-]*)[^\n]*\n(.*?)^[ \t]*```", re.S | re.M)
NON_SHELL = {"json", "jsonc", "yaml", "yml", "toml", "markdown", "md", "text", "txt", "python", "py", "diff", "html",
             "xml", "csv", "js", "javascript", "ts", "typescript"}
DIAGRAM = re.compile(r"[\u2500-\u257f\u25b2-\u25c4\u2190-\u21ff]")  # box drawing, triangles, arrows
PIPE_SPLIT = re.compile(r"\s*(?:\|\||&&|;)\s*|\s+\|\s+")  # a lone | needs spaces: `--kind a|b` is one argument


def strip_examples(text):
    def blank(m):
        skip = m.group(1).lower() in NON_SHELL or DIAGRAM.search(m.group(2))
        return "\n" * m.group(0).count("\n") if skip else m.group(0)
    return FENCED.sub(blank, text)
NOT_CLI = {"cd", "echo", "export", "for", "do", "done", "if", "then", "fi", "set", "cat", "ls", "grep", "sed", "awk", "head",
           "tail", "cut", "sort", "uniq", "tr", "xargs", "rm", "mkdir", "cp", "mv", "true", "false", "test", "while", "time", "sleep"}
SUBCMD_TOOLS = ("gh", "claude", "npx", "git", "docker", "kubectl")


def subcommand(toks):
    """Leading subcommand words: `gh search commits foo` -> 'search commits'; `gh api -X GET …` -> 'api';
    `gh api rate_limit` -> 'api' (paths/args stop the scan)."""
    out = []
    for t in toks[:2]:
        if not re.fullmatch(r"[a-z][a-z-]*", t):
            break
        out.append(t)
    return " ".join(out)


def clean_claim(s):
    s = re.sub(r"[*`]", "", s)
    parts = [p for p in re.split(r"[:|]", s) if re.search(r"\d+\s*(?:/|per\s)", p)]  # keep the piece holding the number
    return re.sub(r"\s+", " ", parts[0] if parts else s).strip(" -()\"'“”")


def extract(skill_dir):
    """Every outside reference in SKILL.md + references/*.md with its first location (file:line).
    JSON/YAML blocks are skipped: they're examples, not dependencies."""
    files = [skill_dir / "SKILL.md"] + (sorted((skill_dir / "references").glob("*.md")) if (skill_dir / "references").is_dir() else [])
    ref = {"cli": {}, "sub": {}, "url": {}, "repo": {}, "version": {}, "limit": {}}
    count = {}
    for f in files:
        rel = f.relative_to(skill_dir).as_posix()
        text = strip_examples(f.read_text(encoding="utf-8", errors="replace"))
        in_code = False
        for i, line in enumerate(text.splitlines(), 1):
            loc = f"{rel}:{i}"
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                cmd = re.sub(r"^\s*(\$|>)\s*", "", line).strip()
                cmd = re.sub(r"(^|\s)#.*$", "", cmd).strip()  # shell comments are prose
                if cmd and not cmd.startswith("|") and "=" not in cmd.split(" ")[0]:
                    for seg in PIPE_SPLIT.split(cmd):
                        toks = seg.split()
                        tool = toks[0].strip("(") if toks else ""
                        if not tool or tool in NOT_CLI or tool.startswith("-") or not re.fullmatch(r"[A-Za-z][\w.-]*", tool):
                            continue  # option continuation lines (`--jq …`) are not commands
                        count[tool] = count.get(tool, 0) + 1
                        ref["cli"].setdefault(tool, loc)
                        sub = subcommand(toks[1:]) if tool in SUBCMD_TOOLS else ""
                        if sub:
                            ref["sub"].setdefault((tool, sub), loc)
            for m in INLINE_SUB.finditer(line):  # `gh search code` written inline
                sub = subcommand([x for x in m.groups()[1:] if x])
                count[m.group(1)] = count.get(m.group(1), 0) + 1
                ref["cli"].setdefault(m.group(1), loc)
                if sub:
                    ref["sub"].setdefault((m.group(1), sub), loc)
            for u in URL.findall(line):
                u = u.rstrip(".,:;")
                if "example" in u or "…" in u or re.search(r"github\.com/(o|owner|o2)/", u):
                    continue  # placeholders; truncated templates (`…/<name>/…`) are cut by URL's lookahead
                m = re.match(r"https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/|$)", u)
                if m and u.count("/") <= 4:
                    ref["repo"].setdefault(f"{m.group(1)}/{m.group(2)}", loc)
                else:
                    ref["url"].setdefault(u, loc)
            for r in REPO.findall(line):
                if not re.search(r"\.(py|md|json|sh|js|ts|txt|yml|yaml)$|^(o|owner|o2)/", r, re.I):
                    ref["repo"].setdefault(r, loc)
            for m in VERSIONED.finditer(line):
                ref["version"].setdefault(m.group(1).lower(), (m.group(2), loc))
            for x in LIMIT.findall(re.sub(r'"[^"]*"|“[^”]*”', " ", line)):  # quoted text is an example, not a claim
                c = clean_claim(x)
                if c:
                    ref["limit"].setdefault(c, loc)
    return ref, count


def existing_repos(names):
    """Which owner/name strings are real repos (drops folder paths and prose like `requires.bins/env`)."""
    real, uniq = set(), sorted(set(names))
    if not uniq or not shutil.which("gh"):
        return set(uniq)
    for i in range(0, len(uniq), 25):
        chunk = uniq[i:i + 25]
        q = "{ " + " ".join(f'r{j}: repository(owner: {json.dumps(n.split("/")[0])}, name: {json.dumps(n.split("/")[1])}) {{ nameWithOwner }}'
                            for j, n in enumerate(chunk)) + " }"
        data, err = gql(q)
        real |= set(chunk) if err else {chunk[j] for j in range(len(chunk)) if data.get(f"r{j}")}
    return real


def gql(query):
    """gh GraphQL -> (data, error). NOT_FOUND repos still come back as data; any other error (rate limit, token,
    outage) means the batch was not checked, so callers must not read missing repos as deleted (lesson L-2026-11-02-4)."""
    _, so, se = run(["gh", "api", "graphql", "-f", f"query={query}"])
    try:
        out = json.loads(so)
    except json.JSONDecodeError:
        return {}, (se or so).strip() or "no output"
    fatal = [e.get("message", "") for e in out.get("errors") or [] if e.get("type") != "NOT_FOUND"]
    return out.get("data") or {}, "; ".join(fatal)


def norm_url(u):
    p = urllib.parse.urlsplit(u)
    return (p.netloc.lower() + p.path).rstrip("/")


def coverage(man, ref, offline=False):
    """The safety net: references in the skill's text that keeper.json doesn't track. A manifest written
    at creation time falls behind the first time someone edits the skill; this catches that."""
    ign = man.get("ignore", [])

    def ignored(key):
        return any(key == g or key.startswith(g + " ") or (g.endswith("*") and key.startswith(g[:-1])) for g in ign)

    deps = man.get("deps", [])
    clis = {d["name"]: d for d in deps if d.get("type") == "cli"}
    out = []
    for tool, loc in ref["cli"].items():
        if tool not in clis and not ignored(tool) and shutil.which(tool):
            out.append(result(f"gap:cli:{tool}", "GAP", f"the text uses `{tool}` but keeper.json doesn't track it",
                              'add a "cli" dep, or list it under "ignore"', loc))
    for (tool, sub), loc in ref["sub"].items():
        if tool not in clis or ignored(f"{tool} {sub}"):
            continue  # an untracked tool is reported once, above
        needs = clis[tool].get("needs", [])
        if not any(n == sub or n.startswith(sub + " ") or sub.startswith(n + " ") for n in needs):
            out.append(result(f"gap:sub:{tool} {sub}", "GAP", f"the text uses `{tool} {sub}` but it isn't in the `{tool}` dep's needs",
                              f'add "{sub}" to needs (or ignore "{tool} {sub}")', loc))
    tracked = [norm_url(d["url"]) for d in deps if d.get("url")]
    for u, loc in ref["url"].items():
        n = norm_url(u)
        if not ignored(u) and not any(n == t or t.startswith(n) or n.startswith(t) for t in tracked):
            out.append(result(f"gap:url:{n[:60]}", "GAP", f"the text references {u} but no dep checks it",
                              'add an "http" / "mcp" / "doc" dep, or ignore it', loc))
    tracked_repos = {d["repo"].lower() for d in deps if d.get("type") == "github-repo"}
    candidates = [r for r in ref["repo"] if r.lower() not in tracked_repos and not ignored(r)]
    for r in ([] if offline else sorted(existing_repos(candidates))):  # telling real repos from prose needs the network
        out.append(result(f"gap:repo:{r}", "GAP", f"the text cites {r} but keeper.json doesn't watch it",
                          'add a "github-repo" dep with its role', ref["repo"][r]))
    for tool, (v, loc) in ref["version"].items():
        tested = (clis.get(tool) or {}).get("tested")
        said, have = [int(x) for x in re.findall(r"\d+", v)], [int(x) for x in re.findall(r"\d+", tested or "")]
        if tested and have[:len(said)] != said:
            out.append(result(f"gap:version:{tool}", "GAP", f"the text says {tool} {v}, keeper.json says it was verified on {tested}",
                              "one of them is stale: update the text or `tested`", loc))
    quotes = [norm_text(c["quote"]) for c in man.get("claims", [])]  # same normalisation as chk_claim (L-2026-11-02-10)
    for phrase, loc in ref["limit"].items():
        p = norm_text(phrase)
        if not ignored(phrase) and not any(q in p or p in q for q in quotes):
            out.append(result(f"gap:claim:{phrase[:40]}", "GAP", f"the text states a limit no claim checks: “{phrase}”",
                              "add a claim with a check, or ignore it", loc))
    return out


# ------------------------------------------------------------------ init ----------------------

def read_prior_art(skill_dir_or_file):
    """A prior-art.md in the shape rotless-skill-modernizer owns (filled by the rotless-github-research skill): `## Repos`
    table (repo, role, …, take) and `## Queries` bullets. Backticked paths in the take column
    (e.g. `src/x/sources.ts`) are the files we borrowed from. Returns None if the file is absent."""
    p = pathlib.Path(skill_dir_or_file)
    p = p if p.suffix == ".md" else p / "references" / "prior-art.md"
    if not p.is_file():
        return None
    text = p.read_text(encoding="utf-8", errors="replace")
    repos, queries, files, section = [], [], {}, ""
    for line in text.splitlines():
        h = re.match(r"^#{2,3}\s+(.*)", line)
        if h:
            section = h.group(1).strip().lower()
            continue
        if section.startswith("repos") and line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            m = re.search(r"([A-Za-z0-9][\w.-]*/[\w.-]+)", re.sub(r"[`\[\]]", "", cells[0]))
            if m and not re.fullmatch(r"[-: ]+", cells[0]):
                repos.append((m.group(1), cells[1] if len(cells) > 1 and cells[1] else "prior art"))
                take = cells[-1] if len(cells) > 2 else ""
                paths = [x for x in re.findall(r"`([^`\s]+)`", take)
                         if not x.startswith(("http", "-")) and re.search(r"\.[A-Za-z0-9]{1,6}$", x)
                         and ("/" in x or x.endswith(".md"))]
                if paths:
                    files[m.group(1)] = sorted(set(paths))
        elif section.startswith("queries"):
            m = re.match(r"^\s*[-*]\s+`?([^`]+?)`?\s*$", line)
            if m:
                queries.append(m.group(1).strip())
    v = re.search(r"verdict:\s*\**([^_*\n]+)", text, re.I)
    d = re.search(r"_date:\s*(\d{4}-\d{2}-\d{2})", text)
    return {"repos": repos, "queries": queries, "files": files, "verdict": v.group(1).strip() if v else None,
            "date": d.group(1) if d else None}


def cmd_init(args):
    d = resolve_skill(args.skill)
    ref, count = extract(d)
    prior = read_prior_art(d)
    roles = {r: role for r, role in (prior or {}).get("repos", [])}
    real = existing_repos(list(ref["repo"]) + list(roles))
    needs = {}
    for (tool, sub) in ref["sub"]:
        needs.setdefault(tool, set()).add(sub)
    deps = []
    for tool in sorted(ref["cli"], key=lambda t: -count.get(t, 0)):
        if not shutil.which(tool):
            continue  # words in diagrams/prose aren't commands; a real dependency that's missing shows up on `check`
        dep = {"type": "cli", "name": tool, "_seen": count.get(tool, 0), "_where": ref["cli"][tool]}
        if tool in ref["version"]:
            dep["tested"] = ref["version"][tool][0]
        if tool in needs:
            dep["needs"] = sorted(needs[tool])
        if tool == "gh":
            dep["upstream"] = "github:cli/cli"
        deps.append(dep)
    for u, loc in sorted(ref["url"].items()):
        # `doc` = a documentation page whose *content* the skill summarises (fingerprinted, CHANGED when edited).
        # Everything else is an endpoint the skill fetches: check it's alive (data pages change daily by design).
        is_doc = re.search(r"(^https?://(docs?|developer|learn|help)\.)|/docs?/|/documentation|/manual|/reference|/spec|\.md$", u, re.I)
        kind = "mcp" if "mcp" in u.lower() else ("doc" if is_doc else "http")
        deps.append({"type": kind, "url": u, "_where": loc} | ({"expect": {"status": 200}} if kind == "http" else {}))
    borrowed = (prior or {}).get("files", {})
    deps += [{"type": "github-repo", "repo": r, "role": roles.get(r, "cited"),
              **({"files": borrowed[r]} if r in borrowed else {}),
              "_where": ref["repo"].get(r, "references/prior-art.md")} for r in sorted(real)]
    claims = [{"id": f"limit-{i + 1}", "quote": q, "check": None, "_where": loc} for i, (q, loc) in enumerate(sorted(ref["limit"].items()))][:10]
    searches = [{"name": f"{d.name}-space", "queries": prior["queries"][:8], "windowDays": 180, "minStars": 1,
                 "_from": "references/prior-art.md"}] if prior and prior["queries"] else []
    draft = {"_draft": f"generated {dt.date.today().isoformat()} by keeper.py init: curate it (delete noise, add expectations, "
                       "give claims a check, add an \"ignore\" list for references you deliberately don't track), then rename to keeper.json",
             "skill": d.name, "verified": {"date": None, "note": ""}, "deps": deps, "claims": claims, "ignore": [],
             "landscape": {"searches": searches}}
    if prior and prior.get("verdict"):
        draft["priorArt"] = {"verdict": prior["verdict"], "file": "references/prior-art.md"}
    target = d / "keeper.draft.json"  # always a draft: the author curates, then renames
    save_json(target, draft)
    mark_owned(d.name)  # running init on a skill is authoring it
    print(f"wrote {target}\n  {sum(x['type'] == 'cli' for x in deps)} CLIs, {sum(x['type'] == 'github-repo' for x in deps)} repos, "
          f"{sum(x['type'] in ('http', 'mcp') for x in deps)} endpoints, {sum(x['type'] == 'doc' for x in deps)} docs, {len(claims)} candidate claims")
    if prior:
        print(f"  imported from references/prior-art.md: {len(roles)} repo(s) with roles, {len(prior['queries'])} landscape quer(ies)"
              + (f"; verdict: {prior['verdict']}" if prior.get("verdict") else ""))
    dropped = sorted((set(ref["repo"]) | set(roles)) - real)
    if dropped:
        print(f"  dropped {len(dropped)} 'owner/name' strings that aren't real repos: {', '.join(dropped[:8])}")


# ------------------------------------------------------------------ own / lint ----------------

def cmd_own(args):
    d = resolve_skill(args.skill)
    mark_owned(d.name)
    print(f"{d.name} is marked as yours: `check` will run the commands in its keeper.json")


def cmd_lint(args):
    """Offline gate (CI): manifests and eval sets parse, every claim quote is still in the text, and the text
    references nothing keeper.json misses. Runs no code from the skill and no network calls, so it is safe on
    any skill (lesson L-2026-11-02-7)."""
    dirs = [resolve_skill(s) for s in args.skills] if args.skills else manifest_skills()
    total = 0
    for d in dirs:
        errs, man = [], None
        try:
            man = json.loads((d / "keeper.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            errs.append("no keeper.json")
        except json.JSONDecodeError as e:
            errs.append(f"keeper.json: {e}")
        for f in sorted((d / "evals").rglob("*.json")) if (d / "evals").is_dir() else []:
            try:
                json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errs.append(f"{f.relative_to(d).as_posix()}: {e}")
        if man is not None:
            texts = skill_texts(d)
            errs += [f"claim {c['id']}: quote not in the text: {c['quote']!r}"
                     for c in man.get("claims", []) if not quote_where(c["quote"], texts)]
            errs += [f"{r['status']} {r['id']}: {r['detail']}" + (f" ({r['where']})" if r.get("where") else "")
                     for r in coverage(man, extract(d)[0], offline=True)]
        print(f"{d.name}: " + ("ok" if not errs else f"{len(errs)} problem(s)"))
        for e in errs:
            print(f"  - {e}")
        total += len(errs)
    sys.exit(1 if total else 0)


# ------------------------------------------------------------------ list / status -------------

def open_notes(name):
    """Open field notes rotless-skill-refiner logged for this skill (lessons from use, not drift)."""
    f = REGISTRY / "notes" / f"{name}.jsonl"
    if not f.is_file():
        return 0
    return sum(1 for line in f.read_text(encoding="utf-8").splitlines() if line.strip() and json.loads(line).get("status") == "open")


def cmd_list(_):
    dirs = owned_skills()
    if not dirs:
        print("no authored skills with keeper.json yet. Start with: keeper.py init <skill>")
    for d in dirs:
        st = load_json(REGISTRY / "state" / f"{d.name}.json", {})
        s = st.get("_lastSummary") or {}
        v = (load_json(d / "keeper.json", {}).get("verified") or {}).get("date")
        print(f"{d.name:22} last check {st.get('_lastRun', 'never')[:16]:16}  verified {v or 'never':10}  "
              + ", ".join([f"{n} {k}" for k, n in s.items() if n and k not in ("OK", "BASELINE")]
                          + ([f"{open_notes(d.name)} open field notes"] if open_notes(d.name) else [])))


PRIOR_ART_STALE_DAYS = 90


def cmd_prior_art_diff(args):
    """Compare the skill's references/prior-art.md with a freshly researched one (from `refresh`)."""
    d = resolve_skill(args.skill)
    old, new = read_prior_art(d), read_prior_art(pathlib.Path(args.new_file))
    if not old or not new:
        sys.exit(f"need both files: {d / 'references' / 'prior-art.md'} and {args.new_file}")
    o, n = dict(old["repos"]), dict(new["repos"])
    print(f"# prior-art diff: {d.name}  ({old.get('date') or '?'} -> {new.get('date') or '?'})\n")
    print(f"verdict: {'unchanged' if old['verdict'] == new['verdict'] else 'CHANGED'}")
    if old["verdict"] != new["verdict"]:
        print(f"  was: {old['verdict']}\n  now: {new['verdict']}")
    added, gone = sorted(set(n) - set(o)), sorted(set(o) - set(n))
    moved = sorted(r for r in set(o) & set(n) if o[r] != n[r])
    print(f"\nnew repos ({len(added)}):" + "".join(f"\n  + {r}  [{n[r]}]" for r in added))
    print(f"dropped repos ({len(gone)}):" + "".join(f"\n  - {r}  [{o[r]}]" for r in gone))
    print(f"role changed ({len(moved)}):" + "".join(f"\n  ~ {r}  {o[r]} -> {n[r]}" for r in moved))
    qa, qg = sorted(set(new["queries"]) - set(old["queries"])), sorted(set(old["queries"]) - set(new["queries"]))
    print(f"queries: +{len(qa)} -{len(qg)}" + "".join(f"\n  + {q}" for q in qa) + "".join(f"\n  - {q}" for q in qg))
    fa = {r: sorted(set(new["files"].get(r, [])) - set(old["files"].get(r, []))) for r in n}
    fa = {r: v for r, v in fa.items() if v}
    if fa:
        print("borrowed files added:" + "".join(f"\n  + {r}: {', '.join(v)}" for r, v in fa.items()))
    print("\nIf approved: replace references/prior-art.md with the new file, then run `check`: new repos show up as GAPs to add to keeper.json.")


def cmd_status(_):
    bad, stale, gaps, learn, old_prior, notes, total = [], [], [], [], [], [], 0
    for d in owned_skills():
        total += 1
        st = load_json(REGISTRY / "state" / f"{d.name}.json", {})
        s = st.get("_lastSummary") or {}
        if s.get("FAIL") or s.get("CHANGED"):
            bad.append(f"{d.name} ({s.get('FAIL', 0)} fail, {s.get('CHANGED', 0)} changed)")
        if s.get("GAP"):
            gaps.append(f"{d.name} ({s['GAP']})")
        if s.get("LEARN"):
            learn.append(f"{d.name} ({s['LEARN']})")
        pa = read_prior_art(d)
        if pa and pa.get("date") and (dt.date.today() - dt.date.fromisoformat(pa["date"])).days > PRIOR_ART_STALE_DAYS:
            old_prior.append(f"{d.name} ({(dt.date.today() - dt.date.fromisoformat(pa['date'])).days}d)")
        if open_notes(d.name):
            notes.append(f"{d.name} ({open_notes(d.name)})")
        last = st.get("_lastRun")
        if not last or (dt.datetime.now() - dt.datetime.fromisoformat(last)).days > 7:
            stale.append(d.name)
    if not total:
        print("rotless-skill-modernizer: no authored skills registered")
        return
    msg = f"rotless-skill-modernizer: {total} authored skill(s)"
    if bad:
        msg += "; NEED FIXING: " + ", ".join(bad)
    if stale:
        msg += "; not checked in 7+ days: " + ", ".join(stale)
    if gaps:
        msg += "; manifest gaps: " + ", ".join(gaps)
    if learn:
        msg += "; upstream changes to review: " + ", ".join(learn)
    if old_prior:
        msg += f"; prior art older than {PRIOR_ART_STALE_DAYS} days (consider `refresh`): " + ", ".join(old_prior)
    if notes:
        msg += "; open field notes for rotless-skill-refiner: " + ", ".join(notes)
    print(msg + ("" if bad or stale or gaps or learn or old_prior or notes else "; all current"))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init")
    i.add_argument("skill")
    i.add_argument("--force", action="store_true")
    c = sub.add_parser("check")
    c.add_argument("skills", nargs="*")
    c.add_argument("--all", action="store_true")
    a = sub.add_parser("ack")
    a.add_argument("skill")
    a.add_argument("ids", nargs="*")
    a.add_argument("--note")
    o = sub.add_parser("own", help="mark a skill as yours, so `check` runs the commands in its keeper.json")
    o.add_argument("skill")
    li = sub.add_parser("lint", help="offline: manifests parse, claim quotes present, nothing untracked (for CI)")
    li.add_argument("skills", nargs="*")
    sub.add_parser("list")
    sub.add_parser("status")
    pd = sub.add_parser("prior-art-diff", help="compare references/prior-art.md with a freshly researched one")
    pd.add_argument("skill")
    pd.add_argument("new_file")
    args = p.parse_args()
    if args.cmd == "check" and not (args.all or args.skills):
        p.error("give skill names or --all")
    {"init": cmd_init, "check": cmd_check, "ack": cmd_ack, "list": cmd_list, "status": cmd_status, "own": cmd_own, "lint": cmd_lint,
     "prior-art-diff": cmd_prior_art_diff}[args.cmd](args)


if __name__ == "__main__":
    main()
