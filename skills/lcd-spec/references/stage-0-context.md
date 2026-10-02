# Stage 0 — Context

Goal: know what already exists before anyone designs anything. This stage produces no file,
only a short note in chat that the next stages lean on.

## Read, in this order

1. **The request.** Quote the user's words to yourself. Later stages get compared against them.
2. **`openspec/incidents.md`, Lessons index.** Note every lesson that touches the area of
   this request: same module, same kind of change (migration, cache, UI container,
   third-party field). Read the full entry for those. They become questions in stage 3 and
   checks in stage 5.
3. **Living specs.** `openspec list --specs`, then read the specs of the capabilities the
   request touches. The change's specs will be deltas against them. A MODIFIED requirement
   has to reproduce the current one verbatim.
4. **Open changes.** `openspec list --json`. For each active change, read its proposal and
   look for overlap: the same files, the same capability, claimed migration/sequence numbers,
   one change taking work from another. Overlap goes into the note. A scope boundary between
   two changes has to be written into **both** proposals later.
5. **The code the request touches.** Enough to know whether the flow exists already and what
   pattern it follows. Plus `git log --oneline -15` for recent motion in that area. Delegate
   a broad sweep to an Explore subagent and keep only its conclusion.
6. **`openspec/roadmap.md`, only when a question is still open.** If the steps above did not
   tell you whether the requested feature already exists, or the request sounds like a bug
   that may have been fixed before, refresh the index and search it:
   `python <skill>/scripts/roadmap.py <project-root>`, then Grep the file for the feature's
   or the bug's words. It holds one line per archived change, open change and `feat` / `fix`
   commit, and each hit names the change directory or the commit to read. Do not read the
   file through, and do not open it when the specs already answered: it grows with the
   project and is an index, not context.

## Scope check

If the request describes several independent subsystems ("chat, billing and analytics"),
say so now and propose splitting it into several changes, each with its own full cycle.
Agree the order with the user and take the first one through the stages. Write the parts
that wait as one line each under `## Planned` in `openspec/roadmap.md`: that section is
kept by hand, and it is where an idea without a change stays findable.

If the request is a one-line fix with no decisions in it, say that lcd-spec is heavier
than the task needs, and let the user choose. If they want lcd-spec anyway, run the full
pipeline at small scale: short design, a two-question grill, a one-task plan.

## Output: the context note

Post 5–10 lines in chat:

- what exists (capabilities, code paths) and what does not;
- relevant lessons from incidents.md (INC ids);
- what the roadmap showed, if you had to search it (the change or commit that already did
  this, or nothing found);
- overlapping open changes and what they claim;
- the scope verdict (one change / split proposed).

Then move to stage 1.
