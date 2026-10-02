"""Behaviour of gate.py - the hard stop between lcd-spec stages."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "lcd-spec" / "scripts"))

import gate  # noqa: E402
import verify_run  # noqa: E402

PROPOSAL = "## Why\nCustomers need exports.\n"
SPEC = "## ADDED Requirements\n\n### Requirement: Export\nThe system SHALL export.\n\n#### Scenario: ok\n- **WHEN** a\n- **THEN** b\n"
DESIGN = "## Context\nx\n\n## Decisions\n- CSV\n"
GRILLING_OK = "# Grilling\n\nVerdict: PASS\n\n## Decisions\n- D1 CSV\n\n## Open questions\n- [x] encoding? -> UTF-8\n"
TASKS = "## 1. Export\n\n- [ ] 1.1 Add exporter\n- [ ] 1.2 Add endpoint\n"
PLAN = ("# Export Implementation Plan\n\n## Global Constraints\n- UTF-8\n\n"
        "## Verification\n- python -m unittest\n\n"
        "## File Structure\n- exporter.py: builds the CSV\n\n---\n\n"
        "### Task 1.1: Add exporter\n\n**Files:**\n- Create: `exporter.py`\n\n"
        "**Interfaces:**\n- Produces: `export(rows) -> str`\n\nStep 1: write test\n\n"
        "### Task 1.2: Add endpoint\n\n**Files:**\n- Modify: `api.py`\n\n"
        "**Interfaces:**\n- Consumes: `export(rows) -> str`\n\nStep 1: write test\n")
AUDIT_OK = ("# Pre-apply audit\n\nVerdict: PASS\n\n## Blockers\n"
            "- [x] migration number V12 taken -> task 0.1 added (INC-20260920-1)\n\n"
            "## Serious\n\n## Minor / docs\n\n## What I did NOT verify\n- live database\n")


def incident(inc_id, change="add-export", extra=""):
    return (f"### {inc_id}: something went wrong\n- **Date:** 2026-09-20\n- **Change:** {change}\n"
            "- **Stage:** audit\n- **Signal:** audit blocker\n- **What happened:** x\n"
            "- **Wrong belief:** not established\n- **Evidence:** x\n- **Class:** rot\n"
            f"{extra}- **Fix:** x\n- **Lesson:** lesson of {inc_id}\n")


def incident_log(*entries):
    ids = [e.split(":", 1)[0].removeprefix("### ") for e in entries]
    index = "".join(f"- {i} - lesson of {i}\n" for i in ids)
    return "# Incidents\n\n## Lessons index\n\n" + index + "\n## Entries\n\n" + "\n".join(entries)
REVIEW_SKIPPED = "# Perspective review\n\nVerdict: SKIPPED\n\nUser declined on 2026-09-24.\n"
REVIEW_OK = ("# Perspective review\n\nVerdict: PASS\n\nPerspectives: tester, architect\n\n"
             "## Must fix\n- [x] [tester] no scenario for empty export -> spec scenario added\n\n"
             "## Should fix\n- [ ] [architect] consider streaming for large files\n\n## Consider\n")


class ChangeFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.change = Path(self._tmp.name) / "openspec" / "changes" / "add-export"
        (self.change / "specs" / "export").mkdir(parents=True)
        self.write("proposal.md", PROPOSAL)
        self.write("specs/export/spec.md", SPEC)
        self.write("design.md", DESIGN)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        (self.change / rel).write_text(text, encoding="utf-8")

    def append(self, rel, text):
        with open(self.change / rel, "a", encoding="utf-8") as fh:
            fh.write(text)

    def passes(self, stage):
        return gate.check(self.change, stage).ok

    def reasons(self, stage):
        return " | ".join(gate.check(self.change, stage).reasons)

    def grill(self, text=GRILLING_OK):
        self.write("grilling.md", text)
        gate.stamp(self.change, "grilling")

    def plan(self):
        self.write("tasks.md", TASKS)
        self.write("plan.md", PLAN)

    def incidents(self, text):
        (self.change.parents[1] / "incidents.md").write_text(text, encoding="utf-8")

    def audit(self, text=AUDIT_OK):
        if not (self.change.parents[1] / "incidents.md").exists():
            self.incidents(incident_log(incident("INC-20260920-1")))
        self.write("audit.md", text)
        gate.stamp(self.change, "audit")

    def review(self, text=REVIEW_SKIPPED):
        self.write("review.md", text)


class GrillingGate(ChangeFixture):
    def test_missing_transcript_blocks(self):
        self.assertFalse(self.passes("grilling"))
        self.assertIn("grilling.md", self.reasons("grilling"))

    def test_stamped_pass_verdict_passes(self):
        self.grill()
        self.assertTrue(self.passes("grilling"), self.reasons("grilling"))

    def test_verdict_other_than_pass_blocks(self):
        self.grill(GRILLING_OK.replace("Verdict: PASS", "Verdict: PENDING"))
        self.assertFalse(self.passes("grilling"))

    def test_unanswered_open_question_blocks(self):
        self.grill(GRILLING_OK + "- [ ] retention period?\n")
        self.assertIn("open question", self.reasons("grilling"))

    def test_unstamped_transcript_blocks(self):
        self.write("grilling.md", GRILLING_OK)
        self.assertIn("stamp", self.reasons("grilling"))

    def test_spec_edited_after_grilling_goes_stale(self):
        self.grill()
        self.append("specs/export/spec.md", "\n### Requirement: Import\nThe system SHALL import.\n")
        self.assertIn("stale", self.reasons("grilling"))

    def test_audit_findings_section_in_design_does_not_stale_grilling(self):
        self.grill()
        self.append("design.md", "\n## Audit findings\n- 2026-09-24 V12 taken -> fixed\n")
        self.assertTrue(self.passes("grilling"), self.reasons("grilling"))

    def test_transcript_without_decisions_section_blocks(self):
        self.grill("# Grilling\n\nVerdict: PASS\n\n## Open questions\n- [x] encoding? -> UTF-8\n")
        self.assertIn("Decisions", self.reasons("grilling"))

    def test_decisions_section_left_as_template_comment_blocks(self):
        self.grill(GRILLING_OK.replace("- D1 CSV\n", "<!-- One block per resolved branch -->\n"))
        self.assertIn("Decisions", self.reasons("grilling"))

    def test_transcript_without_open_questions_section_blocks(self):
        self.grill("# Grilling\n\nVerdict: PASS\n\n## Decisions\n- D1 CSV\n")
        self.assertIn("Open questions", self.reasons("grilling"))


class UnconfirmedMarkers(ChangeFixture):
    """An assumption or gap the artifacts still flag must be settled before grilling passes."""

    def test_unconfirmed_assumption_in_spec_blocks(self):
        self.append("specs/export/spec.md", "\nASSUMED (unconfirmed): exports are CSV only\n")
        self.grill()
        reasons = self.reasons("grilling")
        self.assertIn("specs/export/spec.md", reasons)
        self.assertIn("ASSUMED (unconfirmed)", reasons)

    def test_needs_clarification_marker_in_proposal_blocks(self):
        self.append("proposal.md", "\n[NEEDS CLARIFICATION: who may export?]\n")
        self.grill()
        self.assertIn("proposal.md", self.reasons("grilling"))

    def test_marker_in_design_blocks(self):
        self.append("design.md", "\n- Retention: 30 days. ASSUMED (unconfirmed)\n")
        self.grill()
        self.assertIn("design.md", self.reasons("grilling"))

    def test_marker_inside_template_comment_is_guidance_not_content(self):
        self.append("design.md", "\n<!-- write ASSUMED (unconfirmed): ... for anything not asked -->\n")
        self.grill()
        self.assertTrue(self.passes("grilling"), self.reasons("grilling"))

    def test_unchecked_open_question_in_design_blocks(self):
        self.append("design.md", "\n## Open Questions\n- [ ] streaming or buffered?\n")
        self.grill()
        self.assertIn("design.md", self.reasons("grilling"))

    def test_answered_open_question_in_design_passes(self):
        self.append("design.md", "\n## Open Questions\n- [x] streaming or buffered? -> buffered\n")
        self.grill()
        self.assertTrue(self.passes("grilling"), self.reasons("grilling"))


class PlanGate(ChangeFixture):
    def test_plan_requires_grilling_first(self):
        self.plan()
        self.assertIn("grilling", self.reasons("plan"))

    def test_matching_numbering_passes(self):
        self.grill()
        self.plan()
        self.assertTrue(self.passes("plan"), self.reasons("plan"))

    def test_task_without_plan_section_blocks(self):
        self.grill()
        self.plan()
        self.append("tasks.md", "- [ ] 1.3 Add docs\n")
        self.assertIn("1.3", self.reasons("plan"))

    def test_plan_section_without_task_blocks(self):
        self.grill()
        self.plan()
        self.append("plan.md", "\n### Task 2.1: Extra\nStep 1\n")
        self.assertIn("2.1", self.reasons("plan"))

    def test_placeholder_in_plan_blocks(self):
        self.grill()
        self.plan()
        self.append("plan.md", "Add appropriate error handling. TBD\n")
        self.assertIn("placeholder", self.reasons("plan"))

    def test_missing_global_constraints_blocks(self):
        self.grill()
        self.plan()
        self.write("plan.md", PLAN.replace("## Global Constraints", "## Notes"))
        self.assertIn("Global Constraints", self.reasons("plan"))

    def test_missing_verification_section_blocks(self):
        self.grill()
        self.plan()
        self.write("plan.md", PLAN.replace("## Verification\n- python -m unittest\n\n", ""))
        self.assertIn("Verification", self.reasons("plan"))

    def test_verification_section_without_a_command_blocks(self):
        self.grill()
        self.plan()
        self.write("plan.md", PLAN.replace("- python -m unittest\n", ""))
        self.assertIn("Verification", self.reasons("plan"))

    def test_verification_written_as_prose_blocks(self):
        # verify_run.py runs list items; prose it cannot run would only surface in stage 6
        self.grill()
        self.plan()
        self.write("plan.md", PLAN.replace("- python -m unittest\n", "Run the tests and the linter.\n"))
        self.assertIn("no command", self.reasons("plan"))

    def test_missing_file_structure_section_blocks(self):
        self.grill()
        self.plan()
        self.write("plan.md", PLAN.replace("## File Structure\n- exporter.py: builds the CSV\n\n", ""))
        self.assertIn("File Structure", self.reasons("plan"))

    def test_file_structure_followed_only_by_tasks_counts_as_empty(self):
        # the tasks that follow are '###' headings, so they sit inside the '##' section
        self.grill()
        self.plan()
        self.write("plan.md", PLAN.replace("- exporter.py: builds the CSV\n", ""))
        self.assertIn("File Structure", self.reasons("plan"))

    def test_task_without_files_block_is_named(self):
        self.grill()
        self.plan()
        self.write("plan.md", PLAN.replace("**Files:**\n- Modify: `api.py`\n\n", ""))
        reasons = self.reasons("plan")
        self.assertIn("1.2", reasons)
        self.assertIn("Files", reasons)
        self.assertNotIn("1.1", reasons)

    def test_task_without_interfaces_block_is_named(self):
        self.grill()
        self.plan()
        self.write("plan.md", PLAN.replace("**Interfaces:**\n- Produces: `export(rows) -> str`\n\n", ""))
        reasons = self.reasons("plan")
        self.assertIn("1.1", reasons)
        self.assertIn("Interfaces", reasons)

    def test_files_label_inside_a_code_fence_does_not_count(self):
        self.grill()
        self.plan()
        self.write("plan.md", PLAN.replace("**Files:**\n- Modify: `api.py`\n\n",
                                           "```\n**Files:**\n- Modify: `api.py`\n```\n\n"))
        self.assertIn("Files", self.reasons("plan"))


INCIDENTS = ("# Incidents\n\n## Lessons index\n\n"
             "- INC-20260924-1 - Name the cache invalidator and its delay in the spec\n\n"
             "## Entries\n\n## Retired lessons\n\n"
             "- INC-20260801-1 - Pin the Node version (retired: .nvmrc check)\n")


class LessonsInThePlan(ChangeFixture):
    """Every active lesson in openspec/incidents.md gets an answer in the plan."""

    def ready(self, plan=PLAN):
        (self.change.parents[1] / "incidents.md").write_text(INCIDENTS, encoding="utf-8")
        self.grill()
        self.write("tasks.md", TASKS)
        self.write("plan.md", plan)

    def with_section(self, body):
        return PLAN.replace("## File Structure", f"## Lessons applied\n{body}\n\n## File Structure")

    def test_plan_silent_about_an_active_lesson_blocks(self):
        self.ready()
        self.assertIn("INC-20260924-1", self.reasons("plan"))

    def test_plan_that_answers_the_lesson_passes(self):
        self.ready(self.with_section("- INC-20260924-1 - Task 1.2 names the invalidator"))
        self.assertTrue(self.passes("plan"), self.reasons("plan"))

    def test_lesson_marked_not_applicable_passes(self):
        self.ready(self.with_section("- INC-20260924-1 - not applicable: the change adds no cache"))
        self.assertTrue(self.passes("plan"), self.reasons("plan"))

    def test_lesson_id_mentioned_only_inside_a_task_blocks(self):
        self.ready(PLAN.replace("Step 1: write test\n\n### Task 1.2",
                                "Step 1: write test (see INC-20260924-1)\n\n### Task 1.2"))
        self.assertIn("INC-20260924-1", self.reasons("plan"))

    def test_answering_lesson_10_does_not_answer_lesson_1(self):
        self.ready(self.with_section("- INC-20260924-10 - Task 1.1"))
        self.assertIn("'INC-20260924-1'", self.reasons("plan"))

    def test_retired_lesson_needs_no_answer(self):
        self.ready(self.with_section("- INC-20260924-1 - Task 1.2 names the invalidator"))
        self.assertNotIn("INC-20260801-1", self.reasons("plan"))

    def test_project_without_an_incident_log_needs_no_section(self):
        self.grill()
        self.plan()
        self.assertTrue(self.passes("plan"), self.reasons("plan"))

    def narrowed(self, extra, change="other-change"):
        self.grill()
        self.plan()
        self.incidents(incident_log(incident("INC-20260915-1", change, extra)))

    def test_lesson_about_files_the_plan_does_not_touch_needs_no_answer(self):
        self.narrowed("- **Paths:** **/*.sql\n")
        self.assertTrue(self.passes("plan"), self.reasons("plan"))

    def test_lesson_about_a_file_the_plan_touches_needs_an_answer(self):
        self.narrowed("- **Paths:** **/api.py\n")
        self.assertIn("INC-20260915-1", self.reasons("plan"))

    def test_lesson_needed_only_at_grilling_needs_no_answer_in_the_plan(self):
        self.narrowed("- **Needed at:** grill\n")
        self.assertTrue(self.passes("plan"), self.reasons("plan"))

    def test_lesson_needed_at_apply_is_answered_by_the_plan(self):
        self.narrowed("- **Needed at:** apply\n")
        self.assertIn("INC-20260915-1", self.reasons("plan"))

    def test_incident_this_change_recorded_itself_needs_no_answer(self):
        # an audit blocker or a fix loop of this change is recorded after its plan exists
        self.narrowed("", change="add-export")
        self.assertTrue(self.passes("plan"), self.reasons("plan"))


class AuditGate(ChangeFixture):
    def ready(self):
        self.grill()
        self.plan()

    def test_resolved_audit_passes(self):
        self.ready()
        self.audit()
        self.assertTrue(self.passes("audit"), self.reasons("audit"))

    def test_open_blocker_blocks(self):
        self.ready()
        self.audit(AUDIT_OK.replace("## Serious", "- [ ] entity is package-private\n\n## Serious"))
        self.assertIn("blocker", self.reasons("audit").lower())

    def test_missing_not_verified_section_blocks(self):
        self.ready()
        self.audit(AUDIT_OK.split("## What I did NOT verify")[0])
        self.assertIn("NOT verify", self.reasons("audit"))

    def test_resolved_blocker_without_an_incident_id_blocks(self):
        self.ready()
        self.audit(AUDIT_OK.replace(" (INC-20260920-1)", ""))
        self.assertIn("resolved blocker", self.reasons("audit"))

    def test_resolved_blocker_citing_an_id_missing_from_the_log_blocks(self):
        self.ready()
        self.audit(AUDIT_OK.replace("INC-20260920-1", "INC-20260920-7"))
        self.assertIn("INC-20260920-7", self.reasons("audit"))

    def test_two_blockers_may_share_one_incident(self):
        self.ready()
        self.audit(AUDIT_OK.replace("## Serious", "- [x] V13 taken as well (INC-20260920-1)\n\n## Serious"))
        self.assertTrue(self.passes("audit"), self.reasons("audit"))

    def test_audit_without_blockers_section_blocks(self):
        self.ready()
        self.audit("# Pre-apply audit\n\nVerdict: PASS\n\n## Serious\n\n## What I did NOT verify\n- live database\n")
        self.assertIn("Blockers", self.reasons("audit"))

    def test_plan_edited_after_audit_goes_stale(self):
        self.ready()
        self.audit()
        self.append("plan.md", "Step 2: also refactor\n")
        self.assertIn("stale", self.reasons("audit"))

    def test_ticking_tasks_during_apply_keeps_audit_fresh(self):
        self.ready()
        self.audit()
        self.review()
        self.write("tasks.md", TASKS.replace("- [ ] 1.1", "- [x] 1.1"))
        self.assertTrue(self.passes("apply"), self.reasons("apply"))

    def test_apply_blocked_without_audit(self):
        self.ready()
        self.assertFalse(self.passes("apply"))


class ReviewGate(ChangeFixture):
    """Stage 5b: the perspective review is optional, but the question must have been asked."""

    def ready(self):
        self.grill()
        self.plan()
        self.audit()

    def test_review_requires_audit_first(self):
        self.grill()
        self.plan()
        self.review()
        self.assertIn("audit", self.reasons("review"))

    def test_apply_blocked_until_review_question_is_answered(self):
        self.ready()
        self.assertIn("review.md", self.reasons("apply"))

    def test_declined_review_lets_apply_through(self):
        self.ready()
        self.review(REVIEW_SKIPPED)
        self.assertTrue(self.passes("apply"), self.reasons("apply"))

    def test_finished_review_with_resolved_must_fix_passes(self):
        self.ready()
        self.review(REVIEW_OK)
        self.assertTrue(self.passes("apply"), self.reasons("apply"))

    def test_open_must_fix_blocks(self):
        self.ready()
        self.review(REVIEW_OK.replace("## Should fix", "- [ ] [user] no empty state\n\n## Should fix"))
        self.assertIn("must-fix", self.reasons("apply"))

    def test_pending_review_blocks(self):
        self.ready()
        self.review(REVIEW_OK.replace("Verdict: PASS", "Verdict: PENDING"))
        self.assertIn("PENDING", self.reasons("apply"))

    def test_review_without_chosen_perspectives_blocks(self):
        self.ready()
        self.review(REVIEW_OK.replace("Perspectives: tester, architect\n\n", ""))
        self.assertIn("Perspectives", self.reasons("apply"))

    def test_passed_review_without_must_fix_section_blocks(self):
        self.ready()
        self.review("# Perspective review\n\nVerdict: PASS\n\nPerspectives: tester\n\n## Should fix\n")
        self.assertIn("Must fix", self.reasons("apply"))


class ArchiveGate(ChangeFixture):
    """Stage 7: the change is archived on a recorded green run of the code as it is now."""

    PASSING = f'"{Path(sys.executable).as_posix()}" -c "print(1)"'
    FAILING = f'"{Path(sys.executable).as_posix()}" -c "import sys; sys.exit(4)"'

    def setUp(self):
        super().setUp()
        self.root = self.change.parents[2]
        subprocess.run(["git", "-C", str(self.root), "init", "-q"], check=True, capture_output=True)
        (self.root / "app.py").write_text("print('v1')\n", encoding="utf-8")

    def ready(self, command=PASSING, review=True):
        self.grill()
        self.write("tasks.md", TASKS)
        self.write("plan.md", PLAN.replace("- python -m unittest", f"- `{command}`"))
        self.audit()
        if review:
            self.review()

    def test_change_that_was_never_verified_cannot_be_archived(self):
        self.ready()
        self.assertTrue(self.passes("apply"), self.reasons("apply"))
        self.assertIn("verification.md missing", self.reasons("archive"))

    def test_green_run_of_the_current_code_lets_the_archive_through(self):
        self.ready()
        verify_run.run(self.change)
        self.assertTrue(self.passes("archive"), self.reasons("archive"))

    def test_failed_verification_blocks_the_archive(self):
        self.ready(self.FAILING)
        verify_run.run(self.change)
        self.assertIn("exit 4", self.reasons("archive"))

    def test_code_changed_after_the_run_blocks_the_archive(self):
        self.ready()
        verify_run.run(self.change)
        (self.root / "app.py").write_text("print('v2')\n", encoding="utf-8")
        self.assertIn("stale", self.reasons("archive"))

    def test_ticking_the_tasks_after_the_run_does_not_block_the_archive(self):
        self.ready()
        verify_run.run(self.change)
        self.write("tasks.md", TASKS.replace("- [ ]", "- [x]"))
        self.assertTrue(self.passes("archive"), self.reasons("archive"))

    def test_archive_needs_every_earlier_gate_too(self):
        self.ready(review=False)
        verify_run.run(self.change)
        self.assertIn("review.md", self.reasons("archive"))

    def test_verification_is_not_asked_for_before_the_code_exists(self):
        self.ready()
        self.assertNotIn("verification", self.reasons("apply"))


class TemplateComments(ChangeFixture):
    """The schema templates carry guidance in HTML comments that must not count as content."""

    def test_example_checkbox_inside_comment_is_not_an_open_question(self):
        self.grill(GRILLING_OK + "<!-- example:\n- [ ] question still unanswered\n-->\n")
        self.assertTrue(self.passes("grilling"), self.reasons("grilling"))

    def test_example_checkbox_inside_comment_is_not_an_open_blocker(self):
        self.grill()
        self.plan()
        self.audit(AUDIT_OK.replace("## Serious", "<!-- example:\n- [ ] <finding> - evidence\n-->\n\n## Serious"))
        self.assertTrue(self.passes("audit"), self.reasons("audit"))

    def test_leftover_template_comment_in_plan_blocks(self):
        self.grill()
        self.plan()
        self.append("plan.md", "**Goal:** <!-- one sentence -->\n")
        self.assertIn("placeholder", self.reasons("plan"))


class CommandLine(ChangeFixture):
    def test_reason_quoting_ukrainian_text_is_printed_whatever_the_console_codec(self):
        # piped stdout on Windows defaults to cp1251/cp1252; the gate quotes artifact text
        self.grill()
        self.plan()
        self.audit(AUDIT_OK.replace("migration number V12 taken -> task 0.1 added (INC-20260920-1)",
                                    "номер міграції V12 зайнятий"))
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
        proc = subprocess.run(
            [sys.executable, str(ROOT / "skills" / "lcd-spec" / "scripts" / "gate.py"),
             "check", str(self.change), "audit"], capture_output=True, env=env, timeout=30)
        self.assertEqual(proc.returncode, 1, proc.stderr.decode("utf-8", "replace"))
        self.assertIn("номер міграції V12 зайнятий", proc.stdout.decode("utf-8"))


class Stamp(ChangeFixture):
    def test_restamp_replaces_hash_line(self):
        self.grill()
        gate.stamp(self.change, "grilling")
        text = (self.change / "grilling.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("Artifacts-Hash:"), 1)


if __name__ == "__main__":
    unittest.main()
