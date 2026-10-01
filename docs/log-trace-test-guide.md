# 로그 추적 에이전트 테스트 가이드

이 문서는 저장소를 내려받아 로그 기반 원인 추적 에이전트를 Codespace에서 실행하고, S1~S4 시나리오를 LangSmith Observation과 LLM Judge로 평가하는 방법을 설명한다. 개선 에이전트(meta-harness)로 고도화하는 방법도 함께 다룬다.

## 1. 테스트 범위

테스트 대상은 다음 흐름이다.

- 캠페인 발송 로그를 읽고 문제 단계를 찾는가
- 읽기 전용 조회 도구로 발송 이력·배치·관계·소스·변경 이력을 교차 확인하는가
- 확인된 사실과 추정을 구분하는가
- 개인정보를 마스킹하는가
- 자료가 부족할 때 원인을 지어내지 않고 추가 자료를 요청하는가
- 작업 방식이 효율적인가(같은 도구 반복, 실패 재시도, SKILL 선독, 정답 접근 시도 등)

S1~S4의 정답은 `eval/answer_keys/`에 있다. 정답은 Judge에게만 전달되고 에이전트 실행 환경에는 복사되지 않는다. 평가가 끝날 때까지 정답 내용을 에이전트 대화에 붙여넣지 않는다.

## 2. 사전 준비

### 필수 조건

- Python과 `uv`가 설치된 Codespace
- OpenRouter API 키
- LangSmith 계정과 API 키

### `.env`

```bash
cp .env.example .env
```

```dotenv
# 모델 — 변수 이름은 OPENAI_API_KEY 지만 OpenRouter 키(sk-or-...)를 넣는다
OPENAI_API_KEY=sk-or-...
MODEL_NAME=moonshotai/kimi-k3
MODEL_BASE_URL=https://openrouter.ai/api/v1

# LangSmith Observation
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=log-trace-agent
LANGSMITH_ENDPOINT=https://api.smith.langchain.com   # EU 리전은 https://eu.api.smith.langchain.com

# LLM Judge (선택) — 비우면 MODEL_NAME 을 temperature 0 으로 사용
JUDGE_MODEL_NAME=
```

- 트레이싱 프로젝트 이름은 `log-trace-agent`이고, 코드는 `LANGSMITH_PROJECT`만 읽는다. 프로젝트는 첫 trace가 들어올 때 자동으로 만들어진다.
- `LANGSMITH_API_KEY`가 비어 있으면 경고만 출력하고 트레이싱 없이 실행한다. 이때 LangSmith Dataset과 Experiment도 만들어지지 않지만, 로컬 채점(`comparison.md`)은 그대로 된다.
- Judge는 가능하면 에이전트와 다른 모델을 `JUDGE_MODEL_NAME`에 지정한다. OpenRouter 워크스페이스 guardrail에서 허용된 모델이어야 하며, 막혀 있으면 404 `guardrail restrictions` 오류가 난다. 비워 두면 에이전트 모델을 temperature 0으로 쓴다.
- 비용 지표는 OpenRouter 모델 가격표로 계산한다. 직접 단가를 지정하려면 `MODEL_PRICE_INPUT_PER_M`·`MODEL_PRICE_OUTPUT_PER_M`(100만 토큰당 USD)을 넣는다.
- `.env`는 `.gitignore`에 포함되어 있다. 커밋하거나 공유하지 않는다.

### 설치와 기본 검증

```bash
uv sync
uv run python mock_data/check_consistency.py
uv run python -m unittest discover -s tests -v
```

두 검사가 모두 통과해야 다음 단계로 진행한다.

### LangSmith 연결 확인 (짧은 테스트 1회)

시나리오 하나만 헤드리스로 실행한다(약 1~2분).

```bash
uv run python eval/run_scenarios.py run --variant smoke --scenarios S3
```

