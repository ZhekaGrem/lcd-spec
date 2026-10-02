#!/usr/bin/env python3
"""Read and maintain the project's incident log (openspec/incidents.md).

A lesson nobody re-reads prevents nothing, and a mistake recorded twice as two unrelated
entries hides that it keeps happening. This script checks the log's format, finds the
entry a new incident repeats, counts repeats, and picks the lessons that apply to a stage
and a set of files. gate.py and task_brief.py use it to put those lessons into the plan
gate and into the brief an implementer reads.

Usage:
  python incidents.py validate <incidents.md>                  exit 0 = well-formed, 1 = errors
  python incidents.py find <incidents.md> "<what happened>" [--class C]
                                                               entries a new incident may repeat
  python incidents.py bump <incidents.md> <INC-id> [--date YYYY-MM-DD]
                                                               count one more occurrence
  python incidents.py select <incidents.md> [--stage S ...] [--files PATH ...]
                                                               active lessons that apply
"""
from __future__ import annotations

import argparse
import datetime
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
LESSON_LINE_RE = re.compile(r"^\s*(?:[-*]\s+)?(INC-\d{8}-\d+)\s*[-:–—]\s*(.+?)\s*$")
ENTRY_RE = re.compile(r"^###\s+(INC-\d{8}-\d+)\b[:\s]*(.*)$")
FIELD_RE = re.compile(r"^- \*\*([^*:]+):\*\*\s*(.*)$")
FILES_LABEL_RE = re.compile(r"^\s*\*{0,2}Files:", re.I)
LIST_ITEM_RE = re.compile(r"^\s*[-*]\s+")
CODE_RE = re.compile(r"`([^`]+)`")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WORD_RE = re.compile(r"\w{4,}")

STAGES = ("context", "brainstorm", "artifacts", "grill", "plan", "audit", "perspectives",
          "apply", "archive", "after-archive", "none")
SIGNALS = ("manual audit", "audit blocker", "perspective review", "review cap", "final review",
           "test failure", "user report")
SIGNAL_RE = re.compile(r"^frustration L[123]$")
CLASSES = ("rot", "stillborn", "misread-request", "written-not-consumed", "wrong-runtime",
           "syntax-roulette", "scope-creep", "unverified-claim", "proxy-test", "other")
REQUIRED = ("Date", "Change", "Stage", "Signal", "What happened", "Wrong belief", "Evidence",
            "Class", "Fix", "Lesson")

# Stack tags a file path gives away. A lesson tagged with one of them is skipped for a task
# that touches no such file; any other tag (spring, nextjs, flyway) cannot be judged from
# paths and never excludes a lesson.
TAG_BY_SUFFIX = {
    ".java": "java", ".kt": "kotlin", ".go": "go", ".py": "python", ".sql": "sql", ".php": "php",
    ".ts": "ts", ".tsx": "ts", ".mts": "ts", ".cts": "ts", ".vue": "vue",
    ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js", ".css": "css", ".scss": "css",
}
TAG_BY_NAME = {
    "pom.xml": "maven", "go.mod": "go", "pyproject.toml": "python", "requirements.txt": "python",
    "package.json": "npm", "pnpm-lock.yaml": "pnpm", "dockerfile": "docker",
    "docker-compose.yml": "docker", "docker-compose.yaml": "docker", "compose.yaml": "docker",
}
PATH_TAGS = set(TAG_BY_SUFFIX.values()) | set(TAG_BY_NAME.values())


@dataclass
class Entry:
    id: str
    title: str
    fields: dict = field(default_factory=dict)  # lower-cased field name -> value


@dataclass
class Log:
    entries: list
    active: list   # (id, lesson) from "Lessons index", in file order
    retired: list  # ids from "Retired lessons"


# --- reading -------------------------------------------------------------------

def _section(text: str, title: str) -> str:
    m = re.search(rf"^##\s+{re.escape(title)}[^\n]*\n", text, re.M | re.I)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^##\s", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _lesson_lines(body: str) -> list:
    return [m.groups() for m in map(LESSON_LINE_RE.match, body.splitlines()) if m]


def parse(text: str) -> Log:
    clean = COMMENT_RE.sub("", text.replace("\r\n", "\n"))
    entries, last = [], None
    for line in _section(clean, "Entries").splitlines():
        heading = ENTRY_RE.match(line)
        if heading:
            entries.append(Entry(heading.group(1), heading.group(2).strip()))
            last = None
            continue
        if not entries:
            continue
        item = FIELD_RE.match(line)
        if item:
            last = item.group(1).strip().lower()
            entries[-1].fields[last] = item.group(2).strip()
        elif last and line.startswith((" ", "\t")) and line.strip():
            entries[-1].fields[last] = (entries[-1].fields[last] + " " + line.strip()).strip()
    return Log(entries, _lesson_lines(_section(clean, "Lessons index")),
               [i for i, _ in _lesson_lines(_section(clean, "Retired lessons"))])


