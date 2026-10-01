"""S1~S4 평가 실행과 보고서 저장.

에이전트는 질문 텍스트만 받으므로 자기가 몇 번 시나리오인지 알 수 없다. 그래서 시나리오
ID와 저장 위치는 이 스크립트가 정하고, 에이전트는 보고서를 응답으로만 돌려준다.

보고서는 저장소 루트의 ``runs/<KST YYYYMMDD-HHMMSS>/`` 에 저장한다. workspace 밖이라
에이전트 파일 도구로는 이전 평가 보고서를 볼 수 없다.

사용법(저장소 루트에서):
  # 헤드리스로 S1~S4를 각각 새 대화에서 실행하고 새 평가 폴더에 저장
  uv run python scripts/run_eval.py run
  uv run python scripts/run_eval.py run S2 S4 --run-dir runs/20261001-153000

  # LangSmith Studio에서 실행한 대화(thread)의 최종 보고서를 저장
  uv run python scripts/run_eval.py save S1 --thread-id <thread-id> --new
  uv run python scripts/run_eval.py save S2 --thread-id <thread-id>
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
SCENARIOS = ROOT / "eval" / "scenarios.json"
KST = timezone(timedelta(hours=9))  # 한국은 서머타임이 없어 고정 오프셋으로 충분하다.
SUSPICIOUS = ("eval/", "eval\\", "answer_keys", "scenarios.json")


def load_scenarios() -> dict[str, dict[str, str]]:
    return {s["id"]: s for s in json.loads(SCENARIOS.read_text(encoding="utf-8"))}


def new_run_dir() -> Path:
    path = RUNS / datetime.now(KST).strftime("%Y%m%d-%H%M%S")
    path.mkdir(parents=True, exist_ok=False)
    return path


def latest_run_dir() -> Path | None:
    dirs = sorted(p for p in RUNS.glob("*-*") if p.is_dir()) if RUNS.is_dir() else []
    return dirs[-1] if dirs else None


def resolve_run_dir(run_dir: str | None, new: bool) -> Path:
    if new:
        return new_run_dir()
    if run_dir:
        path = Path(run_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path
    return latest_run_dir() or new_run_dir()


# ---------------------------------------------------------------------------
# 메시지 정리 (in-process 메시지 객체와 LangGraph 서버 JSON 둘 다 처리)
# ---------------------------------------------------------------------------
def _as_dict(message: Any) -> dict[str, Any]:
    if isinstance(message, dict):
        return message
    return {
        "type": getattr(message, "type", ""),
        "content": getattr(message, "content", ""),
        "tool_calls": getattr(message, "tool_calls", []) or [],
    }


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
            if not isinstance(block, dict) or block.get("type") == "text"
        )
    return ""


def final_answer(messages: list[Any]) -> str:
    """마지막 AI 응답 중 텍스트가 있는 것을 최종 보고서로 본다."""
    for message in reversed([_as_dict(m) for m in messages]):
        if message.get("type") == "ai":
            text = _text(message.get("content")).strip()
            if text:
                return text
    return ""


def tool_calls(messages: list[Any]) -> list[dict[str, Any]]:
    calls = []
    for message in (_as_dict(m) for m in messages):
        for call in message.get("tool_calls") or []:
            args = call.get("args", {})
            flat = json.dumps(args, ensure_ascii=False)
            calls.append({
                "name": call.get("name"),
                "args": args,
                "suspicious": any(token in flat for token in SUSPICIOUS),
            })
    return calls


def write_result(run_dir: Path, scenario_id: str, messages: list[Any], force: bool) -> None:
    report = run_dir / f"{scenario_id}.md"
    if report.exists() and not force:
        raise SystemExit(f"{report} 가 이미 있습니다. 덮어쓰려면 --force 를 붙이세요.")
    answer = final_answer(messages)
    if not answer:
        raise SystemExit(f"{scenario_id}: 최종 응답 텍스트를 찾지 못했습니다.")
    calls = tool_calls(messages)
    report.write_text(answer + "\n", encoding="utf-8")
    (run_dir / f"{scenario_id}.tools.json").write_text(
        json.dumps(calls, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[{scenario_id}] 저장: {report.relative_to(ROOT)} (도구 호출 {len(calls)}회)")
    flagged = [c for c in calls if c["suspicious"]]
    if flagged:
        print(f"[{scenario_id}] ⚠️ 평가 파일 접근 시도 {len(flagged)}건: "
              + ", ".join(f"{c['name']}({json.dumps(c['args'], ensure_ascii=False)})" for c in flagged))


# ---------------------------------------------------------------------------
# 하위 명령
# ---------------------------------------------------------------------------
def load_agent():
    # 평가 중에는 셸을 date 로만 제한한다(meta-harness CLI 비활성).
    os.environ["META_HARNESS_ENABLED"] = "0"
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("harness", ROOT / "langchain-deepagents.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent


def cmd_run(args: argparse.Namespace) -> None:
    scenarios = load_scenarios()
    ids = args.scenarios or list(scenarios)
    unknown = [i for i in ids if i not in scenarios]
    if unknown:
        raise SystemExit(f"알 수 없는 시나리오: {unknown}")
    run_dir = Path(args.run_dir).resolve() if args.run_dir else new_run_dir()
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"평가 폴더: {run_dir.relative_to(ROOT)}")
    agent = load_agent()
    for scenario_id in ids:
        if (run_dir / f"{scenario_id}.md").exists() and not args.force:
            print(f"[{scenario_id}] 이미 있어 건너뜀(--force 로 덮어쓰기)")
            continue
        print(f"[{scenario_id}] 실행 중...")
        # 시나리오마다 체크포인터 없이 새로 호출하므로 이전 대화 문맥이 섞이지 않는다.
        state = agent.invoke(
            {"messages": [{"role": "user", "content": scenarios[scenario_id]["question"]}]},
            config={"recursion_limit": args.recursion_limit},
        )
        write_result(run_dir, scenario_id, state["messages"], args.force)


def cmd_save(args: argparse.Namespace) -> None:
    import httpx

    if args.scenario not in load_scenarios():
        raise SystemExit(f"알 수 없는 시나리오: {args.scenario}")
    url = f"{args.server.rstrip('/')}/threads/{args.thread_id}/state"
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    messages = (response.json().get("values") or {}).get("messages") or []
    run_dir = resolve_run_dir(args.run_dir, args.new)
    print(f"평가 폴더: {run_dir.relative_to(ROOT) if run_dir.is_relative_to(ROOT) else run_dir}")
    write_result(run_dir, args.scenario, messages, args.force)


def main() -> None:
    parser = argparse.ArgumentParser(description="S1~S4 평가 실행과 보고서 저장")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="에이전트를 헤드리스로 실행해 보고서를 저장")
    run.add_argument("scenarios", nargs="*", help="실행할 시나리오 ID(생략 시 전체)")
    run.add_argument("--run-dir", help="이어 쓸 평가 폴더(생략 시 새 KST 폴더)")
    run.add_argument("--recursion-limit", type=int, default=200)
    run.add_argument("--force", action="store_true", help="기존 보고서 덮어쓰기")
    run.set_defaults(func=cmd_run)

    save = sub.add_parser("save", help="Studio 대화(thread)의 최종 보고서를 저장")
    save.add_argument("scenario", help="시나리오 ID (예: S1)")
    save.add_argument("--thread-id", required=True, help="Studio 대화의 thread ID")
    save.add_argument("--server", default="http://127.0.0.1:2024", help="langgraph dev 서버 주소")
    target = save.add_mutually_exclusive_group()
    target.add_argument("--new", action="store_true", help="새 KST 평가 폴더를 만든다")
    target.add_argument("--run-dir", help="저장할 평가 폴더(생략 시 가장 최근 폴더)")
    save.add_argument("--force", action="store_true", help="기존 보고서 덮어쓰기")
    save.set_defaults(func=cmd_save)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
