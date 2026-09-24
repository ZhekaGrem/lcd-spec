#!/usr/bin/env python3
"""Hard gates between lcd-spec stages.

OpenSpec's own schema only knows whether an artifact file exists. This script checks
what the file says and whether it is still true:

  grilling  grilling.md has "Verdict: PASS", no unanswered open question, and was
            stamped against the current proposal / specs / design
  plan      grilling passes; plan.md has Global Constraints, no placeholders, and
            exactly the same task numbers as tasks.md
  audit     plan passes; audit.md has "Verdict: PASS", no open blocker, a
            "What I did NOT verify" section, and was stamped against the current
            proposal / specs / design / grilling / plan / tasks
  review    audit passes; review.md exists with "Verdict: SKIPPED" (the user declined the
            perspective review) or "Verdict: PASS" with a "Perspectives:" line and no
            open item under "Must fix"
  apply     review passes

"Stamped" means `gate.py stamp` wrote an Artifacts-Hash line after the stage finished.
Editing any covered artifact afterwards makes the stage stale until it is re-checked
and re-stamped. Ticking checkboxes in tasks.md and appending an "Audit findings"
section to design.md do not count as edits.

Usage:
  python gate.py check  <change-dir> <grilling|plan|audit|review|apply>   exit 0 = PASS, 1 = FAIL
  python gate.py stamp  <change-dir> <grilling|audit>
  python gate.py status <change-dir>
"""
from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

HASH_LINE_RE = re.compile(r"^Artifacts-Hash:.*$", re.M)
VERDICT_RE = re.compile(r"^Verdict:\s*(\S+)", re.M)
TASK_ID_RE = re.compile(r"^\s*- \[[ xX]\] (\d+(?:\.\d+)*)\b", re.M)
PLAN_TASK_RE = re.compile(r"^#{2,4}\s+Task\s+(\d+(?:\.\d+)*)\b")
CHECKBOX_RE = re.compile(r"^(\s*- )\[[xX]\]", re.M)
UNCHECKED_RE = re.compile(r"^\s*- \[ \]", re.M)
PLACEHOLDER_RE = re.compile(
    r"\bTBD\b|\bTODO\b|implement later|fill in details|add appropriate error handling"
    r"|handle edge cases|similar to task\s+\d|<!--", re.I)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)

PERSPECTIVES_RE = re.compile(r"^Perspectives:\s*\S", re.M)

STAGES = ("grilling", "plan", "audit", "review", "apply")


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
    open_q = section(COMMENT_RE.sub("", text), "Open questions")
    if open_q is not None and UNCHECKED_RE.search(open_q):
        n = len(UNCHECKED_RE.findall(open_q))
        reasons.append(f"grilling.md: {n} open question(s) still unanswered")


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

    plan_ids, in_fence = [], False
    for line in plan.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            m = PLAN_TASK_RE.match(line)
            if m:
                plan_ids.append(m.group(1))
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
    blockers = section(COMMENT_RE.sub("", text), "Blockers")
    if blockers is not None and UNCHECKED_RE.search(blockers):
        reasons.append(f"audit.md: {len(UNCHECKED_RE.findall(blockers))} open blocker(s)")
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
    must_fix = section(COMMENT_RE.sub("", text), "Must fix")
    if must_fix is not None and UNCHECKED_RE.search(must_fix):
        reasons.append(f"review.md: {len(UNCHECKED_RE.findall(must_fix))} open must-fix finding(s)")


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
    return result


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
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
