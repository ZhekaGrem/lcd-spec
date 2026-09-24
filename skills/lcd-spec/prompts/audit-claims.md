# Auditor A: claims vs. code (stage 5)

Dispatched in parallel with auditor B. Capable model. Give it paths, not your opinion.

```
description: "Pre-apply audit A (claims vs code): [CHANGE]"
model: [MODEL]
prompt: |
  You audit a planned change before implementation starts. Your question: does the world the
  change describes exist, now, in the shape it claims? Do not judge whether the decisions
  are good; that was settled with the user. Do not modify anything.

  Change: openspec/changes/[CHANGE]/ (proposal.md, specs/, design.md, grilling.md, plan.md,
  tasks.md; design.md may contain "Audit findings" from an earlier audit - re-check those
  against the current text first).
  Repository root: [REPO_DIR]. Other open changes: openspec/changes/ (not archive/).
  Project lessons: openspec/incidents.md.

  Every claim is suspect, including ones marked "verified". Look for two diseases: rot (was
  true, became false: absolute statements about the repo) and stillborn (never true,
  checked by shape, not fact: third-party fields, where code should live, reuse of someone
  else's class).

  Checks:
  1. Every named object (file, class, method, column, endpoint, folder, config key): does it
     exist? with that signature? with that visibility? Check cited line numbers.
  2. Migration/sequence numbers: list every location sharing the numbering space (main,
     seed, test fixtures per build profile) and the numbers other open changes claim. An
     absolute number in the plan should be a task 0.x re-check.
  3. Third-party fields: is there a recorded response, log or fixture proving the field
     arrives? Is it gated by a request flag nobody sets?
  4. Code placement: find the nearest analogue of the same job and why it lives where it
     does. Read the enforced module boundaries.
  4b. Proxy/decorator mechanisms (@Cacheable, @Transactional, @Async, @PreAuthorize,
     middleware, ORM hooks): does the prescribed early return / skip / condition take effect
     where the change puts it? Self-invocation? Annotation order?
  4c. Browser mechanisms: overflow clipping the other axis and killing sticky,
     reduced-motion rules vs. animation-delay and JS timers, focus under auto-scroll, lazy
     loading / content-visibility / inert claims without an observed source.
  5. "Every surface" requirements: grep the old predicate and compare with the spec's list
     (aggregates and COUNT/MAX outside the shared builder, methods that filter nothing,
     same-named methods with different semantics).
  Also: which incidents.md lessons apply, and are they honoured?

  Evidence, not opinion: every finding carries path:line, grep output or a number. A claim
  you could not check goes under NOT VERIFIED, never under fine.

  Output:
  ## Blockers (break implementation at the first gate)
  ## Serious (do not block the start, but make a scenario false)
  ## Minor / docs
  ## NOT VERIFIED (and what would verify it)
  Each item: - claim quoted from artifact (file) - finding - evidence - suggested artifact fix
```
