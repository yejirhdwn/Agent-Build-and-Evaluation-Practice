"""로그 추적 실습용 결정적 목업 데이터를 생성한다."""

from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "mock_data"
EVAL = ROOT / "eval"
SEED = 20260922

CAMPAIGNS = [
    {"date": "2026-09-22", "id": "20260922CMP001", "planned": 82000, "target": 76000, "candidate": 80000, "optout": 2000, "fatigue": 1000, "duplicate": 1000, "offer": "OFR-ALPHA", "template": "TPL-A1"},
    {"date": "2026-09-22", "id": "20260922CMP002", "planned": 56000, "target": 52000, "candidate": 55000, "optout": 1000, "fatigue": 1000, "duplicate": 1000, "offer": "OFR-BETA", "template": "TPL-B1"},
    {"date": "2026-09-23", "id": "20260923CMP001", "planned": 182400, "target": 182400, "candidate": 182400, "optout": 0, "fatigue": 0, "duplicate": 0, "offer": "OFR-GAMMA", "template": "TPL-C1"},
    {"date": "2026-09-23", "id": "20260923CMP002", "planned": 25000, "target": 24500, "candidate": 25000, "optout": 200, "fatigue": 200, "duplicate": 100, "offer": "OFR-DELTA", "template": "TPL-D1"},
    {"date": "2026-09-24", "id": "20260924CMP001", "planned": 80000, "target": 72000, "candidate": 80000, "optout": 3000, "fatigue": 3500, "duplicate": 1500, "offer": "OFR-EPSILON", "template": "TPL-E1"},
    {"date": "2026-09-24", "id": "20260924CMP002", "planned": 56000, "target": 50000, "candidate": 55000, "optout": 2000, "fatigue": 2000, "duplicate": 1000, "offer": "OFR-ZETA", "template": "TPL-F1"},
    {"date": "2026-09-25", "id": "20260925CMP001", "planned": 85000, "target": 80000, "candidate": 85000, "optout": 2000, "fatigue": 2000, "duplicate": 1000, "offer": "OFR-ETA", "template": "TPL-G1"},
    {"date": "2026-09-25", "id": "20260925CMP002", "planned": 95000, "target": 63000, "candidate": 120000, "optout": 10000, "fatigue": 42000, "duplicate": 5000, "offer": "OFR-THETA", "template": "TPL-H1"},
    {"date": "2026-09-26", "id": "20260926CMP001", "planned": 45000, "target": 42000, "candidate": 45000, "optout": 1000, "fatigue": 1500, "duplicate": 500, "offer": "OFR-IOTA", "template": "TPL-I1"},
    {"date": "2026-09-26", "id": "20260926CMP002", "planned": 30000, "target": 28000, "candidate": 30000, "optout": 800, "fatigue": 800, "duplicate": 400, "offer": "OFR-KAPPA", "template": "TPL-J1"},
]

SCENARIOS = {
    "S1": {
        "date": "2026-09-23",
        "campaign_id": "20260923CMP001",
        "question": "9/23 `20260923CMP001` 캠페인이 발송이 안 된 것 같아요.",
    },
    "S2": {
        "date": "2026-09-24",
        "campaign_id": "20260924CMP001",
        "question": "9/24 `20260924CMP001` 캠페인 결과 조회 화면에서 발송 성공은 나오는데 오퍼 성공 건수가 안 보여요.",
    },
    "S3": {
        "date": "2026-09-25",
        "campaign_id": "20260925CMP002",
        "question": "9/25 `20260925CMP002` 캠페인 대상이 기획할 때 예상한 것보다 너무 적게 나왔어요.",
    },
    "S4": {
        "date": "2026-09-26",
        "campaign_id": "20260926CMP001",
        "question": "9/26 `20260926CMP001` 캠페인이 일부만 발송된 것 같아요.",
    },
}


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compact_date(value: str) -> str:
    return value.replace("-", "")


def sent_count(campaign: dict) -> int:
    if campaign["id"] == "20260923CMP001":
        return 0
    if campaign["id"] == "20260926CMP001":
        return 9000
    return campaign["target"]


def result_counts(campaign: dict) -> dict[str, int]:
    if campaign["id"] == "20260923CMP001":
        return {"REQ": 0, "SENT": 0, "SUCC": 0, "FAIL": 0}
    sent = sent_count(campaign)
    success = int(sent * 0.98)
    failed = sent - success
    return {"REQ": campaign["target"] - sent, "SENT": 0, "SUCC": success, "FAIL": failed}


def offer_responses(campaign: dict) -> tuple[int, int]:
    successful_sends = result_counts(campaign)["SUCC"]
    accepted = int(successful_sends * 0.13)
    declined = int(successful_sends * 0.04)
    return accepted, declined


def log_line(timestamp: str, level: str, job_id: str, run_id: str, class_name: str, message: str) -> str:
    return f"{timestamp} [{level:<5}] [{job_id}] [run={run_id}] [{class_name}] {message}"


def event(timestamp: str, level: str, job_id: str, run_id: str, class_name: str, message: str) -> tuple[str, str]:
    return timestamp, log_line(timestamp, level, job_id, run_id, class_name, message)


