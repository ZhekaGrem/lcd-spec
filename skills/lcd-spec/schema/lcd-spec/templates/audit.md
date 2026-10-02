# Pre-apply audit: <!-- change name -->

Verdict: PENDING
<!-- PASS only when every blocker below is ticked (resolved through an artifact update and
     recorded as an incident).
     Then run: python <lcd-spec>/scripts/gate.py stamp <change-dir> audit -->

Audited: <!-- date, HEAD commit --> · Auditors: <!-- A (claims vs code), B (change vs itself) -->

## Blockers

<!-- Break implementation at the first gate (compile, architecture test, migration).
- [ ] <finding> - evidence: path:line / command output - fix: <artifact update>
     Tick it ([x]) only when the fix landed in the artifacts AND the blocker is recorded in
     openspec/incidents.md; end the ticked line with that entry's id: (INC-YYYYMMDD-N).
     The gate fails on a ticked blocker without an id of an existing entry. None found: leave
     the section empty. -->

## Serious

<!-- Do not block the start, but make a spec scenario false. Same format; each is fixed or
     accepted as a named deviation in design.md "Audit findings". -->

## Minor / docs

<!-- Stale citations, no-op tasks, documentation. -->

## Auditor disagreements

<!-- Where A and B disagreed and which artifact settled it. -->

## What I did NOT verify

<!-- Mandatory: anything that needs a live database, a production key, a running stack. -->
