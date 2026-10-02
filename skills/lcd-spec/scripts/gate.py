#!/usr/bin/env python3
"""Hard gates between lcd-spec stages.

OpenSpec's own schema only knows whether an artifact file exists. This script checks
what the file says and whether it is still true:

  grilling  grilling.md has "Verdict: PASS", a non-empty "Decisions" section, an
            "Open questions" section with nothing unanswered, and was stamped against
            the current proposal / specs / design; those artifacts carry no
            "[NEEDS CLARIFICATION" / "ASSUMED (unconfirmed)" marker and design.md has
            no unchecked open question
  plan      grilling passes; plan.md has Global Constraints, a non-empty Verification
            and File Structure, no placeholders, a Files and an Interfaces block in
            every task, exactly the same task numbers as tasks.md, and a "Lessons
            applied" line for every active lesson in openspec/incidents.md that
            applies to the plan's files at the plan or apply stage
  audit     plan passes; audit.md has "Verdict: PASS", a "Blockers" section with
            nothing open and an existing INC id on every resolved blocker, a "What I
            did NOT verify" section, and was stamped against the current
            proposal / specs / design / grilling / plan / tasks
  review    audit passes; review.md exists with "Verdict: SKIPPED" (the user declined the
            perspective review) or "Verdict: PASS" with a "Perspectives:" line and a
            "Must fix" section with nothing open
  apply     review passes
  archive   apply passes; verification.md (written by `verify_run.py <change>`) shows
            every Verification command exiting 0, and the project's files have not
            changed since that run

A required section that is absent fails the gate: a file that dropped the section would
otherwise pass exactly the check the section exists for.

"Stamped" means `gate.py stamp` wrote an Artifacts-Hash line after the stage finished.
Editing any covered artifact afterwards makes the stage stale until it is re-checked
and re-stamped. Ticking checkboxes in tasks.md and appending an "Audit findings"
section to design.md do not count as edits.

Usage:
  python gate.py check  <change-dir> <grilling|plan|audit|review|apply|archive>
                                                             exit 0 = PASS, 1 = FAIL
  python gate.py stamp  <change-dir> <grilling|audit>
  python gate.py status <change-dir>
"""
from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import incidents
import verify_run

HASH_LINE_RE = re.compile(r"^Artifacts-Hash:.*$", re.M)
VERDICT_RE = re.compile(r"^Verdict:\s*(\S+)", re.M)
TASK_ID_RE = re.compile(r"^\s*- \[[ xX]\] (\d+(?:\.\d+)*)\b", re.M)
PLAN_TASK_RE = re.compile(r"^#{2,4}\s+Task\s+(\d+(?:\.\d+)*)\b")
CHECKBOX_RE = re.compile(r"^(\s*- )\[[xX]\]", re.M)
UNCHECKED_RE = re.compile(r"^\s*- \[ \]", re.M)
CHECKED_RE = re.compile(r"^\s*- \[[xX]\]\s*(.*)$", re.M)
INCIDENT_ID_RE = re.compile(r"INC-\d{8}-\d+")
PLACEHOLDER_RE = re.compile(
    r"\bTBD\b|\bTODO\b|implement later|fill in details|add appropriate error handling"
    r"|handle edge cases|similar to task\s+\d|<!--", re.I)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
UNCONFIRMED_RE = re.compile(r"\[NEEDS CLARIFICATION|ASSUMED \(unconfirmed\)", re.I)
TASK_BLOCKS = ("Files", "Interfaces")

PERSPECTIVES_RE = re.compile(r"^Perspectives:\s*\S", re.M)

STAGES = ("grilling", "plan", "audit", "review", "apply", "archive")


@dataclass
class Result:
    stage: str
    reasons: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.reasons


# --- helpers -------------------------------------------------------------------

def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").replace("\r\n", "\n")
    except OSError:
        return None


