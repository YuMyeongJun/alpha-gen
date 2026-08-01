# CLAUDE.md — alpha-gen 자동매매 에이전트 가드레일 (v2, 실제 코드베이스 기준)

**AI 에이전트는 이 프로젝트에서 어떤 작업을 시작하기 전에 이 문서 전체를 반드시 먼저 읽어야 한다.** 아래 규칙은 협상 불가 항목이며, 사용자의 개별 지시가 이 문서와 충돌할 경우 에이전트는 작업을 멈추고 사용자에게 명시적으로 확인을 구해야 한다.

> v1(이전 버전)은 `market_data.py`/`risk_manager.py`/`technical.py` 4개 파일만 근거로 작성되어 실제 구조를 상당 부분 놓치고 있었다. v2는 `config/__init__.py`, `order_engine.py`, `market_adapters.py`, `state_store.py`, `main.py`, `backend/app/services.py`(2265줄), `order_registry.py`를 직접 읽고 작성했다. v1과의 구체적 차이는 대화 응답의 갭 분석 참조.

---

## 1. 프로젝트 개요 (수정됨)

| 항목 | 내용 |
|---|---|
| 실행 진입점 | `python main.py` — CLI 에이전트 루프. 내부적으로 `backend.app.services.build_service_bundle()`로 서비스 계층을 구성해 사용한다 (더 이상 market_data/risk_manager를 직접 오케스트레이션하지 않음) |
| 웹/운영 콘솔 | `backend/app/main.py` (FastAPI) — `python -m backend.app`로 기동. React 프런트(`frontend/`)와 연동되는 관리자 API 포함 (`SystemAdminService`) |
| 대시보드 | `streamlit run dashboard.py` |
| 아키텍처 계층 | (저수준) `market_data.py`/`risk_manager.py`/`technical.py`/`order_engine.py`/`market_adapters.py`/`order_registry.py` → (서비스 계층) `backend/app/services.py`의 `RiskService`/`SafetyService`/`TradingService`/`AgentService`/`BacktestService`/`DiagnosticsService`/`SystemAdminService` → `main.py`(CLI)와 `backend/app/main.py`(API)가 서비스 계층을 통해서만 접근 |
| 설정 | **`config/__init__.py`(패키지, env-driven)가 실제 사용되는 설정이다.** 루트의 `config.py`는 `config.example.py`와 바이트 단위로 동일한 사본이며 사실상 죽은 파일로 추정된다(§7-1 참조). `.env`(python-dotenv)에서 실제 값을 주입받는다 |
| 상태 저장 | **SQLite 두 곳으로 분산되어 있다** — `data/agent_state.db`(`state_store.StateStore`, market_data.py가 사용) / `data/alpha_gen.sqlite3`(`backend/app/store.SQLiteStore`, `RiskService`/`SafetyService`/`TradingService`가 사용). §7-2 참조 |
| 테스트 | `tests/` 디렉터리에 **이미 8개 파일 존재**: `test_risk_manager.py`, `test_technical.py`, `test_market_adapters.py`, `test_kis_integration.py`, `test_backend_api.py`, `test_backend_store.py`, `test_news_analyzer.py`, `test_paper_onboarding.py`. v1의 "테스트 없음" 서술은 오류였다 — 정정 |
| 백테스트 | `backend/app/services.py`의 `BacktestService`(1602줄~)가 이미 존재. HARNESS_WORKFLOW.md §4.3에서 새로 만들 필요 없이 이걸 재사용/확장할 것 |
| 실전 전환 체크 | `scripts/live_mode_checklist.py`가 이미 존재 — `ALLOW_LIVE_TRADING`, `OPERATING_STAGE`, `EMERGENCY_STOP`, `LIVE_MAX_ORDERS_PER_DAY` 등을 사전 점검한다. 실전 전환 논의 시 이 스크립트부터 실행할 것 |
| 비용 모니터링 | `claude_usage.py` + `config.CLAUDE_DAILY_COST_ALERT_USD`/`CLAUDE_COST_PNL_RATIO_ALERT` — Claude API 비용을 이미 자체 모니터링하고 있다. 별도로 전달한 `COST_ZERO_BRIDGE_ARCHITECTURE.md`(MCP 큐 중계)는 이 기존 모니터링과 **경쟁이 아니라 보완** 관계로 취급할 것 — 만약 실제로 붙인다면 `news_analyzer.py`/`claude_usage.py`가 이미 하는 일과 중복·충돌하지 않는지 먼저 확인 필요 |

