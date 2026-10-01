"""LLM-as-a-Judge 채점 (S1~S4).

- 항목별 True/False(형태 b): test-guide 판정표의 9개 항목, 판정마다 보고서 인용 근거와 이유
- 종합 점수(형태 a): 1~5점과 이유
- Pairwise(형태 c): 같은 시나리오의 두 보고서를 A/B 순서를 바꿔 두 번 비교, 엇갈리면 무승부

정답(answer_key)과 판정 기준(rubric.md)은 Judge 프롬프트에만 들어간다. 에이전트 실행 샌드박스에는
eval/ 이 복사되지 않는다. Judge 는 temperature 0 으로 쓰고(가능하면 JUDGE_MODEL_NAME 으로 에이전트와 다른
모델), 출력은 JSON 스키마(structured output)로 받는다.

LangSmith 키가 있으면 Dataset ``log-trace-eval-s1-s4`` 를 갱신하고 ``evaluate()`` 로 Experiment
(``<variant>-<run_set>``)를 남긴다. 원래 에이전트 trace 에도 판정 결과를 feedback 으로 붙인다.

사용법(저장소 루트):
  uv run python eval/judge.py sync-dataset
  uv run python eval/judge.py score runs/<run_set>/baseline
  uv run python eval/judge.py compare --a runs/<A>/baseline --b runs/<B>/v1 [--b runs/<C>/v1 ...]
  uv run python eval/judge.py human-template runs/<run_set>/baseline
  uv run python eval/judge.py agree runs/<run_set>/baseline
  uv run python eval/judge.py summary runs/<run_set>/v1 --redact     # 개선 에이전트용(정답 비노출)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EVAL))

import dotenv  # noqa: E402

dotenv.load_dotenv(ROOT / ".env")

from observability import configure_tracing, project_name  # noqa: E402
from trace_metrics import TABLE_COLUMNS, _cell, metrics_table  # noqa: E402

DATASET_NAME = "log-trace-eval-s1-s4"
ANSWER_KEYS = EVAL / "answer_keys"
RUBRIC = EVAL / "rubric.md"
SCENARIOS = EVAL / "scenarios.json"
JUDGE_VERSION = "1"

ITEMS: list[tuple[str, str]] = [
    ("problem_point", "문제 지점 일치"),
    ("evidence_lines", "핵심 근거 파일·줄 번호 제시"),
    ("cause_ranking", "원인 후보 순위 적절성"),
    ("no_fabrication", "원본에 없는 값 사용 없음"),
    ("no_overclaim", "원인 단정 표현 없음"),
    ("pii_masked", "개인정보 원문 노출 없음"),
    ("report_order", "6단 보고서 순서 준수"),
    ("impact_scope", "영향 범위 판단"),
    ("trap_handling", "시나리오별 함정 처리"),
]
ITEM_LABEL = dict(ITEMS)
# 시나리오의 핵심 판단 항목(무승부 판정에서 회귀 여부를 볼 때 모든 항목을 같은 무게로 본다).


# ---------------------------------------------------------------------------
# 스키마
# ---------------------------------------------------------------------------
class ItemVerdict(BaseModel):
    passed: bool = Field(description="기준 충족이면 true")
    evidence: str = Field(description="판정 근거가 된 보고서 문장 인용(짧게). 없으면 '보고서에 없음'")
    reason: str = Field(description="rubric 기준에 비춘 판정 이유 1~2문장")


class MustMention(BaseModel):
    item: str = Field(description="answer_key '반드시 언급'에서 쪼갠 항목")
    present: bool


class Judgement(BaseModel):
    problem_point: ItemVerdict
    evidence_lines: ItemVerdict
    cause_ranking: ItemVerdict
    no_fabrication: ItemVerdict
    no_overclaim: ItemVerdict
    pii_masked: ItemVerdict
    report_order: ItemVerdict
    impact_scope: ItemVerdict
    trap_handling: ItemVerdict
    must_mention: list[MustMention]
    overall_score: int = Field(description="1~5 종합 점수")
    overall_reason: str


class PairwiseVerdict(BaseModel):
    winner: Literal["A", "B", "tie"]
    reason: str = Field(description="answer_key 기준 결정적 차이. 없으면 tie 이유")


# ---------------------------------------------------------------------------
# Judge 모델
# ---------------------------------------------------------------------------
def judge_model_name() -> str:
    # 가능하면 에이전트와 다른 모델을 JUDGE_MODEL_NAME 으로 지정한다. 비우면 에이전트 모델을
    # temperature 0 으로 쓴다(OpenRouter guardrail 로 다른 모델이 막힌 환경 대비).
    return os.getenv("JUDGE_MODEL_NAME") or os.getenv("MODEL_NAME") or "moonshotai/kimi-k3"


_MODELS: dict[str, Any] = {}


def _structured(schema: type[BaseModel]):
    if schema.__name__ in _MODELS:
        return _MODELS[schema.__name__]
    import httpx
    from langchain.chat_models import init_chat_model

    llm = init_chat_model(
        model=judge_model_name(),
        model_provider="openai",
        api_key=os.getenv("JUDGE_API_KEY") or os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("JUDGE_BASE_URL") or os.getenv("MODEL_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=0,
        max_retries=3,
        timeout=300,
        http_client=httpx.Client(verify=False),
    )
    method = os.getenv("JUDGE_STRUCTURED_METHOD", "json_schema")
    runnable = llm.with_structured_output(schema, method=method).with_config(
        {"tags": ["role:judge"], "metadata": {"role": "judge", "judge_model": judge_model_name()}}
    )
    _MODELS[schema.__name__] = runnable
    return runnable


def _invoke(schema: type[BaseModel], system: str, user: str) -> BaseModel:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    try:
        return _structured(schema).invoke(messages)
    except Exception as exc:  # noqa: BLE001 - 스키마 강제 방식이 안 맞는 모델이면 함수 호출로 재시도
        if os.getenv("JUDGE_STRUCTURED_METHOD"):
            raise
        print(f"[judge] json_schema 실패({type(exc).__name__}), function_calling 으로 재시도", file=sys.stderr)
        os.environ["JUDGE_STRUCTURED_METHOD"] = "function_calling"
        _MODELS.clear()
        return _structured(schema).invoke(messages)


def _rubric() -> str:
    return RUBRIC.read_text(encoding="utf-8")


def answer_key(sid: str) -> str:
    return (ANSWER_KEYS / f"{sid}.md").read_text(encoding="utf-8")


def question(sid: str) -> str:
    for s in json.loads(SCENARIOS.read_text(encoding="utf-8")):
        if s["id"] == sid:
            return s["question"]
    raise KeyError(sid)


SYSTEM_SCORE = """당신은 로그 원인 추적 보고서를 채점하는 엄격한 평가자다. 아래 판정 기준(rubric)과 시나리오 정답(answer_key)만 근거로 보고서를 판정한다. 보고서를 직접 다시 분석하거나 정답을 보완하지 않는다. 각 항목은 rubric 의 해석 기준대로 true/false 로 판정하고, 보고서에서 인용한 근거와 이유를 반드시 남긴다. 모든 텍스트는 한국어로 쓴다.

