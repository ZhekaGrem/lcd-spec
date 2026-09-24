# Incident audit

When a user swears at the agent, blames it, or reports the same failure again, the usual
cause is one wrong belief the agent still treats as fact: about the request, the code, the
runtime, or the tool. Another attempt built on the same belief repeats the failure with small
variations. This protocol stops the loop and looks for that belief. The result is recorded in
`openspec/incidents.md`, so the project, not only this session, learns from it.

The ideas come from the Z.A.E.B.A.L. self-audit protocol
(github.com/howdeploy/Z.A.E.B.A.L). This text is an independent rewrite for lcd-spec.

## Entry

The protocol starts in one of three ways:

- **Hook**: a `<lcd-spec-signal level="N">` block in the context (from `scripts/frustration.py`).
- **Manual**: the user asks for an audit of the session ("зроби аудит", "lcd-spec audit",
  "що пішло не так"). Run level 1 unless a signal already set a higher level.
- **No hook installed**: the user is clearly frustrated **with your work**. Run level 1.
  Do not invent a streak.

### False-trigger check (hook entries only)

First decide whether the message is really aimed at your work. Quotes, a pasted
client message, talk about the detector itself, and swearing about the outside world
("npm знову впав", "цей legacy — лайно") are false triggers. For those, say in one line why,
run the `--dismiss` command from the signal, and continue the task. A lexical dismissal does not
dismiss a real complaint in the same message: still address it.

## Level 1: first signal

1. **Stop** the current line of work.
2. **Reconstruct the chronology.** Go from the original request through every correction to
   now: what was asked, what you did, what you verified. Find the **divergence point**, the
   earliest turn where your interpretation or action departed from the request, and match it
   to the diff or commits it produced.
3. **Two independent auditors.** Dispatch two subagents in parallel with
   `prompts/incident-auditor.md`. Give them **raw artifacts**: the verbatim original request
   and corrections, the transcript path if available, `git status`, the relevant diffs,
   `git log` with timestamps, test and error output. Do **not** give them your diagnosis.
   Poisoned context poisons the audit. Ask one to scrutinize the interpretation of the
   request, and the other the causal path in the code or runtime. If subagents are
   unavailable, say so in one line and do the inventory yourself. Never skip it silently.
4. **Belief inventory.** Tag each statement **FACT** (confirmed by a run, a file, a log,
   with the source named) or **HYPOTHESIS**. Keep competing causes until a **discriminating
   check** separates them: the smallest check whose result would disprove your explanation.
   Run it.
5. **Report to the user**, briefly: the wrong belief (or `not established`), the divergence
   point, the check that decided it, and the next action that changes because of it.
6. Write the incidents.md entry (below). Continue the work within the existing authorization.

## Level 2: repeated signal

Everything in level 1, plus:

- **Audit the previous audit first.** What did it claim? What action was actually taken?
  Why did the symptom repeat? Distinguish new requirements or new information from a fix that
  failed. Without new evidence, change the hypothesis or the approach. Do not repeat the
  same audit, test or patch.
- **Compare against the original request**: quote it verbatim next to what you are doing now.
- No edits until this analysis is done.

## Level 3: the foundation may be wrong

1. **Full stop.** Stop running subagents and background work on the failing line. Launch
   nothing except the two auditors. **No edits and no mutating commands** until the user
   explicitly says to continue ("продовжуй", "continue", "по плану"). There is no technical
   lock. The stop is your discipline.
2. Run the level 2 analysis using **existing evidence only**. A new run, a mutation or an A/B
   experiment is listed as a check to do after the user says to continue.
3. Show the user: the wrong belief or `not established`, the divergence point, the verbatim
   original request, what was actually done, and the discrepancy.
4. Prepare, as text only, a **handoff**: what is known to be correct, what depends on the
   hypothesis and may need rollback, and the checks to run after continuing.
5. Wait. **Evidence is not acknowledgment**: new logs or files from the user allow read-only
   analysis and an updated verdict, not edits. Only an explicit go-ahead lifts the stop, and
   it permits work. It does not prove the problem is solved.

## Named failure patterns

Check your own behaviour against these. They recur:

- **Written is not consumed.** You wrote a config, hook, env variable or instruction file, and
  "the file exists" became "it works". Verify the consumer: the real load path, the real
  registration, the real effect.
- **Healthy is not serving.** A green healthcheck, passing tests or quiet logs prove only that
  the process you looked at is alive. When behaviour contradicts the healthy picture, list
  every candidate instance (local and server, similar names, old builds, other ports) and
  trace one real request to the process that handles it.
- **Syntax roulette.** A command failed and you keep rearranging flags from memory. After one
  failure, read the installed version's `--help` and the current docs, and inspect a local
  wrapper script before you even run its `--help`.
- **Sycophancy / hallucinated correctness.** Two opposite failures: agreeing under pressure
  without evidence, or defending code with invented facts (tests that did not run, features
  that do not exist). Both are fixed the same way: tie every claim to an observed artifact.
- **Proxy test.** A test passes on a nearby unit, a helper or the wrong target. That is
  intermediate evidence. The outcome is the exact artifact the user sees.
- **Invented scope.** Your paraphrase or an earlier audit's paraphrase became the task. Re-read
  the user's action words: investigate is not deploy, compare is not rewrite.

## Output format (both auditors and your summary)

`CONTRACT` (the user's words and corrections, plus the assumption you added) ·
`DIVERGENCE POINT` · `FACTS` (each with its source) · `HYPOTHESES` (at least two, unless one
is directly proven) · `DISCRIMINATING CHECK` (the check, the result that would disprove the
explanation, the action it changes) · `PREVIOUS AUDIT` (claim → action → repeated symptom) ·
`WRONG BELIEF` (only after the check, else `not established`) ·
`STATUS` (CONFIRMED / PARTIAL / UNVERIFIED / DISPROVED, for the diagnosis) ·
`OUTCOME GATE` (the exact user-visible artifact, and whether the result is verified,
partial or unverified).

## Recording the incident

Append to `openspec/incidents.md` (create it from `references/incidents-template.md` if
missing):

- `Signal: frustration L<n>` or `manual audit`;
- `Change:` the active lcd-spec change if any, and the `Stage:` you were in;
- `Wrong belief`, `Evidence`, `Class` (e.g. written-not-consumed, misread-request,
  wrong-runtime, syntax-roulette, rot, stillborn);
- `Fix` and one **Lesson** in the imperative, one that a future spec, grill, plan or audit can
  act on ("Before prescribing a cache, name its invalidator and its delay in the spec").

Add the lesson to the Lessons index. If the wrong belief is not established, still record the
incident with `Wrong belief: not established` and what is still unverified. A repeat of the
same symptom later starts from this entry.
