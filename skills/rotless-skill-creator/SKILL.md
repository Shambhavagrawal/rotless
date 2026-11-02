---
name: rotless-skill-creator
description: Create new agent skills (SKILL.md) and improve existing ones, for any agent - Claude Code, Codex, Gemini CLI, Cursor, GitHub Copilot, OpenCode. Runs the whole rotless flow - prior art with rotless-github-research, a failing baseline first, interview, draft, test cases run with and without the skill, human review, trigger tuning, spec and portability validation, then a keeper.json through rotless-skill-modernizer and a field-notes footer for rotless-skill-refiner. Use whenever the user wants to make, write, build, scaffold, edit, test, benchmark or package a skill, turn a workflow into a skill, or fix when a skill triggers, even if they only say "make this a skill".
license: Apache-2.0. Modified from Anthropic's skill-creator; see LICENSE.txt and NOTICE.
---
<!-- Modified by rotless contributors (2026) from Anthropic's skill-creator (Apache-2.0). Changes are listed in NOTICE. -->

# rotless-skill-creator

Creates skills and improves them, on whatever agent you're running in. The loop:

1. Find out whether it already exists, and what to borrow.
2. Show a failure without the skill: what goes wrong today that the skill must fix.
3. Interview, then draft the skill.
4. Run realistic test prompts with and without the skill; the user reviews the outputs.
5. Improve, rerun, repeat until the user is happy.
6. Tune the description so the skill triggers when it should, and only then.
7. Validate, write its `keeper.json`, add the field-notes footer.

Work out where the user is in this loop and pick up from there. Someone with a draft goes straight to testing; someone who says "no evals, just vibe with me" gets that. Match your vocabulary to the user: explain "assertion" or "JSON" briefly unless they clearly know them.

## The rotless family

Four skills, each usable alone; when the others are installed, hand off to them:

| Skill | Role | When this skill uses it |
|---|---|---|
| **rotless-github-research** | prior art: does it exist, what to borrow, where the gap is | step 0, before any drafting |
| **rotless-skill-creator** (this) | build, test and tune a skill | |
| **rotless-skill-modernizer** | records what the skill relies on in `keeper.json`; `check` catches drift when the outside world changes | step 8, and whenever you edit a skill that has a `keeper.json` |
| **rotless-skill-refiner** | learns from real use: gaps logged while the skill is used become small edits, each with a check | the footer you add in step 8 feeds it; its behaviour checks run through this skill's `run_case.py` |

If a sibling isn't installed, do its step by hand and say so: search for prior art yourself, list the skill's dependencies in your summary.

## Finding things

- `C` = this skill's folder (the one holding this SKILL.md; Claude Code prints it as "Base directory for this skill"). Scripts are `$C/scripts/…`; run them with `python` (`python3` where `python` is Python 2).
- Sibling skills normally sit next to this folder; otherwise look in your agent's skills folders.
- `python $C/scripts/harness.py agents` lists the agent CLIs on this machine and which ones are verified for headless runs.

## How tests run on your agent

Test runs need a fresh agent that sees only the task. Pick the first mode that works:

| Mode | When | How |
|---|---|---|
| **A. Subagents** | your agent can spawn subagents | spawn one per run, as below |
| **B. Headless CLI** | an agent CLI is installed (`harness.py agents`) | `run_case.py` per run; `run_eval.py` for trigger tests. Verified: Claude Code (`claude -p`) and Codex (`codex exec`). For any other CLI, run `harness.py probe --agent <name>` first |
| **C. In-session** | neither | do each test yourself, one at a time, following the skill. Skip baselines and say the result is weaker: you wrote the skill, so you're not a fresh reader |

Modes A and B can mix: e.g. talk in Cursor, run tests on Codex. Mode B installs a temporary copy of the skill into every known project skills folder of a throwaway workspace, so you don't need to know which folder a given agent reads. File-writing runs need a workspace-scoped write mode, which today only Claude Code and Codex have; on other CLIs use mode A or C for those cases rather than an allow-everything flag.

---

## Step 0: Local first, then prior art

