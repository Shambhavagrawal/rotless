# FAQ

## Why not just use Anthropic's skill-creator?

rotless-skill-creator is a fork of it, so the method is the same: interview, draft, test with and without the skill, review, tune the description. The fork runs its tests on other agents' CLIs as well as Claude Code's, starts from a failing baseline, and checks portability. It is also one step of four. The original stops when the skill ships, and skills go wrong after that, when the tools they describe change or when real use shows a gap.

## How is this different from tools that remember corrections?

Tools such as claude-reflect capture your corrections and write them into memory, instruction files or a skill's text. The refiner also changes the skill itself, but every lesson comes with a check that would have caught the problem. The check fails on the old skill and passes on the new one, and every later change must keep it passing, so the same mistake can't come back unnoticed.

## Does each skill work on its own?

Yes. When the others are installed, each hands off to them; when they aren't, it does that step itself or tells you what to do by hand.

## When should I run the modernizer?

Whenever you like: after upgrading a tool a skill uses, or when you notice something changed. Nothing runs on a schedule. You don't have to keep track, though: each skill built with rotless records when it was last updated and checked, and once that's more than 15 days ago (adjustable per skill with `remindAfterDays` in its `rotless.json`) it offers a check at the end of a task.

## Does anything leave my machine?

Only the calls you ask for: searches by the research skill, the modernizer's checks, and test runs through your own agent. There is no telemetry and no hosted service. [privacy.md](privacy.md) lists every call and what is stored locally.

## Will it edit my skills without asking?

No. Every edit is shown to you first, with its evidence and its check, and is applied only if you approve. Skills written by someone else are never edited; the refiner drafts an issue for their author instead.

## Do test runs cost anything?

They are real sessions with your agent, so they use your plan's quota or API credits. The trigger tests run each query several times.

## What is rotless.json?

The list of everything outside a skill that the skill relies on: CLIs and the subcommands it uses, APIs and the fields it reads, MCP servers, docs, repos and limits, each with a check. Older skills may call the file `keeper.json`; both names work.

## Which agents does it support?

Any agent that reads `SKILL.md` can load the skills. Test runs have been verified on Claude Code and Codex. [harnesses.md](harnesses.md) has the details and the test record.

## Why version 0.1?

The skill names, the `rotless.json` format and the commands may still change, and how reliably each skill triggers hasn't been measured yet. 1.0 will mean those are stable.
