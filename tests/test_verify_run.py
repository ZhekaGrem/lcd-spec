"""Behaviour of verify_run.py - the test run a reviewer trusts instead of the implementer's report."""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "lcd-spec" / "scripts"))

import review_package  # noqa: E402
import verify_run  # noqa: E402

PY = f'"{Path(sys.executable).as_posix()}"'

PLAN = """# Export Implementation Plan

## Global Constraints
- UTF-8

## Verification
- `pytest -q` - the unit tests
- `ruff check .`

## File Structure
- exporter.py: builds the CSV

---

### Task 1.1: Add exporter

**Files:**
- Create: `exporter.py`

**Interfaces:**
- Produces: `export(rows) -> str`

**Verify:**
- `pytest tests/test_exporter.py -q`

**Step 1: Write the failing test**

Run: `pytest tests/test_exporter.py::test_missing -q` - expected: FAIL

### Task 1.2: Add endpoint

**Files:**
- Modify: `api.py`

**Interfaces:**
- Consumes: `export(rows) -> str`

**Step 1: Write the failing test**
"""


class Commands(unittest.TestCase):
    """Which commands get run is written in plan.md; nothing is guessed from the stack."""

    def of(self, plan, task_id=None):
        return verify_run.commands(plan, task_id)[0]

    def verification(self, body):
        return self.of(f"# Plan\n\n## Verification\n{body}\n## File Structure\n- a.py: x\n")

    def test_whole_change_runs_the_plans_verification_commands_in_order(self):
        self.assertEqual(self.of(PLAN), ["pytest -q", "ruff check ."])

    def test_words_after_the_command_are_a_note_not_part_of_it(self):
        self.assertEqual(self.verification("- `mvn -q test` - backend unit tests\n"), ["mvn -q test"])

    def test_list_item_without_backticks_is_the_command_itself(self):
        self.assertEqual(self.verification("- python -m unittest\n"), ["python -m unittest"])

    def test_every_line_of_a_fenced_block_is_a_command(self):
        self.assertEqual(self.verification("```bash\npnpm typecheck\n\npnpm test --run\n```\n"),
                         ["pnpm typecheck", "pnpm test --run"])

    def test_comment_line_in_a_fenced_block_is_not_a_command(self):
        self.assertEqual(self.verification("```\n# backend\nmvn -q test\n```\n"), ["mvn -q test"])

    def test_prose_around_the_list_is_not_a_command(self):
        self.assertEqual(self.verification("Run from the repo root:\n\n- `go test ./...`\n"), ["go test ./..."])

    def test_template_comment_is_not_a_command(self):
        self.assertEqual(self.verification("<!-- The commands that prove the whole change:\n- `fake` -->\n"), [])

    def test_task_runs_its_own_verify_block(self):
        self.assertEqual(self.of(PLAN, "1.1"), ["pytest tests/test_exporter.py -q"])

    def test_step_commands_expected_to_fail_are_never_picked_up(self):
        self.assertNotIn("pytest tests/test_exporter.py::test_missing -q", self.of(PLAN, "1.1"))

    def test_task_without_a_verify_block_runs_the_whole_verification(self):
        self.assertEqual(self.of(PLAN, "1.2"), ["pytest -q", "ruff check ."])

    def test_the_source_of_the_commands_is_named(self):
        self.assertIn("Task 1.1", verify_run.commands(PLAN, "1.1")[1])
        self.assertIn("Verification", verify_run.commands(PLAN, "1.2")[1])

    def test_verify_block_ends_where_the_next_block_begins(self):
        plan = PLAN.replace("**Verify:**\n- `pytest tests/test_exporter.py -q`\n",
                            "**Verify:**\n- `pytest tests/test_exporter.py -q`\n- `ruff check exporter.py`\n"
                            "**Notes:**\n- `not a command`\n")
        self.assertEqual(self.of(plan, "1.1"), ["pytest tests/test_exporter.py -q", "ruff check exporter.py"])

    def test_unknown_task_is_an_error(self):
        with self.assertRaises(LookupError):
            verify_run.commands(PLAN, "9.9")


