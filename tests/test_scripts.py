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
