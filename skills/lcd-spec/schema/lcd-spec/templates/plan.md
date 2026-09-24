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

**Step 1: Write the failing test**

```
<!-- real test code -->
```

**Step 2: Run it and watch it fail**

Run: `<!-- exact command -->` - expected: FAIL with <!-- message -->

**Step 3: Write the minimal implementation**

```
<!-- real code -->
```

**Step 4: Run it and watch it pass**

Run: `<!-- exact command -->` - expected: PASS

**Step 5: Commit**

`git commit -m "<!-- conventional message -->"`
