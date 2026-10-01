"""S1~S4 시나리오 헤드리스 실행·저장과 작업 방식 지표.

에이전트는 질문 텍스트만 받으므로 자기가 몇 번 시나리오인지 알 수 없다. 시나리오 ID, variant,
실행 묶음(run_set), 저장 위치는 이 스크립트가 정해 trace metadata 로 붙이고, 보고서도 이 스크립트가
저장한다.

정답 격리(경로 분리): 에이전트는 레포가 아니라 레포 밖 임시 샌드박스에서 실행된다. 샌드박스에는
``eval/``·``runs/``·``.git``·``.env`` 를 복사하지 않고, 시나리오마다 새 workspace 를 만든다.
셸은 ``META_HARNESS_ENABLED=0`` 으로 ``date`` 만 허용된다.

저장 구조: ``runs/<run_set KST>/<variant>/``
  S1.md            최종 보고서
  S1.trace.json    단계별 실행 기록(LLM·도구 호출, 토큰, latency, 오류)
  S1.meta.json     scenario_id·variant·run_set·model·trace_id·지표
  metrics.md       시나리오별 작업 방식 지표 표

사용법(저장소 루트):
  uv run python eval/run_scenarios.py run --variant baseline --scenarios all
  uv run python eval/run_scenarios.py run --variant v1 --harness-dir <variant 경로> --scenarios S2 S4
  uv run python eval/run_scenarios.py save S1 --thread-id <id> --variant studio --new
  uv run python eval/run_scenarios.py metrics runs/<run_set>/<variant> [--source langsmith]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EVAL))

import dotenv  # noqa: E402

dotenv.load_dotenv(ROOT / ".env")

from observability import configure_tracing, kst_stamp, model_name, project_name, run_config  # noqa: E402
from trace_metrics import (  # noqa: E402
    compute_metrics, find_trace_id_for_thread, metrics_table, model_price,
    steps_from_langsmith, steps_from_messages,
)

RUNS = ROOT / "runs"
SCENARIOS = EVAL / "scenarios.json"
HARNESS_ENTRY = "langchain-deepagents.py"
SANDBOX_IGNORE = {
    ".git", ".venv", "venv", "eval", "runs", "workspace", "__pycache__", ".langgraph_api",
    "_archive", "docs", ".meta", "_ws", "_runs", ".env", ".pytest_cache", ".mypy_cache",
    "workspace_improver",
}


def load_scenarios() -> dict[str, dict[str, str]]:
    return {s["id"]: s for s in json.loads(SCENARIOS.read_text(encoding="utf-8"))}


def select_scenarios(ids: list[str]) -> list[str]:
    scenarios = load_scenarios()
    if not ids or ids == ["all"]:
        return list(scenarios)
    unknown = [i for i in ids if i not in scenarios]
    if unknown:
        raise SystemExit(f"알 수 없는 시나리오: {unknown}")
    return ids


# ---------------------------------------------------------------------------
# 메시지 정리
# ---------------------------------------------------------------------------
def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "") if isinstance(b, dict) else str(b)
            for b in content
            if not isinstance(b, dict) or b.get("type") == "text"
        )
    return ""


def _msg_dict(message: Any) -> dict[str, Any]:
    if isinstance(message, dict):
        return message
    return {
        "type": getattr(message, "type", ""),
        "content": getattr(message, "content", ""),
        "tool_calls": getattr(message, "tool_calls", []) or [],
        "tool_call_id": getattr(message, "tool_call_id", None),
        "status": getattr(message, "status", None),
        "usage_metadata": getattr(message, "usage_metadata", None),
    }


def final_answer(messages: list[Any]) -> str:
    """마지막 AI 응답 중 텍스트가 있는 것을 최종 보고서로 본다."""
    for message in reversed([_msg_dict(m) for m in messages]):
        if message.get("type") == "ai":
            text = _text(message.get("content")).strip()
            if text:
                return text
    return ""


# ---------------------------------------------------------------------------
# 샌드박스
# ---------------------------------------------------------------------------
def _ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in SANDBOX_IGNORE or n.endswith((".pyc", ".pyo"))}


def make_sandbox(source: Path, parent: Path) -> Path:
    """하네스 소스를 레포 밖에 복사한다(eval/·runs/·.env 제외)."""
    dst = parent / "harness"
    shutil.copytree(source, dst, ignore=_ignore)
    leaked = [p for p in ("eval", "runs") if (dst / p).exists()]
    if leaked:
        raise SystemExit(f"샌드박스에 평가 경로가 남았습니다: {leaked}")
    return dst


def _worker_cmd(harness: Path, ws: Path, qfile: Path, out: Path, sid: str, variant: str,
                run_set: str, recursion_limit: int, deadline: int) -> list[str]:
    return [
        sys.executable, str(Path(__file__).resolve()), "__worker",
        "--harness-dir", str(harness), "--workspace", str(ws), "--question-file", str(qfile),
        "--out", str(out), "--scenario-id", sid, "--variant", variant, "--run-set", run_set,
        "--recursion-limit", str(recursion_limit), "--deadline", str(deadline),
    ]


def _worker_env(variant: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("WORKSPACE_DIR",)}
    env["META_HARNESS_ENABLED"] = "0"  # 평가 중 셸은 date 만 허용
    env["HARNESS_VARIANT"] = variant
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def trace_url(trace_id: str | None) -> str | None:
    if not trace_id or not configure_tracing(quiet=True):
        return None
    try:
        from langsmith import Client

        client = Client()
        for _ in range(5):
            try:
                return client.get_run_url(run=client.read_run(trace_id), project_name=project_name())
            except Exception:  # noqa: BLE001 - 업로드가 늦으면 잠시 뒤 다시 시도
                time.sleep(3)
    except Exception:  # noqa: BLE001
        return None
    return None


def write_result(out_dir: Path, sid: str, *, messages: list, steps: list, meta: dict) -> dict:
    answer = final_answer(messages)
    (out_dir / f"{sid}.md").write_text((answer or "(최종 응답 없음)") + "\n", encoding="utf-8")
    (out_dir / f"{sid}.trace.json").write_text(
        json.dumps(steps, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    metrics = compute_metrics(steps, wall_s=meta.get("wall_s"), price=model_price(meta.get("model")))
    meta = {**meta, "metrics": metrics, "report_chars": len(answer)}
    (out_dir / f"{sid}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    flag = ""
    if metrics["eval_access_attempts"]:
        flag += f" ⚠️ eval 접근 시도 {metrics['eval_access_attempts']}건"
    if metrics["write_attempts"]:
        flag += f" ⚠️ 쓰기성 명령 {metrics['write_attempts']}건"
    if meta.get("error"):
        flag += f" ⚠️ 오류: {meta['error'][:120]}"
    print(f"[{meta['variant']}/{sid}] 저장 {out_dir / (sid + '.md')} "
          f"(단계 {metrics['total_steps']}, 토큰 {metrics['total_tokens']:,}){flag}")
    return meta


def write_metrics_md(out_dir: Path) -> str:
    rows = {}
    for meta_file in sorted(out_dir.glob("*.meta.json")):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        rows[meta["scenario_id"]] = meta["metrics"]
    if not rows:
        return ""
    table = metrics_table(rows)
    header = f"# 작업 방식 지표 — {out_dir.parent.name}/{out_dir.name}\n\n"
    (out_dir / "metrics.md").write_text(header + table, encoding="utf-8")
    return table


# ---------------------------------------------------------------------------
# 하위 명령
# ---------------------------------------------------------------------------
def run_suite(*, variant: str, scenario_ids: list[str], harness_dir: Path | None = None,
              run_set: str | None = None, runs_root: Path = RUNS, jobs: int = 4,
              recursion_limit: int = 200, deadline: int = 900, force: bool = False) -> Path:
    """시나리오들을 각각 새 thread·새 workspace 로 실행하고 결과 폴더를 돌려준다."""
    tracing = configure_tracing()
    run_set = run_set or kst_stamp()
    out_dir = (runs_root / run_set / variant).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    scenarios = load_scenarios()
    todo = [s for s in scenario_ids if force or not (out_dir / f"{s}.md").exists()]
    for s in set(scenario_ids) - set(todo):
        print(f"[{variant}/{s}] 이미 있어 건너뜀(--force 로 덮어쓰기)")
    print(f"결과 폴더: {out_dir}")
    print(f"variant={variant} run_set={run_set} model={model_name()} tracing={'on → ' + project_name() if tracing else 'off'}")
    if not todo:
        write_metrics_md(out_dir)
        return out_dir

    with tempfile.TemporaryDirectory(prefix="log-trace-sandbox-") as tmp:
        tmp_path = Path(tmp)
        if harness_dir is None:
            harness = make_sandbox(ROOT, tmp_path)
        else:
            harness = Path(harness_dir).resolve()
            if (harness / "eval").exists() or not (harness / HARNESS_ENTRY).is_file():
                raise SystemExit(f"하네스 경로가 올바르지 않습니다(eval/ 포함 또는 {HARNESS_ENTRY} 없음): {harness}")

        def one(sid: str) -> None:
            ws = tmp_path / f"ws-{sid}"
            qfile = tmp_path / f"q-{sid}.txt"
            qfile.write_text(scenarios[sid]["question"], encoding="utf-8")
            raw = tmp_path / f"out-{sid}.json"
            print(f"[{variant}/{sid}] 실행 중...")
            cmd = _worker_cmd(harness, ws, qfile, raw, sid, variant, run_set, recursion_limit, deadline)
            try:
                proc = subprocess.run(cmd, cwd=str(harness), env=_worker_env(variant),
                                      capture_output=True, text=True, encoding="utf-8",
                                      errors="replace", timeout=deadline + 120)
                log = (proc.stdout or "") + (proc.stderr or "")
            except subprocess.TimeoutExpired:
                log = "TIMEOUT"
            (out_dir / f"{sid}.log").write_text(log, encoding="utf-8")
            if not raw.exists():
                print(f"[{variant}/{sid}] 실패: 결과가 없습니다. {out_dir / (sid + '.log')} 를 확인하세요.")
                return
            data = json.loads(raw.read_text(encoding="utf-8"))
            meta = {
                "scenario_id": sid, "variant": variant, "run_set": run_set, "model": model_name(),
                "role": "agent", "trace_id": data.get("trace_id"), "wall_s": data.get("wall_s"),
                "error": data.get("error"), "project": project_name() if tracing else None,
            }
            meta["trace_url"] = trace_url(meta["trace_id"]) if tracing else None
            write_result(out_dir, sid, messages=data["messages"], steps=data["steps"], meta=meta)

        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            list(pool.map(one, todo))

    table = write_metrics_md(out_dir)
    if table:
        print("\n" + table)
    return out_dir


def cmd_run(args: argparse.Namespace) -> None:
    run_suite(
        variant=args.variant, scenario_ids=select_scenarios(args.scenarios),
        harness_dir=Path(args.harness_dir) if args.harness_dir else None,
        run_set=args.run_set, runs_root=Path(args.runs_root).resolve(), jobs=args.jobs,
        recursion_limit=args.recursion_limit, deadline=args.deadline, force=args.force,
    )


def cmd_worker(args: argparse.Namespace) -> None:
    """[내부] 샌드박스 안에서 에이전트 1회 실행. 결과는 --out JSON 으로만 넘긴다."""
    from trace_metrics import TraceRecorder

    harness = Path(args.harness_dir).resolve()
    ws = Path(args.workspace).resolve()
    if ws.exists():
        shutil.rmtree(ws)
    (ws / "input").mkdir(parents=True)
    shutil.copytree(harness / "mock_data" / "logs", ws / "input" / "logs")
    os.environ["WORKSPACE_DIR"] = str(ws)
    os.chdir(harness)
    sys.path.insert(0, str(harness))

    import importlib.util

    result: dict[str, Any] = {"messages": [], "steps": [], "error": None}
    recorder = TraceRecorder()
    trace_id = uuid.uuid4()
    t0 = time.time()
    try:
        spec = importlib.util.spec_from_file_location("harness_under_test", harness / HARNESS_ENTRY)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        config = run_config(role="agent", variant=args.variant, scenario_id=args.scenario_id,
                            run_set=args.run_set)
        config.update({
            "callbacks": [recorder], "recursion_limit": args.recursion_limit,
            "run_id": trace_id, "run_name": f"log-trace {args.variant} {args.scenario_id}",
            # 시나리오마다 새 thread 다(체크포인터 없음). thread_id 는 trace 검색용이다.
            "configurable": {"thread_id": f"{args.run_set}-{args.variant}-{args.scenario_id}"},
        })
        question = Path(args.question_file).read_text(encoding="utf-8")
        state = None
        deadline = t0 + args.deadline if args.deadline > 0 else None
        for state in module.agent.stream({"messages": [{"role": "user", "content": question}]},
                                         config=config, stream_mode="values"):
            if deadline and time.time() > deadline:
                result["error"] = f"deadline {args.deadline}s 초과(부분 기록)"
                break
        result["messages"] = [_msg_dict(m) for m in (state or {}).get("messages", [])]
    except Exception as exc:  # noqa: BLE001 - 실패해도 지금까지의 기록을 남긴다
        import traceback

        result["error"] = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    result["wall_s"] = round(time.time() - t0, 1)
    result["steps"] = recorder.dump()
    result["trace_id"] = str(trace_id)
    try:
        from langchain_core.tracers.langchain import wait_for_all_tracers

        wait_for_all_tracers()
    except Exception:  # noqa: BLE001
        pass
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, default=str), encoding="utf-8")


def _latest_run_set(variant: str) -> str | None:
    sets = sorted(p.parent.name for p in RUNS.glob(f"*/{variant}") if p.is_dir()) if RUNS.is_dir() else []
    return sets[-1] if sets else None


def cmd_save(args: argparse.Namespace) -> None:
    """Studio 에서 실행한 대화(thread)의 최종 보고서와 trace 지표를 저장한다."""
    import httpx

    if args.scenario not in load_scenarios():
        raise SystemExit(f"알 수 없는 시나리오: {args.scenario}")
    response = httpx.get(f"{args.server.rstrip('/')}/threads/{args.thread_id}/state", timeout=30)
    response.raise_for_status()
    messages = (response.json().get("values") or {}).get("messages") or []
    run_set = args.run_set or (None if args.new else _latest_run_set(args.variant)) or kst_stamp()
    out_dir = RUNS / run_set / args.variant
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / f"{args.scenario}.md").exists() and not args.force:
        raise SystemExit(f"{out_dir / (args.scenario + '.md')} 가 이미 있습니다. 덮어쓰려면 --force")

    steps, trace_id, url = None, None, None
    if configure_tracing():
        try:
            from langsmith import Client

            client = Client()
            trace_id = find_trace_id_for_thread(client, project_name(), args.thread_id)
            if trace_id:
                steps = steps_from_langsmith(client, trace_id)
                url = trace_url(str(trace_id))
        except Exception as exc:  # noqa: BLE001
            print(f"[save] LangSmith trace 조회 실패, 메시지로 지표를 계산합니다: {exc}")
    if steps is None:
        steps = steps_from_messages(messages)
    meta = {
        "scenario_id": args.scenario, "variant": args.variant, "run_set": run_set,
        "model": model_name(), "role": "agent", "thread_id": args.thread_id,
        "trace_id": str(trace_id) if trace_id else None, "trace_url": url,
        "project": project_name(), "wall_s": None, "error": None, "source": "studio",
    }
    write_result(out_dir, args.scenario, messages=messages, steps=steps, meta=meta)
    write_metrics_md(out_dir)


def cmd_metrics(args: argparse.Namespace) -> None:
    out_dir = Path(args.run_dir).resolve()
    if args.source == "langsmith":
        if not configure_tracing():
            raise SystemExit("LangSmith 키가 없어 trace 에서 지표를 다시 계산할 수 없습니다.")
        from langsmith import Client

        client = Client()
        for meta_file in sorted(out_dir.glob("*.meta.json")):
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if not meta.get("trace_id"):
                continue
            steps = steps_from_langsmith(client, meta["trace_id"])
            meta["metrics"] = compute_metrics(steps, wall_s=meta.get("wall_s"), price=model_price(meta.get("model")))
            meta["metrics_source"] = "langsmith"
            meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(write_metrics_md(out_dir) or "지표가 없습니다.")


def main() -> None:
    parser = argparse.ArgumentParser(description="S1~S4 헤드리스 실행·저장과 작업 방식 지표")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="시나리오를 샌드박스에서 헤드리스 실행")
    run.add_argument("--variant", default="baseline", help="baseline / v1 / ... (trace metadata)")
    run.add_argument("--scenarios", nargs="*", default=["all"], help="all 또는 S1 S2 ...")
    run.add_argument("--harness-dir", help="실행할 하네스 경로(meta-harness variant). 생략 시 현재 레포")
    run.add_argument("--run-set", help="실행 묶음 이름(기본: 현재 KST 시각)")
    run.add_argument("--runs-root", default=str(RUNS), help="결과 루트(기본 runs/)")
    run.add_argument("--jobs", type=int, default=4, help="동시 실행 시나리오 수")
    run.add_argument("--recursion-limit", type=int, default=200)
    run.add_argument("--deadline", type=int, default=900, help="시나리오별 시간 예산(초)")
    run.add_argument("--force", action="store_true", help="기존 보고서 덮어쓰기")
    run.set_defaults(func=cmd_run)

    save = sub.add_parser("save", help="Studio 대화(thread)의 최종 보고서·지표 저장")
    save.add_argument("scenario", help="시나리오 ID (예: S1)")
    save.add_argument("--thread-id", required=True)
    save.add_argument("--variant", default="studio", help="저장할 variant 폴더 이름(기본 studio)")
    save.add_argument("--server", default="http://127.0.0.1:2024")
    target = save.add_mutually_exclusive_group()
    target.add_argument("--new", action="store_true", help="새 KST run_set 을 만든다")
    target.add_argument("--run-set", help="저장할 run_set(생략 시 같은 variant 의 최근 run_set)")
    save.add_argument("--force", action="store_true")
    save.set_defaults(func=cmd_save)

    met = sub.add_parser("metrics", help="결과 폴더의 시나리오별 지표 표 출력·저장")
    met.add_argument("run_dir", help="runs/<run_set>/<variant>")
    met.add_argument("--source", choices=["local", "langsmith"], default="local",
                     help="langsmith: 업로드된 trace 에서 지표를 다시 계산")
    met.set_defaults(func=cmd_metrics)

    worker = sub.add_parser("__worker")
    for name in ("--harness-dir", "--workspace", "--question-file", "--out", "--scenario-id",
                 "--variant", "--run-set"):
        worker.add_argument(name, required=True)
    worker.add_argument("--recursion-limit", type=int, default=200)
    worker.add_argument("--deadline", type=int, default=900)
    worker.set_defaults(func=cmd_worker)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
