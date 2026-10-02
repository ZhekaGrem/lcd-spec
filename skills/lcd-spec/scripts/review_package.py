#!/usr/bin/env python3
"""Write one file a reviewer reads instead of running git or the tests itself.

The package holds the commit list, a stat summary, the independent run that verify_run.py
recorded and the full diff with 10 lines of context for BASE..HEAD, so the diff never
enters the controller's context. A run that is missing, failed or older than the code is
marked 'Status: FAIL' with the reason: the reviewer sees it instead of a report's claim.

Usage: python review_package.py <change-dir> <base> <head> [label]
Writes <change-dir>/.work/review-<label>.md (label defaults to <base7>-<head7>) and
prints its path. A 'task-…' label takes the run with the same label; any other label takes
the whole-change run (verification.md).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import verify_run


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True, encoding="utf-8").stdout


def write_package(change: Path, base: str, head: str, label: str | None = None) -> Path:
    change = Path(change).resolve()
    repo = Path(git(change, "rev-parse", "--show-toplevel").strip())
    rng = f"{base}..{head}"
    run = verify_run.review_section(change, label)
    label = label or f"{base[:7]}-{head[:7]}"
    text = "\n".join([
        f"# Review package {rng}", "",
        "## Commits", "```", git(repo, "log", "--oneline", rng).rstrip(), "```", "",
        "## Stat", "```", git(repo, "diff", "--stat", rng).rstrip(), "```", "",
        *run,
        "## Diff", "```diff", git(repo, "diff", "-U10", rng).rstrip(), "```", "",
    ])
    work = change / ".work"
    work.mkdir(exist_ok=True)
    path = work / f"review-{label}.md"
    path.write_text(text, encoding="utf-8")
    return path


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (3, 4):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        path = write_package(Path(argv[0]), argv[1], argv[2], argv[3] if len(argv) == 4 else None)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(getattr(exc, "stderr", None) or exc, file=sys.stderr)
        return 3
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
