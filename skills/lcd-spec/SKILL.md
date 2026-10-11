---
name: lcd-spec
description: >
  Hard-gated spec workflow on OpenSpec: dialogue design, proposal/specs/design, grilling of
  every decision, behavioral plan with scope, integrations and verification, pre-apply audit of every claim against the code,
  optional plan review as tester/user/programmer/architect, subagent-driven implementation with a review per task, archive. All change files live and
  are archived in the change directory; project mistakes and user frustration signals are
  tracked in openspec/incidents.md. Use whenever the user wants to plan, specify or build a
  feature, change, fix or refactor worth a spec - "зроби спеку", "нова фіча", "створи
  чейндж", "давай спланируємо", "план реалізації", "починаємо реалізацію", "/opsx:propose",
  "OpenSpec", "grill", "гріл", "apply", "архівуй чейндж" - and whenever an OpenSpec change
  with schema lcd-spec is resumed, even if the skill is not named.
---

# lcd-spec

A change goes through nine stages. Each stage produces a file inside
`openspec/changes/<name>/`, and the next stage cannot start until the gate says the
previous one is done **and still true**. The goal is a spec whose decisions were argued
with the user, whose claims were checked against the code, and whose plan an
implementer subagent can execute without guessing.

```
0 context → 1 brainstorm → 2 artifacts → 3 grill ⛔ → 4 plan ⛔ → 5 audit ⛔ → 5b perspectives ⛔ → 6 apply → 7 archive
```

Stage 5b is optional for the user, but the question is not: the gate needs review.md
to say either `SKIPPED` or `PASS`.

`<skill>` below means the directory that holds this SKILL.md. Scripts are plain Python 3.10+
(stdlib only): run them as `python <skill>/scripts/<name>.py ...`.

## Why the gates are hard

Every stage exists because skipping it once cost real rework:

- **Grill** — a spec written from the agent's own judgment encodes decisions the user never
  made. An unasked decision is a guess with a nice heading.
- **Plan** — a coarse task list pushes design work into implementation, where it happens
  in a hurry, per task, without anyone seeing the whole.
- **Audit** — a plan freezes a snapshot of the tree; the tree moves and nothing signals.
  One real change passed grilling and still carried five blockers into implementation,
  four of them inside a section titled "verified by reading code".
- **Perspectives** — the audit proves the plan matches the code, not that it is right for
  the person testing, using, building or maintaining it. Each role sees different failures.

So the gates are not a formality to route around. When a gate fails, fix the named stage;
do not argue the gate down, edit the verdict line by hand, or re-stamp without re-checking.

Three layers enforce them:

1. **OpenSpec schema `lcd-spec`** — `openspec instructions apply` returns `blocked` while
   grilling.md, plan.md, tasks.md, audit.md or review.md is missing.
2. **`gate.py`** — the schema only sees that a file exists. `gate.py check <change-dir> <stage>`
   checks the verdict, open questions, open blockers, open must-fix findings, plan/tasks
   numbering, placeholders, and
   whether the artifacts changed after the stage was stamped. **gate.py is the authority**:
   OpenSpec says `ready` as soon as audit.md exists, even with `Verdict: PENDING`.
3. **The user** — design, written artifacts, grilling and plan each need the user's explicit
   yes. An approval covers the stage that was shown, not the ones after it.

## Stage map

Read the reference for a stage when you enter it — not all of them upfront.

| # | Stage | Produces | Gate to leave | Reference |
|---|-------|----------|---------------|-----------|
| 0 | Context | chat note | — | `references/stage-0-context.md` |
| 1 | Brainstorm | agreed design (chat), `openspec new change` | user approves design | `references/stage-1-brainstorm.md` |
| 2 | Artifacts | proposal.md, specs/, design.md | `openspec validate` + user reviews | `references/stage-2-artifacts.md` |
| 3 | Grill | grilling.md | `gate.py check … grilling` | `references/stage-3-grill.md` |
| 4 | Plan | plan.md, tasks.md | `gate.py check … plan` + user reviews | `references/stage-4-plan.md` |
| 5 | Pre-apply audit | audit.md, design.md "Audit findings" | `gate.py check … audit` | `references/stage-5-audit.md` |
| 5b | Perspective review | review.md (SKIPPED or PASS) | `gate.py check … apply` | `references/stage-5b-perspectives.md` |
| 6 | Apply | code, ledger.md, ticked tasks.md | all tasks reviewed clean + final review | `references/stage-6-apply.md` |
| 7 | Archive | `openspec/changes/archive/<date>-<name>/` | user confirms | `references/stage-7-archive.md` |
| — | Incident audit | incidents.md entry | — | `references/incident-audit.md` |

## Start of every invocation

1. **Tooling.** `openspec --version` must work. If `openspec/config.yaml` is missing, ask the
   user before running `openspec init`. If `openspec/schemas/lcd-spec/` is missing, ask, then
   run `python <skill>/scripts/install.py <project-root>`. It switches `config.yaml` to
   `schema: lcd-spec` for new changes only; existing changes keep their schema.
2. **New or resume?** Run `openspec list --json`. If the user refers to an existing change,
   or exactly one active change uses schema `lcd-spec`, resume it:
   - `python <skill>/scripts/gate.py status openspec/changes/<name>`
   - `openspec status --change <name>`
   - read `ledger.md` if it exists (stage 6 in progress)

   Resume at the **earliest** stage that is not PASS. A stale stage counts as not PASS.
