"""로그 추적 에이전트를 meta-harness 절차로 개선하는 에이전트(harness-improver 그래프).

log-trace 에이전트(``langchain-deepagents.py``)와 역할을 분리한다. 개선 에이전트는

- 자기 workspace(``workspace_improver/``)에서만 파일 도구를 쓰고, 스킬은 meta-harness 하나만 본다.
- 셸은 ``date`` 와 ``python skills/meta-harness/metaharness.py`` 만 실행할 수 있다(환경변수와 무관).
- 정답(eval/answer_keys)은 읽을 수 없다. 채점은 meta-harness 가 호출하는 Judge 의 비식별 요약
  (항목 통과 여부·점수·pairwise 승패·trace 지표)으로만 받는다.
- 본체를 바꾸는 promote 는 사용자 승인 없이 실행하지 않는다.

헤드리스 실행(저장소 루트):
  uv run python harness_improver.py "meta-harness 로 log-trace 에이전트를 S1~S4 기준으로 개선해줘"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import dotenv
import httpx
from deepagents import HarnessProfile, create_deep_agent
from deepagents._models import get_model_identifier, get_model_provider
from deepagents.profiles.harness import harness_profiles as _profiles
from langchain.chat_models import init_chat_model

from observability import configure_tracing, kst_stamp, run_config
from shell_policy import RestrictedShellBackend

dotenv.load_dotenv()
configure_tracing()

ROOT = Path(__file__).resolve().parent
WORKSPACE = Path(os.getenv("IMPROVER_WORKSPACE_DIR", ROOT / "workspace_improver")).expanduser().resolve()
SEED_SKILL = ROOT / "workspace_seed" / "skills" / "meta-harness"

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY 환경변수가 필요합니다(기본 OpenRouter 키).")

model = init_chat_model(
    model=os.getenv("IMPROVER_MODEL_NAME") or os.getenv("MODEL_NAME", "moonshotai/kimi-k3"),
    model_provider="openai",
    api_key=api_key,
    base_url=os.getenv("MODEL_BASE_URL", "https://openrouter.ai/api/v1"),
    streaming=True,
    stream_usage=True,
    reasoning_effort="medium",
    http_client=httpx.Client(verify=False),
    http_async_client=httpx.AsyncClient(verify=False),
)


def _seed_workspace() -> None:
    """meta-harness 스킬만 개선 에이전트 workspace 에 복사한다(내용이 바뀐 파일만)."""
    dst = WORKSPACE / "skills" / "meta-harness"
    for src in SEED_SKILL.rglob("*"):
        if src.is_dir() or "__pycache__" in src.parts:
            continue
        target = dst / src.relative_to(SEED_SKILL)
        data = src.read_bytes()
        if target.exists() and target.read_bytes() == data:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (WORKSPACE / "meta").mkdir(parents=True, exist_ok=True)


_seed_workspace()

backend = RestrictedShellBackend(
    root_dir=str(WORKSPACE),
    virtual_mode=True,
    inherit_env=True,
    allow_meta_harness=True,
    timeout=3600,  # 평가 세트 실행·채점은 수 분~수십 분 걸린다.
)

SYSTEM_PROMPT = """당신은 로그 원인 추적 에이전트(log-trace 에이전트)를 개선하는 하네스 엔지니어다. 직접 로그를 분석하지 않는다. `meta-harness` 스킬 절차로 log-trace 에이전트의 격리 복제본을 실행·수정·비교해서, 근거가 확실한 개선만 사용자에게 제안한다.

## 작업 범위

- 개선 대상(노브)은 세 가지다: log-trace 에이전트의 시스템 프롬프트(`langchain-deepagents.py` 의 `SYSTEM_PROMPT`), 도구 코드(`trace_tools.py`), log-trace 스킬(`workspace_seed/skills/log-trace/`).
- 평가 세트는 S1~S4 다. 실행과 채점은 `run --suite` · `compare --suite` 로만 한다. 성공기준은 Judge 의 항목별 True/False(9개 항목)와 pairwise 결과다. trace 지표(단계 수·토큰·반복 호출 등)는 참고만 한다.