def section(text: str, title: str) -> str | None:
    """Body of the first '## <title>' section (case-insensitive prefix match), or None."""
    m = re.search(rf"^##\s+{re.escape(title)}[^\n]*\n", text, re.M | re.I)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^##\s", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def strip_section(text: str, title: str) -> str:
    body = section(text, title)
    if body is None:
        return text
    m = re.search(rf"^##\s+{re.escape(title)}[^\n]*\n", text, re.M | re.I)
    return text[: m.start()] + text[m.end() + len(body):]


def _has_content(body: str | None) -> bool:
    """True when a section holds something besides template comments and rules."""
    if body is None:
        return False
    return any(line.strip() and line.strip() != "---"
               for line in COMMENT_RE.sub("", body).splitlines())


def _open_items(text: str, title: str) -> int | None:
    """Unchecked boxes under '## <title>', or None when the section is absent."""
    body = section(COMMENT_RE.sub("", text), title)
    return None if body is None else len(UNCHECKED_RE.findall(body))


def _plan_tasks(plan: str) -> tuple:
    """(text before the first task, [(task id, its lines outside code fences)])."""
    preamble, tasks, in_fence = [], [], False
    for line in plan.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = PLAN_TASK_RE.match(line)
        if m:
            tasks.append((m.group(1), []))
        elif tasks:
            tasks[-1][1].append(line)
        else:
            preamble.append(line)
    return "\n".join(preamble), tasks


def _covered_files(change: Path, artifact: str) -> list:
    """(relative name, normalized content) pairs whose hash the stamp protects."""
    files = []
    for name in ("proposal.md", "design.md"):
        text = _read(change / name)
        if text is not None:
            if name == "design.md":
                text = strip_section(text, "Audit findings")
            files.append((name, text))
    for spec in sorted((change / "specs").rglob("*.md")):
        files.append((spec.relative_to(change).as_posix(), _read(spec) or ""))
    if artifact == "audit":
        for name in ("grilling.md", "plan.md", "tasks.md"):
            text = _read(change / name) or ""
            if name == "grilling.md":
                text = HASH_LINE_RE.sub("", text)
            if name == "tasks.md":
                text = CHECKBOX_RE.sub(r"\1[ ]", text)
            files.append((name, text))
    return files


def artifacts_hash(change: Path, artifact: str) -> str:
    digest = hashlib.sha256()
    for name, text in _covered_files(change, artifact):
        digest.update(name.encode() + b"\0" + text.strip().encode("utf-8") + b"\0")
    return digest.hexdigest()[:16]


# --- stamping -------------------------------------------------------------------

def stamp(change: Path, artifact: str) -> str:
    if artifact not in ("grilling", "audit"):
        raise ValueError("only grilling and audit are stamped")
    path = change / f"{artifact}.md"
    text = _read(path)
    if text is None:
        raise FileNotFoundError(path)
    line = f"Artifacts-Hash: {artifacts_hash(change, artifact)}"
    if HASH_LINE_RE.search(text):
        text = HASH_LINE_RE.sub(line, text, count=1)
    elif VERDICT_RE.search(text):
        m = VERDICT_RE.search(text)
        end = text.find("\n", m.start())
        end = len(text) if end == -1 else end
        text = text[:end] + "\n" + line + text[end:]
    else:
        text = line + "\n\n" + text
    path.write_text(text, encoding="utf-8")
    return line


# --- checks ---------------------------------------------------------------------

def _verdict_and_stamp(change: Path, artifact: str, text: str, reasons: list) -> None:
    m = VERDICT_RE.search(text)
    if not m or m.group(1).upper() != "PASS":
        found = m.group(1) if m else "none"
        reasons.append(f"{artifact}.md: verdict is '{found}', needs 'Verdict: PASS'")
    h = HASH_LINE_RE.search(text)
    if not h:
        reasons.append(f"{artifact}.md: not stamped - run `gate.py stamp <change> {artifact}` "
                       "when the stage is finished")
    elif h.group(0).split(":", 1)[1].strip() != artifacts_hash(change, artifact):
        reasons.append(f"{artifact}.md: stale - artifacts changed after it was stamped; "
                       f"re-check the changes against {artifact}.md, then re-stamp")