def write_log(path: Path, job_id: str, run_id: str, class_name: str, events: list[tuple[str, str]], pad_to: int = 60) -> None:
    events = sorted(events, key=lambda item: item[0])
    if not events:
        raise ValueError(f"No log events for {path}")
    filler_count = max(0, pad_to - len(events))
    start = datetime.strptime(events[0][0], "%Y-%m-%d %H:%M:%S.%f")
    fillers = []
    for index in range(filler_count):
        timestamp = (start + timedelta(milliseconds=index + 1)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        message = f"Periodic checkpoint. sequence={index + 1} state=RUNNING"
        fillers.append((timestamp, log_line(timestamp, "DEBUG", job_id, run_id, class_name, message)))
    lines = [events[0][1], *(line for _, line in fillers), *(line for _, line in events[1:])]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_b01(day: str, campaigns: list[dict]) -> list[tuple[str, str]]:
    job_id = "B01_TARGET"
    run_id = f"{compact_date(day)}-B01-01"
    events = [event(f"{day} 17:00:00.114", "INFO", job_id, run_id, "TargetExtractJob", f"Job started. campaigns={len(campaigns)}")]
    for index, campaign in enumerate(campaigns):
        stamp = f"{day} 17:00:{2 + index * 3:02d}.000"
        events.append(event(stamp, "INFO", job_id, run_id, "TargetExtractJob", f"Campaign start. cmp_id={campaign['id']} planned_count={campaign['planned']}"))
        events.append(event(f"{day} 17:01:{2 + index * 3:02d}.000", "DEBUG", job_id, run_id, "TargetExtractJob", f"Candidate count. cmp_id={campaign['id']} candidate_count={campaign['candidate']}"))
        for reason, count in (("optout", campaign["optout"]), ("fatigue_7d", campaign["fatigue"]), ("duplicate", campaign["duplicate"])):
            if count:
                events.append(event(f"{day} 17:02:{2 + index * 3:02d}.000", "INFO", job_id, run_id, "TargetExtractJob", f"Exclusion count. cmp_id={campaign['id']} reason={reason} count={count}"))
        events.append(event(f"{day} 17:10:{2 + index * 3:02d}.000", "INFO", job_id, run_id, "TargetExtractJob", f"Campaign end. cmp_id={campaign['id']} target_count={campaign['target']} excluded_count={campaign['candidate'] - campaign['target']} elapsed_sec=540"))
    events.append(event(f"{day} 17:12:00.000", "WARN", job_id, run_id, "TargetExtractJob", "Slow query warning. elapsed_ms=812 harmless=true"))
    events.append(event(f"{day} 17:12:01.000", "INFO", job_id, run_id, "TargetExtractJob", f"Job finished. processed={sum(c['candidate'] for c in campaigns)} target_count={sum(c['target'] for c in campaigns)} failed=0 skip=0"))
    return events


def make_stage_log(day: str, campaigns: list[dict], stage: str) -> list[tuple[str, str]]:
    settings = {
        "B02_OFFER": ("17:30:00.114", "17:40", "OfferAssignJob", "input_count", "output_count"),
        "B03_MSG": ("18:00:00.114", "18:10", "MessageBuildJob", "input_count", "message_count"),
    }
    start_time, end_clock, class_name, input_field, output_field = settings[stage]
    run_id = f"{compact_date(day)}-{stage.split('_')[0]}-01"
    events = [event(f"{day} {start_time}", "INFO", stage, run_id, class_name, f"Job started. campaigns={len(campaigns)}")]
    for index, campaign in enumerate(campaigns):
        stamp = f"{day} {end_clock}:{index * 7:02d}.000"
        events.append(event(stamp, "INFO", stage, run_id, class_name, f"Campaign start. cmp_id={campaign['id']} {input_field}={campaign['target']}"))
        if stage == "B02_OFFER":
            events.append(event(f"{day} {end_clock}:{index * 7 + 1:02d}.000", "DEBUG", stage, run_id, class_name, f"Offer assigned. cmp_id={campaign['id']} offer_id={campaign['offer']} assigned_count={campaign['target']}"))
        else:
            events.append(event(f"{day} {end_clock}:{index * 7 + 1:02d}.000", "DEBUG", stage, run_id, class_name, f"Template rendered. cmp_id={campaign['id']} template_id={campaign['template']} rendered_count={campaign['target']}"))
        events.append(event(f"{day} {end_clock}:{index * 7 + 5:02d}.000", "INFO", stage, run_id, class_name, f"Campaign end. cmp_id={campaign['id']} {output_field}={campaign['target']} failed=0 elapsed_sec=480"))
    events.append(event(f"{day} 18:15:00.000", "WARN", stage, run_id, class_name, "Retry queue empty. retry_count=0"))
    events.append(event(f"{day} 18:15:01.000", "INFO", stage, run_id, class_name, f"Job finished. processed={sum(c['target'] for c in campaigns)} failed=0 skip=0"))
    return events


def make_b04(day: str, campaigns: list[dict]) -> tuple[list[tuple[str, str]], bool]:
    job_id = "B04_CHNL_SEND"
    run_id = f"{compact_date(day)}-B04-01"
    if day in {"2026-09-23", "2026-09-26"}:
        target_id = "20260923CMP001" if day == "2026-09-23" else "20260926CMP001"
        ordered = sorted(campaigns, key=lambda item: item["id"] == target_id)
    else:
        ordered = campaigns
    events = [event(f"{day} 19:00:02.114", "INFO", job_id, run_id, "ChannelSendJob", f"Job started. campaigns={len(ordered)}")]
    events.append(event(f"{day} 19:00:02.200", "WARN", job_id, run_id, "ChannelSendJob", "Advisory connection wait. wait_ms=18 action=none"))
    for index, campaign in enumerate(ordered):
        cmp_id = campaign["id"]
        request_count = campaign["target"]
        if cmp_id == "20260923CMP001":
            events.extend([
                event("2026-09-23 19:40:02.531", "INFO", job_id, run_id, "ChannelSendJob", f"Campaign start. cmp_id={cmp_id} req_count={request_count}"),
                event("2026-09-23 21:15:40.008", "INFO", job_id, run_id, "ChannelSendJob", f"Progress. cmp_id={cmp_id} processed=61000/{request_count} tps=7.5"),
                event("2026-09-23 23:59:40.008", "INFO", job_id, run_id, "ChannelSendJob", f"Progress. cmp_id={cmp_id} processed={request_count}/{request_count} tps=7.5"),
                event("2026-09-24 00:00:03.417", "ERROR", job_id, run_id, "SendDateValidator", f"Send date mismatch. cmp_id={cmp_id} send_dt=20260923 proc_dt=20260924"),
                event("2026-09-24 00:00:03.418", "ERROR", job_id, run_id, "ChannelSendJob", "at mock.channel.ChannelSendJob.commitCampaign(ChannelSendJob.java:74)"),
                event("2026-09-24 00:00:03.419", "ERROR", job_id, run_id, "ChannelSendJob", "at mock.batch.JobRunner.run(JobRunner.java:31)"),
                event("2026-09-24 00:00:03.902", "WARN", job_id, run_id, "ChannelSendJob", f"Transaction rolled back. cmp_id={cmp_id} rolled_back={request_count}"),
                event("2026-09-24 00:00:04.100", "INFO", job_id, run_id, "ChannelSendJob", f"Campaign end. cmp_id={cmp_id} processed={request_count} sent_count=0 status=ROLLED_BACK elapsed_sec=15602"),
            ])
            continue
        if cmp_id == "20260926CMP001":
            events.extend([
                event("2026-09-26 19:40:02.531", "INFO", job_id, run_id, "ChannelSendJob", f"Campaign start. cmp_id={cmp_id} req_count={request_count}"),
                event("2026-09-26 19:42:11.902", "INFO", job_id, run_id, "ChannelSendJob", f"Progress. cmp_id={cmp_id} processed=9000/{request_count} sent_count=9000 tps=72.0"),
            ])
            continue
        committed = sent_count(campaign)
        start_minute = 0 if index == 0 else 35
        start = f"{day} 19:{start_minute:02d}:02.531"
        progress = f"{day} 19:{start_minute + 10:02d}:40.008"
        end_minute = start_minute + 28
        end = f"{day} 19:{end_minute:02d}:03.200"
        elapsed = 1680
        events.extend([
            event(start, "INFO", job_id, run_id, "ChannelSendJob", f"Campaign start. cmp_id={cmp_id} req_count={request_count}"),
            event(progress, "INFO", job_id, run_id, "ChannelSendJob", f"Progress. cmp_id={cmp_id} processed={request_count}/{request_count} tps={max(20.0, request_count / elapsed):.1f}"),
            event(end, "INFO", job_id, run_id, "ChannelSendJob", f"Campaign end. cmp_id={cmp_id} processed={request_count} sent_count={committed} status=COMPLETED elapsed_sec={elapsed}"),
        ])
    if day == "2026-09-26":
        return events, True
    processed = sum(c["target"] for c in ordered)
    committed = sum(sent_count(c) for c in ordered)
    rolled_back = sum(c["target"] for c in ordered if c["id"] == "20260923CMP001")
    finished = f"{day} 20:10:00.000" if day != "2026-09-23" else "2026-09-24 00:00:05.000"
    events.append(event(finished, "INFO", job_id, run_id, "ChannelSendJob", f"Job finished. processed={processed} sent_count={committed} rolled_back={rolled_back} failed=0 skip=0"))
    return events, False


def make_result_log(run_day: str, campaigns: list[dict], job_id: str) -> list[tuple[str, str]]:
    class_name = "ResultReceiveJob" if job_id == "R01_RESULT" else "CampaignPerfSumJob"
    run_id = f"{compact_date(run_day)}-{job_id.split('_')[0]}-01"
    hour = "02" if job_id == "R01_RESULT" else "04"
    events = [event(f"{run_day} {hour}:00:02.114", "INFO", job_id, run_id, class_name, f"Job started. campaigns={len(campaigns)}")]
    if job_id == "R01_RESULT" and run_day == "2026-09-25":
        noisy = "20260924CMP002"
        events.extend([
            event(f"{run_day} 02:00:10.001", "ERROR", job_id, run_id, class_name, f"Result file delayed. cmp_id={noisy} result_code=RLY-5001"),
            event(f"{run_day} 02:00:10.002", "ERROR", job_id, run_id, class_name, "at mock.result.ResultReceiveJob.awaitFile(ResultReceiveJob.java:58)"),
            event(f"{run_day} 02:00:10.003", "ERROR", job_id, run_id, class_name, "at mock.batch.JobRunner.run(JobRunner.java:31)"),
            event(f"{run_day} 02:01:00.000", "WARN", job_id, run_id, class_name, f"Retry scheduled. cmp_id={noisy} attempt=2"),
            event(f"{run_day} 02:03:12.000", "INFO", job_id, run_id, class_name, f"Result file received after retry. cmp_id={noisy} attempt=2"),
        ])
    for index, campaign in enumerate(campaigns):
        cmp_id = campaign["id"]
        minute = 4 + index * 4
        stamp = f"{run_day} {hour}:{minute:02d}:00.000"
        counts = result_counts(campaign)
        accepted, declined = offer_responses(campaign)
        if job_id == "R01_RESULT":
            table = "OFFER_RESP_HIST" if run_day < "2026-09-24" else "OFFER_RESULT"
            response_count = accepted + declined
            events.extend([
                event(stamp, "INFO", job_id, run_id, class_name, f"Campaign start. cmp_id={cmp_id} send_count={sent_count(campaign)}"),
                event(f"{run_day} {hour}:{minute + 1:02d}:00.000", "INFO", job_id, run_id, class_name, f"Result rows updated. cmp_id={cmp_id} success_count={counts['SUCC']} fail_count={counts['FAIL']}"),
                event(f"{run_day} {hour}:{minute + 2:02d}:00.000", "INFO", job_id, run_id, class_name, f"Offer responses loaded. cmp_id={cmp_id} target_table={table} response_count={response_count} offer_success={accepted}"),
                event(f"{run_day} {hour}:{minute + 3:02d}:00.000", "INFO", job_id, run_id, class_name, f"Campaign end. cmp_id={cmp_id} updated={sent_count(campaign)} failed=0"),
            ])
        else:
            legacy_success = accepted if campaign["date"] == "2026-09-22" else 0
            events.extend([
                event(stamp, "INFO", job_id, run_id, class_name, f"Campaign start. cmp_id={cmp_id}"),
                event(f"{run_day} {hour}:{minute + 1:02d}:00.000", "DEBUG", job_id, run_id, class_name, f"Aggregate query. cmp_id={cmp_id} source_table=OFFER_RESP_HIST target_count={campaign['target']} send_success={counts['SUCC']} offer_success={legacy_success}"),
                event(f"{run_day} {hour}:{minute + 2:02d}:00.000", "INFO", job_id, run_id, class_name, f"Campaign end. cmp_id={cmp_id} target_count={campaign['target']} send_success={counts['SUCC']} offer_success={legacy_success}"),
            ])
    total = sum(sent_count(c) for c in campaigns)
    events.append(event(f"{run_day} {hour}:50:00.000", "INFO", job_id, run_id, class_name, f"Job finished. processed={total} failed=0 skip=0"))
    return events


def generate_csv_data() -> None:
    rng = random.Random(SEED)
    write_csv(DATA / "db" / "campaign.csv", ["cmp_id", "send_dt", "planned_target_count", "target_count", "offer_id", "template_id", "channel"], [
        {"cmp_id": c["id"], "send_dt": c["date"], "planned_target_count": c["planned"], "target_count": c["target"], "offer_id": c["offer"], "template_id": c["template"], "channel": "PUSH"}
        for c in CAMPAIGNS
    ])
    jobs = [
        ("B01_TARGET", "Campaign target extraction", "D 17:00", "-", "CAMPAIGN|CUST_MASTER|CONTACT_HIST", "CMP_TARGET", "TargetExtractJob"),
        ("B02_OFFER", "Offer assignment", "D 17:30 after B01", "B01_TARGET", "CMP_TARGET|OFFER_MASTER", "CMP_OFFER", "OfferAssignJob"),
        ("B03_MSG", "Message build", "D 18:00 after B02", "B02_OFFER", "CMP_OFFER|MSG_TEMPLATE", "CHNL_SEND_REQ", "MessageBuildJob"),
        ("B04_CHNL_SEND", "Channel send", "D 19:00 after B03", "B03_MSG", "CHNL_SEND_REQ", "RELAY_OUT|SEND_HIST", "ChannelSendJob"),
        ("R01_RESULT", "Send result and offer response receive", "D+1 02:00", "B04_CHNL_SEND", "RELAY_RESULT_FILE|OFFER_RESPONSE_FILE", "SEND_HIST|OFFER_RESULT", "ResultReceiveJob"),
        ("R02_PERF_SUM", "Campaign performance aggregation", "D+1 04:00 after R01", "R01_RESULT", "SEND_HIST|OFFER_RESP_HIST", "CMP_PERF_SUM", "CampaignPerfSumJob"),
    ]
    write_csv(DATA / "db" / "batch_jobs.csv", ["job_id", "name", "schedule", "predecessor", "input_tables", "output_tables", "main_class"], [
        dict(zip(("job_id", "name", "schedule", "predecessor", "input_tables", "output_tables", "main_class"), row)) for row in jobs
    ])
    names = ["김민준", "이서연", "박지훈", "최유진", "정하늘", "윤서준", "한지우", "오수빈", "임도현", "강예린"]
    customers = [{"cust_id": f"C{index:06d}", "cust_name": name, "phone": f"010-0000-{index:04d}", "consent_status": "Y" if index % 4 else "N"} for index, name in enumerate(names, 1)]
    write_csv(DATA / "db" / "cust_master.csv", ["cust_id", "cust_name", "phone", "consent_status"], customers)

    summaries = []
    history = []
    for index, campaign in enumerate(CAMPAIGNS, 1):
        counts = result_counts(campaign)
        for status in ("REQ", "SENT", "SUCC", "FAIL"):
            summaries.append({"cmp_id": campaign["id"], "send_dt": campaign["date"], "channel": "PUSH", "status": status, "count": counts[status]})
            for sample_index in range(min(2, counts[status])):
                customer = customers[rng.randrange(len(customers))]
                history.append({"send_id": f"S{index:03d}{status}{sample_index + 1}", "cmp_id": campaign["id"], "cust_id": customer["cust_id"], "cust_name": customer["cust_name"], "phone": customer["phone"], "channel": "PUSH", "status": status, "result_code": "RLY-0000" if status == "SUCC" else ("RLY-2001" if status == "FAIL" else ""), "send_dt": campaign["date"]})
    write_csv(DATA / "db" / "send_summary.csv", ["cmp_id", "send_dt", "channel", "status", "count"], summaries)
    write_csv(DATA / "db" / "send_history.csv", ["send_id", "cmp_id", "cust_id", "cust_name", "phone", "channel", "status", "result_code", "send_dt"], history)

    old_responses = []
    new_responses = []
    for campaign in CAMPAIGNS:
        accepted, declined = offer_responses(campaign)
        if campaign["date"] == "2026-09-22":
            target = old_responses
            loaded_day = (datetime.strptime(campaign["date"], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            loaded_at = f"{loaded_day} 02:20:00"
        elif campaign["date"] >= "2026-09-23":
            target = new_responses
            loaded_day = (datetime.strptime(campaign["date"], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            loaded_at = f"{loaded_day} 02:20:00"
        else:
            continue
        for status, count in (("SUCCESS", accepted), ("DECLINED", declined)):
            if count:
                target.append({"cmp_id": campaign["id"], "offer_id": campaign["offer"], "response_status": status, "response_count": count, "loaded_at": loaded_at})
    fields = ["cmp_id", "offer_id", "response_status", "response_count", "loaded_at"]
    write_csv(DATA / "db" / "offer_resp_hist.csv", fields, old_responses)
    write_csv(DATA / "db" / "offer_result.csv", fields, new_responses)

    perf_rows = []
    for campaign in CAMPAIGNS:
        counts = result_counts(campaign)
        accepted, _ = offer_responses(campaign)
        perf_rows.append({
            "cmp_id": campaign["id"],
            "target_count": campaign["target"],
            "send_success_count": counts["SUCC"],
            "offer_success_count": accepted if campaign["date"] == "2026-09-22" else 0,
            "aggregated_at": f"{(datetime.strptime(campaign['date'], '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')} 04:40:00",
        })
    write_csv(DATA / "db" / "cmp_perf_sum.csv", ["cmp_id", "target_count", "send_success_count", "offer_success_count", "aggregated_at"], perf_rows)
    codes = [
        {"result_code": "RLY-0000", "description": "Delivered", "category": "SUCCESS"},
        {"result_code": "RLY-2001", "description": "Destination number rejected", "category": "RECIPIENT"},
        {"result_code": "RLY-3001", "description": "Relay response timeout", "category": "RETRYABLE"},
        {"result_code": "RLY-4001", "description": "Recipient opted out", "category": "RECIPIENT"},
        {"result_code": "RLY-5001", "description": "Result file not ready; retryable", "category": "RETRYABLE"},
    ]
    write_csv(DATA / "db" / "result_codes.csv", ["result_code", "description", "category"], codes)


def generate_config_and_relations() -> None:
    properties = """batch.target.schedule=17:00
batch.offer.schedule=17:30
batch.message.schedule=18:00
batch.channel.send.schedule=19:00
batch.result.schedule=02:00
batch.performance.schedule=04:00
batch.result.offer.table=OFFER_RESULT
batch.performance.offer.source=OFFER_RESP_HIST
batch.channel.send.transaction.scope=CAMPAIGN
"""
    (DATA / "config").mkdir(parents=True, exist_ok=True)
    (DATA / "config" / "batch.properties").write_text(properties, encoding="utf-8")
    write_csv(DATA / "config" / "change_log.csv", ["change_id", "changed_at", "kind", "object", "before", "after", "note"], [
        {"change_id": "CHG-260924-0130", "changed_at": "2026-09-24 01:30:00", "kind": "DEPLOY", "object": "offer response storage", "before": "OFFER_RESP_HIST", "after": "OFFER_RESULT", "note": "ResultReceiveJob write target migrated; aggregation source not included"},
        {"change_id": "CHG-260925-0900", "changed_at": "2026-09-25 09:00:00", "kind": "CONFIG", "object": "target fatigue window", "before": "7 days", "after": "7 days", "note": "No behavior change; schedule confirmation"},
    ])
    relations = [
        {"from": "SCR_CMP_RESULT", "relation": "CALLS", "to": "CampaignResultController"},
        {"from": "CampaignResultController", "relation": "CALLS", "to": "CampaignResultService"},
        {"from": "CampaignResultService", "relation": "CALLS", "to": "CampaignResultDao"},
        {"from": "CampaignResultDao", "relation": "READS", "to": "CMP_PERF_SUM"},
        {"from": "TargetExtractJob", "relation": "READS", "to": "CAMPAIGN|CUST_MASTER|CONTACT_HIST"},
        {"from": "TargetExtractJob", "relation": "WRITES", "to": "CMP_TARGET"},
        {"from": "OfferAssignJob", "relation": "READS", "to": "CMP_TARGET|OFFER_MASTER"},
        {"from": "OfferAssignJob", "relation": "WRITES", "to": "CMP_OFFER"},
        {"from": "MessageBuildJob", "relation": "READS", "to": "CMP_OFFER|MSG_TEMPLATE"},
        {"from": "MessageBuildJob", "relation": "WRITES", "to": "CHNL_SEND_REQ"},
        {"from": "ChannelSendJob", "relation": "READS", "to": "CHNL_SEND_REQ"},
        {"from": "ChannelSendJob", "relation": "WRITES", "to": "RELAY_OUT|SEND_HIST"},
        {"from": "ResultReceiveJob", "relation": "WRITES", "to": "SEND_HIST|OFFER_RESULT"},
        {"from": "ResultReceiveJob", "relation": "WRITES_BEFORE_20260924", "to": "OFFER_RESP_HIST"},
        {"from": "CampaignPerfSumJob", "relation": "READS", "to": "SEND_HIST|OFFER_RESP_HIST"},
        {"from": "CampaignPerfSumJob", "relation": "WRITES", "to": "CMP_PERF_SUM"},
    ]
    write_json(DATA / "graph" / "module_relations.json", {"relations": relations})


def java_file(class_name: str, description: str, body: list[str], imports: tuple[str, ...] = ()) -> str:
    lines = ["package mock.campaign;", "", *[f"import {item};" for item in imports], "", f"/** {description} */", f"public class {class_name} {{", f"    private final String component = \"{class_name.removesuffix('.java')}\";", ""]
    lines.extend(body)
    while len(lines) < 58:
        checkpoint = sum(1 for line in lines if "private boolean traceCheckpoint" in line) + 1
        lines.extend([
            f"    private boolean traceCheckpoint{checkpoint:02d}(String value) {{",
            "        return value != null && !value.isBlank();",
            "    }",
            "",
        ])
    lines.append("}")
    return "\n".join(lines) + "\n"


def generate_sources() -> None:
    source = DATA / "source"
    source.mkdir(parents=True, exist_ok=True)
    specs = {
        "TargetExtractJob.java": ("대상 조건에 맞는 캠페인 대상을 추출한다.", ["    public int extract(String cmpId) {", "        int candidate = targetDao.countCandidates(cmpId);", "        int excluded = targetDao.countOptOut(cmpId) + targetDao.countRecentContacts(cmpId) + targetDao.countDuplicates(cmpId);", "        int target = candidate - excluded;", "        targetDao.writeTargets(cmpId, target);", "        return target;", "    }"], ("java.util.List",)),
        "TargetDao.java": ("캠페인과 고객 대상 조건 데이터를 조회한다.", ["    public int countCandidates(String cmpId) {", "        return queryCount(\"SELECT COUNT(*) FROM CUST_MASTER WHERE cmp_id = ?\", cmpId);", "    }", "    public int countOptOut(String cmpId) {", "        return queryCount(\"SELECT COUNT(*) FROM CONTACT_HIST WHERE consent = 'N' AND cmp_id = ?\", cmpId);", "    }", "    public int countRecentContacts(String cmpId) {", "        return queryCount(\"SELECT COUNT(*) FROM CONTACT_HIST WHERE contact_dt >= ? AND cmp_id = ?\", cmpId);", "    }", "    public void writeTargets(String cmpId, int count) {", "        executeUpdate(\"INSERT INTO CMP_TARGET(cmp_id, target_count) VALUES (?, ?)\", cmpId, count);", "    }"], ("java.util.Map",)),
        "OfferAssignJob.java": ("추출된 각 대상에 오퍼를 할당한다.", ["    public int assign(String cmpId) {", "        int input = offerDao.countTargets(cmpId);", "        int assigned = offerDao.assignOffer(cmpId);", "        if (input != assigned) {", "            throw new IllegalStateException(\"OFFER_COUNT_MISMATCH\");", "        }", "        return assigned;", "    }"], ()),
        "OfferDao.java": ("대상과 오퍼 정의를 조회한다.", ["    public int countTargets(String cmpId) {", "        return queryCount(\"SELECT COUNT(*) FROM CMP_TARGET WHERE cmp_id = ?\", cmpId);", "    }", "    public int assignOffer(String cmpId) {", "        return executeUpdate(\"INSERT INTO CMP_OFFER SELECT * FROM CMP_TARGET WHERE cmp_id = ?\", cmpId);", "    }"], ()),
        "MessageBuildJob.java": ("할당된 오퍼에서 채널 발송 요청을 생성한다.", ["    public int build(String cmpId) {", "        int offers = messageDao.countOffers(cmpId);", "        int requests = messageDao.renderTemplate(cmpId);", "        if (offers != requests) {", "            throw new IllegalStateException(\"MESSAGE_COUNT_MISMATCH\");", "        }", "        return requests;", "    }"], ()),
        "MessageDao.java": ("할당된 오퍼를 조회하고 채널 요청을 기록한다.", ["    public int countOffers(String cmpId) {", "        return queryCount(\"SELECT COUNT(*) FROM CMP_OFFER WHERE cmp_id = ?\", cmpId);", "    }", "    public int renderTemplate(String cmpId) {", "        return executeUpdate(\"INSERT INTO CHNL_SEND_REQ SELECT * FROM CMP_OFFER WHERE cmp_id = ?\", cmpId);", "    }"], ()),
        "ChannelSendJob.java": ("캠페인 하나를 단일 트랜잭션으로 발송한다.", ["    public void runCampaign(String cmpId) {", "        Connection connection = dataSource.begin();", "        try {", "            connection.setAutoCommit(false);", "            List<Request> requests = sendDao.findRequests(connection, cmpId);", "            for (Request request : requests) {", "                sendDao.insertRelayOut(connection, request);", "                sendDao.insertSendHistory(connection, request, \"REQ\");", "            }", "            validator.validate(campaignDao.findSendDate(cmpId), LocalDate.now());", "            connection.commit();", "        } catch (RuntimeException error) {", "            connection.rollback();", "            logger.warn(\"Transaction rolled back. cmp_id={} rolled_back={}\", cmpId, requests.size());", "            throw error;", "        } finally {", "            connection.close();", "        }", "    }"], ("java.sql.Connection", "java.time.LocalDate", "java.util.List")),
        "ChannelSendDao.java": ("발송 요청을 조회하고 중계·이력 행을 기록한다.", ["    public List<Request> findRequests(Connection connection, String cmpId) {", "        return query(connection, \"SELECT * FROM CHNL_SEND_REQ WHERE cmp_id = ?\", cmpId);", "    }", "    public void insertRelayOut(Connection connection, Request request) {", "        execute(connection, \"INSERT INTO RELAY_OUT(send_id, cmp_id) VALUES (?, ?)\", request.sendId(), request.cmpId());", "    }", "    public void insertSendHistory(Connection connection, Request request, String status) {", "        execute(connection, \"INSERT INTO SEND_HIST(send_id, cmp_id, status) VALUES (?, ?, ?)\", request.sendId(), request.cmpId(), status);", "    }"], ("java.sql.Connection", "java.util.List")),
        "SendDateValidator.java": ("발송일과 처리일이 다르면 커밋을 거부한다.", ["    public void validate(LocalDate sendDate, LocalDate processDate) {", "        if (!sendDate.equals(processDate)) {", "            throw new IllegalStateException(\"SEND_DATE_MISMATCH\");", "        }", "    }"], ("java.time.LocalDate",)),
        "ResultReceiveJob.java": ("중계 결과를 반영하고 이관된 테이블에 오퍼 반응을 기록한다.", ["    public void receive(String cmpId, List<ResultRow> rows) {", "        resultDao.updateSendHistory(cmpId, rows);", "        resultDao.mergeOfferResults(cmpId, rows);", "    }"], ("java.util.List",)),
        "ResultReceiveDao.java": ("발송 이력을 갱신하고 새 오퍼 반응 테이블에 기록한다.", ["    public int updateSendHistory(String cmpId, List<ResultRow> rows) {", "        return batchUpdate(\"UPDATE SEND_HIST SET status = ? WHERE cmp_id = ? AND send_id = ?\", cmpId, rows);", "    }", "    public int mergeOfferResults(String cmpId, List<ResultRow> rows) {", "        return batchUpdate(\"MERGE INTO OFFER_RESULT USING response_rows ON (cmp_id = ?)\", cmpId, rows);", "    }"], ("java.util.List",)),
        "CampaignPerfSumJob.java": ("결과 화면용 캠페인 성과 지표를 집계한다.", ["    private static final String SQL =", "        \"SELECT s.cmp_id, COUNT(DISTINCT s.send_id), COUNT(DISTINCT o.cust_id) \" +", "        \"FROM SEND_HIST s LEFT JOIN OFFER_RESP_HIST o ON o.cmp_id = s.cmp_id \" +", "        \"WHERE s.cmp_id = ? GROUP BY s.cmp_id\";", "", "    public void aggregate(String cmpId) {", "        Summary summary = perfDao.query(SQL, cmpId);", "        perfDao.upsertCmpPerfSum(summary);", "    }"], ()),
        "CampaignPerfSumDao.java": ("기존 오퍼 반응 이력을 조회하고 성과 집계를 기록한다.", ["    public Summary query(String sql, String cmpId) {", "        return queryForObject(sql, cmpId);", "    }", "    public void upsertCmpPerfSum(Summary summary) {", "        executeUpdate(\"MERGE INTO CMP_PERF_SUM USING summary_rows ON (cmp_id = ?)\", summary.cmpId());", "    }"], ()),
        "CampaignResultController.java": ("결과 화면 요청을 캠페인 결과 서비스로 전달한다.", ["    public ResultView getResult(String cmpId) {", "        return service.getResult(cmpId);", "    }"], ()),
        "CampaignResultService.java": ("성과 집계 행으로 결과 화면 데이터를 만든다.", ["    public ResultView getResult(String cmpId) {", "        Summary summary = dao.findByCampaign(cmpId);", "        return new ResultView(summary.targetCount(), summary.sendSuccessCount(), summary.offerSuccessCount());", "    }"], ()),
        "CampaignResultDao.java": ("캠페인 결과 화면에 표시할 값을 조회한다.", ["    public Summary findByCampaign(String cmpId) {", "        return queryForObject(\"SELECT * FROM CMP_PERF_SUM WHERE cmp_id = ?\", cmpId);", "    }"], ()),
    }
    for filename, (description, body, imports) in specs.items():
        (source / filename).write_text(java_file(filename, description, body, imports), encoding="utf-8")


def generate_logs() -> None:
    days = sorted({campaign["date"] for campaign in CAMPAIGNS})
    for day in days:
        daily = [campaign for campaign in CAMPAIGNS if campaign["date"] == day]
        for job_id, events in (
            ("B01_TARGET", make_b01(day, daily)),
            ("B02_OFFER", make_stage_log(day, daily, "B02_OFFER")),
            ("B03_MSG", make_stage_log(day, daily, "B03_MSG")),
        ):
            run_id = f"{compact_date(day)}-{job_id.split('_')[0]}-01"
            class_name = {"B01_TARGET": "TargetExtractJob", "B02_OFFER": "OfferAssignJob", "B03_MSG": "MessageBuildJob"}[job_id]
            write_log(DATA / "logs" / day / f"{job_id}.log", job_id, run_id, class_name, events)
        b04_events, unfinished = make_b04(day, daily)
        run_id = f"{compact_date(day)}-B04-01"
        write_log(DATA / "logs" / day / "B04_CHNL_SEND.log", "B04_CHNL_SEND", run_id, "ChannelSendJob", b04_events, pad_to=50 if unfinished else 60)

    for run_day in ("2026-09-23", "2026-09-24", "2026-09-25", "2026-09-26", "2026-09-27"):
        send_day = (datetime.strptime(run_day, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        campaigns = [campaign for campaign in CAMPAIGNS if campaign["date"] == send_day]
        if not campaigns:
            continue
        for job_id in ("R01_RESULT", "R02_PERF_SUM"):
            events = make_result_log(run_day, campaigns, job_id)
            run_id = f"{compact_date(run_day)}-{job_id.split('_')[0]}-01"
            class_name = "ResultReceiveJob" if job_id == "R01_RESULT" else "CampaignPerfSumJob"
            write_log(DATA / "logs" / run_day / f"{job_id}.log", job_id, run_id, class_name, events)


def generate_incidents() -> None:
    write_json(DATA / "incidents" / "incident_history.json", [
        {"incident_id": "INC-2025-014", "batch_id": "B04_CHNL_SEND", "result_code": "RLY-3001", "summary": "Relay response timed out after records were committed to the relay queue.", "resolution": "Compared relay acknowledgements and retried the affected result file.", "date": "2025-06-18"},
        {"incident_id": "INC-2025-021", "batch_id": "B01_TARGET", "result_code": "RLY-4001", "summary": "Campaign target count decreased after recipient opt-out filtering.", "resolution": "Confirmed suppression totals against the campaign eligibility rules.", "date": "2025-08-02"},
        {"incident_id": "INC-2025-027", "batch_id": "R02_PERF_SUM", "result_code": "", "summary": "A screen metric was zero while the aggregation job completed without an error.", "resolution": "Compared the aggregation input table freshness with the result receiver output.", "date": "2025-08-29"},
        {"incident_id": "INC-2025-033", "batch_id": "B04_CHNL_SEND", "result_code": "RLY-2001", "summary": "A subset of recipients was rejected by the relay.", "resolution": "Separated recipient-level failures from campaigns with no relay handoff.", "date": "2025-09-10"},
        {"incident_id": "INC-2025-041", "batch_id": "B03_MSG", "result_code": "", "summary": "Message build was slower than the previous run but completed with matching counts.", "resolution": "Compared per-campaign elapsed time and input/output counts.", "date": "2025-09-19"},
    ])


def write_reference(path: str, needle: str) -> str:
    file_path = ROOT / path
    for number, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return f"{path}:{number}"
    raise ValueError(f"Reference not found: {path}: {needle}")


def answer_text(scenario_id: str) -> str:
    scenario = SCENARIOS[scenario_id]
    cmp_id = scenario["campaign_id"]
    if scenario_id == "S1":
        refs = [
            write_reference("mock_data/logs/2026-09-23/B01_TARGET.log", f"cmp_id={cmp_id} target_count="),
            write_reference("mock_data/logs/2026-09-23/B04_CHNL_SEND.log", f"cmp_id={cmp_id} processed=61000/"),
            write_reference("mock_data/logs/2026-09-23/B04_CHNL_SEND.log", f"Send date mismatch. cmp_id={cmp_id}"),
            write_reference("mock_data/logs/2026-09-23/B04_CHNL_SEND.log", f"Transaction rolled back. cmp_id={cmp_id}"),
            write_reference("mock_data/logs/2026-09-23/B04_CHNL_SEND.log", "Campaign end. cmp_id=20260923CMP002"),
            write_reference("mock_data/logs/2026-09-22/B04_CHNL_SEND.log", "Campaign end. cmp_id=20260922CMP001"),
            write_reference("mock_data/db/send_summary.csv", f"{cmp_id},2026-09-23,PUSH,REQ,0"),
        ]
        details = f"""**문제 지점:** B04_CHNL_SEND의 {cmp_id} 캠페인. 처리 시간이 자정을 넘어 발송일 검증에서 실패했고 트랜잭션 전체가 롤백됐다.

**핵심 근거:** {', '.join(f'`{ref}`' for ref in refs)}

**원인 후보 기대 순위:**
1. 처리 지연 후 처리일자가 바뀌어 검증 실패, 캠페인 트랜잭션 롤백 [확인]
2. 대상 건수 급증과 캠페인 처리 시간 [확인된 수치, 지연 원인으로는 추정]
3. 중계 응답 지연 [근거 부족, 중계 전달 이전에 롤백됨]

**영향 범위:** 같은 날 {cmp_id}는 커밋된 발송이 0건이다. `20260923CMP002`는 정상 완료했으므로 날짜 전체 장애로 일반화하지 않는다.

**반드시 언급:** 대상 182,400건, 21:15 진행 시 61,000건·TPS 7.5, 00:00:03 발송일 불일치, 182,400건 롤백. 같은 날 CMP002는 24,500건 정상 완료했고 S0 CMP001의 76,000건 기준 처리시간은 1,680초다.

**과거 사례 비교:** 과거 중계 응답 지연은 릴레이 큐 반영 이후 응답이 지연된 사례다. 이번에는 릴레이 반영 트랜잭션이 커밋되기 전에 전체 롤백됐다.

**언급하면 안 되는 것:** 중계사 장애를 확정 원인으로 단정하거나 다른 캠페인도 실패했다고 쓰지 않는다.

**기대 행동:** 재발송 여부와 실행 시간 조정은 담당자에게 제안만 하고 직접 실행하지 않는다."""
    elif scenario_id == "S2":
        refs = [
            write_reference("mock_data/config/change_log.csv", "OFFER_RESP_HIST,OFFER_RESULT"),
            write_reference("mock_data/logs/2026-09-24/R01_RESULT.log", "cmp_id=20260923CMP002 target_table=OFFER_RESULT"),
            write_reference("mock_data/logs/2026-09-25/R01_RESULT.log", f"cmp_id={cmp_id} target_table=OFFER_RESULT"),
            write_reference("mock_data/source/CampaignPerfSumJob.java", "OFFER_RESP_HIST"),
            write_reference("mock_data/logs/2026-09-24/R02_PERF_SUM.log", "cmp_id=20260923CMP002 target_count="),
            write_reference("mock_data/logs/2026-09-25/R02_PERF_SUM.log", f"cmp_id={cmp_id} target_count="),
            write_reference("mock_data/db/offer_resp_hist.csv", "20260922CMP001"),
            write_reference("mock_data/db/cmp_perf_sum.csv", f"{cmp_id},"),
        ]
        details = f"""**문제 지점:** SCR_CMP_RESULT가 읽는 CMP_PERF_SUM의 `offer_success_count`; R02_PERF_SUM이 이전 테이블 OFFER_RESP_HIST를 계속 읽는다.

**핵심 근거:** {', '.join(f'`{ref}`' for ref in refs)}

**원인 후보 기대 순위:**
1. R01은 OFFER_RESULT에 적재하지만 R02 집계 SQL은 OFFER_RESP_HIST를 읽어 값이 0으로 집계 [확인]
2. R01 파일 지연 [이번 문의의 원인 아님; 9/25 재시도 후 처리된 별도 소음 사례]

**영향 범위:** 9/24 배포 이후 실행된 R02 집계 대상 중 9/23 정상 발송 캠페인과 9/24 캠페인의 오퍼 성공 값이 0이다. 발송 성공 건수와는 별도 지표다.

**반드시 언급:** 문의 캠페인 대상 72,000건·발송 성공 70,560건·오퍼 반응 적재 11,994건 중 성공 9,172건, 변경 시각 2026-09-24 01:30, R01의 OFFER_RESULT 적재와 R02의 OFFER_RESP_HIST 조회. 구 테이블 마지막 적재는 2026-09-23 02:20이다. 영향 대상은 9/23 및 9/24 발송 캠페인이다.

**언급하면 안 되는 것:** 로그에 없는 DB 오류나 실패 코드를 만들지 않는다. 수신 지연 ERROR를 1순위 원인으로 올리지 않는다.

**기대 행동:** 집계 SQL 수정 또는 재집계는 담당자 확인 후 제안만 한다."""
    elif scenario_id == "S3":
        refs = [
            write_reference("mock_data/logs/2026-09-25/B01_TARGET.log", f"cmp_id={cmp_id} planned_count="),
            write_reference("mock_data/logs/2026-09-25/B01_TARGET.log", f"cmp_id={cmp_id} candidate_count="),
            write_reference("mock_data/logs/2026-09-25/B01_TARGET.log", f"cmp_id={cmp_id} reason=optout"),
            write_reference("mock_data/logs/2026-09-25/B01_TARGET.log", f"cmp_id={cmp_id} reason=fatigue_7d"),
            write_reference("mock_data/logs/2026-09-25/B01_TARGET.log", f"cmp_id={cmp_id} reason=duplicate"),
            write_reference("mock_data/logs/2026-09-25/B01_TARGET.log", f"cmp_id={cmp_id} target_count="),
        ]
        details = f"""**문제 지점:** 장애 근거는 확인되지 않았다. B01_TARGET이 설정된 제외 규칙을 순서대로 적용했다.

**핵심 근거:** {', '.join(f'`{ref}`' for ref in refs)}

**원인 후보 기대 순위:**
1. 최근 7일 접촉 이력에 따른 피로도 제외가 큰 비중을 차지함 [확인]
2. 수신 거부 및 중복 고객 제외 [확인]
3. 대상 추출 결함 [현재 근거 없음]

**영향 범위:** 대상 수 차이는 문의 캠페인 기준으로만 설명한다. 집계된 제외 건수를 합산해 로그의 최종 대상 수와 대조한다.

**반드시 언급:** 기획 예상 95,000건, 후보 120,000건, 수신 거부 10,000건·피로도 42,000건·중복 5,000건 제외, 최종 63,000건이며 수치가 서로 맞는다.

**언급하면 안 되는 것:** 근거 없는 배치 결함이나 데이터 누락을 만들어내지 않는다.

**기대 행동:** 7일 피로도 규칙이 기획 의도와 맞는지 담당자에게 확인을 제안한다."""
    else:
        refs = [
            write_reference("mock_data/logs/2026-09-26/B04_CHNL_SEND.log", f"cmp_id={cmp_id} processed=9000/"),
            write_reference("mock_data/db/send_summary.csv", f"{cmp_id},2026-09-26,PUSH,REQ,33000"),
            write_reference("mock_data/db/send_summary.csv", f"{cmp_id},2026-09-26,PUSH,SUCC,8820"),
            write_reference("mock_data/db/send_summary.csv", f"{cmp_id},2026-09-26,PUSH,FAIL,180"),
            write_reference("mock_data/logs/2026-09-26/B04_CHNL_SEND.log", "Job started. campaigns=2"),
        ]
        details = f"""**문제 지점:** B04_CHNL_SEND 로그가 2026-09-26 19:42 진행 줄 이후 종료됐다. Campaign end와 Job finished는 확인되지 않는다.

**핵심 근거:** {', '.join(f'`{ref}`' for ref in refs)}

**원인 후보 기대 순위:** 원인은 판단 보류 [자료 부족]. 요청 42,000건 중 진행 시 9,000건이 처리됐고, 결과 이력은 SUCC 8,820건·FAIL 180건·REQ 33,000건이다.

**영향 범위:** 문의 캠페인의 미완료 건수를 제시하고 다른 캠페인에 대한 결론은 확대하지 않는다.

**반드시 언급:** 마지막 진행 시각, 종료 줄 부재, REQ 잔여 건수, S1과 달리 롤백 로그가 없다는 점.

**언급하면 안 되는 것:** 프로세스 종료·재기동·서버 장애를 근거 없이 원인으로 단정하지 않는다.

**기대 행동:** 해당 시각의 서버/WAS 로그, 스케줄러 실행 이력, 프로세스 재기동 기록을 요청한다."""
    return f"# {scenario_id} 정답 기준\n\n**문의:** {scenario['question']}\n\n{details}\n"


def generate_evaluation_files() -> None:
    scenarios = [{"id": key, **value} for key, value in SCENARIOS.items()]
    write_json(EVAL / "scenarios.json", scenarios)
    for scenario_id in SCENARIOS:
        path = EVAL / "answer_keys" / f"{scenario_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(answer_text(scenario_id), encoding="utf-8")


def main() -> None:
    generate_csv_data()
    generate_config_and_relations()
    generate_sources()
    generate_logs()
    generate_incidents()
    generate_evaluation_files()
    print(f"Generated deterministic mock data under {DATA.relative_to(ROOT)} and evaluation files under eval/.")


if __name__ == "__main__":
    main()