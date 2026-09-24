# Stage 5 — Pre-apply audit

Goal: every factual claim in the change (files, classes, methods, fields, migrations,
mechanisms, surfaces) is re-verified against the code as it is **now**, including claims
already marked "verified". The stamp is a premise too, and premises go stale.

This is not grilling. Grilling checked decisions. The audit checks whether the world the
change describes exists in the shape it claims. It costs about 15 minutes. Finding a
wrong model with half the code written costs days.

Output: `audit.md` (schema template), findings in design.md `## Audit findings`, incidents
for blockers, `Verdict: PASS`, stamped.

## Two diseases

- **Rot**: was true, became false. Symptom: absolute statements about the repository
  ("latest migration is V46", "folder X exists", "the controller is a stub").
- **Stillborn**: was never true, because it was checked by shape, not by fact. Symptom: claims
  about third parties, about where code should live, about reusing someone else's class.

## Run two auditors in parallel

Dispatch both in one message. Give each the change directory path and the repository root,
**not your opinion of the change**. Your framing would poison their read.

- **Auditor A: claims vs. code** (`prompts/audit-claims.md`): checks 1–5 below.
- **Auditor B: change vs. itself and runtime behaviour** (`prompts/audit-self.md`):
  checks 2b and 6–9, plus "the change against itself".

Use a capable model for both. A missed blocker here costs more than the tokens. When they
return, **verify every finding yourself** before accepting it: open the `path:line`, re-run
the grep. An auditor's claim is a hypothesis until you have seen the evidence. Where A and
B disagree, settle it with a primary artifact and record it under "Auditor disagreements".

## The checks

### 1. Every named object gets a grep
List every proper name in the artifacts: files, classes, methods, columns, endpoints,
folders, config keys. Ask three questions of each, not one: does it exist? with that
signature? with that visibility? The second and third catch the most: a class can exist but
be package-private in another module, need an argument this change deletes, or return
exactly the fields the change must not touch. Check line-number citations too: they shift,
and a wrong citation still reads like evidence.

### 2. Migration / sequence numbers are a forecast
List every location that shares the numbering space: main migrations, seeds, test
fixtures, whatever the build composes per profile. Grep the other open changes for the
numbers they claim. An absolute number in an artifact becomes a task 0.x that re-checks
it at apply time.

### 2b. Run the migration in your head on an empty database
For every backfill or `INSERT … SELECT`: has the source migration ever left this branch?
What rows exist after the full chain on a fresh database, and does the spec's
"initial state" scenario agree? An unconditional move of a seeded-empty row creates one
empty item everywhere.

### 3. A third-party field is real only with a recorded response
A DTO field is what we declared, not what the server sends. Look for a recorded response,
a log or a fixture. Zero hits in the dump plus zero readers in the code means the field
never arrived. Check whether a request flag nobody sets gates it.

### 4. Where code lives comes from precedent
Before accepting "the service lives in module X", find the nearest analogue of the same job
and ask why it sits where it does. Read the module boundaries the project enforces
(Modulith `allowedDependencies`, import-lint rules, workspace boundaries). The architecture
test will say the same, but only mid-implementation.

### 4b. A prescribed mechanism must take effect where it is placed
Proxy- or decorator-evaluated mechanisms (`@Cacheable`, `@Transactional`, `@Async`,
`@PreAuthorize`, middleware, ORM hooks) decide around the method. So:

- a conditional inside a cached method cannot stop the lookup or the store;
- an early return meant to skip the cache only works in a caller outside the proxy;
- self-invocation gets no advice;
- two annotations on one method have no guaranteed order.

The tell: "we return early / we skip / we check first" about an annotated method.

### 4c. Frontend mechanisms are evaluated by the browser
- `overflow-x: auto|hidden` forces the other axis off `visible`. Overhangs, glows and focus
  rings get clipped, and `position: sticky` inside it dies.
- A `prefers-reduced-motion` rule shortening `animation-duration` leaves
  `animation-delay` alone. No CSS rule can see a JS timer; that needs `matchMedia`.
- Autoplaying or auto-scrolling regions move content out from under keyboard focus. Walk
  the Tab key through them.
- `loading="lazy"`, `content-visibility`, `inert`, `scroll-snap` with smooth scroll: cite
  where the behaviour was observed, or list it as not verified.

