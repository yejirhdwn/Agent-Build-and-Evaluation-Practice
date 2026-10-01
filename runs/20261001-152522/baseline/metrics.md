# 작업 방식 지표 — 20261001-152522/baseline

| 시나리오 | 총 단계 | LLM | 도구 | 같은 도구·인자 반복 | 도구 실패 | 실패 후 같은 재시도 | 토큰 | latency(s) | 비용($) | SKILL 먼저 읽음 | eval 접근 시도 | 쓰기성 명령 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 | 25 | 9 | 16 | 0 | 0 | 0 | 128,265 | 60.6 | 0.1199 | 예 | 0 | 0 |
| S2 | 30 | 12 | 18 | 0 | 0 | 0 | 169,407 | 67.3 | 0.1468 | 예 | 0 | 0 |
| S3 | 32 | 12 | 20 | 0 | 0 | 0 | 175,758 | 101.9 | 0.1589 | 예 | 0 | 0 |
| S4 | 34 | 12 | 22 | 0 | 0 | 0 | 203,029 | 74.9 | 0.1823 | 예 | 0 | 0 |

도구별 호출 횟수

- S1: search_incident_history 3, read_file 2, ls 2, grep 2, search_source 2, query_campaign 1, get_change_log 1, query_send_history 1, read_source 1, query_perf_summary 1
- S2: search_incident_history 3, get_batch_jobs 2, ls 2, query_table_status 2, grep 2, query_campaign 1, read_file 1, get_module_relations 1, query_perf_summary 1, get_change_log 1, search_source 1, read_source 1
- S3: grep 5, ls 3, search_source 3, read_file 2, search_incident_history 2, query_campaign 1, get_change_log 1, read_source 1, query_perf_summary 1, query_send_history 1
- S4: grep 4, ls 3, read_file 2, query_send_history 2, get_batch_jobs 2, search_source 2, read_source 2, search_incident_history 2, query_campaign 1, query_perf_summary 1, get_change_log 1