출력 첫 줄에 `tracing=on → log-trace-agent`가 보이고, 끝나면 `runs/<KST>/smoke/S3.meta.json`의 `trace_url`이 채워진다. LangSmith → **Tracing Projects → log-trace-agent**에서 `log-trace smoke S3` trace가 보이면 연결된 것이다. trace의 metadata에 `scenario_id=S3`, `variant=smoke`, `run_set=<KST>`, `model`, `role=agent`가 붙어 있다. 확인 후 `runs/<KST>/smoke/`는 지워도 된다.

## 3. 로그 적재 (Studio 실행용)

헤드리스 실행(`eval/run_scenarios.py`)은 시나리오마다 새 workspace를 만들고 로그를 자동으로 넣는다. Studio에서 직접 대화할 때만 로그를 workspace에 적재한다.

```bash
bash scripts/load_logs.sh
find workspace/input/logs -type f | wc -l   # 30
```

입력 로그는 `workspace/input/logs/`에 있고, 에이전트 화면에서는 `/input/logs/`로 보인다.

## 4. 서버와 LangSmith Studio 연결

별도 터미널에서 실행한다.

```bash
LANGGRAPH_TUNNEL=0 uv run python langchain-deepagents.py
```

서버는 기본 포트 `2024`에서 그래프 두 개를 서빙한다.

| 그래프 | 역할 | 셸 허용 |
|---|---|---|
| `deepagent` | 로그 추적 에이전트 | `date`만 (`META_HARNESS_ENABLED`를 켜지 않는다) |
| `harness-improver` | log-trace 에이전트를 meta-harness로 개선하는 에이전트 | `date`, `python skills/meta-harness/metaharness.py` |

포트 공개와 Studio 연결:

1. VS Code 하단 **PORTS** 탭에서 `2024` 포트의 **Port Visibility**를 **Public**으로 바꾼다.
2. **Forwarded Address**(`https://<codespace-name>-2024.app.github.dev`)를 복사한다.
3. LangSmith **Studio → Configure connection**의 Base URL에 붙여 넣는다. 끝의 `/`는 넣지 않는다.
4. 도메인 허용 경고가 나오면 허용한다.
5. 그래프를 선택하고 **Chat**으로 바꾼다.

`curl http://127.0.0.1:2024/ok`가 `{"ok":true}`면 서버가 살아 있다. Studio에서 실행한 대화도 `log-trace-agent` 프로젝트에 `role=agent`(또는 `role=improver`) 태그로 기록된다.

## 5. 시나리오 실행과 보고서 저장

에이전트는 질문 텍스트만 받으므로 자신이 몇 번 시나리오인지 모른다. 시나리오 ID·variant·실행 묶음(run_set)과 저장 위치는 실행 스크립트 `eval/run_scenarios.py`가 정하고 trace metadata로 붙인다. 질문에 `[S1]` 같은 태그를 붙이지 않는다.

```text
runs/<run_set KST YYYYMMDD-HHMMSS>/<variant>/
  S1.md          최종 보고서
  S1.trace.json  단계별 실행 기록(LLM·도구 호출, 토큰, latency, 오류)
  S1.meta.json   scenario_id·variant·run_set·model·trace_id·trace_url·작업 방식 지표
  metrics.md     시나리오별 작업 방식 지표 표
  S1.judge.json  Judge 판정(채점 후)
  comparison.md  시나리오×항목 판정표(채점 후)
```

### 방법 A: 헤드리스 일괄 실행

```bash
uv run python eval/run_scenarios.py run --variant baseline --scenarios all
uv run python eval/run_scenarios.py run --variant baseline --scenarios S2 S4 --run-set <기존 run_set>
```

- 에이전트는 레포 밖 임시 샌드박스에서 실행된다. 샌드박스에는 `eval/`·`runs/`·`.env`·`.git`이 복사되지 않으므로 경로가 분리된다. 셸도 `date`만 허용된다.
- 시나리오마다 새 thread와 새 workspace를 쓰고, 기본 4개를 동시에 실행한다(`--jobs`).
- 기존 보고서는 건너뛴다. 덮어쓰려면 `--force`를 붙인다.

### 방법 B: LangSmith Studio에서 실행

