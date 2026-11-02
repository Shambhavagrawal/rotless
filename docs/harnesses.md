# Agents

rotless is four skills written to the [Agent Skills](https://agentskills.io) spec, so any agent that reads `SKILL.md` can load them. This page covers installing and calling them in each agent, and what has been verified.

"Verified" means someone ran it end to end. Everything else is wired in and expected to work, but has not been tried.

## Summary

| Agent | Install | Call a skill | Creator's test runs |
|---|---|---|---|
| Claude Code | plugin, or copy into a skills folder | `/rotless-skill-refiner`; `/rotless:rotless-skill-refiner` as a plugin | verified (`claude -p`) |
| Codex | plugin, or copy into a skills folder | `$rotless-skill-refiner`, or pick it in the skill picker | verified (`codex exec`) |
| Antigravity CLI | `agy plugin install` | `/rotless:rotless-skill-refiner` | not verified |
| Gemini CLI | copy into a skills folder | ask by name | not verified (`gemini -p`) |
| GitHub Copilot CLI | copy into a skills folder | ask by name | not verified (`copilot -p`) |
| OpenCode | copy into a skills folder | ask by name | not verified (`opencode run`) |
| Cursor | copy into a skills folder | ask by name | not verified (`cursor-agent -p`) |

Before relying on test runs with an agent marked "not verified", check that it loads skills in headless mode:

```bash
python skills/rotless-skill-creator/scripts/harness.py probe --agent gemini
```

The probe installs a throwaway skill about a made-up topic and asks about it. It passes only if the agent loaded the skill.

## Test record

What has been run, with which version. Add a row when you verify something new, including failures.

| Date | Agent | What ran | Result |
|---|---|---|---|
| 2026-11-02 | Claude Code 2.1.316 | `harness.py probe` (loads a project skill headlessly) | passed |
| 2026-11-02 | Claude Code 2.1.316 | `claude plugin validate` on this repo | passed |
| 2026-11-02 | codex-cli 0.154.0 | `harness.py probe` | passed |
| 2026-11-02 | codex-cli 0.166.0 | probe; a behaviour test case with and without rotless-skill-refiner (`run_case.py`); the refiner's trigger tests (`run_eval.py`); installing the plugin from this repo | passed. The test runs found four bugs in the runners, now fixed (rotless-skill-creator lessons 2 to 5); the trigger tests' second run stopped at the Codex usage limit |
| 2026-11-02 | Claude Code 2.1.316 | trigger tests (`run_eval.py`), 20 queries per skill (10 should trigger, 10 near misses), 3 runs each, with your own skills left out (`--setting-sources project`) | 79 of 80 right. rotless-github-research, rotless-skill-modernizer and rotless-skill-refiner 20/20 with no false triggers; rotless-skill-creator 19/20, missing "here's my SKILL.md for invoice-ocr, write test cases for it…" (0 of 3 runs). About 4 minutes per skill with 6 runs at a time. The machine's own CLAUDE.md, which names the rotless skills, was loaded too (`--setting-sources` doesn't skip it), so recall may be higher here than on a clean install |
| 2026-11-02 | Claude Code 2.1.316 | the creator's trigger set again, after rewriting the missed query (it handed the agent a file the run doesn't have) | 20/20; the new query 3 of 3 |
| 2026-11-02 | GitHub Copilot CLI 0.0.382 | `harness.py probe` | failed: exit 1 with no output. Not retried with an allow-everything flag, by design |
| 2026-11-02 | Gemini CLI | not run | the local install was broken |

## Claude Code

```
/plugin marketplace add Shambhavagrawal/rotless
/plugin install rotless@rotless
```

From a terminal: `claude plugin marketplace add Shambhavagrawal/rotless`, then `claude plugin install rotless@rotless`. As a plugin, skills are namespaced: `/rotless:rotless-skill-creator`. Copied into `~/.claude/skills/` or a project's `.claude/skills/`, they're called without the prefix.

## Codex

```bash
codex plugin marketplace add Shambhavagrawal/rotless
codex plugin add rotless@rotless
```

Verified with codex-cli 0.166.0: adding the marketplace and installing the plugin both work, and the install has all four skills. Start a new session afterwards. You can also copy `skills/*` into `~/.codex/skills/` or `~/.agents/skills/`.

## Antigravity

```bash
agy plugin install https://github.com/Shambhavagrawal/rotless
```

Antigravity installs from the root `plugin.json` and the `skills/` folder. Not tried yet.

## Other agents

Install with the [skills CLI](https://github.com/vercel-labs/skills) (`npx skills add Shambhavagrawal/rotless -g`), or copy `skills/*` into the agent's skills folder. These are the folders rotless itself looks in, project level first:

| Agent | Project folder | User folder |
|---|---|---|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Codex | `.agents/skills/` | `~/.codex/skills/`, `~/.agents/skills/` |
| Gemini CLI | `.gemini/skills/` | `~/.gemini/skills/` |
| GitHub Copilot | `.github/skills/` | `~/.copilot/skills/` |
| OpenCode | `.opencode/skills/` | `~/.config/opencode/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |

## How the skills find each other and their files

Each skill works on its own. Installed together, as a plugin or copied side by side, they sit in the same `skills/` folder and find each other as sibling folders. Each skill reaches its own scripts relative to its `SKILL.md`, so nothing depends on where the agent installed it.

The modernizer and refiner keep their state outside the install folder, because a plugin update replaces that folder: in `skill-registry/` next to your skills folder if one already exists there, otherwise in `~/.skill-registry`, or wherever `$SKILL_REGISTRY` points.

## Known limits

- Test runs that create files need a write mode limited to the run's workspace. Today only Claude Code (`--permission-mode acceptEdits`) and Codex (`-s workspace-write`) have one. On other agents, run those cases with subagents or in the session; rotless never uses an allow-everything flag.
- Triggering has been measured on Claude Code only (see the test record). On other agents, a copy of the skill you've installed yourself can answer in place of the test copy, which counts as a missed trigger; `run_eval.py` warns when it finds one. On Claude Code, trigger tests pass `--setting-sources project` to leave your own skills out.