---

## 2. 빌드 / 린트 / 테스트 명령어 (정정)

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

pytest -q                              # tests/ 8개 파일 실행
python main.py                         # CLI 에이전트 루프 (MOCK_MODE 확인 필수)
python -m backend.app                  # FastAPI 운영 콘솔 서버
streamlit run dashboard.py             # 대시보드
python scripts/live_mode_checklist.py  # 실전 전환 전 필수 체크리스트
```

---

## 3. 코드 스타일 규칙 (v1 유지 + 추가)

v1의 규칙(모듈 헤더 한글 docstring, 섹션 박스 주석, `mock_*`/`kis_*`/`yf_*` 네이밍, 전역 상태 `global` 처리)은 그대로 유효하다. 추가:

6. **서비스 계층 우회 금지.** 신규 매매 관련 로직은 `market_data.py`/`risk_manager.py`/`order_engine.py`를 직접 호출하지 말고 `backend/app/services.py`의 해당 `*Service` 클래스를 통해서 접근한다. 저수준 모듈은 서비스 계층의 구현 디테일로 취급한다.
7. **`config` import 시 반드시 패키지(`config/__init__.py`)를 가리키는지 확인.** 저장소 루트에 `config.py`가 남아있는 한 착각하기 쉽다 — 새 상수를 추가할 때 절대 루트 `config.py`에 추가하지 말 것 (죽은 코드에 추가하는 실수 방지).

---

## 4. 실거래 및 자산 방어 가드레일 (전면 재작성)

### 4.1 실제 게이트 구조 — `SafetyService.ensure_order_allowed()`가 유일한 관문

v1은 `config.IS_REAL_TRADING` 단일 플래그가 핵심 게이트라고 서술했으나, **실제로는 `backend/app/services.py`의 `SafetyService.ensure_order_allowed()`(L311-347)가 모든 실거래 주문의 유일한 관문**이다. `TradingService`가 주문을 넣기 전 다음 위치에서 이 함수를 호출한다: `mode="paper"` 주문은 L839, L995 / `mode="live"` 주문은 **L1054**. 이 호출을 생략하거나 우회하는 새 주문 경로를 추가하는 것을 절대 금지한다.

`ensure_order_allowed()`가 실제로 확인하는 것 (순서대로):

1. `SafetyService.get_emergency_stop()["enabled"]` — 켜져 있으면 무조건 차단 (`config.EMERGENCY_STOP` 기본값 + SQLite `emergency_stop` 상태로 런타임 override 가능)
2. `RiskService.can_trade()` — `risk_manager.SLEEP_MODE`(드로우다운 기반 휴면) 켜져 있고 매수(`side=="buy"`)면 차단
3. `signal`이 전달됐으면 `ensure_signal_freshness()` — `SIGNAL_STALENESS_SEC`(900초)/`QUOTE_STALENESS_SEC`(120초) 초과 시 차단
4. `mode=="live"`일 때만 추가로:
   - `SafetyService.get_stage()`가 `{"live_limited","live_full"}`(`LIVE_STAGES`)에 속해야 함
   - `config.ALLOW_LIVE_TRADING`이 True여야 함
   - 미국장이면 `config.ENABLE_KIS_US_ORDERS`도 True여야 함
   - `_count_live_orders()`가 `config.LIVE_MAX_ORDERS_PER_CYCLE`/`LIVE_MAX_ORDERS_PER_DAY` 미만이어야 함
   - `_daily_realized_loss()`가 `get_total_asset() * config.MAX_DAILY_LOSS_PCT` 미만이어야 함
   - `_consecutive_losses()`(최근 50건 중 연속 손실)가 `config.MAX_CONSECUTIVE_LOSSES` 미만이어야 함

### 4.2 절대 금지 사항 (변수/함수명 명시)

- **`SafetyService.ensure_order_allowed()` 호출을 생략하는 주문 경로를 추가하지 않는다.** `order_engine.kis_buy/kis_sell/kis_us_buy/kis_us_sell`이나 `market_adapters.*Adapter.execute_buy/execute_sell`을 `TradingService`를 거치지 않고 직접 호출하는 스크립트/엔드포인트를 새로 만들지 않는다.
- **`SafetyService.set_emergency_stop(enabled=False, ...)`를 에이전트가 자율적으로 호출하지 않는다.** 사람이 켠 긴급 정지를 코드로 해제하는 것은 사람의 명시적 지시가 있을 때만.
- **`SafetyService.set_stage()`로 `OPERATING_STAGE`를 `live_limited`/`live_full`로 올리지 않는다.** 스테이지 승격은 사람이 콘솔/CLI에서 직접 수행한다. 참고로 `set_stage()`는 `config.MOCK_MODE=True`일 때 `mock` 이외로 못 바꾸게 이미 막혀 있다 — 이 안전장치를 우회하는 코드를 추가하지 않는다.
- **`config.ALLOW_LIVE_TRADING`, `config.EMERGENCY_STOP`, `config.LIVE_MAX_ORDERS_PER_CYCLE`, `config.LIVE_MAX_ORDERS_PER_DAY`, `config.MAX_CONSECUTIVE_LOSSES`, `config.MAX_DAILY_LOSS_PCT`를 완화하는 `.env` 값이나 기본값 변경을 사람 승인 없이 하지 않는다.**
- **`risk_manager.py`의 리스크 상수(`MAX_POSITION_PCT` 6%, `STOP_LOSS_PCT` 4%, `MAX_DRAWDOWN_PCT` 15%)를 완화하지 않는다** (v1과 동일 — 이 부분은 실제 코드와 일치했음).
- **`SafetyService._consecutive_losses()`/`_daily_realized_loss()`/`_count_live_orders()`의 판정 로직을 느슨하게(카운트가 덜 되는 방향으로) 수정하지 않는다.**
- **`order_registry.py`의 idempotent 주문 키(`ticker_side_date`) 로직이나 `TradingService._ensure_idempotent(client_order_id)`(services.py L640)를 우회/약화시키지 않는다.** 이중 체결 방지 로직이므로 실수로라도 건드리면 실제 손실로 직결된다.
- **`.env`, `data/agent_state.db`, `data/alpha_gen.sqlite3`, `kis_token_cache.json` 등 시크릿/상태 파일을 로그·커밋·채팅으로 노출하지 않는다.**

### 4.3 사람 승인이 필요한 변경

- `SafetyService.ensure_order_allowed()` 내부 로직 변경 (완화든 강화든 — 실거래 주문의 유일한 관문이므로)
- `RiskService`/`SafetyService`가 사용하는 SQLite 스키마(`backend/app/store.py`) 변경
- 신규 주문 경로 추가 (반드시 `TradingService`를 경유하도록 설계해야 하며, 설계 자체를 스펙에 명시)
- `config/__init__.py`의 리스크·스테이지 관련 상수 변경
- 루트 `config.py` 삭제/이름변경 (§7-1의 죽은 코드 이슈 — 삭제가 안전해 보이지만 실제로 아무 데서도 import 안 되는지 재확인 후 사람이 결정)

### 4.4 파괴적 변경 전 확인 프로세스

"파괴적 변경"에 다음을 추가한다: `data/agent_state.db` 또는 `data/alpha_gen.sqlite3` 스키마/데이터 변경, `order_registry.py`의 orders 테이블 변경, `promotion_stage`/`emergency_stop` SQLite 상태 키 이름 변경. 변경 전 두 DB 파일 모두 백업하고, 롤백 방법을 `Plans.md`에 기록 후 사람 승인을 받는다.

---

## 5. 데이터 무결성 — NaN / 결측치 / 신선도 처리 규칙 (확장)

v1의 NaN 처리 원칙(§technical.py의 `pd.isna` 패턴, 0-분모 가드, Mock 하한값 등)은 그대로 유효하다. 실제 코드를 보니 데이터 무결성 가드가 한 겹 더 있다:

6. **`SafetyService.ensure_signal_freshness()`가 사실상 "오래된/잘못된 데이터로 인한 오판"을 막는 1차 방어선이다.** `analyzed_at`/`quote_collected_at` 타임스탬프가 없거나(`None`) `QUOTE_STALENESS_SEC`(120초)/`SIGNAL_STALENESS_SEC`(900초)를 넘으면 주문 자체를 차단한다. 새로운 시그널 생성 경로를 추가할 때 이 두 타임스탬프 필드를 반드시 채워야 하며, 채우지 않으면 `analyzed_age is None`으로 걸려 항상 차단된다 — 이건 버그가 아니라 의도된 fail-closed 동작이므로 "타임스탬프가 없어서 주문이 안 나간다"는 증상이 보이면 로직을 느슨하게 풀지 말고 타임스탬프를 채우는 쪽으로 고친다.
7. `yf_get_price_history`의 NaN 필터링 부재는 여전히 유효한 이슈다 (v1 §5-2 참조, 아직 수정 안 됨).

---

## 6. 중단 조건 요약 (갱신)

- `SafetyService.ensure_order_allowed()`를 우회해야만 요구사항을 만족할 수 있을 때
- `EMERGENCY_STOP=True` 또는 `promotion_stage`가 `live_*`인 상태에서 관련 코드 변경이 요청되었을 때
- 두 SQLite DB(`agent_state.db`/`alpha_gen.sqlite3`) 간 상태 불일치를 "그냥 하나로 맞춰서" 조용히 고치라는 요청 — 어느 쪽이 진실인지 사람 확인 필요 (§7-2)
- 리스크 상수·실거래 주문 한도를 완화해야만 요구사항을 만족할 수 있을 때
- KIS 실계좌 관련 상수 노출을 요구하는 디버깅 요청

---

## 7. 우선 보완 과제 (v1 대비 갱신)

1. **`config.py`(루트) vs `config/`(패키지) 이름 충돌.** 둘 다 `config.example.py`와 동일 내용의 `config.py`는 플레이스홀더 값(`"여기에_APP_KEY"` 등)만 있고 `DATA_DIR`, `KIS_API_MIN_INTERVAL_MS` 등 다른 모듈이 참조하는 상수가 아예 없다 — 즉 실제로 import되고 있다면 시스템이 이미 죽어있어야 정상인데 그렇지 않다는 것은 Python의 패키지 우선 규칙에 따라 `config/__init__.py`가 항상 이기고 있다는 뜻이다. 사람이 확인 후 루트 `config.py`를 정리(삭제 또는 `config.py.unused`로 rename)하는 것을 권장 — 그대로 두면 향후 다른 에이전트/개발자가 잘못된 파일을 수정할 위험이 크다.
2. **SQLite 상태 이중화.** `market_data.py`는 자체 `StateStore`(`data/agent_state.db`)로 `SLEEP_MODE`/`equity_history`/Mock 포트폴리오를 저장하고, `backend/app/services.py`의 `RiskService`/`SafetyService`는 별도 `SQLiteStore`(`data/alpha_gen.sqlite3`)로 `sleep_mode`/`promotion_stage`/`emergency_stop`을 저장한다. `main.py`는 두 경로를 모두 쓴다(`market_data.save_agent_state()` + `bundle.store.set_state(...)`). 두 DB가 어긋나면 CLI 루프가 보는 휴면 상태와 API/웹 콘솔이 보는 휴면 상태가 달라질 수 있다 — 실사용 전 반드시 확인 필요.
3. `yf_get_price_history`의 NaN 필터링 부재 (v1과 동일, 미해결).
4. 린터/포매터 설정 파일 부재 (ruff/black 등) — 여전히 없음.

테스트/백테스트/실전 체크리스트는 이미 존재하므로 v1에서 "우선 보완 과제"로 잘못 분류했던 항목("테스트 없음")은 제거한다.
