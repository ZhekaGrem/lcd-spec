#!/usr/bin/env python3
"""Extract one task from a change's plan.md into a brief an implementer reads in one call.

The brief holds the plan's Global Constraints, the active lessons from
openspec/incidents.md and the full '### Task N.M' section, so the task text never travels
through the controller's context and the implementer never reads the whole plan or the
incident log.

Usage: python task_brief.py <change-dir> <task-id>
Writes <change-dir>/.work/task-<id>-brief.md and prints its path.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import incidents

TASK_HEADING_RE = re.compile(r"^#{2,4}\s+Task\s+(\d+(?:\.\d+)*)\b")
ANY_H2_RE = re.compile(r"^##\s")


def _global_constraints(lines: list) -> list:
    out, inside = [], False
    for line in lines:
        if re.match(r"^##\s+Global Constraints", line, re.I):
            inside = True
            out.append(line)
            continue
        if inside and ANY_H2_RE.match(line):
            break
        if inside:
            out.append(line)
    return out


def _pitfalls(lessons: list) -> list:
    if not lessons:
        return []
    return ["## Known pitfalls",
            "Mistakes this project already made (openspec/incidents.md). Check your work "
            "against every line before you report.",
            *(f"- {lesson_id} - {lesson}" for lesson_id, lesson in lessons), ""]


def task_section(plan_text: str, task_id: str) -> list:
    """Lines of the '### Task <id>' section, heading included."""
    lines = plan_text.replace("\r\n", "\n").split("\n")
    body, inside, in_fence = [], False, False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and not line.lstrip().startswith("```"):
            m = TASK_HEADING_RE.match(line)
            if m:
                inside = m.group(1) == task_id
            elif inside and ANY_H2_RE.match(line) and not line.startswith("###"):
                inside = False
        if inside:
            body.append(line)
    if not body:
        raise LookupError(f"task {task_id} not found in plan.md (no '### Task {task_id}' heading)")
    return body


def extract_task(plan_text: str, task_id: str, lessons: list = ()) -> str:
    body = task_section(plan_text, task_id)
    constraints = _global_constraints(plan_text.replace("\r\n", "\n").split("\n"))
    parts = [f"# Brief: Task {task_id}", ""]
    if constraints:
        parts += constraints + [""]
    parts += _pitfalls(list(lessons))
    parts += body
    return "\n".join(parts).rstrip() + "\n"


def write_brief(change: Path, task_id: str) -> Path:
    change = Path(change)
    plan = (change / "plan.md").read_text(encoding="utf-8")
    files = incidents.files_named("\n".join(task_section(plan, task_id)))
    brief = extract_task(plan, task_id,
                         incidents.lessons_for(change, stages=("apply",), files=files))
    work = change / ".work"
    work.mkdir(exist_ok=True)
    path = work / f"task-{task_id}-brief.md"
    path.write_text(brief, encoding="utf-8")
    return path


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        path = write_brief(Path(argv[0]), argv[1])
    except (OSError, LookupError) as exc:
        print(exc, file=sys.stderr)
        return 3
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
