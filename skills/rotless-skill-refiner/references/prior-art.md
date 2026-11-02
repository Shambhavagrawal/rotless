# Prior art: rotless-skill-refiner (usage-time skill improver)
_date: 2026-11-02 · verdict: Build. The space is saturated with capture-and-memory tools, but none turns one observed gap into a patch to the skill itself plus a regression check for that gap, behind a human gate, without hooks_

## Verdict
Build, blending proven parts. The verified gap: on one correction or failure, no tool edits the skill's own SKILL.md/scripts and also writes a persistent check tied to that lesson that every later pass must keep passing. claude-reflect edits skills but adds no check; pro-workflow and skillmaxxing gate on an eval set that must already exist and never add a case per lesson; selftune's evals are mostly routing; ratchet-harness adds a test per lesson, but for repo code, not skills.
Borrow: ACE/kayba rule shape and delta ops (trigger + action, near-duplicate search, counters as evidence only); GEPA strict-improvement acceptance; claude-reflect's regex pre-filter + LLM confirm and its skill-vs-memory routing; skillmaxxing's typed bounded edits and promote/revert; pro-workflow's edit budget and rejection buffer (ideas only, no LICENSE file); ratchet-harness's "add the guard before the fix"; hermes' growth caps (ideas only, no LICENSE file); SafeEvolve's write-time and load-time safety check; WikiSkill's lessons ledger kept apart from the skill.
Avoid: hooks and daemons as the core (most common bug class: Windows, env vars, silent data loss), autonomous overwrites on an LLM score (SkillClaw, pro-workflow optimizer), whole-text rewrites (context collapse), unbounded memory files (bloat).
Differentiator: hook-free capture through a footer inside each owned skill; one check per lesson, failing on the old skill and passing on the new; shared checks with rotless-skill-modernizer so one `check` runs the whole ratchet; preferences routed to the user's memory instead of the shared skill; for other people's skills, a drafted upstream issue instead of an edit.

## Repos
| repo | role | ★ | last substantive commit | license | take |
|---|---|---|---|---|---|
| `BayramAnnakov/claude-reflect` | direct match (capture) | 1915 | 2026-10-03 | MIT | `scripts/lib/reflect_utils.py` correction regex tables + false-positive filters; `commands/reflect.md` skill-vs-CLAUDE.md routing; avoid guardrail-before-FP ordering (#43) |
| `rohitg00/pro-workflow` | direct match (apply) | 2940 | 2026-09-29 | none (MIT in package.json only) | ideas only: `skills/skill-optimizer/SKILL.md` edit budget 3/2/3, frozen held-out set from past corrections, rejection buffer; avoid auto-overwrite |
| `Bennyoooo/skillmaxxing` | direct match (gate) | 24 | 2026-10-17 | MIT | `skill-maxing-plugin/skills/optimize-skill/SKILL.md` typed edits (op, target, sourceType), trusted:false until promoted; `src/eval/schema.ts` |
| `selftune-dev/selftune` | partial | 18 | 2026-09-02 | MIT | `packages/runtime/evolution/validate-proposal.ts`, `packages/runtime/evolution/rollback.ts`; "regex only prioritizes review" |
| `affaan-m/ECC` | partial | 295013 | 2026-10-30 | MIT | `skills/continuous-learning-v2/agents/observer.md` confidence + decay for deciding which gaps are real; never edits existing skills |
| `kayba-ai/agentic-context-engine` | borrowed idea | 2605 | 2026-09-21 | Apache-2.0 | `ace/implementations/prompts.py` SkillManager rules (one trigger + one action, 15-50 words, 4-condition broadening gate); `ace/core/skillbook.py` rule record with counters; `ace/deduplication/prompts.py` |
| `ace-agent/ace` | borrowed idea | 1418 | 2026-08-24 | Apache-2.0 | `ace/prompts/reflector.py`, `ace/prompts/curator.py` delta-only curation |
| `gepa-ai/gepa` | borrowed idea | 7242 | 2026-10-31 | MIT | `src/gepa/strategies/instruction_proposal.py` reflection prompt; `src/gepa/strategies/acceptance.py` strict-improvement acceptance |
| `NousResearch/hermes-agent-self-evolution` | adjacent | 5624 | 2026-06-17 | none | ideas only: `evolution/core/constraints.py` size cap, at most 20% growth, PR not commit |
| `ECNU-ICALK/AutoSkill` | adjacent | 609 | 2026-05-10 | none (MIT badge only) | ideas only: four-way triage discard/improve/merge/create, patch-version bump |
| `AMAP-ML/SkillClaw` | adjacent (cautionary) | 2737 | 2026-10-21 | MIT | failure modes: autonomous rewrite, config mutation (#71), path traversal (#68) |
| `ZainRizvi/git-workflow-guards` | borrowed idea + name collision | 0 | 2026-10-31 | MIT | `skills/ratchet-harness/SKILL.md` guard before fix, rules never silently removed; owns the names ratchet-retro and ratchet-harness |
| `alibaba/skill-up` | adjacent | 1408 | 2026-10-27 | Apache-2.0 | evaluation + evolution engine; possible optional backend for running refiner checks |

## Queries
- `self-improving skills`
- `self-evolving skills`
- `learn from corrections`
- `skill evolution`
- `claude reflect`
- `agentic context engineering`
- `filename:SKILL.md "learn from corrections"`
- `filename:SKILL.md "retrospective" "update the skill"`

## Ledger
- Repo search (ghsweep, 11 wordings, 2026-11-02): self-improving skills 539, self-evolving skills 434, skill evolution 983, learn from corrections 228, continuous learning claude 62, claude reflect 291, agent retrospective 212, lessons learned agent 90, agentic context engineering 1506, reflective prompt evolution 9, skill feedback loop 241.
- Code search: `"learn from corrections"` 309 SKILL.md, `"self-improving" skill` 6640, `continuous-learning` 6832 (mostly ECC copies), `retrospective "update the skill"` 60.
- skills.sh: self-improving-agent (alirezarezvani, borghei, volces), learn-from-corrections, pro-workflow skill-optimizer, nicknisi autoskill, skill-evolution-manager. npm: @metaharness/flywheel, ornn-skills, @dsh-cc/command-learn. HN: wienerdog, luml-ai/dreamer, Samurai412/autoskill, dri.es "Self-Improving AI Skills".
- Papers: arXiv 2608.12851 "Practice Makes Unsafe: Skill Misevolution" (all 21 agent x method combos wrote unsafe skills; SafeEvolve write+retrieval checks cut harm 21.3% to 4.0%), arXiv 2608.27454 WikiSkill, arXiv 2603.01145 AutoSkill. Abstracts only.
- Name check: ratchet taken (ratchet-retro, ratchet-harness); kaizen 779 SKILL.md, hone 544, whetstone 22; skill-hone and skill-kaizen 0. Chosen name: rotless-skill-refiner (repo prefix makes it unique).
- Not deep-read (not verified, listed only): wienerdog-ai/wienerdog, luml-ai/dreamer, Samurai412/autoskill, hao-cyber/skill-evolution, haddock-development/claude-reflect-system, jose-compu/self-improving-skills.
- Unavailable: code search 10/min limit hit once (switched to grep.app).