def py(code):
    """A command that runs `code` with this interpreter, the same under sh, bash and cmd."""
    return f'{PY} -c "{code}"'


class Project(unittest.TestCase):
    """A project directory with one change in it, the layout the scripts expect."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.outer = Path(self._tmp.name) / "work"
        self.root = self.outer / "shop"
        self.change = self.root / "openspec" / "changes" / "add-export"
        self.change.mkdir(parents=True)
        # the temp directory may sit inside someone's repository (a home directory under
        # git): git must not climb out of the fixture and take that one for the project's
        ceiling = mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": self._tmp.name})
        ceiling.start()
        self.addCleanup(ceiling.stop)

    def plan(self, *whole, task=()):
        verify = "**Verify:**\n" + "".join(f"- `{c}`\n" for c in task) + "\n" if task else ""
        (self.change / "plan.md").write_text(
            "# Plan\n\n## Verification\n" + "".join(f"- `{c}`\n" for c in whole)
            + "\n## File Structure\n- a.py: x\n\n### Task 1.1: A\n\n**Files:**\n- Create: `a.py`\n\n"
            + verify + "**Step 1: test**\n", encoding="utf-8")

    def run_log(self, **kw):
        path, ok = verify_run.run(self.change, **kw)
        return path.read_text(encoding="utf-8"), ok


class Run(Project):
    def test_passing_command_is_recorded_with_its_output_and_exit_code(self):
        self.plan(py("print('all 14 tests passed')"))
        log, ok = self.run_log()
        self.assertTrue(ok)
        self.assertIn("Result: PASS", log)
        self.assertIn("- exit 0 ", log)
        self.assertIn("all 14 tests passed", log)

    def test_failing_command_is_recorded_with_its_real_exit_code(self):
        self.plan(py("import sys; print('1 failed'); sys.exit(3)"))
        log, ok = self.run_log()
        self.assertFalse(ok)
        self.assertIn("Result: FAIL", log)
        self.assertIn("- exit 3 ", log)
        self.assertIn("1 failed", log)

    def test_commands_after_a_failure_still_run(self):
        self.plan(py("import sys; sys.exit(1)"), py("print('lint ran too')"))
        log, ok = self.run_log()
        self.assertFalse(ok)
        self.assertIn("lint ran too", log)

    def test_one_failure_among_passing_commands_fails_the_run(self):
        self.plan(py("print('fine')"), py("import sys; sys.exit(1)"), py("print('fine')"))
        self.assertIn("Result: FAIL", self.run_log()[0])

    def test_error_output_is_kept_with_the_rest(self):
        self.plan(py("import sys; sys.stderr.write('AssertionError: boom')"))
        self.assertIn("AssertionError: boom", self.run_log()[0])

    def test_commands_run_from_the_project_root(self):
        (self.root / "marker.txt").write_text("found the root", encoding="utf-8")
        self.plan(py("print(open('marker.txt').read())"))
        self.assertIn("found the root", self.run_log()[0])

    def test_shell_syntax_of_the_plan_works_on_every_platform(self):
        # plans are written the way the agent types commands: POSIX shell, also on Windows
        self.plan("test -n x && echo posix-shell-ok")
        log, ok = self.run_log()
        self.assertTrue(ok, log)
        self.assertIn("posix-shell-ok", log)

    def test_long_output_keeps_its_end_and_says_how_much_was_cut(self):
        self.plan(py("for i in range(50): print('line', i)"))
        log, _ = self.run_log(tail=5)
        self.assertIn("line 49", log)
        self.assertIn("line 45", log)
        self.assertNotIn("line 44", log)
        self.assertIn("45 earlier lines omitted", log)

    def test_command_that_never_ends_is_stopped_and_counts_as_failed(self):
        self.plan(py("import time; print('started', flush=True); time.sleep(60)"))
        started = time.monotonic()
        log, ok = self.run_log(timeout=2)
        self.assertLess(time.monotonic() - started, 30)
        self.assertFalse(ok)
        self.assertIn("timed out after 2s", log)
        self.assertIn("started", log)

    def test_output_that_is_not_utf8_does_not_break_the_run(self):
        self.plan(py("import sys; sys.stdout.buffer.write(bytes([255, 254]) + b' still here')"))
        log, ok = self.run_log()
        self.assertTrue(ok)
        self.assertIn("still here", log)

    def test_code_fence_in_the_output_cannot_close_the_log_block(self):
        self.plan(py("print(chr(96) * 3); print('after the fence')"))
        self.assertIn("````", self.run_log()[0])

    def test_whole_change_run_is_kept_next_to_the_other_artifacts(self):
        self.plan(py("print('ok')"))
        path, _ = verify_run.run(self.change)
        self.assertEqual(path, self.change / "verification.md")

    def test_task_run_goes_to_the_scratch_directory_under_its_label(self):
        self.plan(py("print('whole')"), task=[py("print('only the task')")])
        path, _ = verify_run.run(self.change, task_id="1.1")
        self.assertEqual(path, self.change / ".work" / "verify-task-1.1.md")
        log = path.read_text(encoding="utf-8")
        self.assertIn("only the task", log)
        self.assertNotIn("whole", log)

    def test_fix_round_keeps_its_own_log(self):
        self.plan(py("print('ok')"))
        path, _ = verify_run.run(self.change, task_id="1.1", label="task-1.1-fix1")
        self.assertEqual(path.name, "verify-task-1.1-fix1.md")

    def test_log_says_where_the_commands_came_from(self):
        self.plan(py("print('ok')"))
        self.assertIn("Task 1.1 has no 'Verify' block", self.run_log(task_id="1.1")[0])

    def test_plan_without_commands_is_an_error_not_a_pass(self):
        self.plan()
        with self.assertRaises(LookupError):
            verify_run.run(self.change)
        self.assertFalse((self.change / "verification.md").exists())

    def test_change_without_a_plan_is_an_error(self):
        with self.assertRaises(OSError):
            verify_run.run(self.change)


class CommandLine(Project):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = verify_run.main([str(self.change), *args])
        return code, out.getvalue().strip(), err.getvalue()

    def test_green_run_exits_zero_and_prints_the_log_path(self):
        self.plan(py("print('ok')"))
        code, out, _ = self.run_cli()
        self.assertEqual((code, out), (0, str(self.change / "verification.md")))

    def test_failed_command_exits_one_and_still_prints_the_log_path(self):
        self.plan(py("import sys; sys.exit(1)"))
        code, out, _ = self.run_cli()
        self.assertEqual((code, out), (1, str(self.change / "verification.md")))

    def test_task_id_and_label_choose_the_commands_and_the_file(self):
        self.plan(py("print('whole')"), task=[py("print('task')")])
        code, out, _ = self.run_cli("1.1", "--label", "task-1.1-fix2")
        self.assertEqual(code, 0)
        self.assertEqual(Path(out), self.change / ".work" / "verify-task-1.1-fix2.md")
        self.assertIn("task", Path(out).read_text(encoding="utf-8"))

    def test_timeout_and_tail_are_taken_from_the_command_line(self):
        self.plan(py("import time; [print('row', i, flush=True) for i in range(3)]; time.sleep(60)"))
        code, out, _ = self.run_cli("--timeout", "2", "--tail", "1")
        log = Path(out).read_text(encoding="utf-8")
        self.assertEqual(code, 1)
        self.assertIn("timed out after 2s", log)
        self.assertIn("row 2", log)
        self.assertNotIn("row 0", log)

    def test_change_without_a_plan_exits_three_with_the_reason(self):
        code, out, err = self.run_cli()
        self.assertEqual((code, out), (3, ""))
        self.assertIn("plan.md", err)

    def test_plan_without_commands_exits_three_with_the_reason(self):
        self.plan()
        code, _, err = self.run_cli()
        self.assertEqual(code, 3)
        self.assertIn("no commands", err)

    def test_unknown_task_exits_three_with_the_reason(self):
        self.plan(py("print('ok')"))
        code, _, err = self.run_cli("9.9")
        self.assertEqual(code, 3)
        self.assertIn("9.9", err)

    def test_missing_change_directory_argument_is_a_usage_error(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = verify_run.main([])
        self.assertEqual((code, out.getvalue()), (2, ""))


class GitProject(Project):
    """The same project under git, with one commit and a passing whole-change command."""

    def setUp(self):
        super().setUp()
        self.git("init", "-q")
        (self.root / ".gitignore").write_text("build/\nopenspec/changes/**/.work/\n", encoding="utf-8")
        (self.root / "app.py").write_text("print('v1')\n", encoding="utf-8")
        self.plan(py("print('ok')"))
        self.commit("init")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@example.com",
             "-c", "commit.gpgsign=false", *args],
            check=True, capture_output=True, text=True, encoding="utf-8").stdout

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def problems(self, label="final"):
        return " | ".join(verify_run.problems(self.change, label))


class Freshness(GitProject):
    """A run counts only while the code it ran against is the code that is there now."""

    def test_change_that_was_never_run_is_a_problem(self):
        problems = self.problems()
        self.assertIn("verification.md", problems)
        self.assertIn("verify_run.py", problems)

    def test_green_run_on_unchanged_code_has_no_problems(self):
        verify_run.run(self.change)
        self.assertEqual(self.problems(), "")

    def test_failed_command_is_named_with_its_exit_code(self):
        self.plan(py("print('ok')"), "exit 7")
        verify_run.run(self.change)
        problems = self.problems()
        self.assertIn("exit 7", problems)
        self.assertNotIn("print('ok')", problems)

    def test_timed_out_command_is_a_problem(self):
        self.plan(py("import time; time.sleep(60)"))
        verify_run.run(self.change, timeout=1)
        self.assertIn("timed out", self.problems())

    def test_code_edited_after_the_run_makes_it_stale(self):
        verify_run.run(self.change)
        (self.root / "app.py").write_text("print('v2')\n", encoding="utf-8")
        self.assertIn("stale", self.problems())

    def test_file_added_after_the_run_makes_it_stale(self):
        verify_run.run(self.change)
        (self.root / "helper.py").write_text("x = 1\n", encoding="utf-8")
        self.assertIn("stale", self.problems())

    def test_file_deleted_after_the_run_makes_it_stale(self):
        verify_run.run(self.change)
        (self.root / "app.py").unlink()
        self.assertIn("stale", self.problems())

    def test_committing_the_code_that_was_tested_keeps_the_run_fresh(self):
        (self.root / "app.py").write_text("print('v2')\n", encoding="utf-8")
        verify_run.run(self.change)
        self.commit("feat: v2")
        self.assertEqual(self.problems(), "")

    def test_ticking_tasks_and_writing_the_ledger_keeps_the_run_fresh(self):
        verify_run.run(self.change)
        (self.change / "tasks.md").write_text("- [x] 1.1 A\n", encoding="utf-8")
        (self.change / "ledger.md").write_text("Task 1.1: complete\n", encoding="utf-8")
        (self.root / "openspec" / "incidents.md").write_text("# Incidents\n", encoding="utf-8")
        self.assertEqual(self.problems(), "")

    def test_ignored_build_output_keeps_the_run_fresh(self):
        verify_run.run(self.change)
        (self.root / "build").mkdir()
        (self.root / "build" / "out.bin").write_bytes(b"\0\1")
        self.assertEqual(self.problems(), "")

    def test_file_the_commands_generate_is_part_of_what_was_tested(self):
        self.plan(py("open('report.txt', 'w').write('generated')"))
        verify_run.run(self.change)
        self.assertEqual(self.problems(), "")

    def test_task_run_is_looked_up_under_its_label(self):
        self.assertIn("verify-task-1.1.md", self.problems("task-1.1"))
        verify_run.run(self.change, task_id="1.1")
        self.assertEqual(self.problems("task-1.1"), "")

    def test_checking_writes_nothing_into_the_repository(self):
        (self.root / "helper.py").write_text("x = 1\n", encoding="utf-8")
        before = self.git("count-objects", "-v")
        verify_run.run(self.change)
        verify_run.problems(self.change)
        self.assertIn("?? helper.py", self.git("status", "--porcelain"))
        self.assertEqual(self.git("count-objects", "-v"), before)


class ReviewPackage(GitProject):
    """The reviewer reads one file: the diff and the run that was made against it."""

    def setUp(self):
        super().setUp()
        self.plan(py("print('-'.join(['suite', 'green']))"))
        self.commit("docs: plan")
        self.base = self.git("rev-parse", "HEAD").strip()
        (self.root / "app.py").write_text("print('v2')\n", encoding="utf-8")
        self.commit("feat: v2")

    def package(self, label="task-1.1"):
        return review_package.write_package(self.change, self.base, "HEAD", label).read_text(encoding="utf-8")

    def test_package_carries_the_run_made_for_its_task(self):
        verify_run.run(self.change, task_id="1.1")
        text = self.package()
        self.assertIn("Status: PASS", text)
        self.assertIn("suite-green", text)
        self.assertLess(text.index("## Independent run"), text.index("## Diff"))

    def test_package_without_a_run_says_the_commands_were_not_run(self):
        text = self.package()
        self.assertIn("Status: FAIL", text)
        self.assertIn("verify-task-1.1.md missing", text)

    def test_package_built_after_the_code_moved_on_says_the_run_is_stale(self):
        verify_run.run(self.change, task_id="1.1")
        (self.root / "app.py").write_text("print('v3')\n", encoding="utf-8")
        text = self.package()
        self.assertIn("Status: FAIL", text)
        self.assertIn("stale", text)

    def test_package_shows_a_failed_run_as_failed_with_its_output(self):
        self.plan(py("import sys; print('-'.join(['two', 'broken'])); sys.exit(1)"))
        verify_run.run(self.change, task_id="1.1")
        text = self.package()
        self.assertIn("Status: FAIL", text)
        self.assertIn("exit 1", text)
        self.assertIn("two-broken", text)

    def test_fix_round_package_carries_the_run_of_that_round(self):
        verify_run.run(self.change, task_id="1.1")
        self.assertIn("verify-task-1.1-fix1.md missing", self.package("task-1.1-fix1"))
        verify_run.run(self.change, task_id="1.1", label="task-1.1-fix1")
        self.assertIn("Status: PASS", self.package("task-1.1-fix1"))

    def test_whole_branch_package_carries_the_whole_change_run(self):
        self.assertIn("verification.md missing", self.package("final"))
        verify_run.run(self.change)
        text = self.package("final")
        self.assertIn("Status: PASS", text)
        self.assertIn("suite-green", text)

    def test_the_diff_is_still_in_the_package(self):
        text = self.package()
        self.assertIn("+print('v2')", text)
        self.assertIn("feat: v2", text)


class FreshnessWithoutGit(Project):
    def test_run_outside_a_git_repository_cannot_be_called_fresh(self):
        self.plan(py("print('ok')"))
        _, ok = verify_run.run(self.change)
        self.assertTrue(ok)
        self.assertIn("git", " | ".join(verify_run.problems(self.change)))


class ProjectInsideALargerRepository(Project):
    """A project that is a subdirectory of a repository: only the project's own files count.

    Found the hard way: with a home directory under git, the check walked the whole of it.
    """

    def setUp(self):
        super().setUp()
        subprocess.run(["git", "-C", str(self.outer), "init", "-q"], check=True, capture_output=True)
        (self.outer / "elsewhere").mkdir()
        (self.outer / "elsewhere" / "notes.txt").write_text("v1", encoding="utf-8")
        (self.root / "app.py").write_text("print('v1')\n", encoding="utf-8")
        self.plan(py("print('ok')"))
        verify_run.run(self.change)

    def test_file_outside_the_project_does_not_make_the_run_stale(self):
        (self.outer / "elsewhere" / "notes.txt").write_text("v2", encoding="utf-8")
        self.assertEqual(verify_run.problems(self.change), [])

    def test_file_inside_the_project_still_does(self):
        (self.root / "app.py").write_text("print('v2')\n", encoding="utf-8")
        self.assertIn("stale", " | ".join(verify_run.problems(self.change)))


if __name__ == "__main__":
    unittest.main()
