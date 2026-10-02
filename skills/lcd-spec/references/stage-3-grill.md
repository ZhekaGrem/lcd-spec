# Stage 3 — Grill

Goal: every decision the change rests on is made by the user, knowingly, with the
alternatives in view, and recorded. Grilling checks **decisions**. Whether the code is
shaped the way the change claims is stage 5's job.

Output: `grilling.md` from the schema template, `Verdict: PASS`, stamped.

## How to grill

Interview the user relentlessly about every aspect of the change until you share one
understanding of it.

1. **Build the decision tree first** (silently). List every decision in proposal, specs
   and design, plus the ones they skip: error states, empty states, concurrency, limits,
   ordering, permissions, migration and rollback, what happens to existing data, what
   "immediately" means. Every `ASSUMED (unconfirmed)` and `[NEEDS CLARIFICATION` marker in the
   artifacts and every unchecked item under design.md `## Open Questions` is on the tree.
   Order them by dependency: a decision that changes others goes first.
2. **One question per message.** State the decision, the options, and your recommended
   answer with its reason. Wait for the user. Several questions at once get half-answers.
3. **Facts are looked up, decisions are asked.** If the answer is in the code, the living
   specs or the git history, find it, delegating to an Explore subagent when it needs a
   broad sweep, and record it under "Facts looked up". Never ask the user what a grep
   answers. Never decide on the user's behalf what only they can decide: scope, behaviour
   the user sees, trade-offs of cost vs. quality, ordering between changes.
4. **Walk each branch to the end.** An answer that opens new questions gets them asked before
   you move on.
5. **Push on the soft spots.** Vague words ("fast", "simple", "usually"), silent defaults,
   decisions justified only by "that's how X does it", and anything an incidents.md lesson
   warns about.
6. **Re-check earlier decisions** when a late answer changes a global parameter
   (a threshold, a cadence, an ordering, a data shape). Earlier answers given under the old
   value may no longer hold. Ask again.
7. **Domain words.** If the same thing gets two names (Customer vs. User), or one name
   covers two things, stop and settle the term. Then use it consistently in the artifacts.

## Recording

Fill `grilling.md` **as you go**, not from memory at the end:

- `## Decisions`: one block per resolved question (question, options, recommended,
  decided, the user's reason, dependencies). The gate fails on an empty section; a change
  with nothing to decide says `none - <why>`;
- `## Facts looked up`: fact plus evidence (`path:line`, command output);
- `## Lessons from incidents.md applied`: which lessons shaped which decision;
- `## Open questions`: `- [ ]` for anything unresolved. The gate blocks while any stays
  unchecked. `- [x] question -> answer` once resolved. Keep the heading even when the list
  is empty: the gate fails without it.

Decisions that change the artifacts are applied to proposal / specs / design **now**, before
the stamp. The stamp covers those files, and grilling is only meaningful against the text
it grilled. An answered marker is replaced by the answer, and an answered design.md open
question is ticked with its answer.

## Closing

1. Write `## Restated understanding`: the change in a few sentences as it now stands.
2. Ask: "Have we reached a shared understanding? Anything I got wrong?" Wait.
3. On a clear yes, set `Verdict: PASS`, then:
   ```
   python <skill>/scripts/gate.py stamp openspec/changes/<name> grilling
   python <skill>/scripts/gate.py check openspec/changes/<name> grilling
   ```
4. Show the gate output. Only a `PASS` moves you to stage 4.

## Scale

A small change can be grilled in three or four questions. There is no minimum count. There
is a minimum honesty: every real decision was put to the user.
