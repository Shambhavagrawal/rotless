# Releases

## Versions

The version lives in `plugin.json` at the repo root, and the Claude and Codex manifests repeat it. `tests/check_repo.py` fails when they disagree, so CI catches a half-done bump.

rotless follows semantic versioning, with the usual rule before 1.0: a patch release (0.1.1) is a compatible fix, a minor release (0.2.0) may add features or change behaviour. 1.0 comes once the skill names, the `rotless.json` format and the commands are stable and the trigger tests have been measured.

## Making a release

1. Update the version in `plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` and `.codex-plugin/plugin.json`.
2. Add a section for the version to `CHANGELOG.md`; it becomes the release notes.
3. Run `python tests/run_checks.py`, push to `main`, and wait for CI to pass.
4. Tag the commit and push the tag:

   ```bash
   git tag -a v0.1.0 -m "rotless 0.1.0"
   git push origin v0.1.0
   ```
5. The release workflow runs the checks again, refuses a tag that doesn't match `plugin.json`, builds the files below, verifies their checksums, and creates a draft release. Read the draft, then publish it.

Never move or reuse a tag that has been pushed; fix forward with a new patch release.

## What a release contains

- `rotless-<version>.zip`: the whole plugin, for apps that install a plugin from a file.
- `<skill>.skill`, one per skill: a single skill for apps that install skills from a file. Test cases (`evals/`) are left out.
- `SHA256SUMS`: checksums of those files.

`python scripts/build_release.py --out <empty folder>` builds the same files locally.
