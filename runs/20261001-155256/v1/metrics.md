# 작업 방식 지표 — 20261001-155256/v1

| 시나리오 | 총 단계 | LLM | 도구 | 같은 도구·인자 반복 | 도구 실패 | 실패 후 같은 재시도 | 토큰 | latency(s) | 비용($) | SKILL 먼저 읽음 | eval 접근 시도 | 쓰기성 명령 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 | 30 | 10 | 20 | 0 | 0 | 0 | 161,524 | 53.5 | 0.1464 | 예 | 0 | 0 |
| S2 | 36 | 11 | 25 | 0 | 0 | 0 | 220,486 | 117.8 | 0.1866 | 예 | 0 | 0 |
| S3 | 30 | 10 | 20 | 0 | 0 | 0 | 169,808 | 83.9 | 0.1513 | 예 | 0 | 0 |
| S4 | 36 | 14 | 22 | 0 | 0 | 0 | 242,369 | 58.9 | 0.2037 | 예 | 0 | 0 |

도구별 호출 횟수

- S1: grep 5, read_source 3, ls 2, read_file 2, query_perf_summary 2, query_campaign 1, search_source 1, query_send_history 1, get_batch_jobs 1, get_change_log 1, search_incident_history 1
- S2: read_file 5, ls 3, get_module_relations 3, grep 3, search_incident_history 3, query_perf_summary 2, query_table_status 2, query_campaign 1, get_change_log 1, search_source 1, read_source 1
- S3: search_source 4, read_file 3, grep 3, search_incident_history 3, ls 2, query_campaign 1, get_change_log 1, query_perf_summary 1, query_send_history 1, read_source 1
- S4: grep 6, search_incident_history 4, read_file 2, ls 2, read_source 2, query_campaign 1, query_send_history 1, get_batch_jobs 1, query_perf_summary 1, search_source 1, get_change_log 1
