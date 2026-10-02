#!/usr/bin/env python3
"""Run a change's verification commands and keep the raw result for the reviewer.

An implementer's "14/14 passing" is a claim. This script runs the commands itself and
writes what they printed and how they exited, so a reviewer reads a run nobody summarised.

The commands come from plan.md and nothing is guessed from the stack:
  whole change   the list under '## Verification'
  one task       the task's '**Verify:**' block; a task without one runs '## Verification'
A list item is one command: its first `code span`, or the whole item when it has none.
Every line of a fenced block is a command.

Usage: python verify_run.py <change-dir> [<task-id>] [--label L] [--timeout SEC] [--tail N]
Writes <change-dir>/verification.md for the whole change, or
<change-dir>/.work/verify-<label>.md for a task (label defaults to task-<id>), and prints
the path. Exit 0 = every command exited 0, 1 = at least one failed or timed out,
3 = nothing could be run.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import hashlib
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import task_brief

FINAL = "final"  # label of the whole-change run
TIMEOUT = 900    # seconds per command: a watcher or a dev server never exits on its own
TAIL = 200       # output lines kept per command: the end is where runners print the verdict

COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
VERIFICATION_RE = re.compile(r"^##\s+Verification[^\n]*\n", re.M | re.I)
SECTION_END_RE = re.compile(r"^(?:##\s|#{2,4}\s+Task\s+\d)", re.M)
VERIFY_LABEL_RE = re.compile(r"^\s*\*{0,2}Verify:\*{0,2}(.*)$", re.I)
BLOCK_END_RE = re.compile(r"^(?:\*\*|#)")
LIST_ITEM_RE = re.compile(r"^\s*[-*]\s+")
CODE_RE = re.compile(r"`([^`]+)`")
RESULT_RE = re.compile(r"^Result:\s*(\S+)", re.M)
TREE_RE = re.compile(r"^Tree:\s*(\S+)", re.M)
FAILED_RE = re.compile(r"^- (?!exit 0 )(.+)$", re.M)


def _commands_in(lines: list) -> list:
    out, in_fence = [], False
    for line in lines:
        text = line.strip()
        if text.startswith("```"):
            in_fence = not in_fence
        elif in_fence:
            if text and not text.startswith("#"):
                out.append(text)
        elif LIST_ITEM_RE.match(line):
            item = LIST_ITEM_RE.sub("", line, count=1).strip()
            code = CODE_RE.search(item)
            out.append(code.group(1).strip() if code else item)
    return [command for command in out if command]


def _verify_block(task_lines: list) -> list | None:
    """Lines of the task's 'Verify:' block, or None when the task has none."""
    block, in_fence = None, False
    for line in task_lines:
        if block is None:
            label = VERIFY_LABEL_RE.match(line)
            if label:
                block = [f"- {label.group(1).strip()}"] if label.group(1).strip() else []
            continue
        if line.strip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and BLOCK_END_RE.match(line):
            break
        block.append(line)
    return block


def commands(plan_text: str, task_id: str | None = None) -> tuple:
    """(commands to run, where they were taken from)."""
    plan = COMMENT_RE.sub("", plan_text.replace("\r\n", "\n"))
    source = "plan.md '## Verification'"
    if task_id is not None:
        block = _verify_block(task_brief.task_section(plan, task_id))
        if block is not None:
            return _commands_in(block), f"Task {task_id} 'Verify' block"
        source += f" (Task {task_id} has no 'Verify' block)"
    start = VERIFICATION_RE.search(plan)
    if not start:
        return [], source
    rest = plan[start.end():]
    end = SECTION_END_RE.search(rest)
    return _commands_in((rest[: end.start()] if end else rest).split("\n")), source


# --- running ---------------------------------------------------------------------