1. `eval/scenarios.json`에서 해당 시나리오의 `question`을 복사한다.
2. `deepagent` 그래프에서 **New Thread**를 열고 질문만 붙여 넣는다. 시나리오마다 반드시 새 thread를 쓴다.
3. 응답이 끝나면 thread ID를 복사해 저장한다. 첫 시나리오는 `--new`로 새 run_set을 만들고, 나머지는 `--new` 없이 같은 run_set에 이어 저장한다.

```bash
uv run python eval/run_scenarios.py save S1 --thread-id <thread-id> --variant studio --new
uv run python eval/run_scenarios.py save S2 --thread-id <thread-id> --variant studio
```

`save`는 LangSmith에서 thread의 trace를 찾아 작업 방식 지표를 계산한다. trace를 찾지 못하면 대화 메시지로 계산하며, 이때 latency는 비어 있다.

### 작업 방식 지표

실행이 끝나면 시나리오별 표가 출력되고 `metrics.md`에 저장된다. 다시 보려면 다음 명령을 쓴다. `--source langsmith`를 붙이면 업로드된 trace에서 다시 계산한다.

```bash
uv run python eval/run_scenarios.py metrics runs/<run_set>/<variant> [--source langsmith]
```

| 지표 | 의미 |
|---|---|
| 총 단계 / LLM / 도구 | LLM 호출과 도구 호출 수 |
| 같은 도구·인자 반복 | 같은 도구를 같은 인자로 다시 부른 횟수 |
| 도구 실패 / 실패 후 같은 재시도 | 오류 응답 수, 실패한 호출을 같은 인자로 다시 한 횟수 |
| 토큰 / latency / 비용 | 입력+출력 토큰, 실행 시간(초), 추정 비용(USD) |
| SKILL 먼저 읽음 | 첫 도구 호출 묶음에서 `skills/log-trace/SKILL.md`를 읽었는가 |
| eval 접근 시도 | 도구 인자에 `eval/`·`answer_keys`·`runs/` 등이 들어간 횟수 |
| 쓰기성 명령 | `write_file`·`edit_file`, `date` 외 셸 명령 시도 |

## 6. LLM Judge 채점

```bash
uv run python eval/judge.py score runs/<run_set>/<variant>
```

- Judge는 보고서와 해당 시나리오 answer_key, 판정 기준 `eval/rubric.md`만 보고 9개 항목을 True/False로 판정한다(형태 b). 항목마다 보고서 인용 근거와 이유를 남기고, 1~5점 종합 점수와 이유(형태 a)도 남긴다.
- 결과는 `comparison.md`(판정표 + 근거), `S*.judge.json`, `scores.json`에 저장된다. 같은 보고서·정답·rubric·Judge 모델이면 캐시를 재사용하고, `--force`로 다시 채점한다.
- LangSmith 키가 있으면 다음도 함께 남는다.
  - Dataset `log-trace-eval-s1-s4`: input은 question, reference output은 answer_key다. 같은 이름이 있으면 예제만 갱신한다. `uv run python eval/judge.py sync-dataset`으로 따로 갱신할 수도 있다.
  - Experiment `<variant>-<run_set>-xxxx`: **Datasets & Experiments → log-trace-eval-s1-s4**에서 시나리오별 9개 항목 점수, `overall_score`, `pass_count`, `trace_*` 지표를 보고 각 행에서 에이전트 trace 링크(`agent_trace_url`)를 연다.
  - 원래 에이전트 trace(`log-trace-agent` 프로젝트)에 `judge_*` feedback이 붙는다.

### 판정표

