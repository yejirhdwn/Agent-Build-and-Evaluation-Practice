"""LangSmith 트레이싱 설정과 실행 메타데이터.

프로젝트 이름과 엔드포인트는 환경변수(``LANGSMITH_PROJECT``, ``LANGSMITH_ENDPOINT``)에서만
읽는다. 키가 없으면 경고만 남기고 트레이싱을 끈 채로 실행을 계속한다. 키 값은 어디에도
출력하지 않는다.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))  # 한국은 서머타임이 없어 고정 오프셋으로 충분하다.
_TRUE = {"1", "true", "yes", "on"}
_warned = False


def kst_stamp() -> str:
    return datetime.now(KST).strftime("%Y%m%d-%H%M%S")


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in _TRUE


def configure_tracing(*, quiet: bool = False) -> bool:
    """트레이싱 사용 여부를 정하고 반환한다.

    ``LANGSMITH_TRACING=true`` 인데 ``LANGSMITH_API_KEY`` 가 비어 있으면 업로드 오류가 나지 않도록
    트레이싱을 끄고 경고만 출력한다.
    """
    global _warned
    wanted = _flag("LANGSMITH_TRACING") or _flag("LANGCHAIN_TRACING_V2")
    has_key = bool(os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY"))
    if wanted and has_key:
        return True
    if wanted and not has_key:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        reason = "LANGSMITH_API_KEY 가 비어 있어"
    else:
        reason = "LANGSMITH_TRACING 이 꺼져 있어"
    if not quiet and not _warned:
        print(f"[observability] 경고: {reason} LangSmith 트레이싱 없이 실행합니다.", file=sys.stderr)
        _warned = True
    return False


def project_name() -> str:
    return os.getenv("LANGSMITH_PROJECT") or "default"


def model_name() -> str:
    return os.getenv("MODEL_NAME", "moonshotai/kimi-k3")


def run_config(*, role: str, variant: str, scenario_id: str | None = None,
               run_set: str | None = None, extra: dict | None = None) -> dict:
    """trace 에 붙일 metadata/tags 를 담은 RunnableConfig 조각."""
    metadata = {"role": role, "variant": variant, "model": model_name()}
    if scenario_id:
        metadata["scenario_id"] = scenario_id
    if run_set:
        metadata["run_set"] = run_set
    metadata.update(extra or {})
    tags = [f"role:{role}", f"variant:{variant}"]
    if scenario_id:
        tags.append(f"scenario:{scenario_id}")
    if run_set:
        tags.append(f"run_set:{run_set}")
    return {"metadata": metadata, "tags": tags}
