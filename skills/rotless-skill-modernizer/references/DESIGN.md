# rotless-skill-modernizer: design

Status 2026-11-02: the core loop is implemented in `scripts/keeper.py` (init / check / ack / own / lint / list / status). This is one of the four rotless skills (research, creator, modernizer, refiner), and all four are maintained with it. The history below keeps the 2026-10-24 decisions and notes where they changed.

## 1. Scope (decided)

rotless-skill-modernizer is for skill authors. A skill written by someone else belongs to its author, so we don't update, edit, dedupe or manage it. An earlier P0 that inventoried and "updated" all installed skills went the wrong way and has been removed.

The problem it solves: a skill we write makes claims about things outside itself, and those things change without notice.

| Rots | Example | Checker |
|---|---|---|
| CLIs and their subcommands | `gh repo read-dir` renamed; `gh` 2.110 changes a flag | `cli`: present, version vs `tested`, latest release, each `needs` subcommand still exists |
| APIs and their response shapes | npm search drops a field the script parses | `http`: status + `jsonPaths` |
| MCP servers and tool schemas | grep.app renames a parameter | `mcp`: `tools/list` + expected params |
| Packages | a library the skill documents ships a new major | `package` (npm, pypi, crates) vs `tested` |
| Docs pages the skill summarises | the page the skill's rules came from is rewritten | `doc`: normalised content fingerprint; CHANGED until re-read and acked |
| Repos the skill cites or learned from | renamed, archived, deleted, new release | `github-repo` (one GraphQL batch) |
| Other skills it calls | rotless-github-research missing or its script moved | `skill` |
| Claims in its own text | "code search is 10/min" | `claims`: each quote paired with a check; the report points at the SKILL.md line |
| Its own canaries | the skill's self-test | `command` (own scripts only) |
| The landscape | a better tool appears | `landscape.searches` via rotless-github-research; NEW repos |

## 2. Principles

1. Only skills with a `keeper.json` are touched; that file is the opt-in and the authorship marker.
2. The manifest lives inside the skill, so it travels and is versioned with it. State lives outside (`<registry>/state/<skill>.json`), so the skill stays clean and shareable. The registry is an existing `skill-registry/` next to the skills folder, otherwise `~/.skill-registry`, or `$SKILL_REGISTRY`; never the install folder, since plugin updates wipe it (2026-11-02).
3. Never put manifest data in SKILL.md frontmatter: claude.ai and the Skills API reject unknown keys, and the spec's `metadata` maps strings to strings only.
4. Diff-only: baseline on first sight, report changes, `ack` to accept (nvchecker's `take` model).
5. The engine detects and the author decides. The agent proposes fixes as edits, and they're applied only with approval.
6. Declarative checks come first; `command` runs only the skill's own scripts.
7. Local and private: the registry is a local git repo whose history is the audit trail, and it's never pushed.
8. Make skills rot less: keep volatile facts few and declared, and prefer "check the live docs" for fast-moving details.

## 3. Components

```
 your skill/                         keeper.py                          <registry>/ (git)
   SKILL.md, references/, scripts/     init  → keeper.draft.json          state/<skill>.json   baselines, pending values
   keeper.json  (deps, claims,         check → digest, exit 1 if fix     digests/<skill>-<date>.md
                 landscape, verified)  ack   → keeper.json `tested`,
                                               `verified`
                                       list / status (offline)
```

How the skills relate (2026-11-02; this replaces the 2026-10-24 three-skill design, in which research didn't know the others and the build step was Anthropic's unmodified skill-creator):
- There are four skills. Each is usable alone, names the others in a "rotless family" table, and hands off to them when they're installed: research (prior art), creator (build and test; an Apache-2.0 fork of Anthropic's skill-creator), modernizer (drift, when the world changed) and refiner (lessons from use, both fixes and optimizations).
- rotless-github-research knows its callers and writes `prior-art.md` in the shape this skill owns. It still works with no sibling installed.
- rotless-skill-modernizer runs `fix` and `refresh`; `new` hands off to rotless-skill-creator, which comes back for `init`. It owns the `prior-art.md` shape that rotless-github-research fills, and declares the other three skills as dependencies. `mustContain` checks the step names it relies on in each of them.
- rotless-skill-creator names the family in its own text, so the global "Skill authoring flow" rule is optional; the rule only makes agents use the flow without being asked. The keeper.json claim that checked for that rule in the user's home folder was removed on 2026-11-02, because it failed for anyone who installed rotless without pasting the rule.
- Ownership is explicit (2026-11-02). `check` runs the commands in a keeper.json, so only skills listed in `<registry>/owned.json` get checked. `init` adds a skill and `own` adds one by hand; a third-party skill that ships a keeper.json is skipped until the user says it's theirs. `lint` runs no code and makes no network calls, so it works on any skill and in CI.
- A rotless-skill-modernizer `keeper.json` inside rotless-github-research is inert data: rotless-github-research never reads or mentions it.

