"""Behaviour of incidents.py - reading the project's incident log back into the workflow."""
import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "lcd-spec" / "scripts"))

import incidents  # noqa: E402

LOG = """# Incidents

## Lessons index

<!-- One line per active lesson, newest first: INC-id - lesson. -->
- INC-20260924-1 - Name the cache invalidator and its delay in the spec
- INC-20260910-2 - Re-check the migration number at apply time

## Entries

### INC-20260924-1: stale cache after price update
- **Lesson:** Name the cache invalidator and its delay in the spec

## Retired lessons

- INC-20260801-1 - Pin the Node version (retired: enforced by .nvmrc check)
"""


class ActiveLessons(unittest.TestCase):
    def test_index_lines_come_back_in_file_order(self):
        self.assertEqual(incidents.active_lessons(LOG), [
            ("INC-20260924-1", "Name the cache invalidator and its delay in the spec"),
            ("INC-20260910-2", "Re-check the migration number at apply time"),
        ])

    def test_retired_lessons_are_left_out(self):
        ids = [lesson_id for lesson_id, _ in incidents.active_lessons(LOG)]
        self.assertNotIn("INC-20260801-1", ids)

    def test_template_example_inside_a_comment_is_not_a_lesson(self):
        log = "## Lessons index\n\n<!-- e.g.\n- INC-20260101-1 - example only\n-->\n\n## Entries\n"
        self.assertEqual(incidents.active_lessons(log), [])

    def test_log_without_an_index_has_no_lessons(self):
        self.assertEqual(incidents.active_lessons("# Incidents\n\n## Entries\n"), [])


CACHE = """### INC-20260924-1: stale price after update
- **Date:** 2026-09-24
- **Change:** add-price-cache
- **Stage:** after-archive
- **Signal:** user report
- **What happened:** The price cache served the old value for an hour after an admin edit.
- **Trigger:** adding a cache in front of an entity that admins can edit
- **Wrong belief:** The TTL was short enough to not matter.
- **Evidence:** PriceCache.java:41
- **Class:** written-not-consumed
- **Stack:** java, spring
- **Paths:** **/cache/**, **/*Cache*.java
- **Needed at:** plan, apply
- **Fix:** evict on PriceUpdated, commit 3f2a1c9
- **Lesson:** Name the cache invalidator and its delay in the spec
"""
MIGRATION = """### INC-20260910-2: migration number collision
- **Date:** 2026-09-10
- **Change:** add-export
- **Stage:** audit
- **Signal:** audit blocker
- **What happened:** V12 was already taken by a merged change when the plan was applied.
- **Wrong belief:** not established
- **Evidence:** db/migration/V12__orders.sql
- **Class:** rot
- **Fix:** task 0.1 re-checks the number
- **Lesson:** Re-check the migration number at apply time
"""
SCREENS = """### INC-20260901-1: field missing on the mobile screen
- **Date:** 2026-09-01
- **Change:** none
- **Stage:** grill
- **Signal:** frustration L2
- **What happened:** The discount field was specified for the desktop form only.
- **Wrong belief:** The mobile screen reuses the desktop form.
- **Evidence:** app/mobile/checkout.tsx:12
- **Class:** misread-request
- **Stack:** nextjs
- **Needed at:** grill
- **Fix:** spec lists both screens
- **Lesson:** Ask which screens show the field before specifying it
"""
INDEX = """- INC-20260924-1 - Name the cache invalidator and its delay in the spec
- INC-20260910-2 - Re-check the migration number at apply time
- INC-20260901-1 - Ask which screens show the field before specifying it
"""


def log(index=INDEX, entries=(CACHE, MIGRATION, SCREENS), retired=""):
    return ("# Incidents\n\n## Lessons index\n\n" + index + "\n## Entries\n\n"
            + "\n".join(entries) + "\n## Retired lessons\n\n" + retired)


FULL = log()


