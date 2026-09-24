# Stage 5b — Perspective review (optional, but always asked)

Goal: look at the audited plan through the eyes of the people who will live with it. By
now the audit has proven that the plan matches the code. This stage asks whether it is
the right plan for the person testing it, using it, building it and maintaining it.
Those questions are different, and one reviewer rarely holds all of them at once.

Output: `review.md` (schema template). The stage is optional for the user, but the gate
requires the question to have been asked: `Verdict: SKIPPED` if declined, `Verdict: PASS`
after a finished review.

## 1. Ask

After `gate.py check … audit` prints PASS, ask two questions with AskUserQuestion.

**Question 1 (single choice):** "Review the plan from different perspectives before
implementation?" Recommend **yes** when the change has user-facing behaviour, touches data or
more than one module, or has more than ~5 tasks. Recommend **no** for a small internal change.
Say which one you recommend and why in one line.

- **No**: write review.md with `Verdict: SKIPPED` and the date, then go to stage 6.

**Question 2 (multiple choice, only if yes):** "Which perspectives?"

| Option | Looks for |
|--------|-----------|
| Tester | how each scenario gets proven, missing negative and boundary cases, test data, flakiness, regression surface |
| User | whether the flows solve the user's actual problem, empty / error / loading states, surprises, copy, accessibility, the effect on existing users and data |
| Programmer | whether each task can be built without guessing, interface mismatches between tasks, task order, hidden coupling, local run and debug, error handling in code |
| Architect | boundaries and coupling, data model evolution, consistency and concurrency, security, performance at scale, observability, migration and rollback, long-term cost |

The user may type another role ("security", "ops", "product owner"). Brief it the same way,
with a lens you write from their words.

## 2. Run the reviewers

Dispatch one subagent per chosen role **in parallel**, using `prompts/perspective-reviewer.md`
with the role's lens. Use the most capable model. This stage exists for depth. Each reviewer
works in deep-reasoning mode (the megathink directives in the prompt):
- research before judging;
- verify every assumption in the code;
- never make anything up;
- ask "what could go wrong?" of every task.

Give each reviewer the change directory and the repository root, not your summary. Your
framing would narrow their view to the one the audit already had.

## 3. Merge

When all reviewers return:

1. **Verify** each finding before accepting it: read the quoted artifact line and the cited
   code. A finding without evidence goes to "Consider" at most.
2. **De-duplicate** across roles. Keep the finding once and tag every role that raised it,
   e.g. `[tester, user]`.
3. **Classify:**
   - **Must fix**: the plan will ship something wrong for this role (a scenario that cannot
     be tested, a user flow that dead-ends, a task that cannot be built as written, an
     architectural choice that breaks a stated constraint);
   - **Should fix**: a real weakness the user should decide on;
   - **Consider**: ideas and trade-offs, with no decision needed.
4. Record where roles **disagree**: speed vs. robustness, UX vs. scope. These are the user's
   decisions, not yours.

Write review.md with `Verdict: PENDING` and `Perspectives:` listing the chosen roles.

## 4. Resolve with the user

Present Must fix and Should fix in one short list. Show the disagreements one at a time,
each with your recommendation. Then:

- apply fixes to the **artifacts** (specs, design, plan, tasks), never to code;
- a fix that changes a decision re-opens grilling for that point (grill, record, re-stamp);
- any change to proposal / specs / design / plan / tasks makes the audit stale. Re-check the
  changed claims with the stage-5 checks, record them in audit.md, re-stamp it;
- tick each resolved Must fix `- [x]`; record the user's decision on each Should fix;
- a Must fix that reveals a pattern likely to repeat ("we never plan empty states") gets an
  incidents.md entry with a lesson.

When every Must fix is ticked, set `Verdict: PASS`, then:

```
python <skill>/scripts/gate.py check openspec/changes/<name> apply
```

Show the output. Only `PASS apply` moves you to stage 6.
