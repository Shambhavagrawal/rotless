# rotless

**Agent skills rot.** A skill says "`gh search code` allows 10 requests a minute", "call this endpoint", "use this flag". Then the CLI ships a new version, the API changes shape, a step quietly stops working, and the skill keeps confidently telling your agent things that are no longer true. And every time you learn something while using it, a fix or a faster way, the lesson dies with that conversation.

rotless is four [Agent Skills](https://agentskills.io) that build skills which stay true, and get better every time they're used:

| Skill | Job |
|---|---|
| **rotless-github-research** | Before you build: finds every repo, package and tool that already does it (code search, repo search, commits, issues, plus 20 sources off GitHub such as npm, crates.io, Docker Hub, Hugging Face and the MCP Registry), verifies each one, and tells you what to reuse, what to borrow and where the gap is. |
| **rotless-skill-creator** | Builds the skill: a failing baseline first, an interview, the draft, test cases run with and without the skill, a review viewer, trigger tuning, and spec + portability validation. Runs tests on Claude Code, Codex and other agent CLIs. |
| **rotless-skill-modernizer** | Keeps it true as the world changes: a `keeper.json` lists every CLI, API, MCP server, repo, doc and limit the skill relies on, each with a check. `check` tells you what drifted and the exact line to fix. |
| **rotless-skill-refiner** | Makes it better from real use: fixes when something went wrong, optimizations when it worked but could be faster, cheaper or simpler. Notes get logged while you work, and a retro turns them into small edits, **each with a check**: a fix must fail on the old skill and pass on the new one; an optimization must measure better on the same test cases with nothing worse. Each pass leaves the next one better. |

```
idea ─► research ─► create ─► modernize ─► use ─► refine ─┐
        exists?     build +    record what   field    fixes and   │
        borrow?     test       it relies on  notes    optimizations ◄─┘
```

Works with any agent that reads `SKILL.md`: Claude Code, Codex, Gemini CLI, Cursor, GitHub Copilot, OpenCode and the rest. No hooks, no daemons, no telemetry: plain skills and standard-library Python.

## Install

Any agent ([skills CLI](https://github.com/vercel-labs/skills)):

```bash
npx skills add Shambhavagrawal/rotless -g
```

Claude Code plugin:

```
/plugin marketplace add Shambhavagrawal/rotless
/plugin install rotless@rotless
```

Or copy `skills/*` into your agent's skills folder (`~/.agents/skills/`, `~/.claude/skills/`, `~/.codex/skills/`…).

**Requires** Python 3 and the [GitHub CLI](https://cli.github.com) logged in (`gh auth login`). Test runs on other agents use their own CLIs (`claude`, `codex`…) if installed.

## Turn on the flow

Paste this into your agent's global instructions file (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`…), so every skill you write goes through it:

```markdown
## Skill authoring flow
- When creating or editing a skill I author, use the rotless skills together, in this order:
  1. **rotless-github-research**: prior art first (does it exist, what to borrow, what gap is left).
  2. **rotless-skill-creator**: build or improve the skill (failing baseline first, test cases, trigger tuning, validation).
  3. **rotless-skill-modernizer**: in the same change, write or update the skill's `keeper.json`, then run its `check`; finish with no GAP, FAIL or CHANGED.
- While using a skill I author: when a step fails, I correct you, you work around an instruction or you find a better way, log a field note with **rotless-skill-refiner**; its retro turns notes into small edits, each with a check that fails on the old skill and passes on the new.
- Never use them to modify skills written by others.
```

## Use

Ask in plain words, or call a skill by name (`/rotless-skill-refiner` in Claude Code, `$rotless-skill-refiner` in Codex). Which skill answers depends on where the cause lives, not on words like "check" or "broke":

| You say | Skill |
|---|---|
| "Is there anything on GitHub that already scrapes exam results?" | research |
| "Make a skill that turns my standup notes into a Slack post" | create (it runs research first) |
| "Check my skills", "is my scraper skill still up to date?", "I upgraded gh, did anything break?" | modernize: the outside world changed; `check` also lists open field notes |
| "My pdf skill mangled the tables again, fix it for next time", "what went wrong with my deploy skill?" | refine: it misbehaved in use (it runs modernize's `check` first to rule out drift) |
| "My release-notes skill works but takes 8 tool calls, make it leaner", "retro my changelog skill" | refine: an optimization, measured before and after |

Every change to a skill waits for your approval. Checks run only when you ask, and the only network calls are the checks themselves. State lives in a local git repo next to your skills folder (`skill-registry/`), never pushed.

## Dogfooded

All four skills carry their own `keeper.json` and field-notes footer. The first lesson rotless-skill-refiner recorded was a bug in rotless-skill-modernizer itself (Windows CLI shims), fixed with a check that failed on the old code and passes now: see `skills/rotless-skill-modernizer/references/lessons.md`.

## License

MIT, except `skills/rotless-skill-creator`, which is a modified version of Anthropic's skill-creator under Apache-2.0 (its `LICENSE.txt` and `NOTICE` list the changes).
