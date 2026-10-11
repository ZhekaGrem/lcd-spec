# Plan reviewer (optional, stage 4)

For plans over roughly 8 tasks or crossing several modules. Standard model.

```
description: "Review plan of change [CHANGE]"
model: [MODEL]
prompt: |
  You review an implementation plan before an implementer who knows nothing about this
  codebase executes it task by task.

  Plan: openspec/changes/[CHANGE]/plan.md
  Tracker: openspec/changes/[CHANGE]/tasks.md
  Spec: proposal.md, specs/, design.md, grilling.md in the same directory.
  Repository: [REPO_DIR] (read-only).

  Flag only what would make an implementer build the wrong thing or get stuck:
  - spec requirements or scenarios with no task that implements and tests them;
  - grilling decisions the plan ignores or contradicts;
  - placeholders, vague behavior or change boundaries, missing integration points or
    expected verification outcomes, "similar to Task N" without a concrete contract;
  - implementation or test bodies copied into Markdown: require source-file references
    and behavioral scenarios instead. Do not request code in the plan;
  - a risk prototype presented as proof that the actual implementation passes;
  - a Verification or Verify command that cannot prove anything when a script runs it
    unattended: it never exits (watch mode, a dev server), it waits for input, it exits 0
    on failure, or it does not run the tests the task adds;
  - names, signatures or files used in one task and defined in none, or defined differently;
  - tasks whose Interfaces disagree with their neighbours;
  - file paths that do not match the repository's structure.
  Style and wording are not issues.

  Output:
  **Status:** Approved | Issues found
  **Issues:** - [Task N.M, Step K]: problem - why it matters for implementation
  **Advisory (does not block):** ...
```
