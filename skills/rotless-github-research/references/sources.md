# Off-GitHub discovery routes

`scripts/srcsweep.py` already queries most of the routes below in parallel and prints a searched / NOT REACHED ledger. This file holds endpoint details, manual follow-ups, and the sources with no search API (PyPI: per-name only, `https://pypi.org/pypi/<name>/json`; Homebrew; pkg.go.dev; Product Hunt; Reddit).

Gotchas found by testing: the MCP Registry matches names only (the word `github` matches every `io.github.*` namespace, so use a distinctive word) and lists each server once per version (dedupe by name). Registries AND all terms, so keep queries to 1-3 words. Keyword hits are literal: "repository discovery" also returns Hex's "Common Locale Data Repository", and judging relevance is up to you.

All endpoints below were tested and return unauthenticated JSON. Use `curl -s -A "rotless-github-research"` (or a web-fetch tool). Code hosted outside GitHub is still prior art, and packages usually link their source repo.

| Route | Endpoint | Notes |
|---|---|---|
| GitLab | `https://gitlab.com/api/v4/projects?search=<q>&per_page=50&order_by=last_activity_at` | `.path_with_namespace`, `.web_url`, `.last_activity_at`, `.star_count` |
| Codeberg / Forgejo | `https://codeberg.org/api/v1/repos/search?q=<q>&limit=50` | `.data[].full_name` |
| npm | `https://registry.npmjs.org/-/v1/search?text=<q>&size=50` | `.objects[].package.{name,links.repository}`; broad terms match huge counts, so use specific ones |
| crates.io | `https://crates.io/api/v1/crates?q=<q>&per_page=50` | `.crates[].{name,repository,recent_downloads}` |
| PyPI | no search API (HTML only, bot-challenged) | use web search `site:pypi.org <q>`; for a known name, read `.info.project_urls` from `https://pypi.org/pypi/<name>/json` |
| pkg.go.dev / RubyGems | web search `site:pkg.go.dev <q>`; `https://rubygems.org/api/v1/search.json?query=<q>` | |
| MCP Registry | `https://registry.modelcontextprotocol.io/v0/servers?search=<one-word>&limit=50` | one word works best; `.servers[].server.{name,repository.url}` |
| skills.sh | `https://skills.sh/api/search?q=<q>` | semantic search over agent skills; `.skills[].{source,skillId}` |
| gh skill search | `gh skill search <term> --json repo,skillName,stars,description` | uses the code-search quota (10/min), so budget it together with your code searches |
| Claude plugin marketplaces | code search `filename:marketplace.json path:.claude-plugin <term>` | |
| Hugging Face | `https://huggingface.co/api/models?search=<q>&limit=20`, `/api/datasets?search=`, `/api/spaces?search=` | models, datasets and demos often link the training or inference repo |
| HF Papers (arXiv) | `https://huggingface.co/api/papers/search?q=<q>` | the Papers With Code API is dead (2025); for a known arXiv ID, also code-search the ID (`2401.12345`) and the paper title |
| Hacker News | `https://hn.algolia.com/api/v1/search?query=<q>&tags=show_hn` | Show HN posts link repos, and the comments hold launch-day criticism (`tags=story` for all stories) |
| Product Hunt, Reddit, dev.to | web search `site:producthunt.com <q>` etc. | commercial and non-OSS prior art |
| Domain venue | web search | RFCs, standards bodies, regulator guidance, academic venues: the neighbouring discipline that solved it first |

Cross-language ports: also search `<known name> rust|go|python|port|clone|rewrite`.
