# Stage 7 — Archive

Goal: the change moves to `openspec/changes/archive/<date>-<name>/` with everything it
produced, and its deltas merge into the living specs. After this, `openspec/changes/` holds
only work that is still to do.

## Checks before archiving

1. `openspec status --change "<name>"`: all artifacts done.
2. tasks.md: every task `- [x]`. An unticked task means the change is not finished. Ask
   the user whether to finish it or split the remainder into a new change. Never archive
   silently with open tasks.
3. `python <skill>/scripts/gate.py check openspec/changes/<name> archive` prints
   `PASS archive`: every earlier gate still holds, and verification.md is a green run of
   the plan's Verification commands against the code as it is now. On `missing` or `stale`,
   run `python <skill>/scripts/verify_run.py openspec/changes/<name>` and show the result.
   A red run means the change is not finished.
4. `openspec validate "<name>"` passes.
5. `.work/` is gone. ledger.md, grilling.md, plan.md, audit.md and verification.md stay:
   they are the change's history and move with it.

## Archive

Show the user what the archive will merge into the living specs (added / modified / removed
requirements per capability) and ask for confirmation. Then:

```
openspec archive "<name>" -y
```

Check the result: the directory exists under `openspec/changes/archive/`, and
`openspec list --specs` shows the updated capabilities.

## Roadmap

```
python <skill>/scripts/roadmap.py <project-root>
```

It rewrites `openspec/roadmap.md`: the change moves from "In progress" to "Archived
changes", and the `feat` / `fix` commits made since the last run are added. If the change
delivered a line that stood under `## Planned`, delete that line by hand: the script never
touches that section.

## Commit

Commit only if the user asks, following the project's commit conventions. The archive move,
the spec merge and the refreshed roadmap belong in one commit.

## After the archive

A bug reported later in this change's behaviour is an incident. Record it in
`openspec/incidents.md` (`references/incident-audit.md`, "Recording the incident": find,
then bump or add, then validate) with `Stage: after-archive` and `Signal: user report`, and
link the archived directory in the entry. A fix big enough for a spec is a **new** change. Archived changes are not reopened.