class Validate(unittest.TestCase):
    def errors(self, text):
        return " | ".join(incidents.validate(text))

    def test_well_formed_log_has_no_errors(self):
        self.assertEqual(incidents.validate(FULL), [])

    def test_entry_in_the_original_ten_field_format_is_still_valid(self):
        self.assertEqual(incidents.validate(log(INDEX.splitlines(True)[1], (MIGRATION,))), [])

    def test_empty_log_from_the_template_is_valid(self):
        template = (ROOT / "skills/lcd-spec/references/incidents-template.md").read_text(encoding="utf-8")
        self.assertEqual(incidents.validate(template), [])

    def test_two_entries_with_one_id_are_reported(self):
        self.assertIn("INC-20260910-2", self.errors(log(entries=(CACHE, MIGRATION, MIGRATION, SCREENS))))

    def test_unknown_class_is_reported_with_its_value(self):
        errors = self.errors(log(entries=(CACHE.replace("written-not-consumed", "bad-luck"), MIGRATION, SCREENS)))
        self.assertIn("INC-20260924-1", errors)
        self.assertIn("bad-luck", errors)

    def test_unknown_stage_is_reported(self):
        self.assertIn("deploy", self.errors(log(entries=(CACHE, MIGRATION.replace("Stage:** audit", "Stage:** deploy"), SCREENS))))

    def test_unknown_signal_is_reported(self):
        self.assertIn("vibes", self.errors(log(entries=(CACHE, MIGRATION.replace("audit blocker", "vibes"), SCREENS))))

    def test_manual_audit_is_an_accepted_signal(self):
        self.assertEqual(incidents.validate(log(entries=(CACHE, MIGRATION.replace("audit blocker", "manual audit"), SCREENS))), [])

    def test_missing_lesson_field_is_named(self):
        broken = MIGRATION.replace("- **Lesson:** Re-check the migration number at apply time\n", "")
        errors = self.errors(log(entries=(CACHE, broken, SCREENS)))
        self.assertIn("INC-20260910-2", errors)
        self.assertIn("Lesson", errors)

    def test_index_line_without_an_entry_is_reported(self):
        self.assertIn("INC-20260901-1", self.errors(log(entries=(CACHE, MIGRATION))))

    def test_entry_that_is_neither_active_nor_retired_is_reported(self):
        self.assertIn("INC-20260901-1", self.errors(log(index="".join(INDEX.splitlines(True)[:2]))))

    def test_retired_entry_needs_no_index_line(self):
        text = log(index="".join(INDEX.splitlines(True)[:2]),
                   retired="- INC-20260901-1 - Ask which screens (retired: checklist in stage 3)\n")
        self.assertEqual(incidents.validate(text), [])

    def test_stage_the_lesson_is_needed_at_must_be_a_real_stage(self):
        self.assertIn("deploy", self.errors(log(entries=(CACHE.replace("plan, apply", "plan, deploy"), MIGRATION, SCREENS))))

    def test_recurrence_must_be_a_positive_number(self):
        self.assertIn("Recurrence", self.errors(log(entries=(CACHE + "- **Recurrence:** often\n", MIGRATION, SCREENS))))


class Template(unittest.TestCase):
    """The template is where an agent reads the allowed values; the validator must agree with it."""

    def options(self, name):
        template = (ROOT / "skills/lcd-spec/references/incidents-template.md").read_text(encoding="utf-8")
        value = re.search(rf"^- \*\*{name}:\*\* (.+(?:\n  .+)*)", template, re.M).group(1)
        return [option.strip() for option in value.split("|")]

    def test_template_offers_exactly_the_stages_the_validator_accepts(self):
        self.assertEqual(self.options("Stage"), list(incidents.STAGES))

    def test_template_offers_exactly_the_signals_the_validator_accepts(self):
        self.assertEqual(self.options("Signal"), ["frustration L<n>", *incidents.SIGNALS])

    def test_template_offers_exactly_the_classes_the_validator_accepts(self):
        self.assertEqual(self.options("Class"), list(incidents.CLASSES))

    def test_template_names_every_field_that_narrows_or_counts_a_lesson(self):
        template = (ROOT / "skills/lcd-spec/references/incidents-template.md").read_text(encoding="utf-8")
        for name in ("Trigger", "Stack", "Paths", "Needed at", "Recurrence", "Seen"):
            self.assertIn(f"**{name}:**", template)


class FindDuplicate(unittest.TestCase):
    def test_similar_incident_is_found_and_unrelated_ones_are_not(self):
        self.assertEqual(incidents.find(FULL, "cache shows old price after edit"), ["INC-20260924-1"])

    def test_class_filter_keeps_only_that_class(self):
        self.assertEqual(incidents.find(FULL, "migration number taken", cls="rot"), ["INC-20260910-2"])
        self.assertEqual(incidents.find(FULL, "migration number taken", cls="misread-request"), [])

    def test_best_match_comes_first(self):
        other = CACHE.replace("INC-20260924-1", "INC-20260925-1").replace(
            "The price cache served the old value for an hour after an admin edit.", "A cache was added.")
        text = log(INDEX + "- INC-20260925-1 - Name the cache invalidator\n", (other, CACHE, MIGRATION, SCREENS))
        self.assertEqual(incidents.find(text, "price cache served old value")[0], "INC-20260924-1")

    def test_nothing_in_common_finds_nothing(self):
        self.assertEqual(incidents.find(FULL, "kubernetes ingress timeout"), [])


