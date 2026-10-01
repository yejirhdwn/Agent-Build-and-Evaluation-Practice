import importlib.util
import tempfile
import unittest
from pathlib import Path

from shell_policy import RestrictedShellBackend, check_command

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("run_scenarios", _ROOT / "eval" / "run_scenarios.py")
run_scenarios = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_scenarios)
from trace_metrics import compute_metrics, steps_from_messages  # noqa: E402  (run_scenarios 가 경로 추가)


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

    def test_file_tools_cannot_leave_workspace(self):
        with tempfile.TemporaryDirectory() as root:
            ws = Path(root) / "ws"
            ws.mkdir()
            secret = Path(root) / "answer.md"
            secret.write_text("SECRET", encoding="utf-8")
            backend = RestrictedShellBackend(root_dir=str(ws), virtual_mode=True)
            for path in ("/../answer.md", "../answer.md", str(secret)):
                with self.assertRaises(ValueError, msg=path):
                    backend.read(path)


class RunScenariosTest(unittest.TestCase):
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
        self.assertEqual(run_scenarios.final_answer(messages), "① 요약")
        metrics = compute_metrics(steps_from_messages(messages))
        self.assertEqual(metrics["eval_access_attempts"], 1)
        self.assertEqual(metrics["write_attempts"], 1)

    def test_sandbox_excludes_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness = run_scenarios.make_sandbox(_ROOT, Path(tmp))
            self.assertTrue((harness / "langchain-deepagents.py").is_file())
            self.assertTrue((harness / "mock_data" / "logs").is_dir())
            for leaked in ("eval", "runs", ".env", ".git"):
                self.assertFalse((harness / leaked).exists(), leaked)


class TraceMetricsTest(unittest.TestCase):
    def test_work_pattern_metrics(self):
        skill = {"type": "tool", "name": "read_file", "args": {"file_path": "/skills/log-trace/SKILL.md"}}
        bad = {"type": "tool", "name": "read_file", "args": {"file_path": "/x"}, "error": "Error: not found"}
        steps = [
            {"type": "llm", "input_tokens": 100, "output_tokens": 10, "latency_s": 1.0},
            {"type": "tool", "name": "write_todos", "args": {"todos": []}},
            skill, dict(skill), bad, dict(bad),
            {"type": "tool", "name": "execute", "args": {"command": "date"}},
            {"type": "tool", "name": "execute", "args": {"command": "rm -rf /"}},
        ]
        m = compute_metrics(steps, price=(1e-6, 2e-6))
        self.assertTrue(m["skill_read_first"])
        self.assertEqual(m["tool_calls"], 7)
        self.assertEqual(m["duplicate_calls"], 2)
        self.assertEqual(m["failed_tool_calls"], 2)
        self.assertEqual(m["failed_retries"], 1)
        self.assertEqual(m["write_attempts"], 1)
        self.assertEqual(m["total_tokens"], 110)
        self.assertAlmostEqual(m["cost_usd"], 0.00012)


if __name__ == "__main__":
    unittest.main()