def _check_grilling(change: Path, reasons: list) -> None:
    text = _read(change / "grilling.md")
    if text is None:
        reasons.append("grilling.md missing - run stage 3 (grill) first")
        return
    _verdict_and_stamp(change, "grilling", text, reasons)
    if not _has_content(section(text, "Decisions")):
        reasons.append("grilling.md: '## Decisions' is missing or empty - record each decision "
                       "the user made, or 'none - <why>' when the change has none")
    open_q = _open_items(text, "Open questions")
    if open_q is None:
        reasons.append("grilling.md: no '## Open questions' section - keep it, empty when "
                       "nothing is open")
    elif open_q:
        reasons.append(f"grilling.md: {open_q} open question(s) still unanswered")
    _check_unconfirmed(change, reasons)


def _check_unconfirmed(change: Path, reasons: list) -> None:
    """Gaps the artifacts themselves still flag: grilling settles them, it does not pass over them."""
    for name, text in _covered_files(change, "grilling"):
        marks = sorted({m.group(0) for m in UNCONFIRMED_RE.finditer(COMMENT_RE.sub("", text))})
        if marks:
            reasons.append(f"{name}: unresolved marker {marks} - ask the user, write the answer "
                           "in, remove the marker")
        if name == "design.md" and _open_items(text, "Open Questions"):
            reasons.append(f"design.md: {_open_items(text, 'Open Questions')} open question(s) "
                           "still unanswered")


def _check_plan(change: Path, reasons: list) -> None:
    plan = _read(change / "plan.md")
    tasks = _read(change / "tasks.md")
    if plan is None:
        reasons.append("plan.md missing - run stage 4 (plan)")
    if tasks is None:
        reasons.append("tasks.md missing - run stage 4 (plan)")
    if plan is None or tasks is None:
        return
    if section(plan, "Global Constraints") is None:
        reasons.append("plan.md: no '## Global Constraints' section")
    hits = sorted({m.group(0) for m in PLACEHOLDER_RE.finditer(plan)})
    if hits:
        reasons.append(f"plan.md: placeholder text {hits} - write the real content")

    preamble, plan_tasks = _plan_tasks(plan)
    for title, what in (("Verification", "the commands that prove the whole change"),
                        ("File Structure", "each file touched and its one responsibility")):
        if not _has_content(section(preamble, title)):
            reasons.append(f"plan.md: '## {title}' is missing or empty - list {what}")
    if _has_content(section(preamble, "Verification")) and not verify_run.commands(plan)[0]:
        reasons.append("plan.md: '## Verification' names no command verify_run.py can run - "
                       "one list item per command, the command in backticks")
    for task_id, lines in plan_tasks:
        body = "\n".join(lines)
        missing = [b for b in TASK_BLOCKS
                   if not re.search(rf"^\s*\*{{0,2}}{b}:", body, re.M | re.I)]
        if missing:
            reasons.append(f"plan.md: Task {task_id} has no {' / '.join(missing)} block - "
                           "the implementer sees only its own task")
    answered = section(preamble, "Lessons applied") or ""
    files = incidents.files_named("\n".join(line for _, lines in plan_tasks for line in lines))
    # an incident this change records itself (audit blocker, fix loop) postdates its plan
    lessons = incidents.lessons_for(change, stages=("plan", "apply"), files=files,
                                    exclude_change=change.resolve().name)
    unanswered = [lesson_id for lesson_id, _ in lessons
                  if not re.search(rf"{re.escape(lesson_id)}(?!\d)", answered)]
    if unanswered:
        reasons.append(f"plan.md: '## Lessons applied' does not answer {unanswered} from "
                       "openspec/incidents.md - name the task that handles each lesson, or "
                       "'not applicable - <why>'")

    plan_ids = [task_id for task_id, _ in plan_tasks]
    task_ids = TASK_ID_RE.findall(tasks)
    if not task_ids:
        reasons.append("tasks.md: no '- [ ] N.M' tasks found")
    missing_in_plan = [t for t in task_ids if t not in plan_ids]
    missing_in_tasks = [t for t in plan_ids if t not in task_ids]
    if missing_in_plan:
        reasons.append(f"tasks without a '### Task N.M' section in plan.md: {missing_in_plan}")
    if missing_in_tasks:
        reasons.append(f"plan.md sections without a checkbox in tasks.md: {missing_in_tasks}")


