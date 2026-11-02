# rotless

[![selftest](https://github.com/Shambhavagrawal/rotless/actions/workflows/selftest.yml/badge.svg)](https://github.com/Shambhavagrawal/rotless/actions/workflows/selftest.yml)

Agent skills rot. A skill says "`gh search code` allows 10 requests a minute", "call this endpoint", "use this flag". Then the CLI ships a new version, the API changes shape, a step stops working, and the skill keeps telling your agent things that are no longer true. Whatever you learn while using a skill, a fix or a faster way, is lost when the conversation ends.

rotless is four [Agent Skills](https://agentskills.io) for building skills that stay accurate and improve with use:

| Skill | Job |
|---|---|
| rotless-github-research | Before you build, it searches for repos, packages and tools that already do the job: code search, repo search, commits and issues on GitHub, plus 21 other sources such as npm, crates.io, Docker Hub, Hugging Face models and papers, and the MCP Registry. It verifies each GitHub repo it reports (activity, health, real code), checks other hits by hand, and tells you what to reuse, what to borrow and where the gap is. |
| rotless-skill-creator | Builds the skill: a failing baseline first, an interview, the draft, test cases run with and without the skill, a review viewer, trigger tuning, and spec and portability validation. Test runs are real agent sessions on your account, so they use its quota. |
| rotless-skill-modernizer | Keeps the skill accurate as the world changes. Its `keeper.json` lists the CLIs, APIs, MCP servers, repos, docs and limits the skill relies on, each with a check, and a coverage check flags anything the text mentions that the list misses. `check` tells you what drifted and the line to fix. |
| rotless-skill-refiner | Improves the skill from real use: fixes when something went wrong, and optimizations when it worked but could be faster, cheaper or simpler. You log notes while you work, and a retro turns them into small edits, each with a check. A fix must fail on the old skill and pass on the new one; an optimization must measure better on the same test cases with nothing worse. Each pass leaves the next one better. |

```
idea ─► research ─► create ─► modernize ─► use ─► refine ───┐
        exists?     build     record what  log    fix or    │
        borrow?     + test    it relies on notes  optimize  │
                                           ▲                │
                                           └────────────────┘
```

The skills follow the open Agent Skills spec, so any agent that reads `SKILL.md` can load them: Claude Code, Codex, Gemini CLI, Cursor, GitHub Copilot, OpenCode and others. The creator's test runs are verified on Claude Code and Codex so far (see Status). Everything is plain skills and standard-library Python, with no hooks, background daemons or telemetry.

## Install

With the [skills CLI](https://github.com/vercel-labs/skills), for any agent:

```bash
npx skills add Shambhavagrawal/rotless -g
```

As a Claude Code plugin:

```
/plugin marketplace add Shambhavagrawal/rotless
/plugin install rotless@rotless
```

Or copy `skills/*` into your agent's skills folder (`~/.agents/skills/`, `~/.claude/skills/`, `~/.codex/skills/`…).

You need Python 3.10 or later and the [GitHub CLI](https://cli.github.com), logged in with `gh auth login`. The creator's test runs use your agents' own CLIs (`claude`, `codex`…) when they're installed.

## Turn on the flow

Paste this into your agent's global instructions file (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`…), so every skill you write goes through it:

```markdown
## Skill authoring flow
- When creating or editing a skill I author, use the rotless skills together, in this order:
  1. **rotless-github-research**: prior art first (does it exist, what to borrow, what gap is left).
  2. **rotless-skill-creator**: build or improve the skill (failing baseline first, test cases, trigger tuning, validation).
  3. **rotless-skill-modernizer**: in the same change, write or update the skill's `keeper.json`, then run its `check`; finish with no GAP, FAIL or CHANGED.
- While using a skill I author: when a step fails, I correct you, you work around an instruction, you find a better way, or you see it could be faster or cheaper, log a field note with **rotless-skill-refiner**; its retro turns notes into small edits, each with a check.
- Never use them to modify skills written by others.
```

## Use

Ask in plain words, or call a skill by name: `/rotless-skill-refiner` in Claude Code (`/rotless:rotless-skill-refiner` if you installed the plugin), `$rotless-skill-refiner` in Codex. Which skill answers depends on where the cause lives; words like "check" or "broke" don't decide it:

| You say | Skill |
|---|---|
| "Is there anything on GitHub that already scrapes exam results?" | research |
| "Make a skill that turns my standup notes into a Slack post" | create (it runs research first) |
| "Check my skills", "is my scraper skill still up to date?", "I upgraded gh, did anything break?" | modernize: the outside world changed; `check` also lists open field notes |
| "My pdf skill mangled the tables again, fix it for next time", "what went wrong with my deploy skill?" | refine: it misbehaved in use (it runs modernize's `check` first to rule out drift) |
| "My release-notes skill works but takes 8 tool calls, make it leaner", "retro my changelog skill" | refine: an optimization, measured before and after |

The skills ask for your approval before every edit. Nothing runs in the background: searches, checks and test runs happen only when you ask. Their state (check history, field notes, the list of skills you own) lives in a local git repo that is never pushed, `~/.skill-registry`, or `skill-registry/` next to your skills folder if you already have one there.

## Status

Verified:
- Skill loading and headless test runs on Claude Code and Codex.
- The offline checks, on Linux and Windows with Python 3.10 and 3.13, in CI on every push.
- The Claude Code plugin manifest, with `claude plugin validate`.

Not verified yet:
- How reliably each skill's description triggers. The test sets are in each skill's `evals/trigger-eval.json`.
- Test runs on GitHub Copilot, Gemini CLI, OpenCode and Cursor. They're wired in; run `python skills/rotless-skill-creator/scripts/harness.py probe --agent <name>` before relying on one.
- macOS, and an end-to-end `npx skills add` install.

## Dogfooded

All four skills have their own `keeper.json` and field-notes footer, and rotless maintains itself with its own tools. That has produced 29 lessons so far, from real use and from code reviews. Each lesson has a check that failed before its fix and passes now, and CI runs all of them. The first came from the refiner itself: it caught the modernizer failing to start npm-installed CLIs on Windows. Each skill's `references/lessons.md` lists its lessons.

## Contributing

Run what CI runs before opening a pull request:

```bash
python skills/rotless-skill-refiner/scripts/notes.py selftest
python skills/rotless-skill-creator/scripts/test_harness.py
python skills/rotless-skill-modernizer/scripts/test_cli_shims.py
python skills/rotless-skill-modernizer/scripts/test_keeper.py
python skills/rotless-github-research/scripts/test_offline.py
python skills/rotless-skill-modernizer/scripts/keeper.py lint skills/*/
for s in skills/*/; do python skills/rotless-skill-creator/scripts/quick_validate.py "$s" --strict; done
```

A bug fix comes with a check that fails before the fix, recorded in the skill's `references/lessons.md`.

## License

MIT, except `skills/rotless-skill-creator`, which is a modified version of Anthropic's skill-creator under Apache-2.0. Its `LICENSE.txt` and `NOTICE` list the changes.
