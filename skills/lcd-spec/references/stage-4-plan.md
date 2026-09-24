# Stage 4 — Plan

Goal: a plan detailed enough that an implementer subagent with zero context and doubtful
taste builds the right thing. Assume they are skilled but know nothing about this codebase,
its tools or its domain, and are weak at test design.

Output: `plan.md` (detailed) and `tasks.md` (tracker), with identical task numbers.

## Before writing tasks: file structure

Map which files are created or modified and the single responsibility of each. This is
where decomposition gets locked in.

- One clear responsibility per file, with a well-defined interface. Files that change
  together live together; split by responsibility, not by layer.
- Follow the codebase's existing patterns. Do not restructure what the change does not need.
- Prefer smaller focused files. Agents edit them more reliably.

## Task size

A task is the smallest unit that carries its own test cycle and deserves its own review.
Fold setup, config and docs into the task whose deliverable needs them. Split only where a
reviewer could reject one task and approve its neighbour. Each task ends with an
independently testable deliverable.

Steps inside a task are single actions of 2–5 minutes: write the failing test → run it and
watch it fail → minimal code → run it and watch it pass → commit.

## plan.md

Use the schema template. Required parts:

- **Header**: Goal, Architecture, Tech Stack, Spec (the change's own files).
- **Global Constraints**: the spec's project-wide requirements (versions, formats, naming,
  limits), one line each, values copied verbatim. Every task inherits them, and the reviewer
  gets them as its lens.
- **Verification**: the commands that prove the whole change (tests, typecheck, lint, build),
  taken from the project's real scripts.
- **Review Focus**: up to five inputs or failure modes the spec implies but no test covers
  yet, most likely to bite a real user first. The spec says what the software must do,
  and its silence about an input is not permission to break on it. Add the test for each line
  to the task that owns the code.
- **Tasks**: `### Task N.M: <name>`, each with:
  - **Files**: exact paths to create, modify (with line ranges) and test;
  - **Interfaces**: what it consumes from earlier tasks and produces for later ones, with
    exact names and types. An implementer sees only their own task, and this is how they
    learn the neighbours' signatures;
  - **Steps**: numbered `**Step K: …**` paragraphs, not checkboxes, with real code and
    exact commands with expected output.
- If a task depends on a moving number (a migration version, a sequence id), add a
  task 0.x that re-checks the number at apply time. A note does not work, because notes
  don't get executed.

### No placeholders

These are plan failures, and gate.py rejects the first three:

- "TBD", "TODO", "implement later", "fill in details", leftover `<!-- template comments -->`;
- "add appropriate error handling", "handle edge cases", "similar to Task N" (repeat the
  code: tasks are read out of order);
- steps that say what to do without showing how;
- a type, function or file used in one task and defined in none.

## tasks.md

A tracker, not a plan. One `- [ ] N.M <short title>` line per `### Task N.M`, grouped under
`## N. <group>`. The same numbers in both directions (gate.py checks). No detail here:
OpenSpec counts every checkbox in tasks.md as a task, and TDD steps would inflate the
count and make the progress meaningless.

## Self-review

1. **Spec coverage**: every requirement and scenario maps to a task. Add the missing tasks.
2. **Type consistency**: names and signatures agree across tasks (`clearLayers` in 1.3 is
   not `clearFullLayers` in 2.1).
3. **Review Focus**: each line has its test in an owning task.
4. **Grilling decisions**: each decision in grilling.md shows up where it applies.

For a plan over ~8 tasks, or one crossing several modules, also dispatch a plan reviewer
(`prompts/plan-reviewer.md`, standard model) and fix what it finds.

Then:
```
python <skill>/scripts/gate.py check openspec/changes/<name> plan
```

## User review

Give the user the plan path, the number of tasks, and the riskiest two. Ask them to review.
Changes loop back through self-review and the gate. Stage 5 starts only after the user
approves the plan.