| 항목 | 의미 |
|---|---|
| 문제 지점 일치 | 정답의 문제 지점과 같은 배치·단계·테이블, 같은 메커니즘 |
| 핵심 근거 파일·줄 번호 제시 | 결정적 근거의 과반을 `파일:줄`로 제시(±2줄 허용) |
| 원인 후보 순위 적절성 | 1순위가 정답 1순위와 일치. S4는 판단 보류 |
| 원본에 없는 값 사용 없음 | 정답과 모순되는 값이나 없는 오류를 만들지 않음 |
| 원인 단정 표현 없음 | 원인 후보로 제시하고 담당자 확인을 남김 |
| 개인정보 원문 노출 없음 | 이름·전화번호 원문, 불필요한 cust_id 없음 |
| 6단 보고서 순서 준수 | ①~⑥ 섹션이 모두 있고 순서대로 |
| 영향 범위 판단 | 정답 범위를 넓히지도 좁히지도 않음 |
| 시나리오별 함정 처리 | 언급하면 안 되는 것을 피하고 기대 행동을 지킴 |

판정 해석의 세부 기준은 [eval/rubric.md](../eval/rubric.md)에 있다. answer_key는 고치지 않고, 해석이 모호하면 rubric을 고친다.

### Judge 신뢰도 확인

사람 판정과 Judge 판정을 나란히 비교한다.

```bash
uv run python eval/judge.py human-template runs/<run_set>/<variant>   # human_labels.json 생성
# human_labels.json 에 직접 true/false 를 채운다(판정할 시나리오만)
uv run python eval/judge.py agree runs/<run_set>/<variant>            # agreement.md
```

어긋나는 항목이 있으면 `eval/rubric.md`를 먼저 고치고 `score --force`로 다시 채점한다.

## 7. 두 실행 비교 (baseline 대비)

baseline-v0 기준 점수는 [eval/baseline.json](../eval/baseline.json)이 가리키는 `runs/20261001-152522/baseline`이다.

```bash
uv run python eval/judge.py compare --a runs/20261001-152522/baseline --b runs/<run_set>/<variant>
```

- 비교 결과는 B 폴더의 `compare_vs_baseline@20261001-152522.md`에 저장된다.
  - 시나리오×항목 표: `A → B`로 보여주고, 바뀐 칸은 굵게 표시한다.
  - Pairwise(형태 c): 같은 시나리오끼리 A·B 순서와 B·A 순서로 두 번 판정한다. 두 번 모두 같은 보고서를 고를 때만 승리이고, 엇갈리면 무승부다.
  - trace 지표 비교표가 함께 들어간다.
- `--b`를 여러 번 주면 반복 실행을 함께 판정한다. 자동 판정의 기본값은 무승부다. 모든 반복에서 항목 회귀와 pairwise 패배 없이 개선이 있을 때만 승리로 본다.

## 8. 개선 에이전트(meta-harness) 사용법

개선 에이전트는 log-trace 에이전트를 레포 밖 격리 복제본으로 실행·수정·비교한다. 절차는 doctor → init → run → fork → edit → run → compare이고, 확실히 나은 변경만 사용자 승인 후 본체에 promote한다.

### Studio에서

`harness-improver` 그래프의 새 thread에 요청한다.

```text
meta-harness 스킬로 log-trace 에이전트를 S1~S4 평가 세트 기준으로 개선해줘.
baseline 을 --suite 로 실행·진단하고, 가설 하나로 v1 을 만들어 --repeat 2 로 실행한 뒤
compare --suite 로 판정해. promote 는 미리보기까지만 하고 멈춰서 보고해.
```

### 헤드리스로

```bash
uv run python harness_improver.py "<위 요청>"
```

실행 기록은 `runs/improver/<KST>/transcript.md`에 남는다. trace는 `log-trace-agent` 프로젝트에 `role=improver`로 기록되고, 개선 에이전트가 돌린 복제본 실행은 `role=agent`, `variant=v1` 등으로 기록된다.

### 지켜지는 원칙