3. **Announce** in one line which change and stage you are on, e.g.
   "lcd-spec: `add-export`, stage 4 (plan). Grilling PASS, plan missing."

## Where things live

Everything a change produces sits in its own directory. `openspec archive` moves the whole
directory, so specs, transcripts, plans, audits and the ledger are archived together.
Finished work never mixes with work in progress.

```
openspec/
  specs/                      living specs (updated by archive)
  incidents.md                project mistakes and lessons - read at every stage 0
  schemas/lcd-spec/           installed by install.py
  changes/<name>/
    proposal.md  specs/  design.md     stage 2
    grilling.md                        stage 3 (stamped)
    plan.md  tasks.md                  stage 4 (tasks.md = tracker with plan's numbers)
    audit.md                           stage 5 (stamped)
    review.md                          stage 5b (SKIPPED or PASS)
    ledger.md                          stage 6 progress and rulings - survives compaction
    .work/                             scratch: briefs, reports, review packages (gitignored)
  changes/archive/<date>-<name>/       the same directory after stage 7
```

Do not write transcripts, plans or audits anywhere else (no `docs/superpowers/`, no
`docs/plans/`). A file outside the change directory is not archived with it, and a year
later nobody can tell whether it was done.

## Stale stages

A stamp records a hash of the artifacts the stage checked. If they changed afterwards,
the gate reports `stale`. That is the gate doing its job: the check you did no longer covers
the current text.

- **Grilling stale** (proposal/specs/design changed): diff what changed. If any decision
  changed or a new one appeared, grill that point with the user and add it to grilling.md.
  If only wording or facts changed, say what changed under `## Re-stamps`. Then re-stamp.
- **Audit stale** (anything up to plan/tasks changed): re-run the audit checks that the
  change touches, record the result, re-stamp. Ticking tasks and the "Audit findings"
  section in design.md never make anything stale.

## Incidents and frustration signals

`openspec/incidents.md` is the project's memory of what went wrong. Stage 0 reads its
lessons; stages 3 and 5 check the change against them.

Add an entry (format in the file) when:

- a pre-apply audit finds a **Blocker**: the plan diverged from reality, and the lesson
  prevents the next one;
- a task in stage 6 needs **3+ fix rounds** or hits the breaker;
- the final review finds a **Critical** issue;
- an incident audit (below) finishes;
- the user reports a bug in work from an archived change.

**Frustration signals.** The plugin's `UserPromptSubmit` hook (`scripts/frustration.py`)
scores each user message for swearing (Ukrainian, Russian, English), blame
("ти знову все зламав", "я ж просив"), repeated-failure complaints ("досі не працює") and
milder negativity. When the per-session streak crosses a level, it injects a
`<lcd-spec-signal level="N">` block. When you see one, follow `references/incident-audit.md`
at that level **before** continuing the task. Level 3 is a full stop until the user
explicitly says to continue. Without the hook, run the same protocol when the user is
clearly frustrated with your work or asks for an audit.

## Communication

- Talk to the user in their language. Artifacts follow the project's existing language.
  If there is none, use the language of the conversation.
- Questions go **one at a time**, with your recommended answer. Prefer multiple choice. Facts
  you can find in the code, you look up — you do not ask.
- Before stage 1 designs anything, restate the task in your own words and ask whether you
  understood it correctly. Wait for the answer.
- Evidence before claims: never say "done", "passing" or "verified" without the command
  output that shows it. If you did not run it, say "not verified".

## Red flags

| Thought | Reality |
|---------|---------|
| "This change is small, I'll skip grilling" | Small changes get short grills, not none. Scale the stage, keep the gate. |
| "I know what the user wants, I'll fill grilling.md myself" | The transcript records the user's decisions. Yours are recommendations. |
| "OpenSpec says ready, so apply" | OpenSpec only checks that files exist. Run `gate.py check … apply`. |
| "The gate is stale but nothing important changed" | Then re-checking is quick. Do it and re-stamp with the reason. |
| "I'll fix this audit finding in code during apply" | Findings are fixed in the artifacts first. Code follows the plan. |
| "I'll implement this small task myself instead of dispatching" | Controller-written code skips review. Dispatch it. |
| "Put the plan in docs/ like before" | Everything lives in the change directory, or it is not archived with it. |
| "The user swore but the task is almost done" | The signal means your picture may be wrong. Audit first, then finish. |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/install.py <project>` | install schema, switch config, create incidents.md, gitignore `.work/` |
| `scripts/gate.py check <change> <grilling\|plan\|audit\|review\|apply>` | hard gate, exit 1 on FAIL with reasons |
| `scripts/gate.py stamp <change> <grilling\|audit>` | record the artifacts hash after the stage is done |
| `scripts/gate.py status <change>` | all gates at a glance |
| `scripts/task_brief.py <change> <N.M>` | one task + Global Constraints → `.work/task-N.M-brief.md` |
| `scripts/review_package.py <change> <base> <head> [label]` | commits + stat + diff → `.work/review-*.md` |
| `scripts/frustration.py` | the hook; `--classify "text"` to test a message, `--dismiss <session> <event>` to retract |