class Bump(unittest.TestCase):
    def fields(self, text, inc_id):
        return next(e for e in incidents.parse(text).entries if e.id == inc_id).fields

    def test_first_repeat_makes_recurrence_two_and_keeps_both_dates(self):
        text, n = incidents.bump(FULL, "INC-20260910-2", "2026-10-01")
        self.assertEqual(n, 2)
        fields = self.fields(text, "INC-20260910-2")
        self.assertEqual(fields["recurrence"], "2")
        self.assertEqual(fields["seen"], "2026-09-10, 2026-10-01")

    def test_second_repeat_counts_three(self):
        text, _ = incidents.bump(FULL, "INC-20260910-2", "2026-10-01")
        text, n = incidents.bump(text, "INC-20260910-2", "2026-10-05")
        self.assertEqual(n, 3)
        self.assertEqual(self.fields(text, "INC-20260910-2")["seen"], "2026-09-10, 2026-10-01, 2026-10-05")

    def test_other_entries_and_the_index_stay_byte_identical(self):
        text, _ = incidents.bump(FULL, "INC-20260910-2", "2026-10-01")
        self.assertIn(CACHE, text)
        self.assertIn(SCREENS, text)
        self.assertIn(INDEX, text)

    def test_bumped_log_is_still_valid(self):
        text, _ = incidents.bump(FULL, "INC-20260910-2", "2026-10-01")
        self.assertEqual(incidents.validate(text), [])

    def test_unknown_id_is_an_error(self):
        with self.assertRaises(LookupError):
            incidents.bump(FULL, "INC-20200101-9", "2026-10-01")


class Select(unittest.TestCase):
    def ids(self, text=FULL, **kw):
        return [lesson_id for lesson_id, _ in incidents.select(text, **kw)]

    def test_no_filter_returns_every_active_lesson(self):
        self.assertEqual(self.ids(), ["INC-20260924-1", "INC-20260910-2", "INC-20260901-1"])

    def test_stage_filter_drops_lessons_needed_elsewhere(self):
        self.assertEqual(self.ids(stages=["grill"]), ["INC-20260910-2", "INC-20260901-1"])

    def test_lesson_with_paths_applies_to_a_matching_file(self):
        self.assertEqual(self.ids(stages=["apply"], files=["src/main/java/shop/cache/PriceCache.java"]),
                         ["INC-20260924-1", "INC-20260910-2"])

    def test_lesson_with_paths_is_dropped_for_other_files(self):
        self.assertEqual(self.ids(stages=["apply"], files=["frontend/app/page.tsx"]), ["INC-20260910-2"])

    def test_directory_glob_does_not_match_a_longer_directory_name(self):
        self.assertEqual(self.ids(stages=["apply"], files=["src/cached/Price.java"]), ["INC-20260910-2"])

    def test_file_glob_matches_at_the_repository_root(self):
        self.assertIn("INC-20260924-1", self.ids(stages=["apply"], files=["PriceCache.java"]))

    def test_stack_tag_drops_the_lesson_for_files_of_another_language(self):
        java_only = CACHE.replace("- **Paths:** **/cache/**, **/*Cache*.java\n", "")
        text = log(entries=(java_only, MIGRATION, SCREENS))
        self.assertNotIn("INC-20260924-1", self.ids(text, stages=["apply"], files=["frontend/app/page.tsx"]))
        self.assertIn("INC-20260924-1", self.ids(text, stages=["apply"], files=["src/Price.java"]))

    def test_framework_only_tag_cannot_be_judged_from_paths_and_is_kept(self):
        self.assertIn("INC-20260901-1", self.ids(stages=["grill"], files=["src/Price.java"]))

    def test_index_line_without_an_entry_always_applies(self):
        text = "## Lessons index\n\n- INC-20260924-1 - Name the cache invalidator\n\n## Entries\n"
        self.assertEqual(self.ids(text, stages=["apply"], files=["a.go"]), ["INC-20260924-1"])

    def test_retired_lesson_is_never_selected(self):
        text = log(index="".join(INDEX.splitlines(True)[:2]),
                   retired="- INC-20260901-1 - Ask which screens (retired)\n")
        self.assertNotIn("INC-20260901-1", self.ids(text))

    def test_lessons_recorded_by_the_named_change_can_be_left_out(self):
        self.assertEqual(self.ids(exclude_change="add-export"), ["INC-20260924-1", "INC-20260901-1"])


