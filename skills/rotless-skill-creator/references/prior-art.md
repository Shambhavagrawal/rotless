# Prior art: rotless-skill-creator (agent-agnostic skill creator)
_date: 2026-11-02 · verdict: Fork & adapt anthropics/skills skill-creator (Apache-2.0) behind a per-agent runner adapter; blend in superpowers' RED gate and spec validation_

## Verdict
Fork & adapt: Anthropic's skill-creator has the best method (an interview, a draft, runs with and without the skill, grading, a review viewer, then the description loop) and is Apache-2.0, so a fork is allowed if we keep its LICENSE, add a NOTICE and mark changed files. Its runners are Claude-only (`claude -p`, `.claude/commands`, `select` on pipes that breaks on Windows).
Borrow: superpowers' RED gate ("no skill without a failing test first") and "match the form to the failure"; antongulin's port pattern (one headless call per agent, parse its skill-load events); skills-ref's spec rules, reimplemented in stdlib; SkillForge's static trigger lint as the fallback for agents without a headless CLI.
Gap (verified across the routes below): no trigger evaluator works across agents, nothing lints a skill for Claude-only frontmatter, nothing makes a new skill carry a usage-feedback footer for later refining.
Fallback: if a fork is unwanted, write a clean-room creator modelled on openai/skills' simpler 6-step creator plus superpowers' method.

## Repos
| repo | role | ★ | last substantive commit | license | take |
|---|---|---|---|---|---|
| `anthropics/skills` | direct match | 186501 | 2026-10-28 | Apache-2.0 (skill LICENSE.txt) | fork the method, `skills/skill-creator/references/schemas.md`, `skills/skill-creator/agents/grader.md`, `skills/skill-creator/scripts/run_loop.py` (train/holdout split); replace `skills/skill-creator/scripts/run_eval.py` runner |
| `openai/skills` | direct match | 28457 | 2026-06-24 | Apache-2.0 | `skills/.system/skill-creator/scripts/init_skill.py` scaffold flags; degrees-of-freedom guidance; no evals (avoid as sole basis) |
| `obra/superpowers` | borrowed idea | 310821 | 2026-10-20 | MIT | `skills/writing-skills/SKILL.md` RED/GREEN/REFACTOR, pressure scenarios, rationalisation tables, match-form-to-failure |
| `antongulin/opencode-skill-creator` | adjacent (port) | 192 | 2026-10-01 | Apache-2.0 | `plugin/lib/run-eval.ts` pattern: headless run + tool_use parsing, isolated temp skill, conflict guard, failure taxonomy |
| `agentskills/agentskills` | borrowed idea | 26862 | 2026-08-09 | Apache-2.0 | `skills-ref/src/skills_ref/validator.py` rules (fields, name, lengths), reimplement in stdlib |
| `tripleyak/SkillForge` | partial | 916 | 2026-07-29 | MIT | `scripts/run_skill_evals.py` static trigger lint (fallback), triggers.json with near_miss/holdout; avoid its single-skill simulated router |
| `alibaba/skill-up` | adjacent | 1408 | 2026-10-27 | Apache-2.0 | optional heavy eval backend: multi-engine (claude_code, codex, qwen…), baselines, rule_based judges, imports evals.json |
| `rpamis/comet` | adjacent | 3263 | 2026-11-01 | unknown | skill harness for evaluated workflows; not deep-read |

## Queries
- `skill creator`
- `skill-creator`
- `skill authoring`
- `topic:skill-creator`
- `filename:SKILL.md "name: skill-creator"`
- `filename:SKILL.md "name: writing-skills"`

## Ledger
- Repo search (ghsweep, 9 wordings, 2026-11-02): skill creator 3171, skill-creator 2592, create skills 60662, skill builder agent 1014, writing skills 8815, skill authoring 1886, SKILL.md generator 53, topic:skill-creator 70, meta skill 2415.
- Code search: `name: skill-creator` 12560 SKILL.md files (mostly vendored copies of Anthropic's), `name: writing-skills` 2828.
- skills.sh: anthropics, openai, vercel-labs/json-render skill-creators. npm: opencode-skill-creator, jixoai/skill-creator, @allanyiin/skill-creator-advanced. HN: "Improving skill-creator" (Anthropic blog), forks.
- Verified with ghverify.py; deep reads via gh at pinned SHAs (anthropics ca45fc496a, openai 49f948faa9, superpowers 2ce8aa15d0, opencode-skill-creator d4383924e3, skill-up 99894b35a2, SkillForge 4fc8bb486a, agentskills 69ef37e942).
- Unavailable: code search hit its 10/min limit once (switched to grep.app). Not read: Anthropic grader/comparator prompts in full, skill-up Go source, SkillForge compile_skill.py.
