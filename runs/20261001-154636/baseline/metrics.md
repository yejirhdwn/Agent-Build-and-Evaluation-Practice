# 작업 방식 지표 — 20261001-154636/baseline

| 시나리오 | 총 단계 | LLM | 도구 | 같은 도구·인자 반복 | 도구 실패 | 실패 후 같은 재시도 | 토큰 | latency(s) | 비용($) | SKILL 먼저 읽음 | eval 접근 시도 | 쓰기성 명령 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 | 25 | 7 | 18 | 0 | 0 | 0 | 116,797 | 40.5 | 0.1102 | 예 | 0 | 0 |
| S2 | 32 | 11 | 21 | 0 | 0 | 0 | 169,140 | 111.9 | 0.1467 | 예 | 0 | 0 |
| S3 | 28 | 10 | 18 | 0 | 0 | 0 | 146,275 | 91.4 | 0.1272 | 예 | 0 | 0 |
| S4 | 30 | 12 | 18 | 0 | 1 | 0 | 209,822 | 48.2 | 0.1778 | 예 | 0 | 0 |

도구별 호출 횟수

- S1: grep 5, read_file 3, search_incident_history 3, ls 2, query_campaign 1, get_change_log 1, query_send_history 1, read_source 1, query_perf_summary 1
- S2: ls 3, grep 3, get_module_relations 3, search_incident_history 3, read_file 2, query_table_status 2, query_campaign 1, query_perf_summary 1, get_batch_jobs 1, get_change_log 1, read_source 1
- S3: search_source 3, query_send_history 3, read_file 2, ls 2, grep 2, search_incident_history 2, query_campaign 1, get_change_log 1, get_module_relations 1, query_table_status 1
- S4: read_file 5, grep 5, ls 3, query_campaign 1, query_send_history 1, query_perf_summary 1, get_change_log 1, search_incident_history 1