## 반드시 지킬 것

- 정답 파일(`eval/`)과 평가 결과의 판정 근거를 찾거나 읽으려 하지 않는다. 채점 결과는 meta-harness 가 보여주는 요약만 사용한다.
- 시작할 때 `skills/meta-harness/SKILL.md` 를 읽고 그 절차(doctor → init → run → fork → edit → run → compare)를 따른다.
- 가설은 한 번에 하나만 세우고, 노브 하나를 `edit` 로 최소 변경한다. 특정 캠페인 ID·수치·줄번호를 넣지 않고 여러 시나리오에 통하는 일반 원칙으로 쓴다.
- 판정 기본값은 무승부다. 차이가 접전이면 variant 를 2~3회 반복 실행해 매번 우위가 유지될 때만 승리로 본다. 한 시나리오가 좋아져도 다른 시나리오가 회귀하면 무승부다.
- `promote` 는 미리보기(`--yes` 없이)까지만 한다. 실제 반영은 사용자가 승인한 뒤에만 한다.
- 셸은 `date` 와 `python skills/meta-harness/metaharness.py` 만 쓸 수 있다. 오래 걸리는 명령은 `execute` 의 timeout 을 넉넉히(예: 3600) 준다.

## 보고

사이클마다 다음을 짧게 정리해 응답한다: 진단(약한 항목·trace 지표), 가설, 변경 diff, 전후 항목 결과, pairwise, trace 지표 비교, 판정과 이유, 다음 행동(promote 승인 요청 또는 v2 가설)."""


def build_improver(checkpointer=None):
    """개선 에이전트 그래프. 같은 모델을 쓰는 log-trace 에이전트의 프롬프트 프로필과 섞이지 않도록
    그래프를 만드는 동안에만 이 에이전트의 프로필을 등록했다가 원래대로 되돌린다."""
    key = f"{get_model_provider(model)}:{get_model_identifier(model)}"
    saved = _profiles._HARNESS_PROFILES.get(key)
    _profiles._HARNESS_PROFILES[key] = HarnessProfile(base_system_prompt=SYSTEM_PROMPT)
    try:
        graph = create_deep_agent(
            model=model,
            backend=backend,
            skills=["/skills/"],
            checkpointer=checkpointer,
            name="harness-improver",
        )
    finally:
        if saved is None:
            _profiles._HARNESS_PROFILES.pop(key, None)
        else:
            _profiles._HARNESS_PROFILES[key] = saved
    return graph.with_config(run_config(role="improver", variant=os.getenv("HARNESS_VARIANT", "improver")))


agent = build_improver()


if __name__ == "__main__":
    request = " ".join(sys.argv[1:]) or (
        "meta-harness 스킬로 log-trace 에이전트를 S1~S4 평가 세트 기준으로 개선해줘. "
        "baseline 을 실행·진단하고, 가설 하나로 v1 을 만들어 비교한 뒤 promote 전에 멈추고 보고해줘."
    )
    out_dir = ROOT / "runs" / "improver" / kst_stamp()
    out_dir.mkdir(parents=True, exist_ok=True)
    config = {**run_config(role="improver", variant="improver", run_set=out_dir.name), "recursion_limit": 300}
    lines = [f"# harness-improver 실행 기록 ({out_dir.name})", "", f"요청: {request}", ""]
    state = None
    for state in agent.stream({"messages": [{"role": "user", "content": request}]}, config=config,
                              stream_mode="values"):
        last = state["messages"][-1]
        for call in getattr(last, "tool_calls", None) or []:
            line = f"→ {call['name']} {str(call.get('args'))[:300]}"
            print(line, flush=True)
            lines.append(f"- `{line}`")
    messages = (state or {}).get("messages", [])
    final = next((m.content for m in reversed(messages) if m.type == "ai" and m.content), "")
    if isinstance(final, list):
        final = "".join(b.get("text", "") for b in final if isinstance(b, dict))
    lines += ["", "## 최종 응답", "", str(final)]
    (out_dir / "transcript.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + str(final))
    print(f"\n[improver] 기록: {out_dir / 'transcript.md'}")
