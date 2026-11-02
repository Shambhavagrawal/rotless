<p align="center"><img src="assets/icon.svg" width="96" height="96" alt="rotless"></p>

<h1 align="center">rotless</h1>

<p align="center">Agent skills that stay accurate and get better with use.</p>

<p align="center">
  <a href="#install">Install</a> &ensp;·&ensp;
  <a href="#quickstart">Quickstart</a> &ensp;·&ensp;
  <a href="docs/harnesses.md">Agents</a> &ensp;·&ensp;
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

<p align="center"><a href="https://github.com/Shambhavagrawal/rotless/actions/workflows/selftest.yml"><img src="https://github.com/Shambhavagrawal/rotless/actions/workflows/selftest.yml/badge.svg" alt="selftest"></a></p>

Agent skills rot. A skill says "`gh search code` allows 10 requests a minute", "call this endpoint", "use this flag". Then the CLI ships a new version, the API changes shape, a step stops working, and the skill keeps telling your agent things that are no longer true. Whatever you learn while using a skill, a fix or a faster way, is lost when the conversation ends.

rotless is four [Agent Skills](https://agentskills.io) that deal with both, for the skills you write and keep using. For a one-off prompt, or a skill someone else maintains, it's more than you need.

| Skill | Job |
|---|---|
| rotless-github-research | Before you build, it searches for repos, packages and tools that already do the job: code search, repo search, commits and issues on GitHub, plus 21 other sources such as npm, crates.io, Docker Hub, Hugging Face models and papers, and the MCP Registry. It verifies each GitHub repo it reports (activity, health, real code), checks other hits by hand, and tells you what to reuse, what to borrow and where the gap is. |
| rotless-skill-creator | Builds the skill: a failing baseline first, an interview, the draft, test cases run with and without the skill, a review viewer, trigger tuning, and spec and portability validation. Test runs are real agent sessions on your account, so they use its quota. |
| rotless-skill-modernizer | Keeps the skill accurate as the world changes. Its `rotless.json` lists the CLIs, APIs, MCP servers, repos, docs and limits the skill relies on, each with a check, and a coverage check flags anything the text mentions that the list misses. `check` tells you what drifted and the line to fix. It runs only when you ask; when a skill you own hasn't been updated or checked for 15 days, it offers a check at the end of a task. New repos in the skill's space stay listed until you've looked at what they offer. |
| rotless-skill-refiner | Improves the skill from real use: fixes when something went wrong, and optimizations when it worked but could be faster, cheaper or simpler. You log notes while you work, and a retro turns them into small edits, each with a check. A fix must fail on the old skill and pass on the new one; an optimization must measure better on the same test cases with nothing worse. Each pass leaves the next one better. |

```
idea ─► research ─► create ─► use ◄───────────────────────┐
                    │         │                           │
                    │         ├─► refine ─────────────────┤  it misbehaved, or could be better
                    │         │                           │
                    │         └─► modernize ──────────────┘  you ask, or the skill reminds you
                    │
                    └─► writes rotless.json: what the skill relies on
```

The skills follow the open Agent Skills spec, so any agent that reads `SKILL.md` can load them. Everything is plain skills and standard-library Python, with no hooks, background daemons or telemetry.

## Install

### Claude Code

```
/plugin marketplace add Shambhavagrawal/rotless
/plugin install rotless@rotless
```

### Codex

```bash
codex plugin marketplace add Shambhavagrawal/rotless
codex plugin add rotless@rotless
```

### Any other agent

```bash
npx skills add Shambhavagrawal/rotless -g
```

### From a file

Apps that install a plugin or skill from a file, such as Claude's desktop and web apps or Cowork, can use the files attached to each [release](https://github.com/Shambhavagrawal/rotless/releases): `rotless-<version>.zip` for the whole plugin, or one `.skill` file per skill.

### By hand

Copy `skills/*` into your agent's skills folder. [docs/harnesses.md](docs/harnesses.md) covers Antigravity, Gemini CLI, GitHub Copilot, OpenCode and Cursor, the folder each one reads, and what has been verified on each.

You need Python 3.10 or later and the [GitHub CLI](https://cli.github.com), logged in with `gh auth login`. Start a new agent session after installing.

## Quickstart

This walks through one skill from idea to its first lesson. The prompts are written as you'd type them; with the plugin installed in Claude Code you can also call each skill directly, for example `/rotless:rotless-skill-creator`.

### 1. Create the skill

```text
Make a skill that turns my standup notes into a Slack post.
```

rotless-skill-creator starts with rotless-github-research, which looks for skills and tools that already do this and writes what it found to `references/prior-art.md`. Then it shows how your agent handles the task without a skill, interviews you, drafts `SKILL.md`, and writes test cases in `evals/`. It runs them with and without the skill and asks you to review the results. Before it finishes, it records what the skill relies on in `rotless.json`.

### 2. Use it, and say when it gets something wrong

```text
The Slack post was too long again. Fix the skill for next time.
```

rotless-skill-refiner logs a field note, then proposes a small edit to the skill together with a check that fails on the current version. Once you approve, it applies the edit, confirms the check now passes, and writes the lesson to `references/lessons.md`.

### 3. Later, check that it's still accurate

```text
Check my skills.
```

rotless-skill-modernizer runs the checks in each skill's `rotless.json`. It reports what changed outside the skill, such as a new CLI release or a moved API, with the line in the skill to fix, and lists any field notes still waiting for a retro. If new repos have appeared in the skill's space, it offers to research what you could borrow from them. You don't have to remember to ask: once a skill you own is 15 days past its last update or check, it offers this at the end of a task.

## Turn on the flow

To have your agent use rotless for every skill you write, paste this into its global instructions file (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`…):

```markdown
## Skill authoring flow
- When creating or editing a skill I author, use the rotless skills together, in this order:
  1. **rotless-github-research**: prior art first (does it exist, what to borrow, what gap is left).
  2. **rotless-skill-creator**: build or improve the skill (failing baseline first, test cases, trigger tuning, validation).
  3. **rotless-skill-modernizer**: in the same change, write or update the skill's `rotless.json`, then run its `check`; finish with no GAP, FAIL or CHANGED.
- While using a skill I author: when a step fails, I correct you, you work around an instruction, you find a better way, or you see it could be faster or cheaper, log a field note with **rotless-skill-refiner**; its retro turns notes into small edits, each with a check.
- Never use them to modify skills written by others.
```

## Which skill answers

Ask in plain words, or call a skill by name: `/rotless-skill-refiner` in Claude Code (`/rotless:rotless-skill-refiner` with the plugin), `$rotless-skill-refiner` in Codex. Which skill answers depends on where the cause lives; words like "check" or "broke" don't decide it:

| You say | Skill |
|---|---|
| "Is there anything on GitHub that already scrapes exam results?" | research |
| "Make a skill that turns my standup notes into a Slack post" | create (it runs research first) |
| "Check my skills", "is my scraper skill still up to date?", "I upgraded gh, did anything break?" | modernize: the outside world changed; `check` also lists open field notes |
| "My pdf skill mangled the tables again, fix it for next time", "what went wrong with my deploy skill?" | refine: it misbehaved in use (it runs modernize's `check` first to rule out drift) |
| "My release-notes skill works but takes 8 tool calls, make it leaner", "retro my changelog skill" | refine: an optimization, measured before and after |

The skills ask for your approval before every edit. Nothing runs in the background: searches, checks and test runs happen only when you ask. [docs/privacy.md](docs/privacy.md) lists what each skill calls and what it stores.

## Status

Verified:
- Skill loading and headless test runs on Claude Code and Codex, and the Codex plugin install.
- The offline checks, on Linux and Windows with Python 3.10 and 3.13, in CI on every push.
- The Claude Code plugin manifest, with `claude plugin validate`.
- Triggering on Claude Code: 79 of 80 trigger-test queries right (20 per skill, 3 runs each; [docs/harnesses.md](docs/harnesses.md#test-record) has the details).

Not verified yet:
- Triggering on other agents. The test sets are in each skill's `evals/trigger-eval.json`.
- Test runs on Antigravity, Gemini CLI, GitHub Copilot, OpenCode and Cursor; [docs/harnesses.md](docs/harnesses.md) shows how to probe one first.
- macOS, an end-to-end `npx skills add` install, and installing from the release files.
- The refiner's fresh-context review before it shows you a lesson; it needs an agent that can start subagents.

## Dogfooded

rotless maintains itself with its own tools, and every skill has its own `rotless.json` and field-notes footer. That has produced 32 lessons so far, from real use and from code reviews. Each lesson has a check that failed before its fix and passes now, and CI runs all of them. The first came from the refiner itself: it caught the modernizer failing to start npm-installed CLIs on Windows. Each skill's `references/lessons.md` lists its lessons.

## More

- [Agents](docs/harnesses.md): installing and calling the skills in each agent, and the test record.
- [Privacy](docs/privacy.md): what runs, what it sends, and what is stored.
- [FAQ](docs/faq.md): how rotless differs from Anthropic's skill-creator and from memory tools, cost, and version 0.1.
- [Releases](docs/releases.md) and the [changelog](CHANGELOG.md).
- [Contributing](CONTRIBUTING.md), and [AGENTS.md](AGENTS.md) for coding agents working on this repo.

## License

MIT, except `skills/rotless-skill-creator`, which is a modified version of Anthropic's skill-creator under Apache-2.0. Its `LICENSE.txt` and `NOTICE` list the changes.
