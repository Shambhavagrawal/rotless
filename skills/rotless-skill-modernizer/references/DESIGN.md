# rotless-skill-modernizer: design

Status 2026-10-24: core loop implemented (`scripts/keeper.py`: init / check / ack / list / status), two skills maintained (rotless-github-research, rotless-skill-modernizer itself).

## 1. Scope (decided)

rotless-skill-modernizer is for **skill authors**. A skill written by someone else belongs to its author: we don't update, edit, dedupe or manage it (an earlier P0 that inventoried and "updated" all installed skills was the wrong direction and has been removed).

The problem it solves: a skill we write makes claims about things outside itself, and those things change silently:

| Rots | Example | Checker |
|---|---|---|
| CLIs and their subcommands | `gh repo read-dir` renamed; `gh` 2.110 changes a flag | `cli`: present, version vs `tested`, latest release, each `needs` subcommand still exists |
| APIs and their response shapes | npm search drops a field the script parses | `http`: status + `jsonPaths` |
| MCP servers and tool schemas | grep.app renames a parameter | `mcp`: `tools/list` + expected params |
| Packages | a library the skill documents ships a new major | `package` (npm, pypi, crates) vs `tested` |
| Docs pages the skill summarises | the page the skill's rules came from is rewritten | `doc`: normalised content fingerprint; CHANGED until re-read and acked |
| Repos the skill cites or learned from | renamed, archived, deleted, new release | `github-repo` (one GraphQL batch) |
| Other skills it calls | rotless-github-research missing or its script moved | `skill` |
| Claims in its own text | "code search is 10/min" | `claims`: quote ↔ check; report points at the SKILL.md line |
| Its own canaries | the skill's self-test | `command` (own scripts only) |
| The landscape | a better tool appears | `landscape.searches` via rotless-github-research; NEW repos |

## 2. Principles

