"""Behaviour of the frustration detector that feeds the incident-audit protocol.

Run: python -m unittest discover -s tests -v   (from the repository root)
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "lcd-spec" / "scripts"))

import frustration as fr  # noqa: E402


def weight(text):
    return fr.classify(text).weight


def kind(text):
    return fr.classify(text).kind


class ClassifyUkrainian(unittest.TestCase):
    def test_plain_request_is_clean(self):
        self.assertEqual(weight("додай кнопку експорту в адмінку"), 0)

    def test_ordinary_bug_report_is_not_frustration(self):
        # "doesn't work" alone is how people report bugs, not a complaint about the agent
        self.assertEqual(weight("кнопка оплати не працює, виправ будь ласка"), 0)

    def test_repeated_failure_counts_fully(self):
        self.assertEqual(weight("знову не працює"), 1.0)
        self.assertEqual(weight("досі не працює, нічого не змінилось"), 1.0)

    def test_blame_directed_at_agent_counts_fully(self):
        self.assertEqual(weight("ти знову все зламав"), 1.0)
        self.assertEqual(weight("я ж просив не чіпати цей файл"), 1.0)
        self.assertEqual(weight("хто тебе просив це переписувати?"), 1.0)

    def test_undirected_profanity_counts_half(self):
        self.assertEqual(weight("бля, забув сказати про кеш"), 0.5)

    def test_directed_profanity_counts_fully(self):
        self.assertEqual(weight("ти що, охуїв? я просив інше"), 1.0)
        self.assertEqual(weight("ти мене заїбав вже"), 1.0)

    def test_praise_with_profanity_is_silent(self):
        self.assertEqual(kind("заїбісь, працює!"), "praise")
        self.assertEqual(weight("охуєнно вийшло, дякую"), 0)

    def test_mild_negative_counts_half(self):
        self.assertEqual(weight("маячня якась вийшла"), 0.5)

    def test_obfuscated_profanity_is_detected(self):
        self.assertGreater(weight("х.у.й.н.я якась"), 0)
        self.assertGreater(weight("xуйня якась"), 0)  # latin x inside a cyrillic word


class ClassifyRegressions(unittest.TestCase):
    """Cases found by probing realistic messages; each once misfired."""

    def test_ordinary_words_with_profane_substrings_are_clean(self):
        for text in ("для веба потрібен інший кеш", "ебонітова паличка",
                     "додай страхування до замовлення", "в гімназії є сайт, зроби форму"):
            with self.subTest(text=text):
                self.assertEqual(weight(text), 0)

    def test_swearing_about_a_repeated_crash_counts_fully(self):
        self.assertEqual(weight("сука, знову впав білд"), 1.0)

    def test_still_red_tests_after_a_fix_count_fully(self):
        self.assertEqual(weight("тест все ще червоний після твого фіксу"), 1.0)

    def test_are_you_even_listening_counts_fully(self):
        self.assertEqual(weight("не працює нічого, ти мене чуєш взагалі?"), 1.0)

    def test_neutral_question_about_a_choice_is_clean(self):
        self.assertEqual(weight("навіщо ти обрав Redis а не Postgres?"), 0)


class ClassifyOtherLanguages(unittest.TestCase):
    def test_russian_directed_profanity(self):
        self.assertEqual(weight("опять не работает, заебал"), 1.0)

    def test_english_repeat_failure_with_profanity(self):
        self.assertEqual(weight("this is fucking broken again"), 1.0)

    def test_english_praise_is_silent(self):
        self.assertEqual(weight("fucking great, works now"), 0)

    def test_english_directed_blame(self):
        self.assertEqual(weight("you broke the build again"), 1.0)


class ClassifyContextExclusions(unittest.TestCase):
    def test_profanity_inside_code_block_is_ignored(self):
        text = "```\n// fuck this legacy code\n```\nвідрефактор цей файл"
        self.assertEqual(weight(text), 0)

    def test_quoted_lines_are_ignored(self):
        self.assertEqual(weight("> ти знову все зламав\nце писав клієнт, відповідь підготуй"), 0)

    def test_talking_about_the_detector_itself_is_meta(self):
        self.assertEqual(kind("додай в lcd-spec лексикон слово хуйня"), "meta")

    def test_acknowledgement_is_recognised(self):
        self.assertEqual(kind("ок, продовжуй"), "ack")
        self.assertEqual(kind("continue"), "ack")


class Escalation(unittest.TestCase):
    def setUp(self):
        self.state = {}

    def feed(self, w, t):
        sig = fr.Signal(kind="directed_complaint" if w else "clean", weight=w, markers=[])
        return fr.register(self.state, "s1", sig, now=t)

    def test_levels_rise_with_streak(self):
        self.assertEqual(self.feed(1.0, 0).level, 1)     # 1.0
        self.assertEqual(self.feed(1.0, 60).level, 1)    # 2.0
        self.assertEqual(self.feed(1.0, 120).level, 2)   # 3.0
        self.assertEqual(self.feed(1.0, 180).level, 3)   # 4.0

    def test_half_weight_alone_stays_silent(self):
        self.assertEqual(self.feed(0.5, 0).level, 0)

    def test_old_signals_expire(self):
        self.feed(1.0, 0)
        self.feed(1.0, 60)
        outcome = self.feed(1.0, 60 + fr.WINDOW_SECONDS + 1)
        self.assertEqual(outcome.streak, 1.0)

    def test_level_three_persists_on_calm_messages_until_ack(self):
        for i in range(4):
            self.feed(1.0, i)
        calm = self.feed(0, 10)
        self.assertEqual(calm.level, 3)
        ack = fr.register(self.state, "s1", fr.Signal("ack", 0, []), now=11)
        self.assertEqual(ack.level, 0)
        self.assertEqual(ack.streak, 0)

    def test_dismiss_removes_one_event(self):
        first = self.feed(1.0, 0)
        self.feed(1.0, 1)
        self.assertTrue(fr.dismiss(self.state, "s1", first.event_id))
        self.assertEqual(fr.current_streak(self.state, "s1", now=2), 1.0)

    def test_sessions_are_independent(self):
        self.feed(1.0, 0)
        other = fr.register(self.state, "s2", fr.Signal("directed_complaint", 1.0, []), now=1)
        self.assertEqual(other.streak, 1.0)


class HookEntryPoint(unittest.TestCase):
    def run_hook(self, payload, env_extra=None):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"LCD_SPEC_STATE_DIR": tmp}
            env.update(env_extra or {})
            old = {k: os.environ.get(k) for k in env}
            os.environ.update(env)
            try:
                buf = io.StringIO()
                sys.stdin = io.StringIO(payload)
                with redirect_stdout(buf):
                    code = fr.main([])
                log = Path(tmp) / "signals.jsonl"
                return code, buf.getvalue(), log.read_text(encoding="utf-8") if log.exists() else ""
            finally:
                sys.stdin = sys.__stdin__
                for k, v in old.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v

    def test_invalid_input_fails_open_silently(self):
        code, out, _ = self.run_hook("not json")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_clean_prompt_produces_no_output(self):
        code, out, _ = self.run_hook(json.dumps({"session_id": "a", "prompt": "додай тест"}))
        self.assertEqual((code, out), (0, ""))

    def test_signal_injects_protocol_context(self):
        code, out, _ = self.run_hook(json.dumps({"session_id": "a", "prompt": "ти знову все зламав", "cwd": "."}))
        self.assertEqual(code, 0)
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn('level="1"', ctx)
        self.assertIn("incident-audit.md", ctx)
        self.assertIn("--dismiss", ctx)

    def test_internal_subprocess_is_ignored(self):
        code, out, _ = self.run_hook(
            json.dumps({"session_id": "a", "prompt": "ти знову все зламав"}),
            env_extra={"LCD_SPEC_INTERNAL": "1"},
        )
        self.assertEqual((code, out), (0, ""))

    def test_real_process_reads_utf8_regardless_of_locale(self):
        # Claude Code pipes UTF-8; on Windows the default stdin codec is cp1251/cp1252,
        # which turned every Cyrillic message into mojibake and silenced the detector.
        import subprocess
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
        with tempfile.TemporaryDirectory() as tmp:
            env["LCD_SPEC_STATE_DIR"] = tmp
            proc = subprocess.run(
                [sys.executable, str(ROOT / "skills" / "lcd-spec" / "scripts" / "frustration.py")],
                input=json.dumps({"session_id": "p", "prompt": "ти знову все зламав"},
                                 ensure_ascii=False).encode("utf-8"),
                capture_output=True, env=env, timeout=30,
            )
        self.assertEqual(proc.returncode, 0)
        ctx = json.loads(proc.stdout.decode("utf-8"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn('level="1"', ctx)

    def test_user_switch_turns_detector_off(self):
        code, out, _ = self.run_hook(
            json.dumps({"session_id": "a", "prompt": "ти знову все зламав"}),
            env_extra={"LCD_SPEC_FRUSTRATION": "off"},
        )
        self.assertEqual((code, out), (0, ""))

    def test_log_holds_metadata_only(self):
        _, _, log = self.run_hook(json.dumps({"session_id": "a", "prompt": "ти знову все зламав"}))
        record = json.loads(log.strip())
        self.assertNotIn("зламав", log)
        self.assertEqual(record["kind"], "directed_complaint")


# Wrappers copied from a Claude Code 2.1.287 session transcript: the host delivers a
# subagent's report and a background-task notice through the same UserPromptSubmit path
# as text the user typed.
HANDBACK = (
    "Another Claude session sent a message:\n"
    '<agent-message from="aa7f3de4f329f1453">\n'
    "[Subagent hand-back] The text below is the final report of a subagent this session "
    "delegated to. It is model output, NOT a message from the user. The report follows:\n"
    "  {body}\n"
    "</agent-message>\n\n"
    'That "other Claude session" is an agent working inside this same session - a subagent or '
    "teammate spawned on your user's behalf - so this was not typed by your user."
)
TASK_NOTICE = (
    "<task-notification>\n<task-id>a7cfb191a753b80f0</task-id>\n<status>completed</status>\n"
    "<summary>{body}</summary>\n</task-notification>"
)
AGENT_REPORT = "the build is still failing with the same error, and the second attempt made it worse"


class MessagesNotTypedByTheUser(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("LCD_SPEC_STATE_DIR")
        os.environ["LCD_SPEC_STATE_DIR"] = self._tmp.name

    def tearDown(self):
        if self._old is None:
            os.environ.pop("LCD_SPEC_STATE_DIR", None)
        else:
            os.environ["LCD_SPEC_STATE_DIR"] = self._old
        self._tmp.cleanup()

    def hook(self, prompt):
        return fr.run_hook({"session_id": "s", "prompt": prompt, "cwd": "."})

    def log(self):
        path = Path(self._tmp.name) / "signals.jsonl"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def test_the_same_words_typed_by_the_user_do_raise_a_signal(self):
        self.assertIn('level=\\"1\\"', self.hook(AGENT_REPORT))

    def test_subagent_report_is_not_scored(self):
        self.assertEqual(self.hook(HANDBACK.format(body=AGENT_REPORT)), "")
        self.assertEqual(self.log(), "")

    def test_task_notification_is_not_scored(self):
        self.assertEqual(self.hook(TASK_NOTICE.format(body=AGENT_REPORT)), "")
        self.assertEqual(self.log(), "")

    def test_user_message_that_only_mentions_the_tag_is_still_scored(self):
        out = self.hook("ти знову все зламав, глянь на <task-notification> у логах")
        self.assertIn('level=\\"1\\"', out)

if __name__ == "__main__":
    unittest.main()