### 5. "On every surface": enumerate by grep
When a requirement replaces a predicate, generate the affected list by grepping the old
predicate and compare it with the spec's list. Watch for queries that filter outside the
shared builder (aggregates, COUNT, MAX), methods that filter nothing, and same-named methods
with different semantics.

### 6. What sits between the write and the read
For "immediately visible / disappears", ask what is in between: a cache, a projection, an
index, a materialized view. Who invalidates it? If a scheduler does, the requirement is
false for exactly its period. The test is green because it reads the database, while the
UI reads the cache.

### 7. State machines: who cleans up after a death
For every "one at a time / while in progress" guard, ask who clears the flag if the process
dies. `RUNNING` with no startup recovery blocks the feature forever. Also check state
completeness: a state mentioned in prose but missing from the enum.

### 8. "Replaces the set wholesale": save it twice
Walk the **second** save of a full-collection replace (PUT with the full list, delete-all +
re-insert, orphan removal). Fields written by another endpoint get reset. Child ids get
re-minted, and URLs that address a child by id break. Hold the reset state against the
table's constraints. If anything is written elsewhere, the design must say merge by id.

### 9. The version lives on the parent; the change writes the children
Optimistic locks fire only for the row with the version column. For each write, name the
column of the versioned row it modifies. If there is none, the design must prescribe the
bump, and a task must test that the version grew.

### The change against itself
- New fields that don't exist yet: walk "who writes it → who reads it" through the change
  and compare the semantics word for word.
- A scope boundary with a neighbouring change is written into both proposals.
- `MODIFIED` requirements reproduce the original verbatim.
- Late grilling decisions (a changed threshold, cadence or ordering) are re-read against
  the earlier decisions.
- Plan vs. specs: every scenario has a task that tests it. Plan vs. design: no task
  contradicts a decision.
- incidents.md lessons: every relevant lesson is honoured.

## Findings

Don't fix anything as you go, and don't touch code. Collect first, then write audit.md,
grouped by blast radius:

- **Blockers**: break implementation at the first gate (compile, architecture test,
  migration).
- **Serious**: don't block the start, but make a spec scenario false.
- **Minor / docs**: stale citations, no-op tasks, documentation.
- **What I did NOT verify** (mandatory): anything that needs a live database, a production
  key or a running stack. Name it here instead of letting it pass quietly as fine.

Every finding carries evidence: `path:line`, grep output, a number. A claim without a
reference is unfalsifiable and rots exactly like the one you just found.

## Resolving

1. Show the user the grouped list.
2. Anything that changes scope or ordering (drop a requirement, move a boundary, reorder
   changes) goes to the user as a question. Technical matters (module placement, error
   state, cache eviction) you decide, stating the assumption out loud.
3. Apply fixes **to the artifacts** (proposal / specs / design / plan / tasks), never
   straight to code.
4. Append one line per finding to design.md `## Audit findings` (create it on the first
   audit): date, finding with `path:line`, outcome: **fixed in <artifact>**, **accepted
   as a named deviation**, or **dropped, because …**. When this section already exists, read it
   **first** and hold every earlier finding against the current text. A finding that a
   rewrite quietly lost is reported again, with its original date.
5. Add an incidents.md entry for each Blocker (class `rot` or `stillborn` usually), with
   a Lesson future changes can act on.
6. Tick each resolved blocker `- [x]` in audit.md.
7. If a fix changed a **decision**, grilling is now stale for a real reason. Grill that
   point, update grilling.md, re-stamp it. If fixes only corrected facts, re-stamp grilling
   with a line under `## Re-stamps`.
8. `Verdict: PASS`, then:
   ```
   python <skill>/scripts/gate.py stamp openspec/changes/<name> audit
   python <skill>/scripts/gate.py check openspec/changes/<name> audit
   ```
   Show the output. Only `PASS audit` moves you to stage 5b (perspective review), where
   the user decides whether the plan also gets reviewed as tester / user / programmer /
   architect.

## When to audit again

Re-run stage 5 before continuing when the change was planned more than a few days ago and
merges have landed since, when a parallel session worked in the same tree, when the
artifacts were written by another session or agent, or when the design was rewritten after
the last audit. The gate's stale check catches edits to the change. It cannot see edits to
the code the change talks about.
