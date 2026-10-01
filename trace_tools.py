"""교체 가능한 저장소를 사용하는 읽기 전용 캠페인 추적 도구.

VDI 반입 시 ``MockRepository``를 실제 읽기 전용 DB와 소스 색인을 사용하는
구현으로 교체한다. 공개 도구 함수의 이름과 인자 계약은 유지한다.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from langchain_core.tools import tool


_PROJECT_ROOT = Path(__file__).resolve().parent
_MOCK_ROOT = (_PROJECT_ROOT / "mock_data").resolve()
_SOURCE_ROOT = (_MOCK_ROOT / "source").resolve()


class MockRepository:
    """호출자가 전달한 경로를 사용하지 않는 목업 데이터 전용 읽기 저장소."""

    def __init__(self, root: Path = _MOCK_ROOT) -> None:
        self.root = root.resolve()
        if self.root != _MOCK_ROOT:
            raise ValueError("MockRepository는 mock_data 경로만 사용할 수 있습니다.")

    def _csv(self, relative_path: str) -> list[dict[str, str]]:
        path = (self.root / relative_path).resolve()
        if self.root not in path.parents:
            raise ValueError("mock_data 밖의 파일에는 접근할 수 없습니다.")
        with path.open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))

    def _json(self, relative_path: str) -> Any:
        path = (self.root / relative_path).resolve()
        if self.root not in path.parents:
            raise ValueError("mock_data 밖의 파일에는 접근할 수 없습니다.")
        return json.loads(path.read_text(encoding="utf-8"))

    def campaigns(self) -> list[dict[str, str]]:
        return self._csv("db/campaign.csv")

    def send_history(self) -> list[dict[str, str]]:
        return self._csv("db/send_history.csv")

    def send_summary(self) -> list[dict[str, str]]:
        return self._csv("db/send_summary.csv")

    def batch_jobs(self) -> list[dict[str, str]]:
        return self._csv("db/batch_jobs.csv")

    def relations(self) -> list[dict[str, str]]:
        return self._json("graph/module_relations.json")["relations"]

    def incidents(self) -> list[dict[str, Any]]:
        return self._json("incidents/incident_history.json")

    def source_path(self, class_name: str) -> Path | None:
        class_name = Path(class_name).name
        if not class_name.endswith(".java"):
            class_name += ".java"
        candidate = (_SOURCE_ROOT / class_name).resolve()
        if _SOURCE_ROOT not in candidate.parents:
            return None
        return candidate if candidate.is_file() else None

    def source_files(self) -> list[Path]:
        return sorted(_SOURCE_ROOT.glob("*.java"))

    def table_rows(self, table_name: str) -> list[dict[str, str]]:
        table_files = {
            "SEND_HIST": "db/send_history.csv",
            "SEND_SUMMARY": "db/send_summary.csv",
            "OFFER_RESULT": "db/offer_result.csv",
            "OFFER_RESP_HIST": "db/offer_resp_hist.csv",
            "CMP_PERF_SUM": "db/cmp_perf_sum.csv",
        }
        relative_path = table_files.get(table_name.upper())
        if not relative_path:
            return []
        return self._csv(relative_path)

    def change_log(self) -> list[dict[str, str]]:
        return self._csv("config/change_log.csv")


_REPOSITORY = MockRepository()


def _message(text: str) -> dict[str, str]:
    return {"message": text}


def _date_in_range(value: str, start_date: str, end_date: str) -> bool:
    try:
        current = date.fromisoformat(value[:10])
        return date.fromisoformat(start_date) <= current <= date.fromisoformat(end_date)
    except ValueError:
        return False


def _validate_limit(limit: int) -> str | None:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        return "limit은 1에서 100 사이의 정수여야 합니다."
    return None


@tool
def query_send_history(
    campaign_id: str = "", send_date: str = "", status: str = "", limit: int = 20
) -> dict[str, Any] | dict[str, str]:
    """발송 이력을 캠페인 ID, 발송일, 상태로 조회합니다.

    발송 흐름에서 로그 건수를 발송 이력과 교차 확인할 때 사용합니다. campaign_id,
    send_date(YYYY-MM-DD), status는 선택 조건이며, 결과는 상태·채널별 summary와
    개인정보가 포함될 수 있는 상세 행을 limit개까지 반환합니다. limit 기본값은
    20이고 최대 100입니다. 보고서에는 상세 행의 개인정보를 그대로 복사하지 마세요.
    """
    error = _validate_limit(limit)
    if error:
        return _message(error)
    rows = [
        row
        for row in _REPOSITORY.send_history()
        if (not campaign_id or row["cmp_id"] == campaign_id)
        and (not send_date or row["send_dt"] == send_date)
        and (not status or row["status"] == status)
    ]
    if not rows:
        return _message("조건에 맞는 발송 이력이 없습니다.")
    counts = Counter((row["status"], row["channel"]) for row in rows)
    return {
        "summary": [
            {"status": key[0], "channel": key[1], "count": count}
            for key, count in sorted(counts.items())
        ],
        "rows": rows[:limit],
        "total_matching_rows": len(rows),
    }


@tool
def get_batch_jobs(job_id: str = "") -> list[dict[str, str]] | dict[str, str]:
    """배치 잡의 스케줄, 선후행, 입출력 테이블, 주 클래스를 조회합니다.

    특정 단계의 앞뒤 흐름을 확인할 때 사용합니다. job_id를 생략하면 전체 읽기
    흐름을 반환하고, 지정하면 해당 잡만 반환합니다. 반환은 배치 메타데이터 행의
    목록이며 데이터 변경 기능은 없습니다.
    """
    rows = [row for row in _REPOSITORY.batch_jobs() if not job_id or row["job_id"] == job_id]
    return rows or _message("조건에 맞는 배치 잡이 없습니다.")


@tool
def get_module_relations(query: str) -> list[dict[str, str]] | dict[str, str]:
    """화면 ID, 클래스명, 배치 ID, 테이블명으로 모듈 관계를 조회합니다.

    결과 화면에서 테이블과 배치로 거슬러 올라가거나 특정 배치의 읽기·쓰기와
    호출 관계를 확인할 때 사용합니다. query는 화면, 클래스, 배치 ID, 테이블명 중
    하나이며 관계의 from, relation, to를 반환합니다. 테이블을 넣으면 그 테이블을
    읽거나 쓰는 모든 관계가 반환됩니다.
    """
    if not query.strip():
        return _message("화면 ID, 클래스명, 배치 ID 또는 테이블명을 입력하세요.")
    needle = query.strip().lower()
    rows = [
        row
        for row in _REPOSITORY.relations()
        if needle in row["from"].lower() or needle in row["to"].lower()
    ]
    return rows or _message("조건에 맞는 모듈 관계가 없습니다.")


@tool
def read_source(class_name: str, start_line: int = 1, end_line: int = 200) -> dict[str, Any] | dict[str, str]:
    """가상 Java 클래스의 지정 줄 범위를 줄 번호와 함께 읽습니다.

    로그의 클래스와 관계 도구가 찾은 클래스를 소스 근거로 확인할 때 사용합니다.
    class_name은 클래스명이며 .java 확장자는 선택입니다. start_line과 end_line은
    1-based 범위이고 최대 200줄입니다. 반환은 source_file과 numbered_source입니다.
    """
    if start_line < 1 or end_line < start_line or end_line - start_line + 1 > 200:
        return _message("줄 범위는 1 이상이고 최대 200줄이어야 합니다.")
    path = _REPOSITORY.source_path(class_name)
    if path is None:
        return _message("해당 클래스를 찾을 수 없습니다.")
    lines = path.read_text(encoding="utf-8").splitlines()
    selected = [f"{number}: {lines[number - 1]}" for number in range(start_line, min(end_line, len(lines)) + 1)]
    return {"source_file": path.name, "numbered_source": selected}


@tool
def search_source(keyword: str) -> list[dict[str, Any]] | dict[str, str]:
    """가상 Java 소스를 키워드로 검색해 파일명과 줄 번호를 반환합니다.

    클래스명, 테이블명, SQL 조각, 메서드명을 찾을 때 사용합니다. keyword는 비어
    있지 않은 텍스트 검색어이며 반환 각 항목은 source_file, line, text를 가집니다.
    """
    if not keyword.strip():
        return _message("검색어를 입력하세요.")
    results: list[dict[str, Any]] = []
    for path in _REPOSITORY.source_files():
        for line_number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if keyword.casefold() in text.casefold():
                results.append({"source_file": path.name, "line": line_number, "text": text})
    return results or _message("소스에서 검색어를 찾지 못했습니다.")


@tool
def search_incident_history(keyword: str = "", batch_id: str = "", result_code: str = "") -> list[dict[str, Any]] | dict[str, str]:
    """과거 장애 이력을 키워드, 배치 ID, 결과 코드로 검색합니다.

    현재 증상과 과거 사례의 같은 점과 다른 점을 비교할 때 사용합니다. 조건은
    선택 사항이며 keyword는 incident의 모든 문자열 필드를 검색합니다. 반환은
    incident_id, batch_id, result_code, summary, resolution, date 목록입니다.
    """
    needle = keyword.casefold().strip()
    rows = []
    for row in _REPOSITORY.incidents():
        values = " ".join(str(value) for value in row.values()).casefold()
        if (not needle or needle in values) and (not batch_id or row["batch_id"] == batch_id) and (not result_code or row["result_code"] == result_code):
            rows.append(row)
    return rows or _message("조건에 맞는 과거 장애 이력이 없습니다.")


@tool
def query_campaign(campaign_id: str) -> dict[str, str] | dict[str, str]:
    """캠페인의 발송일, 예상 대상 수, 오퍼, 템플릿, 채널을 조회합니다.

    문의에서 캠페인 ID를 정규화하고 B01 대상 수와 이후 발송 흐름을 시작할 때
    사용합니다. 반환은 campaign.csv의 해당 한 행입니다.
    """
    rows = [row for row in _REPOSITORY.campaigns() if row["cmp_id"] == campaign_id]
    return rows[0] if rows else _message("해당 캠페인을 찾을 수 없습니다.")


@tool
def query_table_status(table_name: str, start_date: str, end_date: str) -> list[dict[str, Any]] | dict[str, str]:
    """날짜 범위의 테이블별 적재 건수와 마지막 적재 시각을 조회합니다.

    결과 화면 값이 이상할 때 집계 배치의 원천 테이블이 최근에도 갱신됐는지
    확인하는 데 사용합니다. table_name은 논리 테이블명, 날짜는 YYYY-MM-DD이며,
    반환은 date, loaded_count, last_loaded_at 목록입니다.
    """
    try:
        date.fromisoformat(start_date)
        date.fromisoformat(end_date)
    except ValueError:
        return _message("날짜는 YYYY-MM-DD 형식이어야 합니다.")
    if start_date > end_date:
        return _message("시작일은 종료일보다 늦을 수 없습니다.")
    rows = _REPOSITORY.table_rows(table_name)
    if not rows:
        return _message("조회할 수 있는 테이블이 아니거나 데이터가 없습니다.")
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        timestamp = row.get("loaded_at") or row.get("aggregated_at") or row.get("send_dt", "")
        if timestamp and _date_in_range(timestamp, start_date, end_date):
            grouped.setdefault(timestamp[:10], []).append(row)
    return [
        {"date": key, "loaded_count": len(value), "last_loaded_at": max((row.get("loaded_at") or row.get("aggregated_at") or row.get("send_dt", "") for row in value))}
        for key, value in sorted(grouped.items())
    ] or _message("해당 날짜 범위에 적재 기록이 없습니다.")


@tool
def query_perf_summary(campaign_id: str) -> dict[str, str] | dict[str, str]:
    """화면이 읽는 CMP_PERF_SUM의 캠페인 성과 집계 행을 조회합니다.

    결과 화면의 대상 수, 발송 성공 수, 오퍼 성공 수를 확인하고 로그·원천 테이블과
    교차 검증할 때 사용합니다. 반환은 캠페인 한 행이며 없으면 명확한 메시지입니다.
    """
    rows = [row for row in _REPOSITORY._csv("db/cmp_perf_sum.csv") if row["cmp_id"] == campaign_id]
    return rows[0] if rows else _message("성과 집계 행을 찾을 수 없습니다.")


@tool
def get_change_log(start_date: str, end_date: str) -> list[dict[str, str]] | dict[str, str]:
    """날짜 범위의 설정·배포·소스 변경 이력을 조회합니다.

    로그 이상이 배포나 설정 변경과 시간상 겹치는지 확인할 때 사용합니다. 반환은
    change_id, changed_at, kind, object, before, after, note 목록입니다.
    """
    try:
        date.fromisoformat(start_date)
        date.fromisoformat(end_date)
    except ValueError:
        return _message("날짜는 YYYY-MM-DD 형식이어야 합니다.")
    if start_date > end_date:
        return _message("시작일은 종료일보다 늦을 수 없습니다.")
    rows = [row for row in _REPOSITORY.change_log() if _date_in_range(row["changed_at"], start_date, end_date)]
    return rows or _message("해당 날짜 범위의 변경 이력이 없습니다.")


def build_trace_tools() -> list[Any]:
    """에이전트 등록에 사용할 읽기 전용 추적 도구 목록을 반환한다."""
    return [
        query_send_history,
        get_batch_jobs,
        get_module_relations,
        read_source,
        search_source,
        search_incident_history,
        query_campaign,
        query_table_status,
        query_perf_summary,
        get_change_log,
    ]
