# Auditor B: change vs. itself and runtime behaviour (stage 5)

Dispatched in parallel with auditor A. Capable model. Give it paths, not your opinion.

```
description: "Pre-apply audit B (change vs itself): [CHANGE]"
model: [MODEL]
prompt: |
  You audit a planned change before implementation starts. Your question: is the change
  consistent with itself, and does it survive what the data and the runtime will actually do?
  Do not judge whether the decisions are good; that was settled with the user. Do not
  modify anything.

  Change: openspec/changes/[CHANGE]/ (proposal.md, specs/, design.md, grilling.md, plan.md,
  tasks.md). Repository root: [REPO_DIR]. Living specs: openspec/specs/.
  Neighbouring open changes: openspec/changes/ (not archive/). Project lessons:
  openspec/incidents.md.

  Checks:
  2b. Migrations that move data: has the source migration ever left this branch? After the
      full chain on an EMPTY database, what rows exist, and does the spec's initial-state
      scenario agree?
  6.  "Immediately visible / disappears": what sits between the write and the read (cache,
      projection, index, materialized view)? Who invalidates it, and when?
  7.  "One at a time / in progress" guards: who clears the flag if the process dies? Are all
      states in prose present in the state list?
  8.  Whole-collection replace: walk the SECOND save. Which child fields are written by
      other endpoints and get reset? Do child ids get re-minted and break URLs? Do table
      constraints turn the reset into a failed save?
  9.  Optimistic locking: for each write, which column of the VERSIONED row changes? If
      none, is the bump prescribed and tested?
  Self-consistency:
  - every new field: who writes it → who reads it, semantics compared word for word;
  - MODIFIED requirements reproduce the living spec's requirement verbatim (compare with
    openspec/specs/<capability>/spec.md);
  - scope boundaries with neighbouring changes are written into both proposals;
  - every grilling.md decision shows up in design/specs/plan; late decisions that changed
    a global parameter were re-applied to earlier ones;
  - every spec scenario has a plan task that tests it; no task contradicts design.md;
  - plan.md and tasks.md numbering and titles agree.
  Also: which incidents.md lessons apply, and are they honoured?

  Evidence, not opinion: every finding carries the quoted artifact text with its file, plus
  path:line / grep output for code facts. What you could not check goes under NOT VERIFIED.

  Output:
  ## Blockers
  ## Serious
  ## Minor / docs
  ## NOT VERIFIED (and what would verify it)
  Each item: - claim quoted from artifact (file) - finding - evidence - suggested artifact fix
```