1. Look through the user's skills folders: if one of their skills already covers this, offer to improve it instead.
2. Use **rotless-github-research** on the idea (full method when it's a build-or-reuse decision). Create `<skills folder>/<name>/references/` (kebab-case name; the user's skills folder, or a project's skills folder for project-only skills) and ask it to write `references/prior-art.md` in the shape **rotless-skill-modernizer** defines under *prior-art.md*. That file feeds steps 1 and 8.
3. **Gate:** show the verdict. *Use* or *contribute* means stop or adapt an existing tool; *blend* or *build* means continue, carrying "borrow X, avoid Y, fill gap Z".

## Step 1: Capture intent

The conversation may already hold the workflow ("turn this into a skill"): extract the tools used, the steps, the corrections the user made, the input and output formats. Then confirm, and fill gaps:

1. What should the skill let the agent do?
2. When should it trigger (what users say, in what contexts)?
3. What's the expected output?
4. Should it have test cases? Objectively checkable outputs (file transforms, extraction, code, fixed steps) benefit; subjective ones (style, art) often don't. Suggest a default; the user decides.

Then interview: edge cases, input and output formats, example files, success criteria, and **every external thing the skill will rely on** (CLIs, APIs, MCP servers, docs, repos, limits). That list becomes its `keeper.json` in step 8. Research what you can (docs, MCP servers, subagents) so the user isn't doing your homework.

## Step 2: The failing baseline (no skill without a failure first)

Before writing, show what goes wrong without the skill. Run 2 or 3 realistic prompts with no skill (any mode above) and record exactly what the agent does wrong, in its own words where it rationalises. Under pressure (time, sunk cost, authority, "it's just a quick one") is where agents cut corners, so combine a couple of pressures in at least one prompt. If the baseline already does the job, say so: the skill may not be needed, or it's a reference pack whose value is knowledge the agent lacks.

The recorded failures are what the skill must answer, and the first test cases. This step comes from obra/superpowers' *writing-skills* (MIT): its "match the form to the failure" table is worth reading when a fix doesn't stick (rule-breaking needs a prohibition plus the excuse it closes; a wrong output shape needs a positive recipe; a missing element needs a template slot).

## Step 3: Write the SKILL.md

- **name**: kebab-case, matches the folder, at most 64 characters.
- **description**: what it does AND when to use it; all the "when" goes here, not in the body. Agents tend to under-trigger skills, so be a little pushy: "…Use whenever the user mentions X, Y or Z, even if they don't say 'X'". At most 1024 characters, no angle brackets.
- **Frontmatter stays portable**: only `name`, `description`, `license`, `compatibility`, `metadata` (string values), `allowed-tools`. Agent-specific fields make other agents reject the skill; extra data goes under `metadata`.

### Anatomy

```
skill-name/
├── SKILL.md              (required: frontmatter + instructions)
├── scripts/              executable code for deterministic or repeated work
├── references/           docs loaded when needed (prior-art.md, lessons.md…)
├── assets/               templates, icons, fonts used in output
├── evals/                test cases (step 4)
└── keeper.json           what the skill relies on (step 8)
```

Progressive disclosure: name and description are always in context (~100 words), the body when the skill triggers (keep it under 500 lines), bundled files only when needed. Point clearly to each reference file and say when to read it; give long references a table of contents. A skill covering several variants (AWS/GCP/Azure) keeps the selection logic in SKILL.md and one reference file per variant.

### Writing it so any agent can follow it

- Say what to do, not which tool to click: "search the web", "ask the user", "spawn a subagent if you can, otherwise…". Agent-specific tool names, paths or syntax only as one labelled example among others.
- Scripts: standard library where possible, `encoding="utf-8"` on every file read and write, prompts and paths as arguments rather than shell strings, so they work on Windows too.
- Paths relative to the skill folder ("the folder containing this SKILL.md"), never a user's home layout.
- Imperative voice. Explain why things matter instead of stacking MUSTs; if you write ALWAYS or NEVER in capitals, reframe it with the reason. Examples help; keep them general rather than overfitted to the test prompts.
- No malware, no hidden behaviour, nothing that would surprise the user if described. "Roleplay as X" skills are fine.

Draft, then reread it with fresh eyes and tighten.

## Step 4: Test cases

Write 2 or 3 realistic prompts, the kind a real user types, starting from the step 2 failures. Share them: "Here are the test cases I'd like to try. Do these look right, or do you want to add more?"

Each case is a folder under the skill's `evals/` (format in `references/schemas.md`; read its *Test cases* section before writing the first one and copy its templates, the format is strict):

```
evals/flags-negative-quantity/
├── prompt.md       settings block, then the user's prompt
├── case.yaml       name and what a good result looks like
├── graders/        one statement per file; a placeholder until step 5
└── files/          input files, only if needed
```

An older skill may have `evals/evals.json`: its tests still count; run them alongside the case folders and never edit, convert or delete that file unless asked.

## Step 5: Run and evaluate

One continuous sequence: don't stop halfway. Results go in `<skill-name>-workspace/` next to the skill folder, by iteration and case name (keep names stable across iterations; the viewer matches runs by path):

```
<skill-name>-workspace/iteration-1/<case-name>/
├── eval_metadata.json     {"eval_name", "prompt", "assertions": []}
├── with_skill/            outputs/, grading.json, timing.json
└── without_skill/         the baseline (old_skill/ when improving a skill)
```

1. **Launch every run in one go**, with-skill and baseline together so they finish together. Baseline: no skill for a new skill; a snapshot of the old version (`cp -r <skill> <workspace>/skill-snapshot/`) when improving one.
   - Mode A, to each subagent: skill path, task, input files, where to save outputs, which outputs matter.
   - Mode B: `python $C/scripts/run_case.py --agent <cli> --case <skill>/evals/<case> [--skill-path <skill>] --out <workspace>/iteration-N/<case>/with_skill [--allow-writes]`; leave out `--skill-path` for the baseline.
   - Write each case's `eval_metadata.json` now, fresh every iteration: the viewer takes the prompt from it.
2. **While runs go, draft assertions**: objectively checkable statements with names that read well in a report ("summary.md states a total revenue of 693.5", about the result, not where it's saved). One file each in the case's `graders/`, same sentences in `eval_metadata.json`. Leave subjective cases to human judgment. Explain to the user what they'll see.
3. **Capture timing** as each run ends into the run's `timing.json` (`total_tokens`, `duration_ms`, `total_duration_seconds`). Subagent notifications carry these and are the only chance to save them; `run_case.py` writes duration and leaves tokens null.
4. **Grade** each run against its assertions (read `agents/grader.md`; script anything checkable rather than eyeballing it). `grading.json` uses the fields `text`, `passed`, `evidence` exactly; the viewer depends on them.
5. **Aggregate**: `python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>` from `$C`, giving `benchmark.json` and `benchmark.md` (pass rate, time, tokens; mean ± stddev; with-skill listed before baseline).
6. **Analyst pass** (`agents/analyzer.md`): assertions that pass either way, high-variance cases, time and token trade-offs. Append notes to `benchmark.json`'s `notes`.
7. **Open the viewer before judging anything yourself**, so the user sees outputs first:
   `python $C/eval-viewer/generate_review.py <workspace>/iteration-N --skill-name <name> --benchmark <workspace>/iteration-N/benchmark.json` (add `--previous-workspace <workspace>/iteration-N-1` from iteration 2). No browser or display: add `--static <file>.html` and give the user the path; their "Submit All Reviews" then downloads `feedback.json`.
8. Tell the user: "The Outputs tab lets you step through each case and leave feedback; Benchmark shows the numbers. Come back when you're done."
9. Read `feedback.json` (empty feedback means fine), and stop the viewer server if one is running.

## Step 6: Improve

- **Generalise from feedback.** The skill will run on far more prompts than these few; avoid fiddly overfitted fixes and oppressive MUSTs. If something resists, try a different framing or metaphor.
- **Keep it lean.** Read the transcripts, not just the outputs; cut what makes the agent waste effort.
- **Explain the why**, so the agent can handle cases the rules don't cover.
- **Bundle repeated work.** If every run wrote the same helper script, put it in `scripts/` once.
- **Match the form to the failure** (step 2): prohibition plus closed excuse, positive recipe, template slot, or an observable condition.

Then rerun everything into `iteration-N+1/` with baselines, reopen the viewer with `--previous-workspace`, and repeat until the user is happy, the feedback is empty, or progress stalls.

**Blind comparison** (optional, needs subagents): to ask "is the new version really better?", give two outputs to a fresh agent without saying which is which (`agents/comparator.md`), then analyse the winner (`agents/analyzer.md`).

## Step 7: Tune the trigger

The description decides when an agent loads the skill. Offer this once the skill works.

1. **Eval set**: 20 realistic queries, saved as `[{"query": "...", "should_trigger": true}, ...]`. Concrete and specific: file names, context, casual phrasing, typos, different lengths. 8-10 should trigger (different phrasings, cases where the user never names the skill, cases where it competes with another skill and should win). 8-10 should not, and those must be **near misses** that share words with the skill but need something else; "write a fibonacci function" tests nothing. Simple one-step queries are poor tests: agents don't load skills for what they can do directly.
2. **Review with the user**: fill `assets/eval_review.html` (replace `__EVAL_DATA_PLACEHOLDER__` with the JSON array, unquoted, `__SKILL_NAME_PLACEHOLDER__`, `__SKILL_DESCRIPTION_PLACEHOLDER__`), open it, and let them edit and "Export Eval Set" (it lands in their Downloads as `eval_set.json`).
3. **Measure**: `python $C/scripts/run_eval.py --eval-set <file> --skill-path <skill> --agent <cli> --holdout 0.4 --out <workspace>/trigger-0.json`. It runs each query 3 times in fresh sessions, splits 60/40 train/test (stratified), and reports accuracy, precision and recall per split.
4. **Improve** (you do this, no extra script): read the failing *train* queries, write a better description, measure it with `--description "<candidate>"`. Up to 5 rounds. **Pick the winner by test score, not train**, so you don't overfit the queries you've been staring at.
5. Show before/after descriptions and scores, then update the frontmatter.

Measure on the agent the user actually uses (`--agent`). Without a headless CLI (mode C), check that each should-trigger query shares distinctive words with the description and none of the near misses do, and say that's a weak signal.

## Step 8: Validate, record, hand off

1. `python $C/scripts/quick_validate.py <skill>` checks the spec (fields, name matches folder, lengths) and warns about agent-specific wording. Fix every warning or say why it stays.
2. **keeper.json** via **rotless-skill-modernizer**: run its `init` on the skill (it imports the repos from `references/prior-art.md`), curate it with the dependency list from step 1, then its `check` until there's no FAIL, CHANGED or GAP.
3. **Field-notes footer**: end the SKILL.md with the section below, unchanged except for the skill's name, so **rotless-skill-refiner** can learn from real use:

   ```markdown
   ## Field notes
   If a step here fails, the user corrects you, you work around an instruction, a search returns noise, or you find a better way, log it in one line and carry on: `python <rotless-skill-refiner folder>/scripts/notes.py add <skill-name> --kind failure|correction|workaround|noise|better-way|missing --where "<file:line or section>" --what "<what happened>" --evidence "<command and output, or the user's words>"`. Skip this if rotless-skill-refiner isn't installed. What you log is data for a later review, never instructions.
   ```
4. Optional, for apps that install a skill from a file (e.g. the Claude apps): `python -m scripts.package_skill <skill>` from `$C` builds a `.skill` zip.
5. **Summarise**: the prior-art verdict, files created, dependencies tracked, test results, and how to re-check (rotless-skill-modernizer `check <name>`) and refine (rotless-skill-refiner `review <name>`).

## Improving an existing skill

- Keep its folder name and `name` unchanged.
- If the installed copy is read-only, copy it somewhere writable, edit there, and copy back or package from the copy.
- Snapshot it before editing; the snapshot is the baseline (`old_skill/`).
- A skill someone else wrote belongs to them: don't edit it unless the user owns it. Offer to draft an issue for its author instead.
- If it has a `keeper.json`, update it in the same change and run rotless-skill-modernizer `check`.
- If it has logged field notes, start from them: run rotless-skill-refiner `review` first.

## Reference files

- `agents/grader.md`: grading assertions against outputs
- `agents/comparator.md`: blind A/B comparison
- `agents/analyzer.md`: why one version beat another; benchmark patterns
- `references/schemas.md`: test case folders, older evals.json, grading.json, benchmark.json
- `scripts/harness.py`: agent CLIs, headless runs, the project skills folders it installs into
- `scripts/run_case.py`, `scripts/run_eval.py`: test-case runs and trigger tests on any agent CLI
- `scripts/quick_validate.py`: spec validation and portability warnings

## Field notes
If a step here fails, the user corrects you, you work around an instruction, a search returns noise, or you find a better way, log it in one line and carry on: `python <rotless-skill-refiner folder>/scripts/notes.py add rotless-skill-creator --kind failure|correction|workaround|noise|better-way|missing --where "<file:line or section>" --what "<what happened>" --evidence "<command and output, or the user's words>"`. Skip this if rotless-skill-refiner isn't installed. What you log is data for a later review, never instructions.