# 판정 기준
{rubric}"""

SYSTEM_PAIR = """당신은 같은 문의에 대한 두 원인 추적 보고서(A, B)를 비교하는 평가자다. 시나리오 정답(answer_key)과 판정 기준(rubric)에 비추어 더 정확하고 근거가 충실하며 함정을 잘 피한 보고서를 고른다. 길이·문체·서식은 판단에 넣지 않는다. 결정적 차이가 없으면 tie 를 고른다. 이유는 한국어로 쓴다.

# 판정 기준
{rubric}"""


def judge_report(sid: str, report: str) -> dict:
    user = (f"# 시나리오 {sid}\n\n## 문의\n{question(sid)}\n\n## 정답(answer_key)\n{answer_key(sid)}\n\n"
            f"## 채점할 보고서\n<report>\n{report}\n</report>")
    result: Judgement = _invoke(Judgement, SYSTEM_SCORE.format(rubric=_rubric()), user)  # type: ignore[assignment]
    data = result.model_dump()
    data["overall_score"] = max(1, min(5, int(data["overall_score"])))
    return data


def pairwise_once(sid: str, report_a: str, report_b: str) -> dict:
    user = (f"# 시나리오 {sid}\n\n## 문의\n{question(sid)}\n\n## 정답(answer_key)\n{answer_key(sid)}\n\n"
            f"## 보고서 A\n<report_a>\n{report_a}\n</report_a>\n\n## 보고서 B\n<report_b>\n{report_b}\n</report_b>")
    return _invoke(PairwiseVerdict, SYSTEM_PAIR.format(rubric=_rubric()), user).model_dump()  # type: ignore[union-attr]


def pairwise(sid: str, report_a: str, report_b: str) -> dict:
    """A/B 순서를 바꿔 두 번 판정한다. 두 번 모두 같은 보고서를 고를 때만 승리."""
    first = pairwise_once(sid, report_a, report_b)
    second = pairwise_once(sid, report_b, report_a)
    swapped = {"A": "B", "B": "A", "tie": "tie"}[second["winner"]]
    final = first["winner"] if first["winner"] == swapped and first["winner"] != "tie" else "tie"
    return {"order_ab": first, "order_ba": second, "order_ba_mapped": swapped, "final": final}


# ---------------------------------------------------------------------------
# 결과 폴더
# ---------------------------------------------------------------------------
def _sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def scenario_ids(run_dir: Path) -> list[str]:
    return sorted(p.stem for p in run_dir.glob("S*.md") if p.stem[1:].isdigit())


def load_meta(run_dir: Path, sid: str) -> dict:
    path = run_dir / f"{sid}.meta.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def label(run_dir: Path) -> str:
    return f"{run_dir.name}@{run_dir.parent.name}"


def score_run(run_dir: Path, *, force: bool = False, jobs: int = 4) -> dict[str, dict]:
    """보고서마다 Judge 결과(<sid>.judge.json)를 만들고(캐시), 시나리오별 결과를 돌려준다."""
    sids = scenario_ids(run_dir)
    if not sids:
        raise SystemExit(f"{run_dir} 에 S*.md 보고서가 없습니다.")

    def one(sid: str) -> tuple[str, dict]:
        report = (run_dir / f"{sid}.md").read_text(encoding="utf-8")
        cache = run_dir / f"{sid}.judge.json"
        key = {"report_sha": _sha(report), "answer_key_sha": _sha(answer_key(sid)),
               "rubric_sha": _sha(_rubric()), "judge_model": judge_model_name(), "judge_version": JUDGE_VERSION}
        if cache.exists() and not force:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if all(data.get(k) == v for k, v in key.items()):
                return sid, data
        print(f"[judge] {label(run_dir)} {sid} 채점 중... ({judge_model_name()})", file=sys.stderr)
        data = {**key, "scenario_id": sid, **judge_report(sid, report)}
        cache.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return sid, data

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        return dict(pool.map(one, sids))


def passes(j: dict) -> int:
    return sum(1 for k, _ in ITEMS if j[k]["passed"])


def _verdict(passed: bool | None) -> str:
    return "-" if passed is None else ("일치" if passed else "불일치")


def comparison_md(run_dir: Path, results: dict[str, dict], experiment: str | None) -> str:
    sids = list(results)
    lines = [f"# 판정표 — {label(run_dir)}", ""]
    lines.append(f"- Judge: `{judge_model_name()}` (temperature 0, structured output), rubric: `eval/rubric.md`")
    if experiment:
        lines.append(f"- LangSmith Experiment: `{experiment}` (Dataset `{DATASET_NAME}`)")
    lines += ["", "| 항목 | " + " | ".join(sids) + " |", "|---|" + "---|" * len(sids)]
    for key, name in ITEMS:
        lines.append(f"| {name} | " + " | ".join(_verdict(results[s][key]["passed"]) for s in sids) + " |")
    lines.append("| **통과 항목 수** | " + " | ".join(f"{passes(results[s])}/9" for s in sids) + " |")
    lines.append("| **종합 점수(1~5)** | " + " | ".join(str(results[s]["overall_score"]) for s in sids) + " |")
    mm = [f"{sum(m['present'] for m in results[s]['must_mention'])}/{len(results[s]['must_mention'])}" for s in sids]
    lines.append("| 반드시 언급 커버리지 | " + " | ".join(mm) + " |")
    lines += ["", "판정은 `일치`(True)·`불일치`(False)다. 항목마다 근거와 이유는 아래에 있다.", ""]
    for s in sids:
        j = results[s]
        meta = load_meta(run_dir, s)
        lines += [f"## {s} — 종합 {j['overall_score']}/5", "", f"{j['overall_reason']}", ""]
        if meta.get("trace_url"):
            lines += [f"- trace: {meta['trace_url']}", ""]
        for key, name in ITEMS:
            v = j[key]
            mark = "✅" if v["passed"] else "❌"
            lines.append(f"- {mark} **{name}** — {v['reason']}")
            lines.append(f"  - 근거: {v['evidence']}")
        missing = [m["item"] for m in j["must_mention"] if not m["present"]]
        lines += ["", f"- 반드시 언급 누락: {', '.join(missing) if missing else '없음'}", ""]
    rows = {s: load_meta(run_dir, s).get("metrics") for s in sids}
    rows = {s: m for s, m in rows.items() if m}
    if rows:
        lines += ["## 작업 방식 지표 (trace)", "", metrics_table(rows)]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# LangSmith Dataset / Experiment
# ---------------------------------------------------------------------------
def _client():
    if not configure_tracing():
        return None
    from langsmith import Client

    return Client()


def sync_dataset(client) -> str:
    """Dataset 을 만들거나(없을 때) 같은 이름의 예제를 갱신한다."""
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    if client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
    else:
        dataset = client.create_dataset(DATASET_NAME, description="로그 추적 에이전트 S1~S4 질문과 answer_key")
    existing = {(e.metadata or {}).get("scenario_id"): e for e in client.list_examples(dataset_id=dataset.id)}
    created = updated = 0
    for s in scenarios:
        inputs = {"question": s["question"], "scenario_id": s["id"]}
        outputs = {"answer_key": answer_key(s["id"])}
        metadata = {"scenario_id": s["id"], "date": s["date"], "campaign_id": s["campaign_id"]}
        ex = existing.get(s["id"])
        if ex is None:
            client.create_example(inputs=inputs, outputs=outputs, metadata=metadata, dataset_id=dataset.id)
            created += 1
        elif ex.inputs != inputs or ex.outputs != outputs or (ex.metadata or {}) != metadata:
            client.update_example(ex.id, inputs=inputs, outputs=outputs, metadata=metadata)
            updated += 1
    print(f"[dataset] {DATASET_NAME}: 생성 {created}, 갱신 {updated}, 전체 {len(scenarios)}")
    return str(dataset.id)


METRIC_FEEDBACK = ["total_steps", "tool_calls", "duplicate_calls", "failed_retries", "total_tokens",
                   "latency_s", "cost_usd", "skill_read_first", "eval_access_attempts", "write_attempts"]


def run_experiment(client, run_dir: Path, results: dict[str, dict]) -> str | None:
    """저장된 보고서를 target 출력으로 하는 Experiment 를 만든다(에이전트를 다시 돌리지 않는다)."""
    from langsmith import evaluate

    sync_dataset(client)
    sids = set(results)
    examples = [e for e in client.list_examples(dataset_name=DATASET_NAME)
                if (e.metadata or {}).get("scenario_id") in sids]
    metas = {s: load_meta(run_dir, s) for s in sids}
    variant, run_set = run_dir.name, run_dir.parent.name

    def target(inputs: dict) -> dict:
        sid = inputs["scenario_id"]
        return {"report": (run_dir / f"{sid}.md").read_text(encoding="utf-8"),
                "agent_trace_url": metas[sid].get("trace_url"), "metrics": metas[sid].get("metrics")}

    def llm_judge(inputs: dict, outputs: dict) -> dict:
        j = results[inputs["scenario_id"]]
        res = [{"key": k, "score": int(j[k]["passed"]), "comment": f"{j[k]['reason']} | 근거: {j[k]['evidence']}"}
               for k, _ in ITEMS]
        res.append({"key": "pass_count", "score": passes(j)})
        res.append({"key": "overall_score", "score": j["overall_score"], "comment": j["overall_reason"]})
        return {"results": res}

    def trace_metrics(inputs: dict, outputs: dict) -> dict:
        m = outputs.get("metrics") or {}
        res = []
        for k in METRIC_FEEDBACK:
            v = m.get(k)
            if v is None:
                continue
            if k == "total_tokens":  # feedback 점수 상한(±99,999) 때문에 천 단위로 기록
                res.append({"key": "trace_total_tokens_k", "score": round(v / 1000, 1)})
            else:
                res.append({"key": f"trace_{k}", "score": float(v) if not isinstance(v, bool) else int(v)})
        return {"results": res}

    result = evaluate(
        target, data=examples, evaluators=[llm_judge, trace_metrics], client=client,
        experiment_prefix=f"{variant}-{run_set}", max_concurrency=4,
        metadata={"variant": variant, "run_set": run_set, "judge_model": judge_model_name(),
                  "agent_model": next((m.get("model") for m in metas.values() if m.get("model")), None)},
        description=f"{variant} 보고서(run_set {run_set})를 LLM Judge 로 채점",
    )
    name = result.experiment_name
    print(f"[experiment] {name}")
    return name


def attach_feedback(client, run_dir: Path, results: dict[str, dict]) -> None:
    """원래 에이전트 trace(log-trace-agent 프로젝트)에 판정 결과를 feedback 으로 붙인다."""
    for sid, j in results.items():
        trace_id = load_meta(run_dir, sid).get("trace_id")
        if not trace_id:
            continue
        try:
            for k, _ in ITEMS:
                client.create_feedback(trace_id, key=f"judge_{k}", score=int(j[k]["passed"]), comment=j[k]["reason"])
            client.create_feedback(trace_id, key="judge_overall_score", score=j["overall_score"],
                                   comment=j["overall_reason"])
        except Exception as exc:  # noqa: BLE001 - feedback 은 부가 기능
            print(f"[feedback] {sid} 실패: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 비교·판정
# ---------------------------------------------------------------------------
def decide(a: dict[str, dict], b: dict[str, dict], pair: dict[str, dict]) -> dict:
    """기본값 무승부. 회귀 없이 개선(항목 또는 pairwise)이 있고 pairwise 패배가 없을 때만 승리."""
    common = sorted(set(a) & set(b))
    improved = [(s, k) for s in common for k, _ in ITEMS if not a[s][k]["passed"] and b[s][k]["passed"]]
    regressed = [(s, k) for s in common for k, _ in ITEMS if a[s][k]["passed"] and not b[s][k]["passed"]]
    b_wins = [s for s in common if pair.get(s, {}).get("final") == "B"]
    a_wins = [s for s in common if pair.get(s, {}).get("final") == "A"]
    if not regressed and not a_wins and (improved or b_wins):
        verdict = "B"
    elif not improved and not b_wins and (regressed or a_wins):
        verdict = "A"
    else:
        verdict = "tie"
    return {"verdict": verdict, "improved": improved, "regressed": regressed, "pairwise_b_wins": b_wins,
            "pairwise_a_wins": a_wins}


def compare(a_dir: Path, b_dirs: list[Path], *, out: Path | None, jobs: int, quiet: bool = False) -> dict:
    a = score_run(a_dir, jobs=jobs)
    reps = []
    for b_dir in b_dirs:
        b = score_run(b_dir, jobs=jobs)
        sids = sorted(set(a) & set(b))
        cache = b_dir / f"pairwise_vs_{a_dir.name}@{a_dir.parent.name}.json"
        pair = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
        todo = [s for s in sids if pair.get(s, {}).get("key") != (_sha((a_dir / f"{s}.md").read_text(encoding="utf-8"))
                                                                   + _sha((b_dir / f"{s}.md").read_text(encoding="utf-8")))]

        def one(sid: str) -> tuple[str, dict]:
            ra = (a_dir / f"{sid}.md").read_text(encoding="utf-8")
            rb = (b_dir / f"{sid}.md").read_text(encoding="utf-8")
            print(f"[pairwise] {sid}: {label(a_dir)} vs {label(b_dir)}", file=sys.stderr)
            return sid, {"key": _sha(ra) + _sha(rb), **pairwise(sid, ra, rb)}

        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            pair.update(dict(pool.map(one, todo)))
        cache.write_text(json.dumps(pair, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        reps.append({"dir": b_dir, "scores": b, "pairwise": pair, "decision": decide(a, b, pair)})

    verdicts = {r["decision"]["verdict"] for r in reps}
    final = verdicts.pop() if len(verdicts) == 1 else "tie"
    text = compare_md(a_dir, a, reps, final)
    out = out or (b_dirs[-1] / f"compare_vs_{a_dir.name}@{a_dir.parent.name}.md")
    out.write_text(text, encoding="utf-8")
    if not quiet:
        print(text)
        print(f"[compare] 저장: {out}")
    return {"final": final, "reps": [{"dir": str(r["dir"]), **r["decision"]} for r in reps]}


def _pair_cell(p: dict | None) -> str:
    if not p:
        return "-"
    return f"{p['order_ab']['winner']} / {p['order_ba_mapped']} → **{p['final']}**"


def compare_md(a_dir: Path, a: dict, reps: list[dict], final: str) -> str:
    final_text = {"B": "variant 확실한 우세", "A": "baseline 확실한 우세", "tie": "무승부(baseline 유지)"}[final]
    lines = [f"# 비교 — A `{label(a_dir)}` vs B " + ", ".join(f"`{label(r['dir'])}`" for r in reps), "",
             f"**자동 판정(참고): {final_text}** — 기본값은 무승부다. 반복 실행 {len(reps)}회가 모두 같은 승자를 "
             "가리키고, 항목 회귀와 pairwise 패배가 없을 때만 승리로 본다.", ""]
    for i, r in enumerate(reps, 1):
        b, pair, d = r["scores"], r["pairwise"], r["decision"]
        sids = sorted(set(a) & set(b))
        lines += [f"## 반복 {i}: `{label(r['dir'])}`", "", "### 시나리오×항목 (A → B)", "",
                  "| 항목 | " + " | ".join(sids) + " |", "|---|" + "---|" * len(sids)]
        for k, name in ITEMS:
            cells = []
            for s in sids:
                pa, pb = a[s][k]["passed"], b[s][k]["passed"]
                cell = f"{_verdict(pa)} → {_verdict(pb)}"
                cells.append(f"**{cell}**" if pa != pb else cell)
            lines.append(f"| {name} | " + " | ".join(cells) + " |")
        lines.append("| 통과 항목 수 | " + " | ".join(f"{passes(a[s])} → {passes(b[s])}" for s in sids) + " |")
        lines.append("| 종합 점수 | " + " | ".join(f"{a[s]['overall_score']} → {b[s]['overall_score']}" for s in sids) + " |")
        lines += ["", "### Pairwise (A·B 순서 / B·A 순서 → 최종)", "", "| 시나리오 | 결과 | 이유(A·B 순서) |", "|---|---|---|"]
        for s in sids:
            p = pair.get(s)
            reason = (p or {}).get("order_ab", {}).get("reason", "").replace("|", "/").replace("\n", " ")
            lines.append(f"| {s} | {_pair_cell(p)} | {reason[:300]} |")
        lines += ["", f"- 개선: {', '.join(f'{s}:{ITEM_LABEL[k]}' for s, k in d['improved']) or '없음'}",
                  f"- 회귀: {', '.join(f'{s}:{ITEM_LABEL[k]}' for s, k in d['regressed']) or '없음'}",
                  f"- 반복 판정: {d['verdict']}", "", "### trace 지표 (A → B)", "",
                  "| 시나리오 | " + " | ".join(h for _, h in TABLE_COLUMNS) + " |",
                  "|---|" + "---:|" * len(TABLE_COLUMNS)]
        for s in sids:
            ma = load_meta(a_dir, s).get("metrics") or {}
            mb = load_meta(r["dir"], s).get("metrics") or {}
            lines.append(f"| {s} | " + " | ".join(f"{_cell(ma.get(k))} → {_cell(mb.get(k))}" for k, _ in TABLE_COLUMNS) + " |")
        lines.append("")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 개선 에이전트용 요약(정답 비노출), 사람 판정 비교
# ---------------------------------------------------------------------------
def redacted_summary(run_dir: Path) -> dict:
    """항목 통과 여부·점수·지표만 담는다. Judge 근거·이유·반드시 언급 내용은 answer_key 를
    담을 수 있어 빼고, 누락 개수만 남긴다."""
    results = score_run(run_dir)
    out = {}
    for sid, j in results.items():
        m = load_meta(run_dir, sid).get("metrics") or {}
        out[sid] = {
            "items": {ITEM_LABEL[k]: j[k]["passed"] for k, _ in ITEMS},
            "pass_count": passes(j), "overall_score": j["overall_score"],
            "must_mention_missing_count": sum(1 for x in j["must_mention"] if not x["present"]),
            "metrics": {k: m.get(k) for k, _ in TABLE_COLUMNS},
        }
    return out


def human_template(run_dir: Path) -> Path:
    path = run_dir / "human_labels.json"
    if path.exists():
        raise SystemExit(f"{path} 가 이미 있습니다.")
    data = {"_설명": "true=일치, false=불일치, null=판정 안 함. 판정할 시나리오만 채운다.",
            **{sid: {k: None for k, _ in ITEMS} for sid in scenario_ids(run_dir)}}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def agreement(run_dir: Path) -> str:
    human = json.loads((run_dir / "human_labels.json").read_text(encoding="utf-8"))
    results = score_run(run_dir)
    lines = [f"# 사람 판정 vs Judge — {label(run_dir)}", "", "| 시나리오 | 항목 | 사람 | Judge | 일치 | Judge 근거 |",
             "|---|---|---|---|---|---|"]
    agree = total = 0
    for sid, labels in human.items():
        if sid.startswith("_") or sid not in results:
            continue
        for k, name in ITEMS:
            h = labels.get(k)
            if h is None:
                continue
            j = results[sid][k]
            same = h == j["passed"]
            agree += same
            total += 1
            lines.append(f"| {sid} | {name} | {_verdict(h)} | {_verdict(j['passed'])} | {'✅' if same else '❌'} | "
                         f"{j['reason'].replace('|', '/')} |")
    lines += ["", f"일치율: {agree}/{total}" + (f" ({agree / total:.0%})" if total else ""),
              "", "어긋난 항목은 `eval/rubric.md` 해석 기준을 먼저 고친 뒤 `score --force` 로 다시 채점한다."]
    text = "\n".join(lines) + "\n"
    (run_dir / "agreement.md").write_text(text, encoding="utf-8")
    return text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def cmd_score(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    results = score_run(run_dir, force=args.force, jobs=args.jobs)
    experiment = None
    client = None if args.no_langsmith else _client()
    if client is not None:
        try:
            experiment = run_experiment(client, run_dir, results)
            attach_feedback(client, run_dir, results)
        except Exception as exc:  # noqa: BLE001 - 로컬 판정표는 LangSmith 오류와 무관하게 남긴다
            print(f"[experiment] LangSmith 기록 실패: {exc}", file=sys.stderr)
    text = comparison_md(run_dir, results, experiment)
    (run_dir / "comparison.md").write_text(text, encoding="utf-8")
    scores = {"run_dir": str(run_dir), "experiment": experiment, "judge_model": judge_model_name(),
              "scenarios": {s: {"pass_count": passes(j), "overall_score": j["overall_score"],
                                "items": {k: j[k]["passed"] for k, _ in ITEMS}} for s, j in results.items()}}
    (run_dir / "scores.json").write_text(json.dumps(scores, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(text.split("\n## ")[0])
    print(f"[judge] 저장: {run_dir / 'comparison.md'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-as-a-Judge 채점")
    parser.add_argument("--jobs", type=int, default=4)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sync-dataset", help=f"LangSmith Dataset {DATASET_NAME} 생성·갱신")

    sp = sub.add_parser("score", help="결과 폴더 채점 → comparison.md, scores.json, Experiment")
    sp.add_argument("run_dir")
    sp.add_argument("--force", action="store_true", help="캐시를 무시하고 다시 채점")
    sp.add_argument("--no-langsmith", action="store_true", help="Experiment·feedback 기록 생략")

    sp = sub.add_parser("compare", help="두 실행 묶음 비교(항목·pairwise·trace 지표·자동 판정)")
    sp.add_argument("--a", required=True, help="기준 결과 폴더(baseline)")
    sp.add_argument("--b", required=True, action="append", help="비교 결과 폴더. 반복 실행이면 여러 번 지정")
    sp.add_argument("--out", help="비교 보고서 경로(기본: 마지막 B 폴더 안)")
    sp.add_argument("--json", action="store_true", help="판정 요약 JSON 도 출력")
    sp.add_argument("--quiet", action="store_true", help="비교 보고서 본문을 출력하지 않음(파일에만 저장)")

    sp = sub.add_parser("summary", help="채점 요약 출력")
    sp.add_argument("run_dir")
    sp.add_argument("--redact", action="store_true", help="answer_key 를 담을 수 있는 근거·이유 제외")

    sp = sub.add_parser("human-template", help="사람 판정 입력 파일(human_labels.json) 생성")
    sp.add_argument("run_dir")

    sp = sub.add_parser("agree", help="human_labels.json 과 Judge 결과를 나란히 비교")
    sp.add_argument("run_dir")

    args = parser.parse_args()
    if args.command == "sync-dataset":
        client = _client()
        if client is None:
            raise SystemExit("LANGSMITH_API_KEY 가 없어 Dataset 을 만들 수 없습니다.")
        sync_dataset(client)
    elif args.command == "score":
        cmd_score(args)
    elif args.command == "compare":
        result = compare(Path(args.a).resolve(), [Path(b).resolve() for b in args.b],
                         out=Path(args.out).resolve() if args.out else None, jobs=args.jobs, quiet=args.quiet)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    elif args.command == "summary":
        run_dir = Path(args.run_dir).resolve()
        data = redacted_summary(run_dir) if args.redact else score_run(run_dir)
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.command == "human-template":
        print(f"생성: {human_template(Path(args.run_dir).resolve())}")
    elif args.command == "agree":
        print(agreement(Path(args.run_dir).resolve()))


if __name__ == "__main__":
    main()
