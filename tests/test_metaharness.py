import argparse
import importlib.util
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "metaharness", _ROOT / "workspace_seed" / "skills" / "meta-harness" / "metaharness.py")
mh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mh)


def _edit_args(home, file, find, replace, **kw):
    base = dict(home=home, variant="v1", file=file, find=find, find_file=None, replace=replace,
                replace_file=None, delete=False, count=1, force=False, allow_specific=False)
    base.update(kw)
    return argparse.Namespace(**base)


class MetaHarnessGuardTest(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        os.chdir(_ROOT)
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        vp = Path(self.home) / "variants" / "v1"
        (vp / "workspace_seed" / "skills" / "log-trace").mkdir(parents=True)
        (vp / "workspace_seed" / "skills" / "log-trace" / "SKILL.md").write_text(
            "\n".join(f"규칙 {i}" for i in range(20)) + "\n", encoding="utf-8")
        (vp / "shell_policy.py").write_text("ALLOW = 'date'\n", encoding="utf-8")

    def tearDown(self):
        os.chdir(self._cwd)
        self.tmp.cleanup()

    def _fails(self, fn, args):
        with redirect_stderr(io.StringIO()) as err, redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                fn(args)
        return err.getvalue()

    def test_edit_rejects_non_knob_file(self):
        msg = self._fails(mh.cmd_edit, _edit_args(self.home, "shell_policy.py", "'date'", "'cat'"))
        self.assertIn("노브", msg)

    def test_edit_rejects_scenario_specific_text(self):
        skill = "workspace_seed/skills/log-trace/SKILL.md"
        for text in ("20260923CMP001 를 확인", "B04_CHNL_SEND.log:53 을 본다", "182,400건이면 지연"):
            msg = self._fails(mh.cmd_edit, _edit_args(self.home, skill, "규칙 3", f"규칙 3\n{text}"))
            self.assertIn("과적합", msg)

    def test_edit_allows_general_principle(self):
        skill = "workspace_seed/skills/log-trace/SKILL.md"
        with redirect_stdout(io.StringIO()):
            mh.cmd_edit(_edit_args(self.home, skill, "규칙 3",
                                   "규칙 3\n- 영향 범위는 같은 원인이 닿는 다른 날짜·캠페인을 조회로 확인한다."))
        text = (Path(self.home) / "variants" / "v1" / skill).read_text(encoding="utf-8")
        self.assertIn("영향 범위는", text)

    def test_input_files_cannot_be_answer_keys(self):
        for path in ("eval/answer_keys/S1.md", "../outside.txt"):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                mh.safe_input_file(path)

    def test_show_cannot_escape_run_folder(self):
        run = Path(self.home) / "runs" / "v1"
        run.mkdir(parents=True)
        args = argparse.Namespace(home=self.home, variant="v1", what="../../../../eval/answer_keys/S1.md",
                                  suite=False, scenario=None, rep=None)
        self._fails(mh.cmd_show, args)


if __name__ == "__main__":
    unittest.main()
