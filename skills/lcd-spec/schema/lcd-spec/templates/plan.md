# <!-- Feature --> Implementation Plan

> Executed by the lcd-spec skill, stage 6: one implementer subagent per task, a task
> review after each, a whole-branch review at the end. Progress lives in tasks.md and
> ledger.md, not here.

**Goal:** <!-- one sentence -->

**Architecture:** <!-- 2-3 sentences -->

**Tech Stack:** <!-- key technologies -->

**Spec:** proposal.md, specs/, design.md, grilling.md in this change

## Global Constraints

<!-- Project-wide requirements every task inherits, one line each, exact values copied
     verbatim from the spec/design (versions, formats, naming, limits). -->

## Verification

<!-- The commands that prove the whole change: test / typecheck / lint / build. -->

## Review Focus

<!-- Up to five inputs or failure modes the spec implies but no test exercises yet, most
     likely first; each one gets its test added to the task that owns the code. -->

## File Structure

<!-- Files created or modified and the one responsibility of each. -->

---

### Task 1.1: <!-- name -->

**Files:**
- Create: `exact/path`
- Modify: `exact/path:123-145`
- Test: `tests/exact/path`

**Interfaces:**
- Consumes: <!-- exact signatures from earlier tasks -->
- Produces: <!-- exact names and types later tasks rely on -->
- Integration points: <!-- existing callers, registration points and data flow -->

**Behavior:**
<!-- Observable outcomes, representative inputs, errors and edge cases. -->

**Boundaries:**
<!-- What this task changes and what is outside its scope. -->

**Verify:**
- `<!-- the command that proves this task once it is done, e.g. its test file run to the end -->`

**Step 1: Write the failing test in the working branch**

<!-- Test file, scenario, inputs and expected outcomes in prose; no test code here. -->

**Step 2: Run it and watch it fail**

Run: `<!-- exact command -->` - expected: FAIL with <!-- message -->

**Step 3: Implement in the working branch**

<!-- Describe the required change and integration points; link to files and contracts.
     Write production code once in source files, without copying it into Markdown.
     For a risky assumption, optionally link a short prototype in a separate file and
     record its question, run command, result and limitation. -->

**Step 4: Run it and watch it pass**

Run: `<!-- exact command -->` - expected: PASS

**Step 5: Commit**

`git commit -m "<!-- conventional message -->"`
