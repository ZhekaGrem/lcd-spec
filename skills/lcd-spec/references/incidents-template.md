# Incidents

Project-level log of what went wrong while specifying and building this project, and what
to check next time. Written by the lcd-spec skill (frustration audits, pre-apply audit
blockers, review loops that hit the cap, bugs found after archive). Read at the start of
every new change.

Keep entries short. The **Lesson** line is what future changes read - write it as an
instruction that a future spec, grill, plan or audit can act on.

One mistake is one entry. Before adding an entry, look for the one it repeats
(`incidents.py find`); a repeat is counted on the existing entry (`incidents.py bump`), not
written again. After any edit, `incidents.py validate` checks the format.

## Lessons index

<!-- One line per active lesson, newest first: INC-id - lesson. Retire a lesson by moving
     its line to "Retired lessons" with the reason. -->

## Entries

<!--
### INC-YYYYMMDD-N: <short title>
- **Date:** YYYY-MM-DD
- **Change:** <change name or "none">
- **Stage:** context | brainstorm | artifacts | grill | plan | audit | perspectives | apply |
  archive | after-archive | none
- **Signal:** frustration L<n> | manual audit | audit blocker | perspective review |
  review cap | final review | test failure | user report
- **What happened:** <one or two sentences, facts only>
- **Wrong belief:** <the assumption that turned out false, or "not established">
- **Evidence:** <path:line, command output, commit>
- **Class:** rot | stillborn | misread-request | written-not-consumed | wrong-runtime |
  syntax-roulette | scope-creep | unverified-claim | proxy-test | other
- **Fix:** <what changed, commit or artifact>
- **Lesson:** <imperative sentence a future stage can apply>

Optional. Without them the lesson goes into every plan and every task brief; with them it
goes only where it applies:
- **Trigger:** <the situation right before the mistake: "adding a cache in front of an entity
  admins can edit"> - what `incidents.py find` matches a new incident against
- **Stack:** <tags, comma-separated: java, spring, maven, ts, nextjs, go, python, sql, docker>
- **Paths:** <globs of the files the lesson is about: **/cache/**, **/*Cache*.java>
- **Needed at:** <stages that must see the lesson, comma-separated: plan, apply>

Written by `incidents.py bump`, never by hand:
- **Recurrence:** <how many times this happened>
- **Seen:** <the date of every occurrence>
-->

## Retired lessons