- 개선 에이전트는 정답(`eval/`)을 읽을 수 없다. 파일 도구는 `workspace_improver/` 안으로 묶이고, 셸은 meta-harness CLI만 실행하며, CLI의 입력 파일은 `eval/`·`runs/`를 거부한다. 채점은 항목 통과 여부·점수·pairwise 승패·trace 지표만 받는다.
- variant는 레포 밖 임시 홈에서 실행되고 메시징 커넥터는 꺼져 있다. 본체와 라이브 서버는 promote 전까지 바뀌지 않는다.
- `edit`는 노브(시스템 프롬프트·`trace_tools.py`·log-trace 스킬)만 유일 매칭 find/replace로 고친다. 원본 줄의 30%를 넘게(4줄 이상) 바꾸는 수정은 거부한다. 캠페인 ID·`파일:줄번호`·구체 수치를 넣는 수정은 과적합으로 보고 거부한다.
- promote는 사용자가 승인한 뒤에만 한다.

```bash
# 사용자가 승인한 뒤 (저장소 루트에서)
uv run python workspace_seed/skills/meta-harness/metaharness.py promote --variant v1 --yes
```

사이클 기록은 [docs/improvement_log.md](improvement_log.md)에 남긴다.

## 9. 시나리오별 확인 포인트

실행 전에는 아래 행동 기준만 사용하고, 정답 상세는 채점 결과로만 확인한다.

### S1: 발송되지 않은 캠페인

- 대상 건수와 정상 기준선의 처리 속도를 비교하는가
- 자정 전후 시각과 발송일 검증을 확인하는가
- 트랜잭션 롤백과 실제 발송 이력을 연결하는가
- 같은 날 다른 캠페인까지 장애로 일반화하지 않는가

### S2: 결과 화면의 오퍼 성공 값

- 화면에서 집계 테이블과 집계 배치로 거슬러 올라가는가
- 집계 배치의 원천 테이블과 결과 수신 배치의 적재 테이블을 비교하는가
- ERROR가 없다는 사실만으로 정상이라고 판단하지 않는가
- 관련 없는 지연 ERROR를 우선 원인으로 선택하지 않는가

### S3: 예상보다 적은 대상 수

- 단계별 제외 건수를 확인하고 합계를 계산하는가
- 정상적인 제외 규칙 적용과 실제 결함을 구분하는가
- 없는 장애를 만들어내지 않는가
- 규칙이 기획 의도와 맞는지 확인하도록 제안하는가

### S4: 중간에 끊긴 발송 로그

- 마지막 진행 시각과 처리·미처리 건수를 확인하는가
- 종료 줄이 없다는 사실을 확인하는가
- 롤백이나 서버 장애를 근거 없이 단정하지 않는가
- 서버 로그, 스케줄러 이력, 프로세스 재기동 기록 등 추가 자료를 요청하는가

## 10. 실행 중 확인할 것

LangSmith trace 상세 화면이나 `metrics.md`에서 다음을 확인한다.

- `log-trace` 스킬을 먼저 읽었는가(`SKILL 먼저 읽음`)
- `/input/logs/`의 로그를 검색 후 필요한 줄만 읽었는가, 같은 파일·도구를 의미 없이 반복하지 않았는가
- 실패한 도구를 같은 방식으로 계속 재시도하지 않았는가
- 발송 이력과 성과 집계를 교차 확인했는가, 필요할 때 `read_source`·`search_source`·`get_change_log`를 썼는가
- `eval/` 접근 시도와 쓰기성 명령이 0인가. `execute`는 `date`만 허용되므로 `[거부됨]`이 반복되면 셸로 우회하려 한 것이다

도구를 전혀 쓰지 않았다면 같은 대화에서 다음처럼 다시 요청한다. 정답의 문제 지점이나 숫자는 알려주지 않는다.

```text
추측하지 말고 /input/logs/의 로그와 읽기 전용 조회 도구를 사용해 근거를 확인한 뒤 다시 분석해줘.
```

## 11. 테스트 종료와 정리

- 결과는 `runs/<run_set>/<variant>/`에 저장된다. 보존할 폴더만 검토한 뒤 커밋하고, 확인용 폴더(`smoke` 등)는 지운다.
- meta-harness 임시 홈은 `uv run python workspace_seed/skills/meta-harness/metaharness.py clean --all`로 지운다.
- 서버는 실행 중인 터미널에서 `Ctrl+C`로 종료한다.
