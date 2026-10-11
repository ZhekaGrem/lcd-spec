# Stage 4 — Plan

Goal: describe the required behavior, change boundaries, integration points and checks
well enough that an implementer can build the right thing without guessing requirements.
The plan is a behavioral contract, not a second copy of the implementation. Write tests
and production code once in the working branch during stage 6 and verify those files.

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

Steps describe the intended behavior and test cycle: write the failing test in its source
file → confirm the expected failure → implement in the working branch → verify → commit.
Describe test inputs and expected outcomes in prose; do not write test bodies or production
implementation in Markdown.

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
  - **Behavior**: observable outcomes, representative inputs, errors and edge cases;
  - **Boundaries**: what this task changes and what stays outside its scope;
  - **Interfaces**: what it consumes from earlier tasks and produces for later ones, with
    exact names and types. An implementer sees only their own task, and this is how they
    learn the neighbours' signatures. Name existing callers, registration points and data
    flow that must be connected. A task that shares nothing writes `none`;
  - **Verify**: exact commands that check this task in the working branch, with expected
    outcomes; use unattended commands that terminate and exit non-zero on failure;
  - **Steps**: numbered `**Step K: …**` paragraphs, not checkboxes, describing actions,
    acceptance scenarios and exact commands with expected outcomes. Link to source files
    and interfaces instead of embedding implementation or test code.
- If a task depends on a moving number (a migration version, a sequence id), add a
  task 0.x that re-checks the number at apply time. A note does not work, because notes
  don't get executed.

### No placeholders

These are plan failures, and gate.py rejects the first three:

- "TBD", "TODO", "implement later", "fill in details", leftover `<!-- template comments -->`;
- "add appropriate error handling", "handle edge cases", "similar to Task N" (repeat the
  contract or reference its owning file: tasks are read out of order);
- steps with no concrete behavior, integration point or expected verification outcome;
- a type, function or file used in one task and defined in none.

### Risk prototypes

When a specific uncertainty needs an experiment, keep a short prototype in a separate
file under the change directory, for example `prototypes/<risk>.<ext>`. Record only its
path, the question, run command, observed result and limitation in the plan. Prototypes
are optional and narrowly scoped; they are not a parallel implementation or evidence
that production code passes. During apply, adapt or remove them as appropriate and run
checks against the actual implementation in the working branch.

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
