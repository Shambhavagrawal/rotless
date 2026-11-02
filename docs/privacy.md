# Privacy and data handling

rotless has no hosted service, no account and no telemetry. It is a set of skills and standard-library Python scripts that run on your machine, inside the agent you already use. Your agent's own terms cover what it sends to its model provider.

## What runs, and when

Nothing runs in the background. Every network call happens because you asked for something:

| Skill | Calls | Sends |
|---|---|---|
| rotless-github-research | the GitHub API through your logged-in `gh`, grep.app, and public package registries and sites (npm, crates.io, Docker Hub, Hugging Face, Hacker News and others) | your search terms |
| rotless-skill-creator | your agent CLI (`claude -p`, `codex exec`…) for test runs | test prompts, with the skill under test installed in a throwaway folder |
| rotless-skill-modernizer | the GitHub API, and the URLs, registries and CLIs listed in a skill's `rotless.json` | requests those checks need |
| rotless-skill-refiner | nothing; it reads and writes local files | |

rotless-skill-creator's review pages use your system fonts. The results viewer loads one file from the web, the SheetJS library from cdn.sheetjs.com (one pinned version, checked against its hash), to show spreadsheet outputs. Your browser fetches it when you open the page, and your results stay on your machine. The local review server answers only requests from its own page, so another website open in your browser can't write to your feedback file.

Test runs are real agent sessions on your account, so they use your quota. The research skill's rules tell the agent never to put your private repo names, tokens or file contents into a search, and to leave private repos out of its reports.

## What is stored

The modernizer and refiner keep a local git repository, the registry: `skill-registry/` next to your skills folder if one exists there, otherwise `~/.skill-registry` (or `$SKILL_REGISTRY`). It holds:

- check results and history for each skill you own,
- the list of skills you marked as yours,
- field notes about your skills, and
- snapshots of a skill taken before an edit.

Nothing in it is pushed or uploaded. Field notes are redacted before they're saved: GitHub tokens, API keys, AWS keys, Slack tokens, bearer headers, private keys and `token=` or `"password": …` style values are replaced with `[REDACTED]`. Treat the redaction as a safety net and avoid pasting secrets into notes.

To remove everything rotless stored, delete the registry folder.

## What changes in your skills

The skills edit a skill only after you approve the change. They never edit a skill someone else wrote; for those, the refiner drafts an issue for you to post.
