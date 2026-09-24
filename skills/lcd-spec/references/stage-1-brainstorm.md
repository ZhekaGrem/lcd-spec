# Stage 1 — Brainstorm

Goal: an agreed design, reached in dialogue, before a single artifact is written. Writing
the spec first and discussing it afterwards anchors everyone on the first draft.

**Hard gate:** no artifacts, no code, no scaffolding until the user approves the design
you presented in chat. Read-only exploration is fine.

## 1. Restate and confirm

Before the first design question, write back your understanding and ask the user to
confirm it:

1. The real problem being solved: the goal, not the literal wording.
2. What is already clear.
3. What is ambiguous or open to two readings.
4. What you would most likely get wrong if you started coding now. Name the riskiest
   assumptions.
5. The implementation details that would change the approach.
6. The task in your own words.
7. "Did I understand you correctly?" Then wait.

Separate what the user said from what you assume. If the request already answers most of
this, keep it short, but still ask.

## 2. Questions, one at a time

- One question per message. If a topic needs more, split it into several messages.
- Prefer multiple choice, with your recommendation first and why.
- Ask about purpose, constraints and success criteria. What does "done" look like to the
  user?
- Facts you can read in the code, you read. Only decisions go to the user.
- Use the lessons from stage 0. "Last time the cache hid the change for 10 minutes
  (INC-…). Must this be visible immediately?"

## 3. Two or three approaches

Present 2–3 real alternatives with trade-offs. Lead with the one you recommend and say
why. Cut features nobody asked for from every option (YAGNI). If one option is obviously
right, still name the runner-up and why it lost. That reasoning goes into design.md.

## 4. Design in sections

Present the design in sections sized to their complexity: a few sentences when
straightforward, up to 200–300 words when nuanced. After each section, ask whether it looks
right. Cover:

- architecture and components: units with one purpose and a clear interface each;
- data flow and state, including who writes and who reads every new field;
- error handling and failure states, including who cleans up after a crash;
- testing: what proves each behaviour;
- migration or rollout, if any.

In an existing codebase, follow its patterns. Include targeted improvements where the
current code gets in the way of this change, but no unrelated refactoring.

Hidden complexity found mid-dialogue upgrades the scope. Say so and re-plan. Nothing
downgrades mid-task.

## 5. Approval and naming

When the user approves the design:

1. Propose a kebab-case change name (`add-order-export`) and confirm it.
2. Run `openspec new change "<name>"`, then `openspec status --change "<name>"`. Check that
   the schema is `lcd-spec`.
3. Move to stage 2. The approval covers writing the artifacts, not implementing them.
