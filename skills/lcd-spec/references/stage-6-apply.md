# Stage 6 — Apply (subagent-driven)

Goal: implement plan.md task by task. For each task a fresh implementer subagent does the
work and a fresh reviewer checks it before the next task starts. One whole-branch review
runs at the end.

You are the **controller**. You never write product code yourself: controller-written code
skips review and pollutes the context you need for coordination.

## Entry

```
python <skill>/scripts/gate.py check openspec/changes/<name> apply
```
Anything but `PASS apply` stops you. Go back to the stage it names.

## Setup

1. **Workspace.** Ask the user where to work if they haven't said: a new branch, a git
   worktree, or the current branch. Never start on `main`/`master` without explicit consent.
2. **Ledger.** `openspec/changes/<name>/ledger.md` is your memory. Conversation memory does not
   survive compaction, and controllers that lost their place have re-dispatched whole
   completed task sequences. That is the single most expensive failure seen in practice.
   - If ledger.md exists, trust it and `git log` over your recollection. Tasks with a
     `Task N.M: complete` line are done. Resume at the first one without it. A task whose last
     line is a fix round resumes at the next round.
   - Otherwise create it. First line: `# Ledger - change: <name>`.
3. **Read** plan.md once (Global Constraints, Verification, Review Focus), design.md and
   grilling.md. The spec is the binding authority, and the plan is its argument.
4. **Pre-flight scan.** Before Task 1, check the plan for conflicts and write the result to
   the ledger **as a table**:
   - one row per pair of tasks that share a file or an interface: what one produces, what
     the other consumes, whether they agree;
   - one row per task: does its text agree with itself (the tests it specifies vs. the
     required behavior and integration points, the files it creates vs. the files it later touches)?
   - anything the plan mandates that the review rubric treats as a defect.

   Rule on each conflict (below) before dispatching. "The scan is clean" without the rows is
   not a scan.

## Rulings, not stalls

A running plan does not wait on the user. Conflicts, ambiguities and plan defects are yours
to decide: the spec is the authority, the plan argues from it, and your judgment settles
what neither answers. Ledger every decision as
`Ruling: <what> — <why> — <what it costs if wrong>` and keep going.

Only four things stop you and go to the user: an irreversible or destructive operation; a
security-sensitive action; a side effect outside the workspace that norms say to ask about
(merge, push to a shared branch, publish); a plan so broken that every path forward is a
guess. Do not ask "should I continue?" between tasks.

## Model selection

Always pass a model explicitly. An omitted model inherits the session's, which is
usually the most expensive.

- Implementer working from the behavioral plan: standard tier. Write tests and production
  code in the working branch, and verify that implementation rather than a Markdown copy
  or an exploratory prototype.
- Design judgment or broad codebase understanding: most capable tier.
- Task reviewers: at least standard. Small scoped re-reviews: cheap to standard.
- Final whole-branch review: most capable.
- Fix rounds 4–5: at least one tier above the implementer that got stuck.

The cheapest models take 2–3× the turns on multi-step work. Turn count often beats token
price.

## The task loop

For each task `N.M`, in order, one at a time. Never run implementers in parallel: they
conflict.

**Batch small same-shape work.** Several tiny identical edits (the same one-line change
across files) go to one implementer with one brief listing every file, and get one review.

### 1. Dispatch the implementer
- `BASE=$(git rev-parse HEAD)`: record it. The review needs it.
- `python <skill>/scripts/task_brief.py openspec/changes/<name> N.M` prints the brief path.
- Dispatch with `prompts/implementer.md`: one line on where the task fits, the brief path
  ("read this first, it is your requirements"), interfaces and rulings from earlier tasks the
  brief cannot know, your resolution of any ambiguity you noticed, and the report path
  `openspec/changes/<name>/.work/task-N.M-report.md`.
- Do not paste earlier tasks' history into the dispatch. A fresh subagent needs its task,
  the interfaces it touches, and the global constraints.
