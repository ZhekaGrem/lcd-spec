# Stage 2 — Artifacts: proposal, specs, design

Goal: turn the agreed design into OpenSpec artifacts that a stranger could implement from.

## Writing

For each of `proposal`, `specs`, `design`, in dependency order:

1. `openspec instructions <artifact> --change "<name>" --json`
2. Read its `instruction`, `template`, `rules`, `context` and the dependency files it lists.
   `context` and `rules` constrain **you**; never copy them into the file.
3. Write the file to `resolvedOutputPath`, following the template's sections.

Points that matter more than the template suggests:

- **Proposal / Capabilities** is the contract with specs. Each capability named there needs
  exactly one `specs/<capability>/spec.md`. Check `openspec/specs/` for existing names
  before inventing a new one.
- **MODIFIED requirements** reproduce the current requirement verbatim, then edit. A partial
  block silently deletes the rest at archive time.
- **Scenarios** use exactly `#### Scenario:` with WHEN/THEN. Each scenario is a future test.
- **"On every surface / everywhere"**: enumerate the surfaces by grepping the old
  predicate, and write them into the spec by name.
- **Design / Decisions**: each decision names the alternatives from stage 1 and why they
  lost. Grilling will attack exactly these.
- **Scope boundary with another open change**: edit that change's proposal in the same
  session, so both documents say the same thing.
- **What the user did not say**: anything you filled in on your own gets
  `ASSUMED (unconfirmed): <what you assumed>` right where it is used, and a gap you could
  not fill gets `[NEEDS CLARIFICATION: <question>]`. Open design questions go under design.md
  `## Open Questions` as `- [ ]` items. A silent guess reads like a decision and nobody
  questions it later; a marker becomes a stage 3 question. `gate.py check … grilling` fails
  while any marker or unchecked question remains.

## Self-review before showing the user

Read the three artifacts again with fresh eyes and fix what you find:

1. **Placeholders**: TBD, TODO, empty sections, "etc." hiding real content.
2. **Consistency**: design contradicting a spec, or a scenario contradicting the proposal.
3. **Ambiguity**: any requirement that could be read two ways. Pick one and make it explicit.
4. **Scope**: is this still one change? If not, go back to the user.
5. **Lessons**: each relevant incidents.md lesson is either handled or explicitly marked
   not applicable.

Then run `openspec validate "<name>"` and fix every error.

## User review

Tell the user where the files are and ask them to read the artifacts before grilling
starts. Keep it short: list the capabilities, the key decisions, and the non-goals.
Apply the requested changes, re-run the self-review and validate. Move to stage 3 only after
the user says the artifacts are ready to be grilled.
