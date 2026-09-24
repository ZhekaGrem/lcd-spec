"""Behaviour of gate.py - the hard stop between lcd-spec stages."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "lcd-spec" / "scripts"))

import gate  # noqa: E402

PROPOSAL = "## Why\nCustomers need exports.\n"
SPEC = "## ADDED Requirements\n\n### Requirement: Export\nThe system SHALL export.\n\n#### Scenario: ok\n- **WHEN** a\n- **THEN** b\n"
DESIGN = "## Context\nx\n\n## Decisions\n- CSV\n"
GRILLING_OK = "# Grilling\n\nVerdict: PASS\n\n## Decisions\n- D1 CSV\n\n## Open questions\n- [x] encoding? -> UTF-8\n"
TASKS = "## 1. Export\n\n- [ ] 1.1 Add exporter\n- [ ] 1.2 Add endpoint\n"
PLAN = ("# Export Implementation Plan\n\n## Global Constraints\n- UTF-8\n\n"
        "### Task 1.1: Add exporter\nStep 1: write test\n\n### Task 1.2: Add endpoint\nStep 1: write test\n")
AUDIT_OK = ("# Pre-apply audit\n\nVerdict: PASS\n\n## Blockers\n- [x] migration number V12 taken -> task 0.1 added\n\n"
            "## Serious\n\n## Minor / docs\n\n## What I did NOT verify\n- live database\n")
REVIEW_SKIPPED = "# Perspective review\n\nVerdict: SKIPPED\n\nUser declined on 2026-09-24.\n"
REVIEW_OK = ("# Perspective review\n\nVerdict: PASS\n\nPerspectives: tester, architect\n\n"
             "## Must fix\n- [x] [tester] no scenario for empty export -> spec scenario added\n\n"
             "## Should fix\n- [ ] [architect] consider streaming for large files\n\n## Consider\n")


class ChangeFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.change = Path(self._tmp.name) / "add-export"
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

    def audit(self, text=AUDIT_OK):
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


class Stamp(ChangeFixture):
    def test_restamp_replaces_hash_line(self):
        self.grill()
        gate.stamp(self.change, "grilling")
        text = (self.change / "grilling.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("Artifacts-Hash:"), 1)


if __name__ == "__main__":
    unittest.main()
