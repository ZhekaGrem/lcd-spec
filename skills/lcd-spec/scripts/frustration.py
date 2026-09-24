#!/usr/bin/env python3
"""Frustration detector for the lcd-spec incident-audit protocol.

Runs as a Claude Code UserPromptSubmit hook. Reads the hook payload from stdin,
scores the user's message for swearing, blame and repeated-failure complaints
(Ukrainian, Russian, English), keeps a per-session streak in a sliding window,
and - when the streak crosses a level - injects a short instruction that points
the agent at references/incident-audit.md.

Design rules:
- fail open: any error exits 0 with no output, so the hook never blocks a session;
- the log stores metadata only (kind, weight, level), never message text;
- cues live in lexicon/<lang>.txt, so adding a language is adding a file.

Switch off: set the environment variable LCD_SPEC_FRUSTRATION=off
(e.g. in the "env" block of ~/.claude/settings.json).

Manual use:
  python frustration.py --dismiss <session_id> <event_id>   retract one false trigger
  python frustration.py --classify "text"                   print the classification
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from pathlib import Path

WINDOW_SECONDS = 30 * 60
LEVEL_THRESHOLDS = ((4.0, 3), (2.5, 2), (1.0, 1))  # streak >= threshold -> level

SCRIPT_PATH = Path(__file__).resolve()
LEXICON_DIR = SCRIPT_PATH.parent / "lexicon"
PROTOCOL_PATH = SCRIPT_PATH.parents[1] / "references" / "incident-audit.md"

SECTIONS = ("profanity", "praise", "directed", "blame", "failure", "repeat", "negative", "ack")
META_RE = re.compile(r"\blcd[- ]?spec\b")


@dataclass
class Signal:
    kind: str
    weight: float
    markers: list = field(default_factory=list)


@dataclass
class Outcome:
    level: int
    streak: float
    event_id: str | None


# --- lexicon -----------------------------------------------------------------

def load_lexicon(directory: Path = LEXICON_DIR) -> dict:
    lexicon = {name: [] for name in SECTIONS}
    for path in sorted(directory.glob("*.txt")):
        section = None
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                continue
            if section in lexicon:
                lexicon[section].append(re.compile(line))
    return lexicon


_LEXICON = None


def lexicon() -> dict:
    global _LEXICON
    if _LEXICON is None:
        _LEXICON = load_lexicon()
    return _LEXICON


# --- normalization -------------------------------------------------------------

CYR = "а-яіїєґё"
LOOKALIKES = str.maketrans({"a": "а", "c": "с", "e": "е", "i": "і", "o": "о", "p": "р",
                            "x": "х", "y": "у", "k": "к", "0": "о", "3": "з"})
FENCE_RE = re.compile(r"```.*?(```|$)", re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
SEPARATOR_RE = re.compile(rf"(?<=[{CYR}])[.\-_*]+(?=[{CYR}])")
TOKEN_RE = re.compile(r"\S+")


def normalize(text: str) -> str:
    text = FENCE_RE.sub(" ", text)
    text = INLINE_CODE_RE.sub(" ", text)
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(">"))
    text = unicodedata.normalize("NFKC", text).lower().replace("’", "'")

    def fix_token(match):
        token = match.group(0)
        if re.search(rf"[{CYR}]", token):
            return token.translate(LOOKALIKES)
        return token

    text = TOKEN_RE.sub(fix_token, text)
    return SEPARATOR_RE.sub("", text).strip()


# --- classification ------------------------------------------------------------

def _hits(text: str, section: str) -> list:
    found = []
    for pattern in lexicon()[section]:
        m = pattern.search(text)
        if m:
            found.append(m.group(0).strip())
    return found


def classify(text: str) -> Signal:
    norm = normalize(text or "")
    if not norm:
        return Signal("clean", 0)
    if META_RE.search(norm):
        return Signal("meta", 0)

    hits = {name: _hits(norm, name) for name in SECTIONS}
    repeated_failure = bool(hits["failure"] and hits["repeat"])
    complaint = bool(hits["blame"]) or repeated_failure

    if not (hits["profanity"] or complaint or hits["negative"]):
        return Signal("ack", 0) if hits["ack"] else Signal("clean", 0)

    if hits["profanity"] and hits["praise"] and not complaint:
        return Signal("praise", 0, hits["profanity"] + hits["praise"])

    candidates = []  # priority order: the first of the highest weight names the kind
    if hits["blame"]:
        candidates.append((1.0, "directed_complaint", hits["blame"]))
    if repeated_failure:
        candidates.append((1.0, "repeat_failure", hits["failure"] + hits["repeat"]))
    if hits["profanity"] and hits["directed"]:
        candidates.append((1.0, "directed_profanity", hits["profanity"] + hits["directed"]))
    if hits["profanity"]:
        candidates.append((0.5, "profanity", hits["profanity"]))
    if hits["negative"]:
        candidates.append((0.5, "negative", hits["negative"]))

    best = max(w for w, _, _ in candidates)
    weight, kind, _ = next(c for c in candidates if c[0] == best)
    markers = sorted({m for _, _, ms in candidates for m in ms})
    return Signal(kind, weight, markers)


# --- escalation state --------------------------------------------------------------

def _session(state: dict, session_id: str) -> dict:
    return state.setdefault("sessions", {}).setdefault(session_id, {"events": [], "l3": False})


def _prune(sess: dict, now: float) -> None:
    sess["events"] = [e for e in sess["events"] if now - e["t"] <= WINDOW_SECONDS]


def level_for(streak: float) -> int:
    for threshold, level in LEVEL_THRESHOLDS:
        if streak >= threshold:
            return level
    return 0


def current_streak(state: dict, session_id: str, now: float) -> float:
    sess = _session(state, session_id)
    _prune(sess, now)
    return sum(e["w"] for e in sess["events"])


def register(state: dict, session_id: str, signal: Signal, now: float) -> Outcome:
    sess = _session(state, session_id)
    _prune(sess, now)
    if signal.kind == "ack":
        sess["events"] = []
        sess["l3"] = False
        return Outcome(0, 0, None)

    event_id = None
    if signal.weight > 0:
        event_id = uuid.uuid4().hex[:12]
        sess["events"].append({"id": event_id, "t": now, "w": signal.weight})
    streak = sum(e["w"] for e in sess["events"])

    if signal.weight > 0:
        level = level_for(streak)
    else:
        level = 3 if sess["l3"] else 0
    if level == 3:
        sess["l3"] = True
    return Outcome(level, streak, event_id)


def dismiss(state: dict, session_id: str, event_id: str) -> bool:
    sess = _session(state, session_id)
    before = len(sess["events"])
    sess["events"] = [e for e in sess["events"] if e["id"] != event_id]
    removed = len(sess["events"]) < before
    if removed and level_for(sum(e["w"] for e in sess["events"])) < 3:
        sess["l3"] = False
    return removed


# --- persistence -----------------------------------------------------------------

def state_dir() -> Path:
    return Path(os.environ.get("LCD_SPEC_STATE_DIR") or Path.home() / ".lcd-spec")


def load_state(directory: Path) -> dict:
    try:
        return json.loads((directory / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(directory: Path, state: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix="state.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    os.replace(tmp, directory / "state.json")


def append_log(directory: Path, record: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / "signals.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


# --- hook output -------------------------------------------------------------------

def render_context(signal: Signal, outcome: Outcome, session_id: str) -> str:
    if signal.weight == 0:  # a calm message while a level-3 stop is active
        return (f'<lcd-spec-signal level="3" kind="stop-active">\n'
                f"A level-3 stop from the incident-audit protocol is still active ({PROTOCOL_PATH}). "
                "No edits or mutating commands until the user explicitly says to continue. "
                "New evidence in this message allows read-only analysis only.\n"
                "</lcd-spec-signal>")
    dismiss_cmd = f'"{sys.executable}" "{SCRIPT_PATH}" --dismiss {session_id} {outcome.event_id}'
    cues = ", ".join(signal.markers[:8]) or "-"
    return (f'<lcd-spec-signal level="{outcome.level}" kind="{signal.kind}" '
            f'weight="{signal.weight}" streak="{outcome.streak}">\n'
            f"The user's message reads as frustration with your work (level {outcome.level} of 3). "
            f'Before anything else, follow the incident-audit protocol, section "Level {outcome.level}": '
            f"{PROTOCOL_PATH}\n"
            f"Matched cues: {cues}\n"
            "If this is a false trigger (a quote, a meta-mention, swearing about something other than "
            f"your work), say so in one line, run `{dismiss_cmd}`, and continue the task.\n"
            "</lcd-spec-signal>")


def run_hook(payload: dict) -> str:
    session_id = str(payload.get("session_id") or "default")
    signal = classify(str(payload.get("prompt") or ""))
    directory = state_dir()
    state = load_state(directory)
    now = time.time()
    outcome = register(state, session_id, signal, now)
    save_state(directory, state)

    if signal.weight > 0 or signal.kind == "ack":
        append_log(directory, {
            "ts": int(now), "session": session_id, "cwd": payload.get("cwd"),
            "kind": signal.kind, "weight": signal.weight,
            "streak": outcome.streak, "level": outcome.level,
        })
    if outcome.level == 0:
        return ""
    context = render_context(signal, outcome, session_id)
    # ASCII-escaped JSON survives any stdout codec (cp1251/cp1252 on Windows)
    return json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                              "additionalContext": context}})


def read_stdin() -> str:
    """The host pipes UTF-8; never trust the locale codec (cp1251/cp1252 on Windows)."""
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is None:  # replaced by a text stream (tests)
        return sys.stdin.read()
    return buffer.read().decode("utf-8", errors="replace")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv[:1] == ["--dismiss"] and len(argv) == 3:
            directory = state_dir()
            state = load_state(directory)
            ok = dismiss(state, argv[1], argv[2])
            save_state(directory, state)
            print("dismissed" if ok else "no such event (already dismissed?)")
            return 0
        if argv[:1] == ["--classify"] and len(argv) == 2:
            sig = classify(argv[1])
            print(json.dumps({"kind": sig.kind, "weight": sig.weight, "markers": sig.markers}))
            return 0
        if os.environ.get("LCD_SPEC_INTERNAL") == "1":
            return 0
        if os.environ.get("LCD_SPEC_FRUSTRATION", "").lower() == "off":
            return 0
        payload = json.loads(read_stdin() or "{}")
        if not isinstance(payload, dict):
            return 0
        out = run_hook(payload)
        if out:
            sys.stdout.write(out)
    except Exception:  # fail open: never block the user's session
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
