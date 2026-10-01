import importlib.util
import tempfile
import unittest
from pathlib import Path

from shell_policy import RestrictedShellBackend, check_command

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("run_eval", _ROOT / "scripts" / "run_eval.py")
run_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_eval)


class ShellPolicyTest(unittest.TestCase):
    def test_date_commands_are_allowed(self):
        for command in ("date", "TZ=Asia/Seoul date +%Y%m%d-%H%M%S", "date -u", "date -Iseconds"):
            self.assertIsNone(check_command(command, allow_meta_harness=False), command)

    def test_answer_key_reads_are_blocked(self):
        for command in (
            "cat ../eval/answer_keys/S1.md",
            "date; cat ../eval/answer_keys/S1.md",
            "date && cat ../eval/answer_keys/S1.md",
            "date $(cat ../eval/answer_keys/S1.md)",
            "date `cat ../eval/answer_keys/S1.md`",
            "date -f ../eval/answer_keys/S1.md",
            "date -r ../eval/answer_keys/S1.md",
            "date > /tmp/x",
            "python -c 'print(open(\"../eval/answer_keys/S1.md\").read())'",
            "ls ..",
        ):
            self.assertIsNotNone(check_command(command, allow_meta_harness=True), command)

    def test_meta_harness_requires_opt_in(self):
        command = "python skills/meta-harness/metaharness.py run --variant baseline --query-file meta/queryA.txt"
        self.assertIsNotNone(check_command(command, allow_meta_harness=False))
        self.assertIsNone(check_command(command, allow_meta_harness=True))
        self.assertIsNotNone(check_command("python other.py", allow_meta_harness=True))

    def test_backend_refuses_without_running(self):
        with tempfile.TemporaryDirectory() as root:
            backend = RestrictedShellBackend(root_dir=root, virtual_mode=True)
            result = backend.execute("cat ../eval/answer_keys/S1.md")
            self.assertEqual(result.exit_code, 126)
            self.assertIn("거부됨", result.output)


class RunEvalTest(unittest.TestCase):
    def test_final_answer_and_suspicious_calls(self):
        messages = [
            {"type": "human", "content": "질문"},
            {"type": "ai", "content": "", "tool_calls": [
                {"name": "read_file", "args": {"file_path": "/input/logs/a.log"}},
                {"name": "execute", "args": {"command": "cat ../eval/answer_keys/S1.md"}},
            ]},
            {"type": "tool", "content": "..."},
            {"type": "ai", "content": [{"type": "text", "text": "① 요약"}]},
        ]
        self.assertEqual(run_eval.final_answer(messages), "① 요약")
        calls = run_eval.tool_calls(messages)
        self.assertEqual([c["suspicious"] for c in calls], [False, True])


if __name__ == "__main__":
    unittest.main()
