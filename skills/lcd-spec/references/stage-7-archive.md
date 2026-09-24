# Stage 7 — Archive

Goal: the change moves to `openspec/changes/archive/<date>-<name>/` with everything it
produced, and its deltas merge into the living specs. After this, `openspec/changes/` holds
only work that is still to do.

## Checks before archiving

1. `openspec status --change "<name>"`: all artifacts done.
2. tasks.md: every task `- [x]`. An unticked task means the change is not finished. Ask
   the user whether to finish it or split the remainder into a new change. Never archive
   silently with open tasks.
3. The plan's Verification commands ran green in stage 6. If code changed since, run them
   again and show the output.
4. `openspec validate "<name>"` passes.
5. `.work/` is gone. ledger.md, grilling.md, plan.md and audit.md stay: they are the change's
   history and move with it.

## Archive

Show the user what the archive will merge into the living specs (added / modified / removed
requirements per capability) and ask for confirmation. Then:

```
openspec archive "<name>" -y
```

Check the result: the directory exists under `openspec/changes/archive/`, and
`openspec list --specs` shows the updated capabilities.

## Commit

Commit only if the user asks, following the project's commit conventions. The archive move
and the spec merge belong in one commit.

## After the archive

A bug reported later in this change's behaviour is an incident. Add it to
`openspec/incidents.md` with `Stage: after-archive`, and link the archived directory in the
entry. A fix big enough for a spec is a **new** change. Archived changes are not reopened.
