#!/usr/bin/env python3
"""Install the lcd-spec OpenSpec schema into a project that already ran `openspec init`.

- copies schema/lcd-spec into <project>/openspec/schemas/lcd-spec (overwrites: the
  schema belongs to the skill, not to the project);
- switches openspec/config.yaml to `schema: lcd-spec` for NEW changes (existing changes
  keep the schema recorded in their own .openspec.yaml);
- creates openspec/incidents.md if it does not exist;
- adds the per-change scratch directory to .gitignore;
- writes openspec/roadmap.md from the project's changes and commits (its hand-written
  'Planned' section is kept).

Idempotent. Usage: python install.py <project-root>
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import roadmap

SKILL_DIR = Path(__file__).resolve().parents[1]
SCHEMA_SRC = SKILL_DIR / "schema" / "lcd-spec"
INCIDENTS_TEMPLATE = SKILL_DIR / "references" / "incidents-template.md"
GITIGNORE_LINE = "openspec/changes/**/.work/"


def install(project: Path) -> list:
    project = Path(project)
    openspec = project / "openspec"
    config = openspec / "config.yaml"
    if not config.is_file():
        raise FileNotFoundError(f"{config} not found - run `openspec init` in {project} first")
    done = []

    target = openspec / "schemas" / "lcd-spec"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(SCHEMA_SRC, target)
    done.append(f"schema -> {target}")

    text = config.read_text(encoding="utf-8")
    if re.search(r"^schema:.*$", text, re.M):
        text = re.sub(r"^schema:.*$", "schema: lcd-spec", text, count=1, flags=re.M)
    else:
        text = "schema: lcd-spec\n" + text
    config.write_text(text, encoding="utf-8")
    done.append("config.yaml -> schema: lcd-spec")

    incidents = openspec / "incidents.md"
    if not incidents.exists():
        shutil.copyfile(INCIDENTS_TEMPLATE, incidents)
        done.append(f"created {incidents}")

    gitignore = project / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if GITIGNORE_LINE not in existing.splitlines():
        sep = "" if existing.endswith("\n") or not existing else "\n"
        gitignore.write_text(existing + sep + GITIGNORE_LINE + "\n", encoding="utf-8")
        done.append(f".gitignore += {GITIGNORE_LINE}")

    done.append(f"roadmap -> {roadmap.write(project)}")
    return done


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        for line in install(Path(argv[0])):
            print(line)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
