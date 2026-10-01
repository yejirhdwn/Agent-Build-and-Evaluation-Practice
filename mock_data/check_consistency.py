"""생성된 목업 로그·테이블 건수·정답 근거를 읽기 전용으로 검증한다."""

from __future__ import annotations

import csv
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "mock_data"
LOG_LINE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} \[(?:DEBUG|INFO |WARN |ERROR)\] \[[A-Z0-9_]+\] \[run=[^]]+\] \[[A-Za-z0-9]+\] .+$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def line_for(path: Path, pattern: str) -> str:
    matches = [line for line in path.read_text(encoding="utf-8").splitlines() if pattern in line]
    require(bool(matches), f"Missing expected line in {path.relative_to(ROOT)}: {pattern}")
    return matches[0]


def check_log_file(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    require(50 <= len(lines) <= 300, f"Log line count out of range: {path.relative_to(ROOT)} has {len(lines)}")
    for number, line in enumerate(lines, 1):
        require(LOG_LINE.match(line) is not None, f"Invalid log format: {path.relative_to(ROOT)}:{number}")
    return lines


def main() -> None:
    campaigns = read_csv(DATA / "db" / "campaign.csv")
    summary_rows = read_csv(DATA / "db" / "send_summary.csv")
    perf_rows = read_csv(DATA / "db" / "cmp_perf_sum.csv")
    campaign_by_id = {row["cmp_id"]: row for row in campaigns}
    summary = {(row["cmp_id"], row["status"]): int(row["count"]) for row in summary_rows}
    performance = {row["cmp_id"]: row for row in perf_rows}
    require(len(campaign_by_id) == 10, "Expected ten unique campaigns across 2026-09-22 through 2026-09-26")

    log_files = sorted((DATA / "logs").rglob("*.log"))
    require(len(log_files) == 30, f"Expected 30 batch logs, found {len(log_files)}")
    for path in log_files:
        check_log_file(path)

    for campaign in campaigns:
        cmp_id = campaign["cmp_id"]
        day = campaign["send_dt"]
        target = int(campaign["target_count"])
        b01 = DATA / "logs" / day / "B01_TARGET.log"
        b02 = DATA / "logs" / day / "B02_OFFER.log"
        b03 = DATA / "logs" / day / "B03_MSG.log"
        b04 = DATA / "logs" / day / "B04_CHNL_SEND.log"
        for path, needle, expected in (
            (b01, f"cmp_id={cmp_id} target_count=", target),
            (b02, f"cmp_id={cmp_id} output_count=", target),
            (b03, f"cmp_id={cmp_id} message_count=", target),
        ):
            line = line_for(path, needle)
            actual = int(re.search(r"(?:target_count|output_count|message_count)=(\d+)", line).group(1))
            require(actual == expected, f"{cmp_id}: {path.name} count {actual} != target {expected}")

        states = {status: summary.get((cmp_id, status), 0) for status in ("REQ", "SENT", "SUCC", "FAIL")}
        committed = states["SENT"] + states["SUCC"] + states["FAIL"]
        if cmp_id == "20260923CMP001":
            rollback = line_for(b04, f"Transaction rolled back. cmp_id={cmp_id}")
            require(f"rolled_back={target}" in rollback, f"{cmp_id}: rollback count does not match request count")
            require(sum(states.values()) == 0, f"{cmp_id}: rolled-back transaction must leave no send history")
            require("Send date mismatch." in b04.read_text(encoding="utf-8"), "S1 date mismatch evidence is missing")
        elif cmp_id == "20260926CMP001":
            progress = line_for(b04, f"Progress. cmp_id={cmp_id} processed=")
            processed = int(re.search(r"processed=(\d+)/", progress).group(1))
            require(processed == committed == 9000, f"{cmp_id}: partial progress and committed send counts differ")
            require(states["REQ"] == target - processed, f"{cmp_id}: remaining REQ count is inconsistent")
            require(f"Campaign end. cmp_id={cmp_id}" not in b04.read_text(encoding="utf-8"), "S4 campaign must not have an end line")
            require("Job finished." not in b04.read_text(encoding="utf-8"), "S4 must not have a job finished line")
            require(b04.read_text(encoding="utf-8").splitlines()[-1].find("Progress.") >= 0, "S4 log must end at its progress line")
        else:
            end = line_for(b04, f"Campaign end. cmp_id={cmp_id}")
            logged = int(re.search(r"sent_count=(\d+)", end).group(1))
            require(logged == committed == target, f"{cmp_id}: B04 and SEND_HIST counts differ")
            require(states["REQ"] == 0, f"{cmp_id}: completed campaign has remaining REQ rows")

        perf = performance[cmp_id]
        require(int(perf["target_count"]) == target, f"{cmp_id}: performance target count differs from campaign")
        require(int(perf["send_success_count"]) == states["SUCC"], f"{cmp_id}: performance send success differs from send summary")
        expected_offer_success = int(perf["offer_success_count"]) if day == "2026-09-22" else 0
        require(int(perf["offer_success_count"]) == expected_offer_success, f"{cmp_id}: unexpected offer aggregation value")

    old_table = read_csv(DATA / "db" / "offer_resp_hist.csv")
    new_table = read_csv(DATA / "db" / "offer_result.csv")
    old_latest = max(row["loaded_at"] for row in old_table)
    require(old_latest == "2026-09-23 02:20:00", "Legacy offer response table should have its final D+1 load on 2026-09-23")
    require(all(row["loaded_at"] >= "2026-09-24 01:30:00" for row in new_table), "Post-migration responses must be in OFFER_RESULT")
    for cmp_id, campaign in campaign_by_id.items():
        result_day = (datetime.strptime(campaign["send_dt"], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        r01 = DATA / "logs" / result_day / "R01_RESULT.log"
        r02 = DATA / "logs" / result_day / "R02_PERF_SUM.log"
        require(r01.is_file() and r02.is_file(), f"Missing D+1 result logs for {cmp_id}")
        expected_table = "OFFER_RESP_HIST" if result_day < "2026-09-24" else "OFFER_RESULT"
        loaded_line = line_for(r01, f"Offer responses loaded. cmp_id={cmp_id}")
        require(f"target_table={expected_table}" in loaded_line, f"{cmp_id}: R01 wrote to the wrong offer table")
        table_rows = old_table if expected_table == "OFFER_RESP_HIST" else new_table
        table_count = sum(int(row["response_count"]) for row in table_rows if row["cmp_id"] == cmp_id)
        logged_count = int(re.search(r"response_count=(\d+)", loaded_line).group(1))
        require(table_count == logged_count, f"{cmp_id}: R01 response rows differ from the destination table")
        old_success = sum(int(row["response_count"]) for row in old_table if row["cmp_id"] == cmp_id and row["response_status"] == "SUCCESS")
        expected_offer_success = old_success if expected_table == "OFFER_RESP_HIST" else 0
        aggregate_line = line_for(r02, f"Campaign end. cmp_id={cmp_id}")
        aggregate_offer_success = int(re.search(r"offer_success=(\d+)", aggregate_line).group(1))
        require(aggregate_offer_success == expected_offer_success, f"{cmp_id}: R02 aggregate does not match its legacy source table")
        require(int(performance[cmp_id]["offer_success_count"]) == expected_offer_success, f"{cmp_id}: screen summary does not match R02 output")

    for java_file in (DATA / "source").glob("*.java"):
        line_count = len(java_file.read_text(encoding="utf-8").splitlines())
        require(50 <= line_count <= 150, f"Java source line count out of range: {java_file.name} has {line_count}")

    customer_rows = read_csv(DATA / "db" / "cust_master.csv") + read_csv(DATA / "db" / "send_history.csv")
    for row in customer_rows:
        if row.get("phone"):
            require(re.fullmatch(r"010-0000-\d{4}", row["phone"]) is not None, f"Non-mock phone number found: {row['phone']}")

    answer_files = sorted((ROOT / "eval" / "answer_keys").glob("S*.md"))
    require([path.stem for path in answer_files] == ["S1", "S2", "S3", "S4"], "Expected S1-S4 answer keys")
    reference_pattern = re.compile(r"(mock_data/[^` ]+):(\d+)")
    for answer_file in answer_files:
        content = answer_file.read_text(encoding="utf-8")
        references = reference_pattern.findall(content)
        require(bool(references), f"No evidence references in {answer_file.name}")
        for relative, number in references:
            target_path = ROOT / relative
            lines = target_path.read_text(encoding="utf-8").splitlines()
            require(int(number) <= len(lines), f"Answer reference out of range: {relative}:{number}")

    print(f"Consistency checks passed: {len(campaigns)} campaigns, {len(log_files)} logs, {len(list((DATA / 'source').glob('*.java')))} Java sources, {sum(len(re.findall(reference_pattern, p.read_text(encoding='utf-8'))) for p in answer_files)} answer references.")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, OSError, ValueError) as error:
        print(f"Consistency check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error