Three layers decide who populates and maintains `keeper.json`:
1. Capture while authoring (primary): whoever writes or edits the skill writes the manifest in the same change, because that's when the knowledge exists. Creation goes through rotless-skill-creator (Anthropic's upstream skill-creator also works, used as-is). Its Interview-and-Research step surfaces the dependencies, and rotless-skill-modernizer's SKILL.md tells the agent to write `keeper.json` along with the skill's files and to run `check` for baselines.
2. Coverage safety net (automatic): every `check` rescans the text and reports, with file:line, references the manifest doesn't cover (GAP). This catches the edit where nobody updated the manifest.
3. On-demand checks: the dependency, claim and landscape checks below run when someone asks. There's no scheduler, by decision, because a result is only useful when an agent harness and a person can act on it.
`init` is the fallback for existing skills without a manifest.

- extract (shared by init and coverage) scans SKILL.md and `references/*.md`, skipping JSON/YAML example blocks and "quoted examples". It collects commands on PATH and their subcommands (from code blocks and inline backticks), stated versions, URLs (http, mcp, doc), backticked or linked `owner/repo` names (verified to exist), and "N/min"-style limits, and records each one's first file:line.
- init writes `keeper.draft.json` from extract, each entry with `_where`, for the author to curate.
- coverage compares extract with the manifest: an untracked CLI, a subcommand missing from `needs`, a URL not covered (host and path prefix match), an unwatched real repo, a version in the text contradicting `tested`, or a limit no claim quote covers. It honours `ignore` (exact, word-prefix, or `*` prefix).
- check runs every dep, claim, landscape search and the coverage scan. It groups results as Fix the skill (FAIL, CHANGED), Not tracked in keeper.json (GAP), New in the landscape, Worth a look, Baseline and OK, saves a digest and commits state. It exits 1 only for FAIL or CHANGED.
- ack accepts pending values (CLI and package versions into `tested`, doc fingerprints) and stamps `verified`.
- fix is done by the agent, following SKILL.md: read the digest, open the cited line or script, research what's true now, propose an edit, apply it on approval, re-check, then ack.

Implementation notes learned by testing: `gh` and `claude` exit 0 and print the parent's help for unknown subcommands, so a subcommand counts as present only if its own help names it. The npx-skills `skillFolderHash` and the gh-skill `github-tree-sha` are git tree SHAs.

## 4. Roadmap

- Done: init, check (cli, http, mcp, package, doc, github-repo, skill, command, claims, landscape), the coverage safety net with `ignore`, ack, list, status and registry history. Authoring-time capture is written into SKILL.md, with the skill-creator handoff. rotless-github-research was migrated off its old `watch.py`/`watchlist.json`, and rotless-skill-modernizer maintains itself. In the coverage test, all 6 references added in a later edit were flagged with file:line. Upstream learning (2026-10-24): cited repos remember the commit last reviewed (`seenSha`), and `check` lists meaningful commits since then and changes to borrowed `files` as LEARN. Windows with only trivial commits advance on their own, and `ack` moves the baseline. Borrowed paths are verified until confirmed, `init` imports borrowed files from prior-art.md's take column, and `refresh` with `prior-art-diff` re-runs the prior art and shows what changed (status hints after 90 days).
- Next:
  - No scheduling (decided 2026-10-24): checks run on demand. An agent harness (Claude Code, Codex, Antigravity…) runs the skills, so the useful moments are when a session exists: on request, after an edit, or before relying on a skill whose `status` is stale.
  - `doc` checker: optional CSS-selector or section scoping to cut noise on large pages.
  - A `fix` helper that turns a digest into a checklist with file/line links.
  - Extend extract and coverage beyond limits to CLI flags (`--match`) and "X doesn't support Y" statements.
  - Testing behaviour belongs to skill-creator's test-case loop (with/without-skill runs, grading, viewer), which checks that a skill works; rotless-skill-modernizer checks that it's still true. After a substantive fix, re-run the skill-creator tests if the skill has them. (If CI with Claude Code ever needs it: `claude plugin eval … --no-publish`; without the flag the report may be published to claude.ai.)
  - Optional hook: when a file in an owned skill is edited, remind the agent to update `keeper.json`. It needs a settings change, so only if the user wants it.

## 5. Prior art (researched 2026-10-24)

More than 40 skill package managers exist (npx-skills, skillfish, asm, qvr, grimoire, HarnessKit, tech-leads-club, ClawHub…). They track whether a skill's own files match their source. None declares or checks a skill's external dependencies (OpenClaw's `requires.bins/env` only checks presence), none tests a skill's claims, and none watches the repos or docs a skill cites. The closest ideas borrowed: nvchecker and brew livecheck (a version-check strategy per source, `take`), urlwatch (doc change detection), rotless-github-research's own `selftest.py` (claims as canaries), skill-validator (spec and link checks) and `claude plugin eval` (behaviour).
