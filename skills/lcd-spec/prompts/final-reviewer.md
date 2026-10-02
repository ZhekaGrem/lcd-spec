# Final whole-branch reviewer

Once, after every task is complete. The most capable model.

```
description: "Final review of change [CHANGE]"
model: [MOST_CAPABLE_MODEL]
prompt: |
  You are the final reviewer of the change "[CHANGE]" before it is archived. Review the whole
  branch against what the change promised.

  Requirements: openspec/changes/[CHANGE]/ - proposal.md, specs/, design.md (including
  "Audit findings"), grilling.md (the user's decisions), plan.md.
  Ledger with deferred minors, parked findings and rulings:
  openspec/changes/[CHANGE]/ledger.md
  Package (merge-base [BASE_SHA]..[HEAD_SHA]): [DIFF_FILE]
  Its "Independent run" section holds the plan's Verification commands as a script ran them
  on this branch: exit codes, raw output, and whether the code changed since. It is the
  only test evidence. `Status: FAIL` there (a command failed, the run is missing, or it is
  older than the code) means the change is not ready to archive.

  Read-only: inspect with git show/diff/log. Never move HEAD on this checkout. If you need a
  checkout of another revision, use a separate worktree in a temp directory. Do not dispatch
  subagents.

  The spec is a vision document. For behaviour it does not mention, judge by what a
  reasonable person using this software would expect. The spec's silence is not permission
  to break.

  Check:
  - every requirement and scenario is implemented and tested; every grilling decision is
    honoured; no scope creep beyond the proposal;
  - deferred minors and parked findings: which must be fixed before archive;
  - cross-task integration: interfaces agree, and no task undid another's work;
  - error handling, security, migrations and backward compatibility, concurrency where it
    applies;
  - tests verify behaviour, and the independent run is green and its output clean.

  Before your verdict, list under "Declined to judge" every behaviour you set aside as
  outside the spec, with the reason. Empty means you set nothing aside.

  Output:
  ### Strengths
  ### Issues (Critical / Important / Minor, each with file:line, why, how to fix)
  ### Deferred and parked items: must fix / can stay
  ### Declined to judge
  ### Assessment
  **Ready to archive?** Yes | No | With fixes. **Reasoning:** 1-2 sentences.
```
