# Cursor Automation Workflow

## 목적

`alpha-gen`에서 Cursor의 `agent`, `subagent`, `MCP`, `rule`을 일관되게 사용하는 운영 표준입니다. 목표는 전략 개발과 서비스 운영을 모두 자동화하되, 실거래 결정은 항상 코드 기반 안전정책을 거치게 만드는 것입니다.

## 기본 원칙

- 제어면은 `backend/app/services.py` 중심으로 유지합니다.
- LLM은 `리서치`, `설명`, `초안 생성`, `이상징후 요약`을 담당하고, 주문 가능 여부는 `SafetyService`와 `RiskService`가 최종 판정합니다.
- 실거래 관련 변경은 `store -> API -> frontend` 세 층을 함께 수정합니다.

## 권장 Subagent 분해

### 개발 자동화

- `explore`: 영향 범위 탐색, 전략/모듈 구조 파악
- `generalPurpose`: 리팩터링, 테스트 추가, 문서 보강
- `ci-investigator`: 실패 테스트나 CI 체크 원인 분석
- `browser-use` 또는 `cursor-ide-browser`: 운영 콘솔 회귀 검증

### 서비스 운영 자동화

- `ResearchAgent`: 뉴스, 섹터 테마, 감성 결과 요약
- `SignalAgent`: 종목별 시그널 후보 생성
- `RiskAgent`: 한도, 손절, 드로우다운, 긴급정지 판정
- `ExecutionAgent`: 브로커 제출, 응답 추적, 상태 전이 기록
- `OpsAgent`: 워커 상태, 감사 이벤트, 거부 사유, 재시도 사유 요약

## MCP 사용 표준

- `cursor-ide-browser`: 웹 운영 콘솔 수동/자동 회귀 확인
- `plugin-linear-linear`: 전략 개선, 버그, 운영 이슈 티켓화
- `cursor-app-control`: 워크트리 이동, 프로젝트 루트 전환, 반복 작업 보조
- **`alpha-gen` (프로젝트 MCP)**: `health_check`, `get_safety_policy`, `list_audit_events`, `get_worker_status`, `run_setup_check`, `run_backend_tests`

프로젝트 MCP 등록: [`.cursor/mcp.json`](../.cursor/mcp.json). 로컬 FastAPI(`http://127.0.0.1:8000`) 실행 후 tool을 호출합니다. `ALPHA_GEN_BASE_URL`로 base URL을 override할 수 있습니다.

## Project Skills & Commands

| Skill / Command | 용도 |
|-----------------|------|
| `alpha-gen-readiness` / `ops-check` | setup_check + backend pytest + API ready 요약 |
| `alpha-gen-ops-console` | browser MCP로 `/` 운영 콘솔 회귀 |
| `alpha-gen-live-gate` / `promote-stage` | 운영 단계 승격 체크리스트 |
| `alpha-gen-incident` / `incident-triage` | audit/worker/orders 기반 triage |
| `alpha-gen-ops-loop` | `/loop` 또는 watch script 주기 감시 |

Skills: [`.cursor/skills/`](../.cursor/skills/). Commands: [`.cursor/commands/`](../.cursor/commands/).

## Loop / SDK 자동 점검

### Loop (IDE 내 주기 감시)

- Skill: `.cursor/skills/alpha-gen-ops-loop/SKILL.md`
- Windows: `scripts/cursor_ops_watch.ps1` (기본 5분, `ALPHA_GEN_WATCH_INTERVAL_SEC`)
- bash: `scripts/cursor_ops_watch.sh`
- Sentinel: `AGENT_LOOP_TICK_ALPHA_GEN_OPS` — 중복 loop 금지

예시:

```
/loop 5m alpha-gen ops watch: health, safety policy, worker status 요약
```

### SDK (선택, CI/외부 one-shot)

```bash
py automation/cursor_readiness_agent.py
```

- `CURSOR_API_KEY` 있으면 `cursor-sdk`로 readiness prompt 실행
- 없거나 패키지 미설치 시 `setup_check` + `pytest tests/test_backend_*.py` 로컬 fallback

## File-scoped Rules

- [`.cursor/rules/backend-trading-control-plane.mdc`](../.cursor/rules/backend-trading-control-plane.mdc) — `backend/app/**/*.py`
- [`.cursor/rules/frontend-ops-console.mdc`](../.cursor/rules/frontend-ops-console.mdc) — `frontend/**`
- [`.cursor/rules/alpha-gen-trading-safety.mdc`](../.cursor/rules/alpha-gen-trading-safety.mdc) — always apply

## Frontend (React + Vite)

운영 콘솔은 `frontend/`의 Vite + React + TS입니다. FastAPI는 `frontend/dist/`를 서빙합니다. 개발 스펙: [`docs/frontend_development.md`](../docs/frontend_development.md).

추천 순서:

1. `explore` subagent로 영향 범위를 찾습니다.
2. 필요한 작업은 Linear 이슈로 남깁니다.
3. 구현 후 브라우저 MCP로 운영 콘솔을 검증합니다.
4. 실패 시 `ci-investigator` 또는 추가 `explore` subagent로 역추적합니다.

## 실거래 변경 체크리스트

실거래 관련 수정 전후에는 아래를 반드시 확인합니다.

1. `config/__init__.py`의 운영 단계와 안전한 기본값이 유지되는가
2. `backend/app/store.py`에 상태 전이와 감사 이벤트가 남는가
3. `backend/app/main.py` 또는 관련 API에서 운영자가 현재 상태를 볼 수 있는가
4. `frontend`에서 긴급정지, 운영 단계, 경고 상태가 드러나는가
5. 관련 테스트가 추가되었는가

## 반복 작업 템플릿

### 전략 변경

1. `explore`로 영향 파일 확인
2. 백엔드 정책/상태 저장 변경
3. API와 UI 노출 보강
4. 테스트 추가
5. 브라우저 검증

### 장애 대응

1. 최근 감사 이벤트 확인
2. 주문 상태 전이 확인
3. 긴급정지 필요 여부 판단
4. 원인 분류 후 Linear 이슈 생성