def _git_bash() -> str | None:
    """Git for Windows' bash. `bash` on PATH is no use there: it is the WSL launcher."""
    candidates = [os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")]
    git = shutil.which("git")
    if git:
        candidates += [parent / "bin" / "bash.exe" for parent in list(Path(git).resolve().parents)[:3]]
    return next((str(c) for c in candidates if c and Path(c).is_file()), None)


def _shell() -> list | None:
    """argv prefix of a POSIX shell: plans are written the way the agent types commands.
    None on a Windows machine without Git Bash, where the system shell has to do."""
    if os.name != "nt":
        return ["/bin/sh", "-c"]
    bash = _git_bash()
    return [bash, "-c"] if bash else None


def _stop(proc: subprocess.Popen) -> None:
    """Kill the command and what it started: a watcher's children outlive their shell."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=10)


def _execute(command: str, cwd: Path, timeout: float) -> tuple:
    """(exit code or None on timeout, combined output, seconds)."""
    shell = _shell()
    started = time.monotonic()
    # a file, not a pipe: a pipe stays open while any grandchild lives, and stdin is closed
    # so a command that asks a question fails instead of waiting for an answer
    with tempfile.TemporaryFile() as out:
        proc = subprocess.Popen([*shell, command] if shell else command, shell=shell is None,
                                cwd=cwd, stdin=subprocess.DEVNULL, stdout=out,
                                stderr=subprocess.STDOUT, start_new_session=os.name != "nt")
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _stop(proc)
            code = None
        out.seek(0)
        text = out.read().decode("utf-8", errors="replace")
    return code, text, time.monotonic() - started


def _tail(text: str, limit: int) -> str:
    lines = text.replace("\r\n", "\n").rstrip("\n").split("\n")
    if len(lines) <= limit:
        return "\n".join(lines)
    return f"[... {len(lines) - limit} earlier lines omitted ...]\n" + "\n".join(lines[-limit:])


def _block(text: str) -> list:
    """`text` as a fenced block whose fence no line of the text can close."""
    fence = "`" * max(3, 1 + max(map(len, re.findall(r"`+", text)), default=0))
    return [f"{fence}text", text or "(no output)", fence]


def log_path(change: Path, label: str) -> Path:
    change = Path(change)
    return change / "verification.md" if label == FINAL else change / ".work" / f"verify-{label}.md"


def run(change: Path, task_id: str | None = None, label: str | None = None,
        timeout: float = TIMEOUT, tail: int = TAIL) -> tuple:
    """Run the commands and write the log. Returns (log path, True when every one exited 0)."""
    change = Path(change)
    todo, source = commands((change / "plan.md").read_text(encoding="utf-8"), task_id)
    if not todo:
        raise LookupError(f"no commands to run in {source} - write them in plan.md as "
                          "list items, each command in backticks")
    label = label or (f"task-{task_id}" if task_id else FINAL)
    root = change.resolve().parents[2]  # <root>/openspec/changes/<name>

    summary, output, ok = [], [], True
    for number, command in enumerate(todo, 1):
        code, text, seconds = _execute(command, root, timeout)
        ok = ok and code == 0
        outcome = f"timed out after {timeout:g}s" if code is None else f"exit {code} ({seconds:.1f}s)"
        summary.append(f"- {outcome}: `{command}`")
        output += [f"#### {number}. `{command}`", "", *_block(_tail(text, tail)), ""]

    path = log_path(change, label)
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join([
        f"# Independent run: {label}", "",
        f"Result: {'PASS' if ok else 'FAIL'}",
        # taken after the commands: a file they generate or reformat is part of what ran
        f"Tree: {tree_id(change) or 'unknown'}",
        f"Commands: {source}",
        f"Ran: {datetime.datetime.now().isoformat(timespec='seconds')} in {root}", "",
        # third-level headings: review_package.py puts the log under its own '## ' heading
        "### Summary", "", *summary, "",
        "### Output", "", *output]), encoding="utf-8")
    return path, ok


# --- is the run still true? ---------------------------------------------------------

def tree_id(change: Path) -> str | None:
    """Hash of the project's files as they are now, or None when git cannot list them.

    It covers tracked and untracked files under the project root, skips ignored ones and
    the openspec directory (ticking tasks and writing the ledger are not code changes),
    and does not depend on what is committed. Git only lists the names: nothing is staged
    or written, and a repository that merely contains the project (a home directory under
    git) is never walked beyond the project.
    """
    openspec = Path(change).resolve().parents[1]
    root, skip = openspec.parent, os.fsencode(openspec.name) + b"/"
    try:
        listed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            check=True, capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    digest, seen = hashlib.sha256(), False
    for name in sorted(set(listed.split(b"\0")) - {b""}):
        if name.startswith(skip):
            continue
        try:
            data = (root / os.fsdecode(name)).read_bytes()
        except OSError:
            continue  # deleted but still in the index, or a submodule directory
        digest.update(name + b"\0" + hashlib.sha256(data).digest())
        seen = True
    # no file at all means git ignores the project here, and every state would hash alike
    return digest.hexdigest()[:16] if seen else None


def problems(change: Path, label: str = FINAL) -> list:
    """Why the run labelled `label` does not prove the code as it is now. Empty = it does."""
    change = Path(change)
    path = log_path(change, label)
    name = path.relative_to(change).as_posix()
    try:
        head = path.read_text(encoding="utf-8").split("\n### Output", 1)[0]
    except OSError:
        return [f"{name} missing - the commands were not run independently; run "
                f"`verify_run.py <change>{'' if label == FINAL else ' <task-id>'}`"]
    reasons = []
    failed = FAILED_RE.findall(head.partition("### Summary")[2])
    result = RESULT_RE.search(head)
    if failed or not result or result.group(1) != "PASS":
        reasons.append(f"{name}: not green - " + ("; ".join(failed) or "no 'Result: PASS' line"))
    recorded, current = TREE_RE.search(head), tree_id(change)
    if not recorded or recorded.group(1) == "unknown" or current is None:
        reasons.append(f"{name}: cannot tell whether the code changed after the run - "
                       "the project is not a git repository")
    elif recorded.group(1) != current:
        reasons.append(f"{name}: stale - the code changed after the run; run verify_run.py again")
    return reasons


def review_section(change: Path, label: str | None) -> list:
    """Lines for a review package: whether the run for `label` holds, then the run itself.

    A task package ('task-…') carries that task's run; any other package is a whole-branch
    one and carries the whole-change run.
    """
    label = label if label and label.startswith("task-") else FINAL
    found = problems(change, label)
    lines = ["## Independent run", ""]
    if found:
        lines += ["Status: FAIL", *(f"- {reason}" for reason in found)]
    else:
        lines += ["Status: PASS - every command exited 0 and the code has not changed since the run"]
    try:
        log = log_path(change, label).read_text(encoding="utf-8")
    except OSError:
        return lines + [""]
    return lines + ["", *log.rstrip().split("\n")[1:], ""]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="verify_run.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("change", type=Path)
    parser.add_argument("task", nargs="?")
    parser.add_argument("--label")
    parser.add_argument("--timeout", type=float, default=TIMEOUT)
    parser.add_argument("--tail", type=int, default=TAIL)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        path, ok = run(args.change, args.task, args.label, args.timeout, args.tail)
    except (OSError, LookupError) as exc:
        print(exc, file=sys.stderr)
        return 3
    print(path)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
