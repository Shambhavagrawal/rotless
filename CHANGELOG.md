# Changelog

## Unreleased

- rotless-skill-creator step 7: trigger queries must not hand the agent a file to open, since trigger runs get none; the creator's own trigger set now passes 20/20 on Claude Code.

## 0.2.0 (2026-11-02)

- Skills remind you to check them: `rotless.json` records when a skill was last `updated` and `checked`, and when both are more than `remindAfterDays` old (15 by default) the skill offers a modernizer check at the end of a task. New `keeper.py updated` command; `list` and `status` show each skill's age.
- New repos found in a skill's space stay listed in every check until reviewed, and the modernizer offers to research what to borrow from them.
- README diagram shows modernize as an on-demand loop beside refine.
- The reminder asks `keeper.py status` once per session, so only skills you own remind you; rotless's own skills no longer ask everyone who installs them. It also stays out of replies that must be machine-readable.
- Trigger tests stop as soon as the skill loads: the test copy only prints its token, since agents choose a skill from its description (a probe now takes 14 seconds). On Claude Code they leave your own installed skills out, so an installed copy can't answer for the test copy. Each skill's trigger set now has 20 queries; on Claude Code 2.1.316, 79 of 80 were right.
- The eval review server accepts feedback only from its own page (another site could write `feedback.json` before) and no longer kills whatever else uses its port. The review pages use system fonts and say "your agent session" instead of naming one agent.
- `run_case.py` notices input files rewritten within the same timestamp, and lists deleted ones in `deleted-files.txt`.
- Replacing a multi-paragraph `description: |` in a test copy no longer leaves its later paragraphs behind.
- `scripts/sync_skills.py` refuses to copy when a source skill lacks a folder the repo has (such as `evals/` in a skill installed from a `.skill` file), since the copy would delete it.
- Research scripts: `ghverify.py` ignores non-GitHub URLs and GitHub's own pages (topics, orgs…), `srcsweep.py --repos` drops those pages too, and a slash in a query no longer breaks the AUR search.

## 0.1.0 (2026-11-02)

First release.

- rotless-github-research: prior art from GitHub code, repos, commits and issues, plus 21 other sources including Hugging Face papers, with each GitHub repo verified.
- rotless-skill-creator: an agent-agnostic fork of Anthropic's skill-creator. It starts from a failing baseline, runs test cases and trigger tests through each agent's headless CLI (verified on Claude Code and Codex), and checks the spec and portability.
- rotless-skill-modernizer: `rotless.json` manifests, drift checks, explicit ownership before any check runs code, and an offline `lint` for CI. It still reads manifests named `keeper.json`, the earlier name.
- rotless-skill-refiner: field notes from real use, and retros that turn them into fixes and optimizations, each with a check.
- rotless-skill-refiner gets a second opinion before it shows you a lesson: a fresh subagent that sees only the notes, the diff and the checks re-runs the safety scan and challenges the lesson. Not measured yet.
- The skills use the sibling skills installed next to them, never another install or an older plugin-cache version.
- Installs as a Claude Code plugin, a Codex plugin (verified) and with the skills CLI. Each release also carries a plugin ZIP, one `.skill` file per skill and SHA256SUMS, built and checked by `scripts/build_release.py`.
- `tests/run_checks.py` runs every offline check; CI and releases use it. `tests/check_repo.py` checks links, file paths in the skills, manifest agreement and Codex listing limits.
- 32 recorded lessons, each with a check that CI runs on Linux and Windows.
