# lcd-spec

**A hard-gated spec workflow for Claude Code, built on [OpenSpec](https://github.com/Fission-AI/OpenSpec).**
It takes a feature from a rough idea to an archived, implemented change. On the way, every
decision gets argued with you, every claim in the plan gets checked against the real code, and
every task is built by a fresh subagent and reviewed before the next one starts.

```
0 context → 1 brainstorm → 2 artifacts → 3 grill ⛔ → 4 plan ⛔ → 5 audit ⛔ → 5b perspectives ⛔ → 6 apply ⛔ → 7 archive
```

⛔ = a hard gate. The next stage cannot start until a script confirms the previous one is
done **and still true**.

---

## Why this exists

AI-assisted planning tends to fail in the same few ways:

| Failure | What it looks like | What lcd-spec does about it |
|---|---|---|
| **Decisions nobody made** | The agent writes a spec full of confident choices you were never asked about. | **Grilling**: an interview, one question at a time, each with a recommendation. The transcript is saved, and the gate refuses to move on while any question is open. |
| **Plans that drift from reality** | The plan says "latest migration is V46" or "reuse `OrderService`", but the code moved, or it was never true. | **Pre-apply audit**: two independent subagents re-check every file, class, field, migration number and mechanism the change names, against the code as it is *now*. |
| **Plans that are too vague to build** | "Add error handling", "similar to task 3", a coarse checklist. The real design happens mid-implementation, in a hurry. | **Detailed plan**: every task lists exact files, interfaces and TDD steps with real code. A script rejects placeholders. |
| **Right for the code, wrong for people** | The plan compiles but can't be tested, dead-ends the user, or paints the architecture into a corner. | **Perspective review** (optional): deep-reasoning reviewers look at the plan as a tester, a user, a programmer and/or an architect. |
| **One long context doing everything** | The agent implements 20 tasks in one session, reviews its own work, and loses track after compaction. | **Subagent-driven apply**: a fresh implementer per task, a fresh reviewer per task, a ledger that survives compaction, and a final whole-branch review. |
| **"Tests pass", says the report** | The implementer's summary says green, but the code was edited after the last run, or the summary stitches several runs together. | **Independent run**: after each task a script runs the task's commands itself and records raw output and exit codes. The reviewer reads that run, and it is marked stale as soon as a project file changes. |
| **Docs scattered and stale** | Grilling notes, plans and audits pile up in `docs/`, and nobody knows which ones are done. | **One directory per change**: everything lives in `openspec/changes/<name>/`, and `openspec archive` moves all of it together. |
| **The same mistakes, again** | The project keeps hitting the same class of bug, and each session starts fresh. | **Incident log**: `openspec/incidents.md` collects lessons, and every new change reads them first. A frustration detector turns "you broke it again" into a structured audit. |

## The stages

| # | Stage | What happens | Output |
|---|---|---|---|
| 0 | **Context** | Reads the living specs, open changes, recent commits and the project's incident lessons. Flags requests that should be split. | a short note in chat |
| 1 | **Brainstorm** | Restates the task and asks you to confirm it. Then questions one at a time, 2–3 approaches with trade-offs, and the design presented in sections for your approval. | agreed design, `openspec new change` |
| 2 | **Artifacts** | Writes proposal, delta specs (SHALL + WHEN/THEN scenarios) and design with the alternatives considered. Self-reviews, runs `openspec validate`, and you review. | `proposal.md`, `specs/`, `design.md` |
| 3 | **Grill** ⛔ | Walks the decision tree with you. Facts are looked up in the code; decisions are asked. Earlier answers are revisited when a late answer changes a global parameter. | `grilling.md` (verdict + stamp) |
| 4 | **Plan** ⛔ | A plan an engineer with zero context could follow: file structure, global constraints, review focus, `### Task N.M` sections with TDD steps. Plus `tasks.md`, a tracker with the same numbers. | `plan.md`, `tasks.md` |
| 5 | **Pre-apply audit** ⛔ | Two parallel auditors. A checks claims against the code (names, signatures, visibility, migration numbering, third-party fields, proxy/CSS mechanisms, "every surface" greps). B checks the change against itself (empty-DB migrations, caches between write and read, crash recovery, whole-collection saves, optimistic locking). Findings carry `path:line` evidence. | `audit.md` (verdict + stamp) |
| 5b | **Perspectives** ⛔ | You're asked whether to review the plan from other angles, and which ones: **tester**, **user**, **programmer**, **architect**, or your own. One deep-reasoning subagent per role runs in parallel. Findings are merged into Must fix / Should fix / Consider. Declining is fine, but the question is always asked. | `review.md` (SKIPPED or PASS) |
| 6 | **Apply** | A fresh implementer subagent per task, an independent run of the task's test commands, then a fresh task reviewer (spec compliance + quality) who reads that run, up to 5 fix rounds with model escalation, a final whole-branch review, and every controller decision logged as a ruling. | code, `ledger.md`, ticked `tasks.md`, `verification.md` |
| 7 | **Archive** ⛔ | Checks everything is done and that the recorded verification run is green and still matches the code, shows what merges into the living specs, runs `openspec archive`, and refreshes the roadmap. | `openspec/changes/archive/<date>-<name>/`, `roadmap.md` |

## How the gates work

Three layers, from coarse to strict:

1. **The OpenSpec schema `lcd-spec`** adds `grilling`, `plan`, `audit` and `review` as artifacts.
   `openspec instructions apply` returns `blocked` while any of them is missing.
2. **`gate.py`**: OpenSpec only knows that a file *exists*. The gate reads what it *says*:

   ```bash
   python skills/lcd-spec/scripts/gate.py status openspec/changes/add-export
   PASS  grilling
   PASS  plan
   FAIL  audit
   FAIL  review
   FAIL  apply
   FAIL  archive
   ```

   What it checks:
   - verdict lines;
   - unanswered questions, open blockers and open must-fix findings;
   - required sections: one that is missing or empty fails, it does not pass by absence;
   - leftover `ASSUMED (unconfirmed)` and `[NEEDS CLARIFICATION` markers in the artifacts;
   - that every task in `plan.md` names its files and interfaces;
   - that `plan.md` answers every active lesson from `openspec/incidents.md`;
   - that every resolved audit blocker cites an incident entry;
   - that `plan.md` and `tasks.md` carry exactly the same task numbers;
   - leftover placeholders or template comments;
   - **staleness**. After grilling and after the audit, `gate.py stamp` records a hash of the
     artifacts they covered. If a spec is edited after it was grilled, the gate says `stale`
     until someone re-checks it. Ticking tasks and appending audit findings don't count as edits.
   - **the verification run**, before archive. `verify_run.py` runs the plan's Verification
     commands and writes `verification.md` with every exit code. The gate fails while a
     command is red, or while a project file changed after the run.
3. **You.** The design, the written artifacts, the grill and the plan each need an explicit yes.

## Where things live

```
openspec/
  specs/                        living specs, updated by archive
  incidents.md                  project lessons, read at the start of every change
  roadmap.md                    index of done / open / planned work, searched on demand
  schemas/lcd-spec/             installed by install.py
  changes/<name>/
    proposal.md specs/ design.md
    grilling.md                 decisions, facts, open questions, verdict, stamp
    plan.md                     detailed TDD plan
    tasks.md                    tracker: - [ ] N.M, same numbers as plan.md
    audit.md                    blockers / serious / minor / what was NOT verified
    review.md                   perspective review, or SKIPPED
    ledger.md                   apply progress and rulings, survives compaction
    verification.md             the final run of the Verification commands, with exit codes
    .work/                      briefs, reports, task runs, review packages (gitignored, deleted at the end)
  changes/archive/<date>-<name>/  all of the above, after stage 7
```

## Incident tracking and the frustration detector

`openspec/incidents.md` is the project's memory. Entries are added when:
- the audit finds a blocker;
- a task needs 3+ review rounds;
- the final review finds something critical;
- a bug surfaces after archive;
- the frustration detector fires.

Each entry ends with a **lesson** phrased as an instruction. A lesson nobody re-reads
prevents nothing, so the lessons come back mechanically:

- stage 0 of every new change reads them;
- the plan gate fails until `plan.md` answers each active lesson (the task that handles it,
  or why it does not apply);
- every implementer brief carries the lessons that apply to the task's files as
  "Known pitfalls", and the task reviewer checks the diff against them;
- the audit gate fails on a resolved blocker that has no incident entry behind it.

An entry can say where its lesson belongs (`Needed at: plan, apply`, `Paths: **/cache/**`,
`Stack: java`), so a lesson about migrations does not pad the brief of a CSS task.

The same mistake is never written twice. `incidents.py` keeps the log honest:

```bash
python skills/lcd-spec/scripts/incidents.py find openspec/incidents.md "cache shows the old price"
INC-20260924-1 (seen 1x) - Name the cache invalidator and its delay in the spec

python skills/lcd-spec/scripts/incidents.py bump openspec/incidents.md INC-20260924-1
INC-20260924-1: recurrence 2
The lesson as written did not stop the repeat. Turn it into something that runs: a test, a lint rule, a hook or a gate check.

python skills/lcd-spec/scripts/incidents.py validate openspec/incidents.md
OK: 12 entries, 9 active lessons
```

Entries written in the original ten-field format stay valid; the new fields are optional.

The plugin ships a `UserPromptSubmit` hook (`scripts/frustration.py`) that scores each
message you send:

| Signal | Weight | Example |
|---|---|---|
| Swearing, not addressed to the agent | 0.5 | «бля, забув сказати» |
| Swearing addressed to the agent | 1.0 | «ти що, наробив?» |
| Blame, no swearing needed | 1.0 | «ти знову все зламав», "I told you not to…" |
| The same failure again | 1.0 | «досі не працює», "still failing with the same error" |
| Mild negativity | 0.5 | «маячня», "garbage" |
| Praise with swearing, or an ordinary bug report | 0 | «все добре, працює!», "the button doesn't work, please fix" |

It detects Ukrainian, Russian and English, including dot/dash obfuscation and latin
look-alike letters. Code blocks, quoted lines and talk about the detector itself are ignored.
Within a 30-minute window the weights add up to a level:
- **L1** (1.0): the agent stops, reconstructs what diverged from your request, and runs
  two independent auditors on the raw evidence;
- **L2** (2.5): it also audits its previous audit;
- **L3** (4.0): full stop, no edits until you explicitly say to continue.

Every finished audit becomes an incident with a lesson.

- Test a phrase: `python skills/lcd-spec/scripts/frustration.py --classify "text"`
- Turn it off: set `LCD_SPEC_FRUSTRATION=off` in the `env` block of `~/.claude/settings.json`
- Add words or a language: one regex per line in `skills/lcd-spec/scripts/lexicon/<lang>.txt`
- State and a metadata-only log (never message text): `~/.lcd-spec/`

## Roadmap: "is this already there?"

`openspec/roadmap.md` is a one-line-per-item index of the project, written by a script:

```bash
python skills/lcd-spec/scripts/roadmap.py .
```

```markdown
## Planned
- bulk price import from XLSX

## In progress
- add-export [order-export] - Export orders as CSV (3/7 tasks)

## Archived changes
- 2026-09-24 import-supplier-prices [price-import] - Import supplier prices from a CSV upload → changes/archive/2026-09-24-import-supplier-prices/

## Features
- 2026-09-20 shipment-notification: notify the customer when an order ships (3f2a1c9)

## Fixes
- 2026-09-21 cart: keep the discount when the quantity changes (9b1e77a)
```

- **In progress** and **Archived changes** come from `openspec/changes/`.
- **Features** and **Fixes** come from `feat` and `fix` commits (Conventional Commits), so
  work done without a spec is in the index too. Other commit types are left out.
- **Planned** is the one section you write by hand, for ideas that have no change yet. The
  script keeps it.

The agent does not load this file at the start of a change. It searches it only when the
specs leave a question open: does this feature exist already, was this bug fixed before.
The script runs at install, at archive, and whenever that question comes up.

## Install

Requirements: [Claude Code](https://code.claude.com), the OpenSpec CLI
(`npm i -g @fission-ai/openspec`), and Python 3.10+ (stdlib only, no pip).

**As a plugin** (the skill and the detector hook together):

```
/plugin marketplace add ZhekaGrem/lcd-spec
/plugin install lcd-spec@lcd-spec
```

**As a personal skill** (e.g. to edit it in place), link `skills/lcd-spec` into
`~/.claude/skills/lcd-spec`. Then add the hook to `~/.claude/settings.json` yourself:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "timeout": 10,
        "command": "python \"$HOME/.claude/skills/lcd-spec/scripts/frustration.py\"" } ] }
    ]
  }
}
```

Don't enable both at once, or the skill loads twice.

## Use it in a project

```bash
openspec init
python <path-to>/skills/lcd-spec/scripts/install.py .
```

`install.py` does five things:
- copies the schema into `openspec/schemas/lcd-spec/`;
- switches `openspec/config.yaml` to `schema: lcd-spec` for **new** changes (existing changes
  keep their own schema);
- creates `openspec/incidents.md`;
- gitignores the per-change scratch directory;
- writes `openspec/roadmap.md` from the changes and commits the project already has.

You can also just ask Claude to spec something, and the skill offers to install itself.

Then talk to Claude normally:

- *"let's spec an order export feature"*: starts at stage 0
- *"continue the add-export change"*: resumes at the first stage that isn't PASS
- *"let's start implementing"*: checks the apply gate, then runs the subagents
- *"what went wrong?"*: runs a manual incident audit

## Repository layout

```
.claude-plugin/          plugin + marketplace manifests
hooks/hooks.json         the frustration-detector hook
skills/lcd-spec/
  SKILL.md               the orchestrator: stages, gates, rules
  references/            one file per stage + incident-audit protocol + incidents template
  prompts/               subagent prompts: implementer, reviewers, auditors, perspective reviewer
  schema/lcd-spec/       the OpenSpec schema and its templates
  scripts/               gate.py, incidents.py, verify_run.py, roadmap.py, frustration.py
                         (+ lexicon/), install.py, task_brief.py, review_package.py