class CommandLine(unittest.TestCase):
    """The four commands as the agent runs them: exit code, printed lines, the file on disk."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log = Path(self._tmp.name) / "incidents.md"
        self.write(FULL)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, text):
        self.log.write_bytes(text.encode("utf-8"))

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = incidents.main([args[0], str(self.log), *args[1:]])
        return code, out.getvalue(), err.getvalue()

    def test_validate_reports_a_well_formed_log_with_its_counts(self):
        self.assertEqual(self.run_cli("validate")[:2], (0, "OK: 3 entries, 3 active lessons\n"))

    def test_validate_fails_and_names_the_broken_entry(self):
        self.write(log(entries=(CACHE.replace("written-not-consumed", "bad-luck"), MIGRATION, SCREENS)))
        code, out, _ = self.run_cli("validate")
        self.assertEqual(code, 1)
        self.assertIn("INC-20260924-1: Class 'bad-luck'", out)

    def test_find_prints_the_match_with_its_count_and_lesson(self):
        code, out, _ = self.run_cli("find", "cache shows old price after edit")
        self.assertEqual((code, out), (
            0, "INC-20260924-1 (seen 1x) - Name the cache invalidator and its delay in the spec\n"))

    def test_find_shows_how_often_a_repeated_incident_was_seen(self):
        self.run_cli("bump", "INC-20260924-1", "--date", "2026-10-01")
        self.assertIn("INC-20260924-1 (seen 2x)", self.run_cli("find", "cache shows old price")[1])

    def test_find_without_a_match_prints_nothing_and_succeeds(self):
        self.assertEqual(self.run_cli("find", "kubernetes ingress timeout")[:2], (0, ""))

    def test_find_rejects_a_class_outside_the_list(self):
        code, out, _ = self.run_cli("find", "cache", "--class", "bad-luck")
        self.assertEqual((code, out), (2, ""))

    def test_bump_writes_the_count_to_the_file_and_says_what_to_do_next(self):
        code, out, _ = self.run_cli("bump", "INC-20260910-2", "--date", "2026-10-01")
        self.assertEqual(code, 0)
        self.assertIn("INC-20260910-2: recurrence 2", out)
        self.assertIn("something that runs", out)
        saved = self.log.read_bytes().decode("utf-8")
        self.assertIn("- **Recurrence:** 2\n- **Seen:** 2026-09-10, 2026-10-01\n", saved)

    def test_bump_leaves_every_other_byte_of_the_file_alone(self):
        self.run_cli("bump", "INC-20260910-2", "--date", "2026-10-01")
        saved = self.log.read_bytes().decode("utf-8")
        self.assertEqual(saved, FULL.replace(
            "- **Lesson:** Re-check the migration number at apply time\n",
            "- **Lesson:** Re-check the migration number at apply time\n"
            "- **Recurrence:** 2\n- **Seen:** 2026-09-10, 2026-10-01\n"))

    def test_bump_keeps_windows_line_endings_of_a_log_that_has_them(self):
        self.write(FULL.replace("\n", "\r\n"))
        self.run_cli("bump", "INC-20260910-2", "--date", "2026-10-01")
        saved = self.log.read_bytes().decode("utf-8")
        self.assertIn("- **Recurrence:** 2\r\n", saved)
        self.assertNotIn("\n", saved.replace("\r\n", ""))

    def test_bump_of_an_unknown_id_fails_and_leaves_the_file_alone(self):
        code, _, err = self.run_cli("bump", "INC-20200101-9")
        self.assertEqual(code, 3)
        self.assertIn("INC-20200101-9", err)
        self.assertEqual(self.log.read_bytes().decode("utf-8"), FULL)

    def test_select_prints_the_lessons_for_a_stage_and_files(self):
        code, out, _ = self.run_cli("select", "--stage", "apply", "--files", "frontend/app/page.tsx")
        self.assertEqual((code, out), (0, "INC-20260910-2 - Re-check the migration number at apply time\n"))

    def test_select_accepts_several_stages(self):
        out = self.run_cli("select", "--stage", "plan", "--stage", "grill")[1]
        self.assertEqual([line.split(" ")[0] for line in out.splitlines()],
                         ["INC-20260924-1", "INC-20260910-2", "INC-20260901-1"])

    def test_missing_log_file_is_an_error_not_an_empty_result(self):
        self.log.unlink()
        code, out, err = self.run_cli("select")
        self.assertEqual((code, out), (3, ""))
        self.assertIn("incidents.md", err)

    def test_lesson_in_ukrainian_is_printed_whatever_the_console_codec(self):
        # piped stdout on Windows defaults to cp1251/cp1252; a Cyrillic lesson must not crash
        lesson = "Перевіряй номер міграції перед apply"
        self.write(FULL.replace("Re-check the migration number at apply time", lesson))
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
        proc = subprocess.run(
            [sys.executable, str(ROOT / "skills" / "lcd-spec" / "scripts" / "incidents.py"),
             "select", str(self.log), "--stage", "audit"],
            capture_output=True, env=env, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertIn(f"INC-20260910-2 - {lesson}", proc.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