def _check_audit(change: Path, reasons: list) -> None:
    text = _read(change / "audit.md")
    if text is None:
        reasons.append("audit.md missing - run stage 5 (pre-apply audit)")
        return
    _verdict_and_stamp(change, "audit", text, reasons)
    blockers = _open_items(text, "Blockers")
    if blockers is None:
        reasons.append("audit.md: no '## Blockers' section - keep it, empty when none were found")
    elif blockers:
        reasons.append(f"audit.md: {blockers} open blocker(s)")
    known = incidents.entry_ids(change)
    for line in CHECKED_RE.findall(section(COMMENT_RE.sub("", text), "Blockers") or ""):
        cited = INCIDENT_ID_RE.findall(line)
        if not cited:
            reasons.append(f"audit.md: resolved blocker without an incident entry: '{line[:60]}' - "
                           "record it in openspec/incidents.md and cite the INC id on this line")
        for incident_id in cited:
            if incident_id not in known:
                reasons.append(f"audit.md: blocker cites {incident_id}, which has no entry in "
                               "openspec/incidents.md")
    if section(text, "What I did NOT verify") is None:
        reasons.append("audit.md: no '## What I did NOT verify' section")


def _check_review(change: Path, reasons: list) -> None:
    text = _read(change / "review.md")
    if text is None:
        reasons.append("review.md missing - stage 5b: ask the user whether to run the perspective "
                       "review; if declined, write review.md with 'Verdict: SKIPPED'")
        return
    m = VERDICT_RE.search(text)
    verdict = m.group(1).upper() if m else "none"
    if verdict == "SKIPPED":
        return
    if verdict != "PASS":
        reasons.append(f"review.md: verdict is '{m.group(1) if m else 'none'}', "
                       "needs 'Verdict: PASS' (or SKIPPED if the user declined)")
    if not PERSPECTIVES_RE.search(text):
        reasons.append("review.md: no 'Perspectives:' line naming the roles the user chose")
    must_fix = _open_items(text, "Must fix")
    if must_fix is None:
        reasons.append("review.md: no '## Must fix' section - keep it, empty when none were found")
    elif must_fix:
        reasons.append(f"review.md: {must_fix} open must-fix finding(s)")


def check(change: Path, stage: str) -> Result:
    change = Path(change)
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}; expected one of {STAGES}")
    result = Result(stage)
    order = STAGES.index(stage)
    _check_grilling(change, result.reasons)
    if order >= 1:
        _check_plan(change, result.reasons)
    if order >= 2:
        _check_audit(change, result.reasons)
    if order >= 3:
        _check_review(change, result.reasons)
    if order >= 5:
        result.reasons.extend(verify_run.problems(change))
    return result


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    incidents.utf8_output()
    if len(argv) >= 2 and argv[0] == "status":
        change = Path(argv[1])
        worst = 0
        for stage in STAGES:
            r = check(change, stage)
            print(f"{'PASS' if r.ok else 'FAIL'}  {stage}")
            worst = worst or (0 if r.ok else 1)
        return worst
    if len(argv) == 3 and argv[0] == "check":
        r = check(Path(argv[1]), argv[2])
        if r.ok:
            print(f"PASS {r.stage}")
            return 0
        print(f"FAIL {r.stage}:")
        for reason in r.reasons:
            print(f"  - {reason}")
        return 1
    if len(argv) == 3 and argv[0] == "stamp":
        print(stamp(Path(argv[1]), argv[2]))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