def active_lessons(text: str) -> list:
    """(INC id, lesson) pairs from '## Lessons index', in file order."""
    return parse(text).active


def _items(value: str | None) -> list:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


# --- validate ------------------------------------------------------------------

def validate(text: str) -> list:
    log = parse(text)
    errors, seen = [], set()
    for entry in log.entries:
        if entry.id in seen:
            errors.append(f"{entry.id}: id used by more than one entry")
        seen.add(entry.id)
        f = entry.fields
        missing = [name for name in REQUIRED if not f.get(name.lower())]
        if missing:
            errors.append(f"{entry.id}: missing field(s) {', '.join(missing)}")
        if f.get("date") and not DATE_RE.match(f["date"]):
            errors.append(f"{entry.id}: Date '{f['date']}' is not YYYY-MM-DD")
        if f.get("stage") and f["stage"] not in STAGES:
            errors.append(f"{entry.id}: Stage '{f['stage']}' is not one of {', '.join(STAGES)}")
        if f.get("signal") and f["signal"] not in SIGNALS and not SIGNAL_RE.match(f["signal"]):
            errors.append(f"{entry.id}: Signal '{f['signal']}' is not 'frustration L1-3' or one of "
                          f"{', '.join(SIGNALS)}")
        if f.get("class") and f["class"] not in CLASSES:
            errors.append(f"{entry.id}: Class '{f['class']}' is not one of {', '.join(CLASSES)}")
        bad = [s for s in _items(f.get("needed at")) if s not in STAGES]
        if bad:
            errors.append(f"{entry.id}: Needed at names unknown stage(s) {', '.join(bad)}")
        if "recurrence" in f and not re.fullmatch(r"[1-9]\d*", f["recurrence"]):
            errors.append(f"{entry.id}: Recurrence '{f['recurrence']}' is not a positive number")

    active = [i for i, _ in log.active]
    for lesson_id in sorted({i for i in active if active.count(i) > 1}):
        errors.append(f"{lesson_id}: listed more than once in Lessons index")
    for lesson_id in active + log.retired:
        if lesson_id not in seen:
            errors.append(f"{lesson_id}: has a lesson line but no entry under Entries")
    for entry_id in sorted(seen - set(active) - set(log.retired)):
        errors.append(f"{entry_id}: entry has no line in Lessons index or Retired lessons")
    return errors


# --- find a repeat ---------------------------------------------------------------

def _words(text: str) -> set:
    return set(WORD_RE.findall(text.lower()))


def find(text: str, query: str, cls: str | None = None) -> list:
    """Ids of entries that share words with `query`, the closest first."""
    wanted, scored = _words(query), []
    for order, entry in enumerate(parse(text).entries):
        f = entry.fields
        if cls and f.get("class") != cls:
            continue
        own = _words(" ".join([entry.title, f.get("what happened", ""), f.get("trigger", ""),
                               f.get("lesson", "")]))
        score = len(wanted & own)
        if score:
            scored.append((-score, order, entry.id))
    return [entry_id for _, _, entry_id in sorted(scored)]


# --- count a repeat ---------------------------------------------------------------

def bump(text: str, entry_id: str, date: str) -> tuple:
    """(new text, recurrence) after one more occurrence. Only that entry's lines change."""
    lines = text.replace("\r\n", "\n").split("\n")
    start = next((i for i, line in enumerate(lines)
                  if (m := ENTRY_RE.match(line)) and m.group(1) == entry_id), None)
    if start is None:
        raise LookupError(f"{entry_id}: no such entry")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith(("## ", "### "))),
               len(lines))
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1  # keep the blank lines that separate entries where they are

    fields = next(e for e in parse(text).entries if e.id == entry_id).fields
    count = int(fields["recurrence"]) + 1 if fields.get("recurrence", "").isdigit() else 2
    seen = _items(fields.get("seen")) or _items(fields.get("date"))
    updated = {"Recurrence": str(count), "Seen": ", ".join(seen + [date])}

    block = []
    for line in lines[start:end]:
        item = FIELD_RE.match(line)
        name = item.group(1).strip() if item else None
        if name in updated:
            block.append(f"- **{name}:** {updated.pop(name)}")
        else:
            block.append(line)
    block += [f"- **{name}:** {value}" for name, value in updated.items()]
    return "\n".join(lines[:start] + block + lines[end:]), count


# --- select the lessons that apply -------------------------------------------------

