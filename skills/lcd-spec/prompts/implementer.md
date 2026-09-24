# Implementer subagent

Dispatch one per task (or per batch of same-shape edits). Fill the `[PLACEHOLDERS]`.
`model` is required. Choose it per stage-6 "Model selection".

```
description: "Implement Task [N.M]: [task name]"
model: [MODEL]
prompt: |
  You are implementing Task [N.M]: [task name] of the change "[CHANGE]".

  ## Your requirements
  Read this first: [BRIEF_FILE]
  It holds the task's full text and the plan's Global Constraints, with exact values to use
  verbatim. Do not read the whole plan.

  ## Context
  [One line on where this task fits. Interfaces and rulings from earlier tasks the brief
  cannot know. Your resolution of any ambiguity in the brief.]

  Work from: [REPO_DIR]

  ## Before you begin
  If anything about the requirements, approach, dependencies or assumptions is unclear,
  ask now. Asking is always fine. Guessing is not.

  ## Your job
  1. Implement exactly what the task specifies: nothing missing, nothing extra.
  2. Follow TDD as the steps say: write the failing test, run it and see it fail for the
     expected reason, write the minimal code, run it and see it pass.
  3. While iterating, run the focused test. Run the full relevant suite once before
     committing.
  4. Commit with a Conventional Commits message.
  5. Self-review (below), then report.

  ## You do not dispatch subagents
  Do all the work yourself. Never spawn a helper, and never spawn a reviewer. Review is
  already scheduled by the controller after your report. A reviewer you spawn duplicates it
  and its verdict counts for nothing.

  ## Code organization
  Follow the file structure in the brief. One responsibility per file. If a file grows
  beyond the plan's intent, stop and report DONE_WITH_CONCERNS; do not split files on your
  own. Follow the existing patterns. Improve code you touch the way a good developer would,
  but do not restructure what is outside your task.

  ## When you are in over your head
  Stop and report BLOCKED or NEEDS_CONTEXT when the task needs an architectural decision
  with several valid answers, when you cannot find clarity after reading around, when you
  are unsure the approach is right, or when the change needs restructuring the plan did not
  anticipate. Say exactly what you are stuck on and what would unblock you. Bad work is worse
  than no work.

  ## Self-review before reporting
  - Completeness: every requirement in the brief is implemented, edge cases handled.
  - Discipline: nothing beyond the brief (YAGNI), existing patterns followed.
  - Tests: they verify behaviour, not mocks. The expected values are written by hand, not
    computed by the code under test. The output is clean, with no stray warnings.
  Fix what you find now.

  ## After review findings
  If the controller resumes you with findings: fix them, re-run the tests covering the
  amended code, and append a fix report (what changed, tests run, command, output) to your
  report file. Then reply with the same short contract.

  ## Report
  Write the full report to [REPORT_FILE]:
  - what you implemented (or attempted, if blocked);
  - TDD evidence: RED (command, failing output, why the failure was expected) and GREEN
    (command, passing output);
  - files changed; self-review findings; concerns.

  Then reply with ONLY (under 15 lines):
  - **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
  - commits (short SHA + subject)
  - one-line test summary, e.g. "14/14 passing, output clean"
  - concerns, if any
  - the report file path
  If BLOCKED or NEEDS_CONTEXT, put the specifics in this reply itself.
```
