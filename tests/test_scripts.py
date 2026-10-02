"""Behaviour of the helper scripts: task_brief.py and install.py."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "lcd-spec" / "scripts"))

import install  # noqa: E402
import task_brief  # noqa: E402

PLAN = """# Plan

## Global Constraints
- UTF-8 everywhere

## Review Focus
- empty file

### Task 1.1: Exporter
Step 1: test for exporter

### Task 1.2: Endpoint
Step 1: test for endpoint

```markdown
### Task 1.2: this heading is inside a fence and is not a task
```

### Task 1.10: Docs
Step 1: docs
"""


class TaskBrief(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.change = Path(self._tmp.name)
        (self.change / "plan.md").write_text(PLAN, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_brief_holds_only_the_requested_task_plus_constraints(self):
        path = task_brief.write_brief(self.change, "1.1")
        text = path.read_text(encoding="utf-8")
        self.assertIn("UTF-8 everywhere", text)
        self.assertIn("test for exporter", text)
        self.assertNotIn("test for endpoint", text)
        self.assertNotIn("Docs", text)
        self.assertEqual(path.parent.name, ".work")

    def test_fenced_heading_does_not_end_the_task(self):
        text = task_brief.write_brief(self.change, "1.2").read_text(encoding="utf-8")
        self.assertIn("inside a fence", text)
        self.assertNotIn("Step 1: docs", text)

    def test_unknown_task_raises(self):
        with self.assertRaises(LookupError):
            task_brief.write_brief(self.change, "9.9")


class TaskBriefLessons(unittest.TestCase):
    """The implementer never reads incidents.md, so the brief carries its lessons."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.openspec = Path(self._tmp.name) / "openspec"
        self.change = self.openspec / "changes" / "add-export"
        self.change.mkdir(parents=True)
        (self.change / "plan.md").write_text(PLAN, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def brief(self, task_id="1.1"):
        return task_brief.write_brief(self.change, task_id).read_text(encoding="utf-8")

    def test_brief_carries_the_active_lessons(self):
        (self.openspec / "incidents.md").write_text(
            "## Lessons index\n\n- INC-20260924-1 - Name the cache invalidator in the spec\n\n"
            "## Retired lessons\n\n- INC-20260801-1 - Pin the Node version\n", encoding="utf-8")
        text = self.brief()
        self.assertIn("INC-20260924-1", text)
        self.assertIn("Name the cache invalidator in the spec", text)
        self.assertNotIn("INC-20260801-1", text)
        self.assertIn("test for exporter", text)

    def test_brief_without_a_log_mentions_no_incidents(self):
        self.assertNotIn("INC-", self.brief())

    def test_brief_with_an_empty_index_mentions_no_incidents(self):
        (self.openspec / "incidents.md").write_text("## Lessons index\n\n## Entries\n", encoding="utf-8")
        self.assertNotIn("incidents", self.brief().lower())

    def narrowed(self, extra):
        (self.change / "plan.md").write_text(
            "# Plan\n\n## Global Constraints\n- UTF-8\n\n"
            "### Task 1.1: Exporter\n\n**Files:**\n- Create: `src/export/exporter.py`\n"
            "- Modify: `src/api.py:10-42`\n\n**Interfaces:**\n- Produces: `export()` in `ignored.sql`\n\n"
            "Step 1: test for exporter\n\n"
            "### Task 1.2: Migration\n\n**Files:**\n- Create: `db/V13__export.sql`\n\nStep 1: migrate\n",
            encoding="utf-8")
        (self.openspec / "incidents.md").write_text(
            "## Lessons index\n\n- INC-20260915-1 - Re-check the migration number\n\n## Entries\n\n"
            "### INC-20260915-1: collision\n- **Change:** other\n" + extra, encoding="utf-8")

    def test_lesson_about_other_files_stays_out_of_the_brief(self):
        self.narrowed("- **Paths:** **/*.sql\n")
        self.assertNotIn("INC-20260915-1", self.brief("1.1"))

    def test_lesson_about_a_file_of_this_task_is_in_the_brief(self):
        self.narrowed("- **Paths:** **/*.sql\n")
        self.assertIn("INC-20260915-1", self.brief("1.2"))

    def test_line_range_after_a_path_does_not_hide_the_file(self):
        self.narrowed("- **Paths:** src/api.py\n")
        self.assertIn("INC-20260915-1", self.brief("1.1"))

    def test_lesson_needed_only_at_grilling_stays_out_of_the_brief(self):
        self.narrowed("- **Needed at:** grill\n")
        self.assertNotIn("INC-20260915-1", self.brief("1.1"))


class Install(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def init_openspec(self):
        (self.project / "openspec").mkdir()
        (self.project / "openspec" / "config.yaml").write_text(
            "schema: spec-driven\n\n# context: |\n", encoding="utf-8")

    def test_refuses_without_openspec(self):
        with self.assertRaises(FileNotFoundError):
            install.install(self.project)

    def test_installs_schema_and_switches_config(self):
        self.init_openspec()
        install.install(self.project)
        self.assertTrue((self.project / "openspec/schemas/lcd-spec/schema.yaml").is_file())
        config = (self.project / "openspec/config.yaml").read_text(encoding="utf-8")
        self.assertIn("schema: lcd-spec", config)
        self.assertIn("# context: |", config)
        self.assertTrue((self.project / "openspec/incidents.md").is_file())

    def test_is_idempotent(self):
        self.init_openspec()
        install.install(self.project)
        (self.project / "openspec/incidents.md").write_text("# kept\n", encoding="utf-8")
        install.install(self.project)
        gitignore = (self.project / ".gitignore").read_text(encoding="utf-8")
        self.assertEqual(gitignore.count(install.GITIGNORE_LINE), 1)
        self.assertEqual((self.project / "openspec/incidents.md").read_text(encoding="utf-8"), "# kept\n")


if __name__ == "__main__":
    unittest.main()
