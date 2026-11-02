# Changelog

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