tests/                   unittest suite for the scripts
```

## Tests

```bash
python -m unittest discover -s tests -v
```

The suite covers:
- the detector: UA/RU/EN, obfuscation, false positives on ordinary words, escalation, the
  level-3 stop;
- the hook as a real subprocess fed UTF-8, whatever the console codec;
- every gate: stale detection, required sections, numbering, placeholders, template
  comments, lessons answered in the plan, incidents behind audit blockers, the review
  question, the verification run before archive;
- the incident log: format check, finding a repeat, counting it, picking the lessons for a
  stage and a set of files;
- the independent run: which commands are taken from the plan, real subprocesses with exit
  codes, timeouts, staleness against a git working tree, the run inside a review package;
- the roadmap: which commits and changes are listed, the hand-written section surviving a
  rewrite, a project that sits inside a larger repository;
- the brief extractor and the installer.

The suite starts real processes and small git repositories in a temp directory, so it
needs `git` on the PATH and takes about a minute.

## Credits

lcd-spec stands on:
- [OpenSpec](https://github.com/Fission-AI/OpenSpec) (MIT);
- [superpowers](https://github.com/obra/superpowers) by Jesse Vincent (MIT): brainstorming,
  writing plans, subagent-driven development;
- [mattpocock/skills](https://github.com/mattpocock/skills) (MIT): grilling;


Details are in [NOTICE.md](NOTICE.md).

## License

[MIT](LICENSE)