1. Only skills with a `keeper.json` are touched; that file is the opt-in and the authorship marker.
2. The manifest lives **inside the skill** (travels with it, versioned with it); state lives **outside** (`<skills folder>/../skill-registry/state/<skill>.json`, or `$SKILL_REGISTRY`), so the skill stays clean and shareable.
3. Never put manifest data in SKILL.md frontmatter: claude.ai / Skills API reject unknown keys and the spec's `metadata` is string→string only.
4. Diff-only: baseline on first sight, report changes, `ack` to accept (nvchecker's `take` model).
5. The engine detects; the author decides. Fixes are edits proposed by the agent and applied only with approval.
6. Declarative checks first; `command` runs only the skill's own scripts.
7. Local and private: registry is a local git repo (history = audit trail), never pushed.
8. Make skills rot less: keep volatile facts few and declared; prefer "check the live docs" for fast-moving details.

## 3. Components

```
 your skill/                         keeper.py                          <skills>/../skill-registry/ (git)
   SKILL.md, references/, scripts/     init  → keeper.draft.json          state/<skill>.json   baselines, pending values
   keeper.json  (deps, claims,         check → digest, exit 1 if fix     digests/<skill>-<date>.md
                 landscape, verified)  ack   → keeper.json `tested`,
                                               `verified`
                                       list / status (offline)
```

**How the three skills relate (decided 2026-10-24):**
- **rotless-github-research is independent.** It doesn't know the other two, and its SKILL.md never mentions them.
- **rotless-skill-modernizer knows both.** It orchestrates `new`/`fix`, owns the `prior-art.md` shape it asks rotless-github-research to fill, and declares both as dependencies. `mustContain` checks the rotless-github-research and skill-creator step names it relies on.
- **skill-creator should know the other two**, but it's Anthropic's skill: not edited by us, and overwritten by claude.ai sync. Its awareness comes from the Skill authoring flow rule in the user's global agent instructions file (CLAUDE.md, AGENTS.md, GEMINI.md…; added 2026-10-24, loaded in every session); a claim in keeper.json checks the rule is still there.
- A rotless-skill-modernizer `keeper.json` inside rotless-github-research is inert data: rotless-github-research never reads or mentions it.

Three layers decide who populates and maintains `keeper.json`:
1. **Capture while authoring** (primary): whoever writes or edits the skill writes the manifest in the same change, because that's when the knowledge exists. Creation usually goes through Anthropic's `skill-creator` (used as-is, never modified); its Interview-and-Research step surfaces the dependencies, and rotless-skill-modernizer's SKILL.md tells the agent to write `keeper.json` when the skill's files are written and to run `check` for baselines.
2. **Coverage safety net** (automatic): every `check` rescans the text and reports references the manifest doesn't cover (GAP), with file:line. Catches the edit where nobody updated the manifest.
3. **On-demand checks**: the dependency/claim/landscape checks below, run when someone asks (no scheduler, by decision: a result is only useful when an agent harness and a person can act on it).
`init` is the fallback for existing skills without a manifest.

- **extract** (shared by init and coverage): scans SKILL.md + `references/*.md`, skipping JSON/YAML example blocks and "quoted examples", for commands on PATH and their subcommands (code blocks and inline backticks), stated versions, URLs (http / mcp / doc), backticked or linked `owner/repo` (verified to exist), and "N/min"-style limits; records each one's first file:line.
- **init**: writes `keeper.draft.json` from extract (each entry with `_where`); the author curates.
- **coverage**: compares extract with the manifest: untracked CLI, subcommand missing from `needs`, URL not covered (host+path prefix match), unwatched real repo, a version in the text contradicting `tested`, a limit no claim quote covers; honours `ignore` (exact, word-prefix, or `*` prefix).
- **check**: runs every dep, claim, landscape search and the coverage scan; groups results Fix the skill (FAIL, CHANGED) / Not tracked in keeper.json (GAP) / New in the landscape / Worth a look / Baseline / OK; saves a digest; commits state. Exit 1 only for FAIL/CHANGED.
- **ack**: accepts pending values (CLI/package versions into `tested`, doc fingerprints) and stamps `verified`.
- **fix** (the agent, via SKILL.md): read the digest → open the cited line/script → research the new reality → propose edit → apply on approval → re-check → ack.

Implementation notes learned by testing: `gh` and `claude` exit 0 and print the parent's help for unknown subcommands, so a subcommand counts as present only if its own help names it; the npx-skills `skillFolderHash` / gh-skill `github-tree-sha` are git tree SHAs.

## 4. Roadmap

- **Done**: init, check (cli, http, mcp, package, doc, github-repo, skill, command, claims, landscape), coverage safety net with `ignore`, ack, list, status, registry history; authoring-time capture written into SKILL.md (with the skill-creator handoff); rotless-github-research migrated (replacing its old `watch.py`/`watchlist.json`); rotless-skill-modernizer maintains itself. Coverage test: 6/6 references added in a later edit flagged with file:line. Upstream learning (2026-10-24): cited repos remember the commit last reviewed (`seenSha`); `check` lists meaningful commits since then and changes to borrowed `files` as LEARN (trivial-only windows auto-advance; `ack` moves the baseline); borrowed paths are verified until confirmed; `init` imports borrowed files from prior-art.md's take column; `refresh` + `prior-art-diff` re-run the prior art and show what changed (status hints after 90 days).
- **Next**:
  - No scheduling (decided 2026-10-24): checks are on demand. Skills are run by an agent harness (Claude Code, Codex, Antigravity…), so the useful moments are when a session exists: on request, after an edit, before relying on a skill whose `status` is stale.
  - `doc` checker: optional CSS-selector/section scoping to cut noise on large pages.
  - A `fix` helper that turns a digest into a checklist with file/line links.
  - Extend extract/coverage beyond limits: CLI flags (`--match`), "X doesn't support Y" statements.
  - Behaviour is **not** rotless-skill-modernizer's job: skill-creator's test-case loop (with/without-skill runs, grading, viewer) checks that a skill works; rotless-skill-modernizer checks that it's still true. After a substantive fix, re-run the skill-creator tests if the skill has them. (If ever needed for CI with Claude Code: `claude plugin eval … --no-publish`; without the flag the report may be published to claude.ai.)
  - Optional hook: when a file in an owned skill is edited, remind the agent to update `keeper.json` (needs a settings change; only if the user wants it).

## 5. Prior art (researched 2026-10-24)

40+ skill package managers exist (npx-skills, skillfish, asm, qvr, grimoire, HarnessKit, tech-leads-club, ClawHub…). They track whether a *skill's own files* match their source. None declares or checks a skill's external dependencies (OpenClaw's `requires.bins/env` is presence-only), none tests a skill's claims, none watches the repos/docs a skill cites. Closest ideas borrowed: nvchecker / brew livecheck (strategy-per-source version checks, `take`), urlwatch (doc change detection), rotless-github-research's own `selftest.py` (claims as canaries), skill-validator (spec/link checks), `claude plugin eval` (behaviour).
