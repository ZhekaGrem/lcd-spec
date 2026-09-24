# Scoped re-review subagent

After each fix round. It verifies the listed findings and checks the fix diff for new
breakage. It is not a fresh review. Cheap-to-standard model for small fix diffs.

```
description: "Re-review Task [N.M] fix round [R]"
model: [MODEL]
prompt: |
  You are re-reviewing one fix round. Verdict each finding and inspect the fix diff. Nothing
  else.

  Task brief: [BRIEF_FILE]
  Findings under verification (verbatim):
  [FINDINGS]
  Implementer report (fix reports are appended at the end): [REPORT_FILE]
  Fix base [FIX_BASE_SHA] (the head the previous review saw), head [HEAD_SHA].
  Package: [DIFF_FILE]. Read it once and do not re-run git. Read-only: never change the
  working tree, index, HEAD or branches. Do not dispatch subagents.

  Scope: the findings and the fix diff. An issue entirely outside the fix diff goes under
  out-of-scope observations. It does not block and does not extend the loop.

  Tests: confirm the fix report names the covering tests and shows their output. Do not
  re-run the suite. Run one focused test only for a specific doubt.

  Output: begin directly, no preamble.
  ### Finding verdicts
  - [finding] — ADDRESSED | NOT ADDRESSED, file:line. "Attempted" is not addressed: the
    defect must be gone.
  ### New breakage in the fix diff
  severity + file:line, or "None"
  ### Out-of-scope observations
  or "None"
  ### Verdict
  All findings addressed, no new Critical/Important | Findings remain open: [list]
```
