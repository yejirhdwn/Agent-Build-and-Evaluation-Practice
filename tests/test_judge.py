import importlib.util
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("judge", _ROOT / "eval" / "judge.py")
judge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(judge)


def _scores(**failed):
    """시나리오별 실패 항목만 지정해 Judge 결과 모양을 만든다."""
    out = {}
    for sid in ("S1", "S2"):
        out[sid] = {k: {"passed": k not in failed.get(sid, ()), "evidence": "", "reason": ""} for k, _ in judge.ITEMS}
        out[sid].update(must_mention=[], overall_score=4, overall_reason="")
    return out


class PairwiseTest(unittest.TestCase):
    def _run(self, first, second):
        answers = iter([{"winner": first, "reason": ""}, {"winner": second, "reason": ""}])
        original = judge.pairwise_once
        judge.pairwise_once = lambda *a: next(answers)
        try:
            return judge.pairwise("S1", "a", "b")["final"]
        finally:
            judge.pairwise_once = original

    def test_consistent_win_survives_swap(self):
        # 두 번째 판정은 순서를 바꿨으므로 'A' 가 원래 B 를 뜻한다.
        self.assertEqual(self._run("B", "A"), "B")

    def test_position_bias_becomes_tie(self):
        self.assertEqual(self._run("A", "A"), "tie")
        self.assertEqual(self._run("B", "tie"), "tie")


class DecideTest(unittest.TestCase):
    def test_default_is_tie_without_decisive_change(self):
        self.assertEqual(judge.decide(_scores(), _scores(), {})["verdict"], "tie")

    def test_improvement_without_regression_wins(self):
        a = _scores(S1=("impact_scope",))
        self.assertEqual(judge.decide(a, _scores(), {})["verdict"], "B")

    def test_mixed_improvement_and_regression_is_tie(self):
        a = _scores(S1=("impact_scope",))
        b = _scores(S2=("trap_handling",))
        self.assertEqual(judge.decide(a, b, {})["verdict"], "tie")

    def test_pairwise_loss_blocks_win(self):
        a = _scores(S1=("impact_scope",))
        self.assertEqual(judge.decide(a, _scores(), {"S2": {"final": "A"}})["verdict"], "tie")


if __name__ == "__main__":
    unittest.main()