- Record the implementer's agent id: fix rounds 1–3 resume it.

### 2. Handle the status
- **DONE**: go to review.
- **DONE_WITH_CONCERNS**: read the concerns. Correctness or scope concerns get resolved
  before review. Observations get noted.
- **NEEDS_CONTEXT**: supply it and re-dispatch.
- **BLOCKED**: more context → same model; more reasoning → stronger model; too big → split;
  plan wrong → rule on the correction, ledger it, re-dispatch with the ruling.

Never make the same model retry without changing something.

### 3. Review
- `python <skill>/scripts/review_package.py openspec/changes/<name> $BASE HEAD task-N.M`
  prints the package path. Use the recorded BASE, never `HEAD~1`, which drops all but the
  last commit of a multi-commit task.
- Dispatch `prompts/task-reviewer.md` with the brief, the report, the package, and the
  Global Constraints copied verbatim.
- Never pre-judge for the reviewer ("don't flag X", "at most Minor"). If you think a finding
  would be wrong, let it be raised and adjudicate it.
- Resolve every "⚠️ cannot verify from diff" item yourself. A real gap counts as a failed
  spec review.

### 4. Fix loop (spec ❌, any Critical/Important, or a confirmed ⚠️ gap)
- Minor findings: ledger `Task N.M: minor (deferred): …`. They never enter the loop.
- A finding that conflicts with the plan's text: rule on it (spec wins), ledger it, then act.
- Otherwise a round = one fix dispatch + one scoped re-review (`prompts/re-review.md` with
  a package from `review_package.py … $FIX_BASE HEAD task-N.M-fixR`). At most 5 rounds:
  - rounds 1–3: resume the same implementer with the findings verbatim;
  - rounds 4–5: a fresh implementer on a stronger model, framed as "a prior implementer
    tried N times; you own it now; read the report file for what was tried".
- Ledger each round: `Task N.M: fix round R/5 (X addressed, Y open — …; commits a..b)`.
- **Breaker** after round 5: adjudicate each open finding. Park it with a ruling if the
  reviewer is wrong or it is real but nothing builds on it. Rule on the smallest unblocking
  change if it is load-bearing. Every adjudication is a ledger line; nothing is dropped
  silently.
- A task that needed **3+ rounds** or tripped the breaker gets an incidents.md entry: why the
  plan or the implementer could not see the problem, and the lesson.

### 5. Complete
- Tick `- [x] N.M` in tasks.md.
- Ledger `Task N.M: complete (commits a..b, review clean)` or `(…, K parked)`.
- Never move on while Critical/Important findings are neither fixed nor parked with a ruling
  at the cap.

## Final review

1. Run the plan's **Verification** commands yourself and keep the output.
2. `review_package.py … <merge-base> HEAD final`, then dispatch `prompts/final-reviewer.md`
   on the most capable model, pointing it at the ledger's deferred and parked lines.
3. Findings go to **one** fix dispatch with the full list, then **one** scoped re-review.
   Residuals are adjudicated as at the breaker. There is no second fix wave. Residual
   load-bearing findings go to the user.
4. A Critical finding gets an incidents.md entry.
5. Delete `openspec/changes/<name>/.work/`. Keep ledger.md: it is archived with the change.

## Reporting

Your final message lists:

- tasks completed, with commit ranges;
- verification commands and their real output (pass/fail as shown, not paraphrased);
- **"Rulings I made"**: every `Ruling:` line from the ledger, in order, each with what it
  costs if wrong. This is the only place the decisions you took on the user's behalf reach
  them;
- incidents added.

Then offer stage 7.

## Frustration during apply

If a `<lcd-spec-signal>` arrives mid-apply, stop dispatching. Level 3 also means
stopping running subagents. Run `references/incident-audit.md` first. The ledger lets you
resume exactly where you were once the audit is done and, at level 3, the user said to
continue.