def _glob(pattern: str) -> re.Pattern:
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def _path_tags(files: list) -> set:
    tags = set()
    for name in files:
        path = PurePosixPath(name)
        tags.add(TAG_BY_SUFFIX.get(path.suffix.lower()))
        tags.add(TAG_BY_NAME.get(path.name.lower()))
    return tags - {None}


def select(text: str, stages=(), files=(), exclude_change: str | None = None) -> list:
    """Active (id, lesson) pairs that apply to any of `stages` and to `files`.

    A lesson without an entry, or whose entry leaves Needed at / Paths / Stack out, always
    applies: an old log keeps working, it just cannot be narrowed.
    """
    log = parse(text)
    by_id = {entry.id: entry.fields for entry in reversed(log.entries)}
    files = [str(name).replace("\\", "/").removeprefix("./") for name in files]
    out = []
    for lesson_id, lesson in log.active:
        f = by_id.get(lesson_id, {})
        if exclude_change and f.get("change") == exclude_change:
            continue
        needed = _items(f.get("needed at"))
        if stages and needed and not set(needed) & set(stages):
            continue
        if files:
            globs = [_glob(g) for g in _items(f.get("paths"))]
            if globs and not any(g.match(name) for g in globs for name in files):
                continue
            judged = set(_items(f.get("stack"))) & PATH_TAGS
            if judged and not judged & _path_tags(files):
                continue
        out.append((lesson_id, lesson))
    return out


def files_named(text: str) -> list:
    """Paths in the list under each 'Files:' label of plan text, line ranges dropped."""
    out, inside = [], False
    for line in text.splitlines():
        if FILES_LABEL_RE.match(line):
            inside = True
        elif inside and line.strip():
            if not LIST_ITEM_RE.match(line):
                inside = False
                continue
            out += [re.sub(r":\d+(?:-\d+)?$", "", name.strip()) for name in CODE_RE.findall(line)]
    return out


def log_path(change: Path) -> Path:
    """openspec/incidents.md of the project that owns openspec/changes/<name>."""
    return Path(change).resolve().parents[1] / "incidents.md"


def _log_text(change: Path) -> str:
    try:
        return log_path(change).read_text(encoding="utf-8")
    except OSError:
        return ""


def lessons_for(change: Path, **filters) -> list:
    """select() over the change's project log; no log, no lessons."""
    return select(_log_text(change), **filters)


def entry_ids(change: Path) -> set:
    return {entry.id for entry in parse(_log_text(change)).entries}


# --- command line ------------------------------------------------------------------

def utf8_output() -> None:
    """Print UTF-8 whatever the console codec: a piped stdout on Windows is cp1251/cp1252,
    and a lesson written in Ukrainian comes out as mojibake or as a UnicodeEncodeError."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="incidents.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "find", "bump", "select"):
        sub.add_parser(name).add_argument("log", type=Path)
    sub.choices["find"].add_argument("query")
    sub.choices["find"].add_argument("--class", dest="cls", choices=CLASSES)
    sub.choices["bump"].add_argument("id")
    sub.choices["bump"].add_argument("--date", default=datetime.date.today().isoformat())
    sub.choices["select"].add_argument("--stage", action="append", default=[], choices=STAGES)
    sub.choices["select"].add_argument("--files", nargs="*", default=[])
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    utf8_output()
    try:
        text = args.log.read_bytes().decode("utf-8")
    except OSError as exc:
        print(exc, file=sys.stderr)
        return 3

    if args.command == "validate":
        errors = validate(text)
        for error in errors:
            print(error)
        if not errors:
            log = parse(text)
            print(f"OK: {len(log.entries)} entries, {len(log.active)} active lessons")
        return 1 if errors else 0
    if args.command == "find":
        fields = {e.id: e.fields for e in parse(text).entries}
        for entry_id in find(text, args.query, args.cls):
            f = fields[entry_id]
            print(f"{entry_id} (seen {f.get('recurrence', '1')}x) - {f.get('lesson', '')}")
        return 0
    if args.command == "bump":
        newline = "\r\n" if "\r\n" in text else "\n"
        try:
            text, count = bump(text, args.id, args.date)
        except LookupError as exc:
            print(exc, file=sys.stderr)
            return 3
        # bytes, not text mode: the log keeps the line endings it had
        args.log.write_bytes(text.replace("\n", newline).encode("utf-8"))
        print(f"{args.id}: recurrence {count}")
        print("The lesson as written did not stop the repeat. Turn it into something that runs: "
              "a test, a lint rule, a hook or a gate check.")
        return 0
    for lesson_id, lesson in select(text, stages=args.stage, files=args.files):
        print(f"{lesson_id} - {lesson}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
