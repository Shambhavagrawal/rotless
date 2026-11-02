# Contributing to rotless

Bug reports, fixes and ideas are welcome. Open an issue first for anything larger than a fix, so we can agree on the approach before you write it.

## Setup

You need Python 3.10 or later and the [GitHub CLI](https://cli.github.com) logged in. There's nothing to install: every script uses the standard library.

## Checks

Run this from the repo root before opening a pull request. CI runs the same script on Linux and Windows, and a release runs it again before building.

```bash
python tests/run_checks.py
```

It runs the repo check (`tests/check_repo.py`), each skill's self-tests and lesson checks, `keeper.py lint`, strict validation of every skill, and a trial build of the release files.

These need no network and no agent CLI. Two more checks call live services and stay local, because they need tokens and quota: `keeper.py check <skill>` (after `keeper.py own <skill>`) and the creator's test runs.

## Developing in your agent's skills folder

If you work on the skills where your agent loads them, for example `~/.claude/skills`, copy them into the repo before committing:

```bash
python scripts/sync_skills.py --dry-run   # what would change
python scripts/sync_skills.py             # copy, then run the checks
```

Use `--from <folder>` for another skills folder. It copies only the skills already in `skills/`, leaves out caches, test workspaces and drafts, stores text with LF line endings, and won't overwrite uncommitted changes.

## What a good pull request has

- One change, explained in a few sentences.
- For a bug fix, a check that fails before the fix and passes after, and an entry in the skill's `references/lessons.md`. [AGENTS.md](AGENTS.md) describes how.
- `rotless.json` updated if the skill's dependencies changed.
- A line in `CHANGELOG.md` for anything a user would notice.
- Plain prose in docs and skills, without dashes, decorative bold or slogans.

[AGENTS.md](AGENTS.md) lists the rules the checks don't cover, such as files that stay untouched and sentences other files depend on.

## AI-assisted contributions

Using an agent is fine; most of this repo was written with one. You stay responsible for every line:

- Read and understand the whole change before you submit it.
- Run the checks yourself and say in the pull request that you did.
- Answer review comments in your own words; don't paste a model's reply.
- Say in the pull request that an agent helped, and which one.

## Reporting a problem with a skill

Use the bug report template. The most useful reports name the skill, the agent and its version, what you asked, what happened, and the exact command output or field note.

## License

Contributions are under the repo's license: MIT, except `skills/rotless-skill-creator`, which is Apache-2.0 (see its `NOTICE`).
