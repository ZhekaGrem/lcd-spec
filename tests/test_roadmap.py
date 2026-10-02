"""Behaviour of roadmap.py - the index that answers "is this feature there, was this bug fixed"."""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "lcd-spec" / "scripts"))

import install  # noqa: E402
import roadmap  # noqa: E402

PROPOSAL = """## Why

Admins re-type prices from the supplier sheet by hand.

## What Changes

<!-- Describe what will change. -->
- **Import** supplier prices from a CSV upload
- Show the rows that failed

## Capabilities
"""


class Project(unittest.TestCase):
    """A project under git with an openspec directory, the layout the skill works in."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.outer = Path(self._tmp.name) / "work"
        self.root = self.outer / "shop"
        self.openspec = self.root / "openspec"
        (self.openspec / "changes").mkdir(parents=True)
        # the temp directory may sit inside someone's repository (a home directory under git)
        ceiling = mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": self._tmp.name})
        ceiling.start()
        self.addCleanup(ceiling.stop)
        self.clock = 0

    def git(self, *args, cwd=None, env=None):
        return subprocess.run(
            ["git", "-C", str(cwd or self.root), "-c", "user.name=t", "-c", "user.email=t@example.com",
             "-c", "commit.gpgsign=false", *args],
            check=True, capture_output=True, text=True, encoding="utf-8",
            env={**os.environ, **(env or {})}).stdout

    def commit(self, subject, day, path="app.py", cwd=None):
        """One commit on 2026-09-<day> that changes `path`; returns its short hash."""
        self.clock += 1
        target = (cwd or self.root) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"change {self.clock}\n", encoding="utf-8")
        stamp = f"2026-09-{day:02d}T12:00:{self.clock:02d}"
        self.git("add", "-A", cwd=cwd)
        self.git("commit", "-q", "-m", subject, cwd=cwd,
                 env={"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp})
        return self.git("rev-parse", "--short", "HEAD", cwd=cwd).strip()

    def change(self, name, archived_on=None, proposal=PROPOSAL, capabilities=(), tasks=None):
        parent = self.openspec / "changes" / ("archive" if archived_on else "")
        directory = parent / (f"{archived_on}-{name}" if archived_on else name)
        directory.mkdir(parents=True)
        if proposal is not None:
            (directory / "proposal.md").write_text(proposal, encoding="utf-8")
        for capability in capabilities:
            (directory / "specs" / capability).mkdir(parents=True)
            (directory / "specs" / capability / "spec.md").write_text("## ADDED Requirements\n", encoding="utf-8")
        if tasks is not None:
            (directory / "tasks.md").write_text(tasks, encoding="utf-8")
        return directory

    def built(self):
        return roadmap.build(self.root)

    def section(self, title):
        """Lines of one '## <title>' section of the roadmap."""
        body = self.built().split(f"## {title}\n", 1)[1].split("\n## ", 1)[0]
        return [line for line in body.splitlines() if line.strip()]


class Commits(Project):
    def setUp(self):
        super().setUp()
        self.git("init", "-q")

    def test_feature_commit_is_listed_with_its_date_scope_text_and_hash(self):
        sha = self.commit("feat(shipment-notification): notify the customer when an order ships", 20)
        self.assertEqual(self.section("Features"), [
            f"- 2026-09-20 shipment-notification: notify the customer when an order ships ({sha})"])

    def test_fix_commit_is_listed_under_fixes_not_features(self):
        sha = self.commit("fix(cart): keep the discount when the quantity changes", 21)
        self.assertEqual(self.section("Fixes"),
                         [f"- 2026-09-21 cart: keep the discount when the quantity changes ({sha})"])
        self.assertEqual(self.section("Features"), ["- none yet"])

    def test_commit_without_a_scope_is_listed_by_its_text(self):
        sha = self.commit("fix: stop the export from timing out", 22)
        self.assertEqual(self.section("Fixes"), [f"- 2026-09-22 stop the export from timing out ({sha})"])

    def test_breaking_change_is_marked(self):
        sha = self.commit("feat(api)!: drop the v1 order endpoints", 23)
        self.assertEqual(self.section("Features"),
                         [f"- 2026-09-23 api: drop the v1 order endpoints (BREAKING) ({sha})"])

    def test_commits_that_are_neither_features_nor_fixes_are_left_out(self):
        for subject in ("chore: bump dependencies", "docs: explain the export", "refactor(cart): split the service",
                        "Modify swearing examples in README.md", "fixture: add sample orders"):
            self.commit(subject, 10)
        self.assertEqual(self.section("Features") + self.section("Fixes"), ["- none yet", "- none yet"])

    def test_newest_commit_comes_first(self):
        self.commit("feat: first", 1)
        self.commit("feat: second", 2)
        self.assertEqual([line.split(" ")[2] for line in self.section("Features")], ["second", "first"])

    def test_only_the_subject_line_of_a_commit_is_used(self):
        self.commit("feat: export orders\n\nfix: this line is body text, not a fix", 5)
        self.assertEqual(self.section("Fixes"), ["- none yet"])

    def test_project_without_git_history_still_gets_a_roadmap(self):
        self.assertEqual(self.section("Features"), ["- none yet"])


class ProjectInsideALargerRepository(Project):
    def test_commits_that_touch_only_other_directories_are_not_this_projects(self):
        self.git("init", "-q", cwd=self.outer)
        self.commit("feat: something in another project", 3, path="elsewhere/x.py", cwd=self.outer)
        mine = self.commit("feat: export orders", 4, path="shop/app.py", cwd=self.outer)
        self.assertEqual(self.section("Features"), [f"- 2026-09-04 export orders ({mine})"])


class Changes(Project):
    def test_archived_change_is_listed_with_date_capabilities_summary_and_where_it_lives(self):
        self.change("import-supplier-prices", "2026-09-24", capabilities=("price-import", "admin-pricing"))
        self.assertEqual(self.section("Archived changes"), [
            "- 2026-09-24 import-supplier-prices [admin-pricing, price-import] - "
            "Import supplier prices from a CSV upload "
            "→ changes/archive/2026-09-24-import-supplier-prices/"])

    def test_newest_archived_change_comes_first(self):
        self.change("add-cart", "2026-08-01")
        self.change("add-export", "2026-09-01")
        self.assertEqual([line.split(" ")[2] for line in self.section("Archived changes")],
                         ["add-export", "add-cart"])

    def test_change_without_what_changes_falls_back_to_its_why(self):
        self.change("add-cart", "2026-08-01", proposal="## Why\n\nCustomers cannot buy two items at once.\n")
        self.assertIn("- Customers cannot buy two items at once. →", self.section("Archived changes")[0])

    def test_change_without_a_proposal_is_listed_by_name(self):
        self.change("add-cart", "2026-08-01", proposal=None)
        self.assertEqual(self.section("Archived changes"),
                         ["- 2026-08-01 add-cart → changes/archive/2026-08-01-add-cart/"])

    def test_proposal_saved_with_a_byte_order_mark_is_still_read(self):
        # Windows editors and PowerShell's utf8 put a BOM in front of the first heading
        self.change("add-cart", "2026-08-01", proposal="﻿## What Changes\n\n- Cart for several items\n")
        self.assertIn("add-cart - Cart for several items →", self.section("Archived changes")[0])

    def test_long_summary_is_cut(self):
        self.change("add-cart", "2026-08-01", proposal="## What Changes\n\n- " + "word " * 60 + "\n")
        self.assertLess(len(self.section("Archived changes")[0]), 200)

    def test_open_change_is_in_progress_with_its_task_count(self):
        self.change("add-export", capabilities=("order-export",),
                    tasks="## 1. Export\n\n- [x] 1.1 Exporter\n- [ ] 1.2 Endpoint\n- [ ] 1.3 Docs\n")
        self.assertEqual(self.section("In progress"), [
            "- add-export [order-export] - Import supplier prices from a CSV upload (1/3 tasks)"])

    def test_open_change_without_tasks_has_no_plan_yet(self):
        self.change("add-export")
        self.assertTrue(self.section("In progress")[0].endswith("(no plan yet)"))

    def test_the_archive_directory_is_not_an_open_change(self):
        self.change("add-cart", "2026-08-01")
        self.assertEqual(self.section("In progress"), ["- none yet"])

    def test_archived_change_is_not_in_progress_and_open_change_is_not_archived(self):
        self.change("add-cart", "2026-08-01")
        self.change("add-export")
        self.assertEqual(len(self.section("In progress")), 1)
        self.assertEqual(len(self.section("Archived changes")), 1)


class Planned(Project):
    """The only hand-written part: ideas that have no change yet."""

    def test_new_roadmap_has_an_empty_planned_section_to_fill_in(self):
        self.assertIn("## Planned\n", self.built())

    def test_hand_written_plans_survive_regeneration(self):
        path = roadmap.write(self.root)
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("## Planned\n", "## Planned\n\n- bulk price import from XLSX\n- loyalty points\n"),
                        encoding="utf-8")
        self.change("add-export")
        again = roadmap.write(self.root).read_text(encoding="utf-8")
        self.assertIn("- bulk price import from XLSX\n- loyalty points\n", again)
        self.assertIn("- add-export", again)

    def test_planned_lines_are_not_duplicated_by_repeated_runs(self):
        path = roadmap.write(self.root)
        path.write_text(path.read_text(encoding="utf-8").replace("## Planned\n", "## Planned\n\n- loyalty points\n"),
                        encoding="utf-8")
        roadmap.write(self.root)
        self.assertEqual(roadmap.write(self.root).read_text(encoding="utf-8").count("- loyalty points"), 1)


class Write(Project):
    def test_roadmap_is_written_into_the_openspec_directory(self):
        self.assertEqual(roadmap.write(self.root), self.openspec / "roadmap.md")

    def test_running_again_with_nothing_new_leaves_the_file_byte_identical(self):
        self.git("init", "-q")
        self.commit("feat: export orders", 4)
        self.change("add-cart", "2026-08-01")
        first = roadmap.write(self.root).read_bytes()
        self.assertEqual(roadmap.write(self.root).read_bytes(), first)

    def test_file_says_it_is_an_index_to_search_not_to_read_through(self):
        self.assertIn("search it", self.built().lower())

    def test_ukrainian_text_is_written_as_utf8(self):
        self.change("add-cart", "2026-08-01", proposal="## What Changes\n\n- Кошик на кілька товарів\n")
        self.assertIn("Кошик на кілька товарів", roadmap.write(self.root).read_bytes().decode("utf-8"))


class CommandLine(Project):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = roadmap.main(list(args))
        return code, out.getvalue().strip(), err.getvalue()

    def test_writes_the_roadmap_and_prints_its_path(self):
        code, out, _ = self.run_cli(str(self.root))
        self.assertEqual((code, out), (0, str(self.openspec / "roadmap.md")))
        self.assertTrue((self.openspec / "roadmap.md").is_file())

    def test_project_without_openspec_is_an_error(self):
        code, out, err = self.run_cli(str(self.outer))
        self.assertEqual((code, out), (3, ""))
        self.assertIn("openspec", err)

    def test_no_argument_is_a_usage_error(self):
        self.assertEqual(self.run_cli()[0], 2)


class InstalledWithTheSchema(Project):
    def test_install_writes_the_first_roadmap(self):
        (self.openspec / "config.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
        self.change("add-cart", "2026-08-01")
        install.install(self.root)
        self.assertIn("add-cart", (self.openspec / "roadmap.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
