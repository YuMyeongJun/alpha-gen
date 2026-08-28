# spec.md

이 파일은 harness 작업 항목별로 섹션을 누적한다 (완료된 항목도 감사 기록으로 유지).

---

# P0: `place_manual_order()` 안전게이트 우회 수정 — ✅ 완료 (2026-08-01)

## 배경 (왜)

`backend/app/services.py`의 `TradingService.place_manual_order()`(L1456-1513)는 UI에서 사용자가 직접 실행하는 수동 매수/매도 경로다. 현재 이 함수는 `emergency_stop` 여부만 확인하고, `SafetyService.ensure_order_allowed()`를 전혀 호출하지 않는다. 그 결과 다음이 전부 무시된다:

- 리스크 휴면 모드 (`RiskService.can_trade()`)
- live 승격 스테이지 체크 (`SafetyService.get_stage() in LIVE_STAGES`)
- `config.ALLOW_LIVE_TRADING`
- 미국장 `config.ENABLE_KIS_US_ORDERS`
- 사이클당/일일 실거래 주문 한도 (`LIVE_MAX_ORDERS_PER_CYCLE`/`LIVE_MAX_ORDERS_PER_DAY`)
- 일일 손실 한도 (`MAX_DAILY_LOSS_PCT`)
- 연속 손실 한도 (`MAX_CONSECUTIVE_LOSSES`)

`config.MOCK_MODE=False`이고 KIS 자격증명이 설정되어 있으면(`config.KIS_CREDENTIALS_CONFIGURED`), 이 함수는 `order_engine.kis_buy/kis_sell/kis_us_buy/kis_us_sell`을 직접 호출해 **실계좌에 실주문을 낸다**(L1503-1514). 이는 CLAUDE.md §4.1/§4.2가 명시한 "`SafetyService.ensure_order_allowed()`가 모든 실거래 주문의 유일한 관문"이라는 규칙에 대한 실제 위반이다.

**사람 확인 결과 (2026-08-01 대화)**:
1. 이 우회는 버그로 판단됨 — 전체 게이트를 다른 주문 경로(`place_paper_order`/`place_live_order`)와 동일하게 적용한다. "수동이니까 예외"라는 근거는 인정하지 않는다.
2. `POST /api/orders/manual` 엔드포인트의 인증 부재는 **이번 spec 범위에서 제외**한다 — 별도 spec으로 분리해서 다룬다.

## 영향받는 파일

- **서비스 계층**: `backend/app/services.py` — `TradingService.place_manual_order()`만 수정. `SafetyService.ensure_order_allowed()` 내부 로직은 변경하지 않는다(그대로 호출만 추가).
- **저수준 모듈**: 없음. `order_engine.py`/`market_adapters.py`는 건드리지 않는다.
- **테스트**: `tests/test_backend_api.py`에 케이스 추가 (기존 컨벤션 따름 — emergency-stop 차단 테스트 패턴 참고).

## 리스크/게이트 파라미터 변경 여부

**없음.** `config/__init__.py`의 상수(`MAX_POSITION_PCT`, `ALLOW_LIVE_TRADING`, `LIVE_MAX_ORDERS_PER_DAY` 등)는 일절 변경하지 않는다. 기존 게이트 로직에 새 호출 지점을 추가하는 것뿐이다. 따라서 `RISK LIMIT CHANGE APPROVED` 서명은 필요 없다.

## `config.MOCK_MODE`/`OPERATING_STAGE`/`ensure_order_allowed()`에 대한 영향

- `ensure_order_allowed()` 함수 자체는 **변경 없음** — 새 호출 지점만 추가.
- `place_manual_order()`가 내부적으로 브로커 실행 여부를 결정하던 기존 조건(`not config.MOCK_MODE and config.KIS_CREDENTIALS_CONFIGURED`)을 `mode` 파라미터(`"live"` vs `"paper"`) 결정에 그대로 재사용한다 — 새로운 판단 기준을 만들지 않는다.
- `mode="live"`로 게이트를 통과하지 못하면(stage 불충분/`ALLOW_LIVE_TRADING=False`/한도초과 등) 해당 수동 주문은 **거부**되고, 페이퍼 폴백으로 자동 전환되지 않는다 — "게이트를 통과 못 했으니 조용히 페이퍼로 처리"는 우회의 재발이므로 명시적으로 금지.
- `mode="paper"`인 경우(즉 MOCK_MODE거나 KIS 미설정)에도 `ensure_order_allowed(mode="paper", ...)`를 호출해 `emergency_stop`/휴면모드 체크는 동일하게 적용한다.

## 동작 변경 상세

### Before
```python
policy = self.safety_service.get_policy()
stop_state = policy["emergency_stop"]
if stop_state["enabled"]:
    raise TradingSafetyError(...)
# 이후 곧바로 브로커 실행 or 페이퍼 폴백
```

### After
```python
mode = "live" if (not config.MOCK_MODE and config.KIS_CREDENTIALS_CONFIGURED) else "paper"
self.safety_service.ensure_order_allowed(mode=mode, session=session, side=side, signal=None)
# 통과하지 못하면 TradingSafetyError가 그대로 전파되어 API 레이어(main.py의 기존 except (ValueError, TradingSafetyError))가
# 400으로 변환한다 — place_manual_order의 기존 emergency_stop 체크(raise 방식)와 동일한 패턴 유지, 새 try/except 불필요.
# 통과 시에만 기존 브로커 실행/페이퍼 폴백 로직 진행
```

**순서 수정 (TDD 1단계에서 발견)**: 게이트 체크는 `market_data.get_price()` 호출보다 **먼저** 수행한다. 기존 코드는 시세 조회를 먼저 하는데, `mode="live"`로 판정되는 상황(실계좌 자격증명 설정됨)에서는 이 시세 조회 자체가 실제 KIS 네트워크 호출이다 — 게이트가 어차피 차단할 주문인데 불필요하게 외부 API를 먼저 호출하는 건 낭비이자, 테스트에서 실제로 이 순서 때문에 `RuntimeError`(KIS 인증 실패)가 의도한 `TradingSafetyError`보다 먼저 발생함을 확인했다(1단계 테스트 실행 로그). `place_live_order`는 `_create_intent`에 가격이 필요해 순서가 다르지만, `place_manual_order`는 그런 제약이 없으므로 게이트를 시세 조회 앞으로 옮긴다.

`signal=None`을 명시적으로 전달한다 — 수동 주문은 자동 신호에서 발생하지 않으므로 `ensure_signal_freshness()`는 자연히 스킵된다(기존 `ensure_order_allowed` 시그니처가 이미 지원하는 동작, 신규 분기 아님).

## 필요한 백테스트/승격 시나리오

없음. 이 변경은 주문 게이트 로직이며 백테스트 경로(`backtest.py`/`BacktestService`)와 무관하다. 대신 `pytest -q` 전체 회귀와, 아래 신규 케이스 통과가 검증 기준이다.

## 테스트 요구사항 (HARNESS_WORKFLOW.md §2 기준)

1. **정상 케이스**: 모든 게이트 통과 시 기존과 동일하게 주문 체결됨 (회귀 없음).
2. **긴급정지**: 기존 동작 유지 (이미 테스트됨, 회귀 확인만).
3. **휴면 모드(신규)**: `RiskService.can_trade()==False`이고 `side="buy"`이면 수동 매수도 차단됨.
4. **live 스테이지 미충족(신규)**: `mode`가 `"live"`로 판정되는 조건에서 `SafetyService.get_stage()`가 `LIVE_STAGES`에 없으면 차단됨 — 브로커 호출(`order_engine.kis_buy` 등)이 아예 일어나지 않아야 함(mock으로 패치해 호출 여부 검증).
5. **`ALLOW_LIVE_TRADING=False`(신규)**: live 모드 판정 시 차단됨.
6. **주문 한도 초과(신규)**: `LIVE_MAX_ORDERS_PER_CYCLE`/`_DAY` 초과 시 차단됨.
7. **일일 손실/연속 손실 한도(신규)**: 각각 초과 시 차단됨.
8. 위 3~7번 차단 케이스 모두 **거부 응답**을 반환하고 페이퍼 폴백으로 전환되지 않는지 확인.

---

# P1: 대시보드 휴면 상태 표시가 잘못된 DB를 참조하는 문제 수정

## 배경 (왜)

CONTEXT.md §15와 종합 점검(2026-08-01)에서 확인한 상태 이중화 문제 — `data/agent_state.db`(`state_store.StateStore`)와 `data/alpha_gen.sqlite3`(`backend/app/store.SQLiteStore`)가 분리되어 있다. 사람 확인 결과, **`alpha_gen.sqlite3`를 source of truth로 삼는다.**

**범위를 좁힌 이유**: 처음엔 "sleep_mode 등 공유 개념 전체 제거"로 넓게 접근하려 했으나, 코드를 직접 추적한 결과:
- `main.py`의 실제 CLI 루프(`run_agent_loop`, L103-168)는 이미 `build_service_bundle()` → `agent_service.run_cycle()`/`bundle.risk_service.can_trade()`를 사용한다 — 즉 **실시간 매매 판단은 이미 전부 `alpha_gen.sqlite3` 기준**이다. `agent_state.db`는 크래시 종료 시(`except`/`KeyboardInterrupt`)에만 백업 성격으로 갱신된다.
- `bought_today`/`equity_history`/`sentiments`는 `main.py` 자신의 프로세스 내부 동작(당일 중복매수 방지 등)에 쓰이는 상태이자 대시보드 표시용이지, `SafetyService.ensure_order_allowed()`의 게이트 판단에는 전혀 관여하지 않는다. 이걸 억지로 걷어내면 `main.py` 재시작 시 복구 로직(`add_bought_today`가 `_store`에 즉시 동기화되는 것)을 건드리게 되어 스코프가 커지고 위험도 커진다.
- 실제로 위험한 어긋남은 **`dashboard.py`가 `risk_manager.SLEEP_MODE`/`SLEEP_REASON`를, Streamlit 스크립트 시작 시 1회(`market_data.load_agent_state()`, dashboard.py:198) `agent_state.db`에서 읽어온 값으로 표시**한다는 것 하나뿐이다. 실제 실시간 휴면 상태는 `alpha_gen.sqlite3`에만 정확히 반영되므로, 대시보드가 "실제로는 거래 중인데 휴면"으로 잘못 표시할 수 있다(위험한 방향 — CONTEXT.md/종합점검에서 확인).

따라서 P1은 **대시보드의 휴면 상태 표시 하나만** `alpha_gen.sqlite3` 참조로 바꾼다. `bought_today`/`equity_history`/`sentiments`는 이번 스코프에서 건드리지 않는다(각각이 안전 게이트와 무관한 순수 표시/CLI 내부 상태이므로 사람이 별도로 원하지 않는 한 손대지 않는 것이 안전).

## 영향받는 파일

- **`market_data.py`**: 신규 함수 `get_live_sleep_state(db_path: str | None = None) -> tuple[bool, str]` 추가. `config.MOCK_MODE`일 때는 기존 `_apply_agent_fields()`의 Mock 안전장치(테스트용 휴면 잔재가 Mock 루프를 막지 않도록 항상 `False`)와 동일한 동작을 유지한다.
  - **구현 수정(독립 리뷰에서 발견)**: 처음엔 `backend.app.store.SQLiteStore(bootstrap_legacy=False)`로 구현했으나, 이 클래스의 생성자는 `bootstrap_legacy=False`여도 `legacy_bootstrap_done` 상태 키에 매번 **쓰기**를 한다(store.py:26-27) — Streamlit이 재실행될 때마다 별도 프로세스가 운영 DB(`alpha_gen.sqlite3`)에 쓰기를 시도해 `main.py`의 writer와 락 경합 위험이 생긴다. `SQLiteStore`를 쓰지 않고 `sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)`로 진짜 읽기 전용 연결을 사용하도록 수정했다. 순환 임포트 우려 자체는 원래 없었음(`backend/app/store.py`는 `market_data`를 임포트하지 않음, 확인됨) — 이번 수정의 이유는 순환 임포트가 아니라 부작용(쓰기) 회피다.
- **`dashboard.py`**: L450, L455의 `risk_manager.SLEEP_MODE`/`risk_manager.SLEEP_REASON` 참조를 `market_data.get_live_sleep_state()` 호출 결과로 교체.
- **저수준 모듈 중 건드리지 않는 것**: `state_store.py`, `risk_manager.py`, `backend/app/services.py`(`RiskService`/`SafetyService` 내부 로직 무변경 — 읽기만 추가).
- **테스트**: `market_data.py`에 신규 함수가 생기므로 `tests/test_market_adapters.py` 또는 신규 `tests/test_market_data_state.py`(기존 컨벤션에 맞춰 어느 쪽이 적합한지는 구현 시점에 기존 파일 구조를 보고 판단)에 케이스 추가.

## 리스크/게이트 파라미터 변경 여부

없음. 표시 로직만 변경. `ensure_order_allowed()`/`can_trade()`/게이트 상수는 전혀 건드리지 않는다.

## `config.MOCK_MODE`/`OPERATING_STAGE`/`ensure_order_allowed()`에 대한 영향

없음 — 이 변경은 읽기 전용 표시 경로이며 어떤 주문 로직에도 관여하지 않는다.

## 상태 저장소 영향 (CLAUDE.md §7-2 명시 요구)

- **어느 DB를 건드리는가**: `alpha_gen.sqlite3`를 **새로 읽기만** 한다 (쓰기 없음). `agent_state.db`는 전혀 건드리지 않는다(기존 Mock 필드용 용도 그대로 유지).
- **다른 쪽과 값이 어긋날 가능성**: 이 변경 자체가 그 어긋남(대시보드 vs 실제 휴면상태)을 해소하는 목적이므로, 변경 후에는 대시보드가 항상 `alpha_gen.sqlite3`의 최신 값을 보여준다. 단, `main.py`가 크래시 후 재시작 직전까지의 짧은 공백 동안에는 `alpha_gen.sqlite3`도 최신이 아닐 수 있음(기존에도 있던 한계, 이번 변경으로 악화되지 않음).

## 필요한 백테스트/승격 시나리오

없음. 표시 로직 변경이며 매매 판단에 영향 없음.

## 테스트 요구사항

1. **정상 케이스**: `config.MOCK_MODE=False`, DB에 `sleep_mode=False` → `get_live_sleep_state()`가 `(False, "")` 반환.
2. **휴면 감지**: `config.MOCK_MODE=False`, DB에 `sleep_mode=True`, `sleep_reason="드로우다운 -15%"` → 그대로 반환.
3. **Mock 모드 안전장치**: `config.MOCK_MODE=True`이고 DB에 `sleep_mode=True`가 저장돼 있어도 `(False, "")`를 반환해야 함(기존 `_apply_agent_fields()`의 Mock 예외 처리와 동일 원칙 — 테스트 잔재가 Mock 루프를 막지 않도록).
4. **DB 파일이 없거나 빈 상태**: 새 tmp DB(테이블은 생성되지만 키가 비어있음) → 기본값 `(False, "")` 반환 (`store.get_state`의 기본값 동작에 의존, 예외 발생 안 함).

---

# P2: `yf_get_price_history` NaN 필터링 추가

## 배경 (왜)

CLAUDE.md §5-7(및 §7-3)에 명시된 기존 이슈. `market_data.py:794-803`의 `yf_get_price_history()`가 `hist["Close"].tolist()`를 NaN 제거 없이 그대로 반환한다. yfinance는 상장정지/거래정지/데이터 공백일에 NaN 종가를 반환할 수 있고, 최근 추가된 유럽 종목(§신규 유니버스)일수록 이런 공백이 더 잦을 수 있다. 종합 점검(2026-08-01)에서 확인: 이 NaN이 `technical.py`의 `calc_rsi`/`calc_ma`/`get_volatility_target_from_history`로 그대로 흘러들어가며, 현재는 `MA_LONG(20) > RSI_PERIOD+1(15)`라는 우연 덕에 MA 쪽이 먼저 fail-closed로 막아줘서 실제 오탐 매수로 이어지지는 않지만, `.env`에서 이 기간 설정이 바뀌면 RSI 과매수 체크가 NaN을 조용히 통과시키는 실제 오탐 매수 경로가 될 수 있다. 또한 `get_volatility_target_from_history`에서 `int(max(prev_slice))`가 NaN에 대해 `ValueError`를 던져(상위 try/except가 잡아 해당 종목만 스킵되긴 하지만) 불필요한 예외 경로를 만든다.

**근본 수정 위치**: 두 개별 소비처(`calc_rsi`/`calc_ma`/변동성 계산)를 각각 방어하는 대신, 데이터가 만들어지는 지점(`yf_get_price_history`)에서 NaN을 제거한다 — CLAUDE.md가 지목한 지점과 정확히 일치하고, 하위 소비처를 전부 건드리지 않아도 두 문제(잠재적 오탐, 불필요한 예외)가 함께 해소된다.

## 영향받는 파일

- **`market_data.py`**: `yf_get_price_history()`(L794-803) 한 줄만 수정 — `hist["Close"].tolist()` → `hist["Close"].dropna().tolist()`.
- **건드리지 않는 것**: `technical.py`(calc_rsi/calc_ma/get_volatility_target_from_history 내부 로직 무변경 — 방어 로직 추가 없이 소스에서 차단), `get_price_history()`의 길이 체크(`len(hist) >= RSI_PERIOD+1`)는 이미 존재하며 NaN 제거로 리스트가 짧아지는 경우도 기존 로직 그대로 mock 폴백으로 처리됨 (무변경으로 충분).
- **테스트**: `tests/test_market_adapters.py` 또는 신규 파일에 `yf.Ticker.history()`를 monkeypatch해 NaN 포함 케이스 검증.

## 리스크/게이트 파라미터 변경 여부

없음.

## `config.MOCK_MODE`/`OPERATING_STAGE`/`ensure_order_allowed()`에 대한 영향

없음 — 시세 데이터 정제 로직이며 주문 게이트와 무관.

## 필요한 백테스트/승격 시나리오

없음.

## 테스트 요구사항

1. **NaN 섞인 케이스**: Close에 NaN이 중간중간 섞인 DataFrame → 반환 리스트에 NaN 없이 실제 값만 순서 유지되어 포함.
2. **전부 NaN인 케이스**: 빈 리스트 반환 → 호출자(`get_price_history`)의 기존 길이체크가 자동으로 mock 폴백 처리하는지 확인(회귀).
3. **NaN 없는 정상 케이스**: 기존 동작과 동일 결과 (회귀).

---

# P3: 세이프티 크리티컬 함수 테스트 커버리지 추가

## 배경 (왜)

종합 점검(2026-08-01)에서 확인: CLAUDE.md가 "절대 완화 금지"로 명시한 함수들 중 다수가 직접 테스트되지 않고 있었다. P0 작업으로 `ensure_order_allowed()`의 live 분기(stage/`ALLOW_LIVE_TRADING`/주문한도/일손실/연속손실)는 이미 상당 부분 커버됐다 — 이 spec은 **P0 이후에도 남아있는** 공백만 다룬다:

1. `order_registry.py`의 멱등 주문 키 로직(`make_order_key`/`idempotent_buy`/`idempotent_sell`/`is_duplicate`) — 테스트 전무. 현재 어디서도 호출 안 되는 미배선 상태(dead code)지만, CLAUDE.md가 "실수로라도 건드리면 실제 손실"이라고 명시한 이중체결 방지 로직이므로 배선되기 전에 테스트로 보호해둔다.
2. `TradingService._ensure_idempotent()`/`_create_intent()`의 멱등성 — 테스트 전무.
3. `SafetyService.ensure_signal_freshness()` — 테스트 전무.
4. `RiskService.can_trade()` — 직접 테스트 없음(간접적으로만 확인됨).
5. `SafetyService.set_emergency_stop(enabled=False)` — disable 경로 테스트 없음(enable만 커버됨).

**P0 이후 이미 커버된 것이라 이번에 다시 안 다루는 것**: `SafetyService.set_stage()`의 `MOCK_MODE` 가드는 기존 `test_safety_and_audit_endpoints`(MOCK_MODE=True에서 차단)와 P0의 `test_manual_order_blocked_when_allow_live_trading_false`(MOCK_MODE=False에서 성공)가 양방향 다 이미 커버한다.

## 영향받는 파일

- **신규 테스트만 추가, 프로덕션 코드 변경 없음.**
- `tests/test_order_registry.py` (신규) — `order_registry.py` 대상.
- `tests/test_backend_api.py`에 케이스 추가 — `_ensure_idempotent`/`_create_intent`/`ensure_signal_freshness`/`can_trade`/`set_emergency_stop(disable)` 대상.

## 리스크/게이트 파라미터 변경 여부

없음 — 프로덕션 코드를 전혀 수정하지 않는다.

## 테스트 요구사항

1. `make_order_key`가 `TICKER_SIDE_YYYY-MM-DD[_REASON]` 형식을 만드는지.
2. `idempotent_buy`를 같은 키로 두 번 호출 시 두 번째는 `order_engine.execute_buy`를 호출하지 않고 차단되는지(FILLED 이후) / PENDING 상태에서도 차단되는지.
3. `idempotent_sell`도 동일 패턴 + `realized_pnl` 반환 확인.
4. `TradingService._ensure_idempotent(None)` → `None`, 모르는 `client_order_id` → `None`, 아는 `client_order_id` → 해당 주문 반환.
5. `_create_intent()`를 같은 `client_order_id`로 두 번 호출 시 새 주문이 생기지 않고 동일 주문이 반환되는지(`store.list_recent_orders()` 개수로 검증).
6. `ensure_signal_freshness()` — `analyzed_at`/`quote_collected_at`가 `None`이거나 `SIGNAL_STALENESS_SEC`/`QUOTE_STALENESS_SEC` 초과 시 `TradingSafetyError`, 신선하면 예외 없음.
7. `RiskService.can_trade()` — store `sleep_mode` True/False에 따라 정확히 반환.
8. `SafetyService.set_emergency_stop(enabled=False)` — 이후 `emergency_stop.enabled`가 `False`가 되고, 이전에 막혔던 주문이 다시 통과하는지.

---

# P4: 경미한 정리 항목

## 배경 (왜)

종합 점검(2026-08-01)에서 확인한 두 가지 회귀/고아 파일:

1. **`docker-compose.yml`이 깨져 있음**: `archive/`로 옮겨진(커밋 `cd262dd`) 루트 `config.py`/`mock_state.json`을 여전히 bind-mount하고 있어(`./config.py:/app/config.py:ro`, `./mock_state.json:/app/mock_state.json`) `docker compose up` 시 소스 경로가 없어 실패하거나 빈 마운트가 생긴다. 실제 설정은 `.env`(`config/__init__.py`가 로드)에서 오고, 상태는 이제 `data/agent_state.db`/`data/alpha_gen.sqlite3`(SQLite)에 있으므로 마운트 대상 자체가 바뀌어야 한다.
2. **`migrate_to_sqlite.py`가 고아 상태**: `mock_state.json → agent_state.db` 1회성 마이그레이션 스크립트로 이미 완료됨(CONTEXT.md). 코드 어디서도 import/실행되지 않음(CONTEXT.md 문서 언급 제외 확인).

## 영향받는 파일

- **`docker-compose.yml`**: `config.py`/`mock_state.json` 마운트를 `.env`(`env_file:`) + `./data:/app/data`(SQLite 두 DB 영속화)로 교체.
- **`migrate_to_sqlite.py` → `archive/migrate_to_sqlite.py`**: `git mv`로 이동(삭제 아님, 기존 archive 정리 방식과 동일).

## 리스크/게이트 파라미터 변경 여부

없음. 인프라 설정 파일과 고아 스크립트 이동만.

## 검증

- 코드 전체에서 `migrate_to_sqlite` 참조가 `CONTEXT.md`(문서, 무해) 외에 없음을 grep으로 재확인.
- `pytest -q` 회귀 (docker-compose.yml/스크립트 이동은 Python import 경로와 무관하므로 영향 없어야 함).
- Docker가 로컬에 없어 `docker compose config`로 직접 검증은 못 함 — YAML 문법을 수동 검토.

---

# P5: 백엔드 API 인증 게이트 추가 — 🔲 사람 승인 대기 (P6의 선행 조건)

## 배경 (왜)

P0에서 "`POST /api/orders/manual`의 인증 부재는 별도 spec으로 분리"로 미뤄둔 항목이다. P6(n8n 연동)이 이 부채를 **선택 사항에서 차단 조건으로** 바꾼다.

현재 `backend/app/main.py`에는 인증이 **전혀 없다**:

- 모든 라우트에 `Depends(...)` 인증 의존성이 하나도 없다 (grep 확인: 0건).
- `CORSMiddleware(allow_origins=["*"], allow_credentials=True, allow_methods=["*"])` — 전 출처 허용.
- 현재 안전한 유일한 이유는 `config.WEB_HOST` 기본값이 `127.0.0.1`(L575)이라 루프백에만 바인딩되기 때문이다.

n8n이 별도 호스트/컨테이너에서 돌면 `ALPHA_GEN_HOST=0.0.0.0`으로 바꿔야 하고, 그 순간 네트워크에 도달 가능한 누구나 인증 없이 다음을 호출할 수 있다:

- `POST /api/orders/manual` → `place_manual_order()` → KIS 실계좌 주문 시도
- `POST /api/safety/emergency-stop {"enabled": false}` → 긴급정지 해제
- `POST /api/safety/stage {"stage": "live_full"}` → 실거래 승격
- `POST /api/system/db/reset` → DB 초기화

즉 **P5 없이 P6를 붙이면 안 된다.**

## 영향받는 파일

- **`backend/app/main.py`** (라우트 계층): 인증 의존성 추가, CORS origin 제한.
- **`backend/app/models.py`**: 변경 없음.
- **`config/__init__.py`**: 신규 상수 추가 (아래 참조 — 기존 리스크/게이트 상수는 **변경 없음**).
- **`backend/app/services.py`**: **변경 없음.** 서비스 계층은 인증을 모른다 (라우트 계층 관심사).
- **`tests/test_backend_api.py`**: 인증 테스트 추가.

## 신규 config 상수 (모두 fail-closed 기본값)

| 상수 | 기본값 | 의미 |
|---|---|---|
| `API_AUTH_TOKEN` | `""` | 정적 bearer 토큰. `.env`에서 주입 |
| `API_AUTH_REQUIRED` | `True` | 인증 강제 여부 |
| `API_CORS_ORIGINS` | `"http://localhost:5173"` | 콤마 구분 허용 출처. `*` 금지 |

`API_AUTH_REQUIRED=True`인데 `API_AUTH_TOKEN`이 비어 있으면 **앱 기동을 실패시킨다** (조용히 인증을 끄지 않는다). `MOCK_MODE=True`에서만 토큰 없이 기동 허용 — 단 이때도 쓰기 라우트는 `127.0.0.1` 요청만 통과.

## 인증 적용 범위

- **읽기 라우트**(`GET /api/health`, `/api/ready`): 인증 면제 — 컨테이너 헬스체크용.
- **그 외 모든 라우트**: bearer 토큰 필수.
- **관리자 라우트**(`/api/safety/*`, `/api/system/*`, `/api/agent/worker/*`): 토큰 + 기존 `confirm: true` 이중.

## 리스크/게이트 파라미터 변경 여부

**없음.** `MAX_POSITION_PCT`, `STOP_LOSS_PCT`, `MAX_DRAWDOWN_PCT`, `ALLOW_LIVE_TRADING`, `EMERGENCY_STOP`, `LIVE_MAX_ORDERS_PER_CYCLE`, `LIVE_MAX_ORDERS_PER_DAY`, `MAX_CONSECUTIVE_LOSSES`, `MAX_DAILY_LOSS_PCT`, `QUOTE_STALENESS_SEC`, `SIGNAL_STALENESS_SEC` 전부 그대로. 접근 제어만 **강화** 방향으로 추가.

`config.MOCK_MODE` / `config.OPERATING_STAGE` / `SafetyService.ensure_order_allowed()` 영향: **없음.**

---

# P6: n8n → TradingService 연동 (외부 제안 경로) — 🔲 사람 승인 대기

## 배경 (왜)

n8n 워크플로우의 Claude 노드가 고배당 종목 후보와 매수 수량을 JSON으로 출력하고, 이를 alpha-gen에 태워 실행하려는 요구.

**그대로 붙이면 안 되는 이유** — n8n 프롬프트가 출력하는 `orders[].volume`을 그대로 주문 수량으로 쓰면 CLAUDE.md §4.1의 게이트 구조가 무력화된다. LLM은 `total_asset`, 현재 포지션, `MAX_POSITION_PCT`(6%), `CONFIDENCE_SIZING`을 보지 못한 채 수량을 정하기 때문이다.

기존 코드에 이미 올바른 패턴이 있다 — `TradingService.auto_buy_from_signals()`(services.py L1149)는 수량을 LLM이 아니라 `risk_manager.get_position_size(total_asset, sentiment_score, price)`(L1184)로 **서버가** 계산하고, `execution_mode()`에 따라 `place_paper_order`/`place_shadow_order`/`place_live_order`로 분기한다. 외부 제안 경로도 이 패턴을 그대로 따른다.

## 핵심 설계 원칙

> **n8n은 후보를 좁히기만 한다. 넓히지 못한다.**
> 실행 대상 = (alpha-gen이 자체 생성한 `buy_signal=true` 시그널) ∩ (n8n이 제안한 티커)

이 교집합 규칙 하나가 아래 문제를 동시에 해결한다:

| 문제 | 교집합 규칙이 해결하는 방식 |
|---|---|
| LLM 환각 티커 | 서버 시그널에 없는 종목은 애초에 교집합에 없음 |
| `analyzed_at`/`quote_collected_at` 위조 → `ensure_signal_freshness()` fail-closed 우회 | 외부 payload의 타임스탬프를 **아예 받지 않는다.** 서버가 `store.list_recent_signals()`에서 자기가 만든 시그널을 조회해 붙임 |
| 수량 산정에 `sentiment_score`가 필요한데 배당 전략엔 없음 | 서버 시그널이 `sentiment_score`를 이미 갖고 있음 (services.py L549) |
| 외부가 리스크 한도를 넓힘 | 교집합은 원소 수가 늘어날 수 없음 |

## 아키텍처

```
n8n Cron
  → GET /api/dashboard, /api/portfolio, /api/signals   (읽기, 컨텍스트 수집)
  → Claude 노드 (고배당 전략 프롬프트) → 후보 티커 JSON
  → POST /api/external/proposals                        ← 신규 엔드포인트 (딱 1개)
        ↓
   ExternalProposalService  (services.py 신규 클래스)
        ↓ ① 화이트리스트 검증 ② 서버 시그널 교집합 ③ 서버측 사이징 ④ 외부 전용 한도
        ↓
   TradingService.place_paper_order / place_shadow_order / place_live_order  (기존, 무변경)
        ↓
   SafetyService.ensure_order_allowed()                 ← 기존 게이트 그대로
```

**n8n은 `order_engine.py` / `market_adapters.py` / `order_registry.py`에 어떤 경로로도 접근하지 않는다.**

## 요청/응답 계약

### 요청 — `POST /api/external/proposals`

```json
{
  "proposal_id": "n8n:{$execution.id}",
  "session": "KR",
  "candidates": [
    {"stock_code": "005930", "rank": 1, "max_qty": 3, "rationale": "배당락 3일 전, payout 42%"}
  ],
  "context": {"fx_rate": 1342.5, "strategy": "high_dividend_v1"}
}
```

- `max_qty`: **상한 힌트일 뿐.** 실제 수량 = `min(max_qty, risk_manager.get_position_size(...))`. 즉 완화 방향으로 작용 불가.
- `rationale` / `context`: 감사 로그(`store.add_audit_event(payload=...)`)와 order metadata에만 기록. 어떤 판정에도 쓰이지 않는다.
- `analyzed_at`/`quote_collected_at`/`sentiment_score`/`current_price`는 **요청 스키마에 존재하지 않는다** (있으면 422 거절).

### 응답

서버가 실제 체결 결과로 생성한다. **LLM이 `telegram_message`를 만들지 않는다** — 실행 전에 쓰인 "매수 완료" 문구는 실제 체결 여부와 무관하게 나가므로 허위 보고가 된다.

```json
{
  "proposal_id": "n8n:1234",
  "mode": "paper",
  "accepted": [{"stock_code": "005930", "qty": 2, "price": 71300, "status": "filled", "order_id": "..."}],
  "rejected": [{"stock_code": "O", "reason": "서버 시그널에 buy_signal=true 없음"}],
  "telegram_message": "…서버가 체결 결과로 생성…"
}
```

## 신규 config 상수 (전부 강화 방향, fail-closed)

| 상수 | 기본값 | 의미 |
|---|---|---|
| `EXTERNAL_PROPOSAL_ENABLED` | `False` | 사람이 명시적으로 켜야 동작 |
| `EXTERNAL_PROPOSAL_ALLOW_LIVE` | `False` | `False`면 `execution_mode()=="live"`여도 외부 제안은 paper로 강등 |
| `EXTERNAL_PROPOSAL_MAX_PER_RUN` | `3` | 1회 요청당 최대 주문 수 |
| `EXTERNAL_PROPOSAL_MAX_PER_DAY` | `5` | 일일 외부 제안 주문 수 |
| `EXTERNAL_PROPOSAL_ALLOWED_SESSIONS` | `"KR"` | 허용 세션 |

기존 `LIVE_MAX_ORDERS_PER_CYCLE`/`PER_DAY` 한도 **위에 추가로** 얹힌다. 대체가 아니다.

## 명시적 금지 사항

1. **`place_manual_order()`를 쓰지 않는다.** 이 함수는 `client_order_id`를 받지 않고 `_create_intent()`를 호출하지 않아 `order_events` 행을 만들지 않는다 → `_count_live_orders()`/`_daily_realized_loss()`/`_consecutive_losses()` 집계에 잡히지 않는다. n8n은 재시도가 기본 동작이므로 멱등성이 없는 이 경로는 이중 체결로 직결된다.
2. **매수 전용.** `side`는 항상 `"buy"`. 매도는 `run_stop_loss_cycle()`/EOD 로직이 소유한다. 외부 오판에 의한 강제 청산을 막는다.
3. **스테이지·긴급정지 조작 불가.** `ExternalProposalService`는 `execution_mode()`/`get_stage()`를 **읽기만** 한다. `set_stage()`/`set_emergency_stop()`을 호출하지 않는다 (CLAUDE.md §4.2).
4. **종목 자동 추가 금지.** 화이트리스트(`config.KR_STOCKS` + `config.US_STOCKS` + `store.get_custom_stocks()`)에 없으면 거절. `store.add_custom_stock()`을 호출하지 않는다.
5. **`ensure_order_allowed()` 내부를 건드리지 않는다.**

## 멱등성

`client_order_id = f"ext:{proposal_id}:{session}:{stock_code}:buy"`.

`store.create_order()`가 쓰는 `order_events.client_order_id`는 `UNIQUE`(store.py L85)이고 `_create_intent()`가 `_ensure_idempotent()`로 선조회하므로(services.py L645-652), n8n HTTP Request 노드 재시도나 워크플로우 재실행 시 두 번째 호출은 기존 주문을 반환하고 새 주문을 만들지 않는다.

`proposal_id`는 n8n `$execution.id` 기반이라 실행마다 고유하다. **주의**: n8n에서 "Retry from failed node"가 아니라 "Execute Workflow"를 다시 누르면 새 `$execution.id`가 발급되어 멱등 키가 달라진다 — 이 경우 `EXTERNAL_PROPOSAL_MAX_PER_DAY`가 2차 방어선이다.

## 구현 불가 / 데이터 부재로 이번 스코프에서 제외

n8n 프롬프트의 가드레일 4개 중 3개는 **alpha-gen에 데이터 소스가 없어 서버가 검증할 수 없다**:

| n8n 가드레일 | 저장소 현황 | 처리 |
|---|---|---|
| 환율 1,350원 기준 국장/미장 배분 | ✅ `market_data.fetch_usd_krw()`(L752) 존재 | 서버가 자체 환율로 재확인 가능. 단 이번 스코프에선 `context.fx_rate`를 감사 로그에만 기록 |
| 배당수익률 / 배당성향 / 배당락일 | ❌ **전무.** `dividend`/`배당`/`payout` grep 0건 | 서버 검증 불가. n8n 자체 데이터로 후보 선정에만 사용, 리스크 판정엔 일절 반영 안 함 |
| 섹터 30% 집중 제한 | ❌ `KR_STOCKS`/`US_STOCKS`에 `sector` 필드 없음 | **구현 불가.** 별도 작업 필요 |
| 예수금 2% 현금 보존 | △ `store.get_paper_cash()` 존재하나 명시적 현금 하한 로직 없음 | 별도 작업 |

**전략 정합성 경고**: alpha-gen은 뉴스 감성(`sentiment_score`) + 기술적 지표 + OHLCV 기반 모멘텀 시스템이다. `CONFIDENCE_SIZING`은 감성 점수 2/1/0/-1/-2에만 매핑된다(config L437-442). 고배당 전략은 이 축과 무관하므로, 교집합 규칙 하에서 **"배당은 좋은데 감성 점수가 낮은 종목"은 영구히 주문되지 않는다.** 이것은 버그가 아니라 이 설계가 의도한 fail-closed 동작이다. 배당 전략을 1급 시민으로 만들려면 배당 데이터 레이어 + 사이징 축 추가라는 별도의 훨씬 큰 작업이 필요하며, 그건 이 spec의 범위가 아니다.

## 영향받는 파일

- **`backend/app/services.py`**: `ExternalProposalService` 신규 클래스 추가, `build_service_bundle()`에 등록. **기존 `SafetyService`/`TradingService`/`RiskService`는 무변경.**
- **`backend/app/main.py`**: `POST /api/external/proposals` 라우트 1개 추가 (P5 인증 의존성 적용).
- **`backend/app/models.py`**: `ExternalProposalRequest` 추가.
- **`config/__init__.py`**: 위 신규 상수 5개 추가.
- **저수준 모듈**(`order_engine.py`/`market_adapters.py`/`order_registry.py`/`risk_manager.py`/`market_data.py`): **전부 무변경.**

## 리스크/게이트 파라미터 변경 여부

**기존 상수 변경 없음.** 신규 상수 5개는 전부 추가 제약(강화)이며 기본값이 `False`/보수적 수치다.

`SafetyService.ensure_order_allowed()` 영향: **없음** — 호출만 하고 내부는 건드리지 않는다.

## 검증 시나리오 (HARNESS_WORKFLOW.md §4)

1. `EXTERNAL_PROPOSAL_ENABLED=False`(기본) → 모든 제안 거절.
2. 화이트리스트 밖 티커(`"FAKE"`) → 거절, 종목 자동 추가 안 됨.
3. 서버 시그널이 `buy_signal=false` → 거절 (n8n이 아무리 강력히 제안해도).
4. `max_qty=999` → 실제 qty가 `get_position_size()` 값으로 캡됨.
5. 동일 `proposal_id` 2회 호출 → 두 번째는 기존 order 반환, 신규 주문 0건.
6. `EMERGENCY_STOP=True` → 전량 거절.
7. 휴면 모드(`SLEEP_MODE=True`) → 매수 전량 거절.
8. `EXTERNAL_PROPOSAL_MAX_PER_RUN=3`인데 후보 10개 → 3건만 실행.
9. `execution_mode()=="live"` + `EXTERNAL_PROPOSAL_ALLOW_LIVE=False` → paper로 강등 실행.
10. 요청에 `analyzed_at` 포함 → 422 거절 (타임스탬프 주입 차단).

---

# P7: 배당 데이터 레이어 (`dividends.py`) — 🔲 사람 승인 대기

## 배경 (왜)

**사람 결정 (2026-08-27 대화)**: 배당 데이터는 n8n이 아니라 **alpha-gen 내부에 둔다.**

이 결정이 옳은 이유 — P6 설계상 외부(n8n)가 보낸 값은 서버가 검증할 수 없으므로 **리스크 판정에 일절 쓸 수 없다**(감사 로그 기록만). 배당 데이터가 alpha-gen 안에 있어야만 `배당성향 85% 초과 제외` 같은 규칙을 서버가 강제하는 게이트로 만들 수 있다. n8n에 두면 배당 규칙은 영원히 "권고"에 머문다.

## 기존 자산 재사용

`ohlcv.py`가 그대로 템플릿이다 — 전용 SQLite(`data/ohlcv.db`), `_to_yf_ticker()`, `fetch_and_store()`, `get_latest_signals()`, `refresh_all()` 구조를 동일하게 따른다. `yfinance>=0.2.40`은 이미 `requirements.txt`에 있으므로 신규 의존성 없음.

## 데이터 소스 및 수집 필드

`yfinance.Ticker(...)`에서 수집:

| 필드 | yfinance 출처 | 용도 |
|---|---|---|
| `dividend_yield` | `.info["dividendYield"]` | 후보 선정 |
| `payout_ratio` | `.info["payoutRatio"]` | **배당 함정 필터 (85% 초과 제외)** |
| `ex_dividend_date` | `.info["exDividendDate"]` | 배당락 임박(3~5일) 가점 |
| `dividend_history` | `.dividends` | 배당 연속성/삭감 이력 |
| `trailing_eps` | `.info["trailingEps"]` | 적자 기업 제외 |

## 신규 파일 / 영향받는 파일

- **`dividends.py`** (신규, 저수준 모듈): `data/dividends.db` 전용. `ohlcv.py`와 동일 컨벤션.
- **`config/__init__.py`**: 배당 필터 상수 추가.
- **`backend/app/services.py`**: P6의 `ExternalProposalService`가 참조. **기존 `*Service` 무변경.**
- **`tests/test_dividends.py`** (신규).
- **`order_engine.py`/`market_adapters.py`/`risk_manager.py`/`market_data.py`**: 무변경.

## 신규 config 상수

| 상수 | 기본값 | 의미 |
|---|---|---|
| `DIVIDEND_MAX_PAYOUT_RATIO` | `0.85` | 초과 시 후보 제외 (배당 함정) |
| `DIVIDEND_MIN_YIELD` | `0.03` | 최소 배당수익률 |
| `DIVIDEND_TRAP_YIELD_THRESHOLD` | `0.08` | 이 값 초과 시 payout/EPS 검증 강제 |
| `DIVIDEND_EX_DATE_WINDOW_DAYS` | `5` | 배당락 임박 판정 창 |
| `DIVIDEND_DATA_MAX_AGE_HOURS` | `24` | 초과 시 stale → **fail-closed 제외** |

`DIVIDEND_DATA_MAX_AGE_HOURS`는 `ensure_signal_freshness()`와 같은 fail-closed 철학이다 (CLAUDE.md §5-6). 배당 데이터가 없거나 오래되면 후보에서 **제외**하지, 통과시키지 않는다.

## 알려진 선행 이슈 (이 spec에서 함께 처리)

`ohlcv.py:61`의 `_to_yf_ticker()`가 KR 6자리 코드를 무조건 `.KS`(KOSPI)로 변환한다. `config.KR_STOCKS`에는 KOSDAQ 종목이 포함되어 있어(`086520` 에코프로, `196170` 알테오젠, `277810`, `357780` 등) 이들은 yfinance 조회가 실패하거나 잘못된 데이터를 반환한다.

`dividends.py`는 이 버그를 상속하지 않도록 `.KS` 실패 시 `.KQ`로 재시도하는 변환 함수를 자체 구현한다. **`ohlcv.py` 자체 수정은 이번 스코프 밖**(별도 항목) — 기존 시그널 생성 동작을 건드리지 않기 위함.

## 리스크/게이트 파라미터 변경 여부

**기존 상수 변경 없음.** 신규 상수 5개는 전부 후보를 **좁히는** 방향(추가 제외 조건)이다.

`config.MOCK_MODE` / `config.OPERATING_STAGE` / `SafetyService.ensure_order_allowed()` 영향: **없음.**

## P6에 미치는 영향

P6 spec의 "구현 불가" 표가 다음과 같이 갱신된다:

| 항목 | P7 이후 |
|---|---|
| 배당수익률/배당성향/배당락일 | ✅ **서버 검증 가능** — 게이트로 승격 |
| 섹터 30% 집중 제한 | ❌ 여전히 불가 (`sector` 필드 없음) — 별도 항목 |
| 현금 2% 보존 | ❌ 여전히 불가 — 별도 항목 |

단 **교집합 규칙은 유지된다** — 배당 데이터가 생겨도 `buy_signal=true`가 아닌 종목은 주문되지 않는다. 배당 필터는 교집합을 **더 좁히는** 3차 조건으로 작동한다.

## 검증 시나리오

1. `payout_ratio=0.90` → 제외
2. `dividend_yield=0.12` + `payout_ratio=None` → 제외 (검증 불가 = 제외)
3. `trailing_eps` 음수(적자) → 제외
4. 배당 데이터가 `DIVIDEND_DATA_MAX_AGE_HOURS` 초과 → 제외 (fail-closed)
5. yfinance 응답에 `NaN`/`None` 혼재 → 크래시 없이 제외 (CLAUDE.md §5)
6. KOSDAQ 종목(`086520`) → `.KQ` 폴백으로 정상 수집
7. `ex_dividend_date`가 과거 → 배당락 임박 가점 없음, 제외도 아님

---

# P9: 실데이터 백테스트 재작성 — 🔲 사람 승인 대기

## 배경 (왜)

현재 `backtest.py`는 **손실을 낼 수 없는 구조**다. 전략 검증 도구가 아니라 배관 스모크 테스트다.

| 위치 | 내용 | 결과 |
|---|---|---|
| `backtest.py:63` | `generate_mock_price_history()` → `random.uniform(-0.015, 0.015)` 랜덤워크 | 실제 주가가 아닌 난수 |
| `backtest.py:75` | `sell_price = int(history[-1] * 1.02)` | **모든 거래 청산가를 +2%로 하드코딩. 승률 항상 100%** |
| `backtest.py:63,75` | 매수·매도가 같은 봉(`history[-1]`) | 보유 기간·가격 경로 없음 |
| `backtest.py:55` | `default_scores = {code: 2 for code in stocks}` | 전 종목 최대 강세 가정 |
| 전체 | 수수료·거래세·슬리피지 상수 부재 (`config/__init__.py` grep 0건) | 비용 0 |

따라서 이 백테스트의 `total_return_pct`/`win_rate` 출력은 **전략에 대한 정보량이 0**이다.

추가로 **라이브/백테스트 불일치**가 있다. 라이브 경로(`services.py:504-511`)는 `market_data.get_prev_day()`로 **실제 전일 고가/저가**를 받아 `evaluate_buy_technicals(..., prev_day=prev_day)`에 넘긴다. 반면 `backtest.py`는 `prev_day`를 넘기지 않아 `technical.py:162`의 `price_history[-15:-1]` (14일 고저 프록시)로 폴백한다. 변동성 돌파 목표가(`calc_volatility_target`)가 달라지므로 **현재 백테스트는 라이브와 다른 전략을 검증하고 있다.**

**운영 현황**: `data/` 디렉터리가 존재하지 않는다. 이 시스템은 mock/paper 포함 한 번도 실행된 적이 없다 — 주문 0건, 자산 이력 0건, OHLCV 0건.

## 핵심 설계 결정 ①: 감성 축은 정직하게 백테스트할 수 없다

라이브 매수 조건은 `services.py:544`의 `base_buy = sentiment["score"] >= SENTIMENT_BUY_THRESHOLD and technicals["signal"]` 이다. 이 중 **감성 축은 과거 재현이 불가능**하다:

1. 과거 뉴스 확보 불가 — `news_analyzer.py`는 feedparser RSS 기반이라 최근 것만 나온다.
2. **치명적 룩어헤드** — 과거 날짜에 대해 지금 Claude를 호출하면 모델이 그 이후 결과를 이미 알고 있다. 감성 점수가 미래 정보로 오염된다.
3. 비용 — 종목×일자만큼 LLM 호출이 필요하다 (`CLAUDE_DAILY_COST_ALERT_USD` 초과 확실).

**따라서 감성을 "재현"하려 시도하지 않는다. 대신 시나리오 축으로 분리해 구간(bracket)을 만든다:**

| 시나리오 | 감성 처리 | 해석 |
|---|---|---|
| `tech_only` | 감성 조건 항상 통과 | **기술 레이어 단독 성능.** 가장 중요한 기준선 |
| `sentiment_random` | 관측된 통과율(paper 운영에서 측정)로 베르누이 랜덤, 시드 고정 | 감성이 무작위일 때 |
| `sentiment_oracle` | 향후 N일 수익률 상위만 통과 | **상한선.** 감성이 완벽할 때조차 이 정도라는 천장 |

**판정 규칙**: `tech_only`가 벤치마크를 못 이기면, 감성 축이 전체 알파를 혼자 짊어져야 한다는 뜻이다. 그건 훨씬 높은 입증 책임이며 백테스트로는 증명할 수 없으므로 **실전 승격 근거로 쓸 수 없다.**

## 핵심 설계 결정 ②: 라이브 코드 경로를 그대로 재생한다

백테스트 전용 전략 로직을 새로 쓰지 않는다. `technical.evaluate_buy_technicals()`와 `risk_manager.get_position_size()`/`check_stop_loss()`를 **라이브와 동일한 인자 형태로** 호출한다. 특히:

- `prev_day={"prev_high": ..., "prev_low": ...}`를 **실제 OHLCV의 전일 고저로 채워서 넘긴다** (라이브 동작과 일치시킴).
- `quote={"current_price": ..., "open_price": ...}`도 실제 봉에서 채운다.

이렇게 해야 "백테스트는 좋았는데 실전은 다르다"의 원인 하나를 제거할 수 있다.

## 룩어헤드 차단 규칙 (구현 시 불변식)

1. t일 판단에는 **t-1일까지의 종가**와 **t일 시가**만 쓴다. t일 종가/고가/저가는 판단에 쓰지 않는다.
2. 체결가는 판단 시점 이후 가격을 쓴다 — 매수는 t일 시가(또는 목표가 돌파 시 목표가), 절대 t일 종가가 아니다.
3. 지표(RSI/MA/MACD/볼린저)는 t 시점까지 잘린 시계열로만 계산한다. 전체 구간에 한 번 계산 후 슬라이싱하지 않는다.
4. 종목 유니버스를 "지금 `config.KR_STOCKS`에 있는 종목"으로 고정하는 것은 **생존 편향**이다 — 한계로 명시하고 리포트에 기록한다(이번 스코프에서 해결하지 않음).

## 비용 모델

| 상수 | 기본값 | 비고 |
|---|---|---|
| `BACKTEST_FEE_BPS_BUY` | `1.5` | **사용자가 실제 KIS 수수료율로 교체 필요** |
| `BACKTEST_FEE_BPS_SELL` | `1.5` | 동일 |
| `BACKTEST_TAX_BPS_SELL_KR` | `18.0` | 증권거래세+농특세. **현행 세율 확인 후 교체 필요** |
| `BACKTEST_SLIPPAGE_BPS` | `10.0` | 시장가 체결 가정 |

기본값은 **플레이스홀더**다. 사용자가 실제 계좌 조건으로 채우기 전까지 결과를 승격 근거로 쓰지 않는다.

비용 민감도 리포트를 필수 출력에 포함한다 — 슬리피지 0/5/10/20bps에서 수익률이 어떻게 변하는지. 여기서 부호가 바뀌면 그 전략은 실전 불가다.

## 워크포워드 검증

전체 구간을 단일 백테스트하지 않는다. 롤링 분할:

- 학습(파라미터 관찰) 구간 → 검증(out-of-sample) 구간을 앞으로 굴린다
- `RSI_PERIOD`/`MA_SHORT`/`MA_LONG`/`K_VALUE`/`STOP_LOSS_PCT`를 학습 구간에서 고른 뒤 검증 구간 성과만 집계한다
- **검증 구간 성과만 리포트한다.** 학습 구간 성과는 보고서에 넣지 않는다 (과최적화 자기기만 방지)

`ohlcv.py`가 200일치를 저장하므로 초기 구간이 짧다. `fetch_and_store(days=...)`를 늘려 최소 3~5년치를 확보하는 것을 선행 작업으로 둔다.

## 벤치마크 (필수)

절대 수익률만 보고하지 않는다. 반드시 함께 출력:

1. **동일 유니버스 동일가중 매수 후 보유** — 종목 선택에 알파가 있는가
2. **KOSPI 지수** (`^KS11`) 매수 후 보유 — 시장 대비 알파가 있는가
3. MDD, 샤프 비율, 회전율, 거래 횟수

**이 시스템의 존재 이유는 2번을 이기는 것이다.** 못 이기면 지수 ETF를 사는 게 낫고, 그 결론도 유효한 결과다.

## 사전 등록 성공/실패 판정 기준

결과를 본 뒤 합리화하지 않기 위해 **구현 전에** 기준을 고정한다:

- **실패**: `tech_only` 시나리오의 워크포워드 검증 구간 수익률이 비용 반영 후 KOSPI 매수후보유보다 낮음 → 전략 재설계. P6/P8(자동화) 진행 중단.
- **보류**: 이기지만 MDD가 `MAX_DRAWDOWN_PCT`(15%)를 초과 → 사이징 재조정 후 재검증.
- **조건부 통과**: 비용 반영 후에도 벤치마크 초과 + MDD 15% 이내 + 슬리피지 20bps에서도 부호 유지 → **paper 관찰 단계로만** 진행. 실전 승격 근거로는 여전히 불충분.

백테스트 통과가 실전 승격 근거가 되는 경우는 없다. 최소 수개월 paper 관찰이 별도로 필요하다.

## 영향받는 파일

- **`backtest.py`**: 전면 재작성. 기존 `run_backtest()` 시그니처는 `BacktestService`가 호출하므로 **하위 호환 유지**(신규 인자는 기본값 제공).
- **`backend/app/services.py`**: `BacktestService.run()`이 신규 파라미터(시나리오, 비용, 워크포워드)를 전달하도록 확장. **다른 `*Service` 무변경.**
- **`backend/app/models.py`**: `BacktestRequest` 확장.
- **`config/__init__.py`**: 비용 상수 4개 추가.
- **`tests/test_backtest.py`** (신규).
- **`ohlcv.py`**: 무변경 (읽기만). 단 `_to_yf_ticker()` `.KS` 하드코딩 문제로 KOSDAQ 종목은 데이터 확보 불가 — 리포트에 제외 종목으로 명시 (P7에서 `.KQ` 폴백 구현 후 재실행).
- **`technical.py`/`risk_manager.py`/`market_data.py`/`order_engine.py`**: **무변경.** 호출만 한다.

## 리스크/게이트 파라미터 변경 여부

**없음.** `MAX_POSITION_PCT`, `STOP_LOSS_PCT`, `MAX_DRAWDOWN_PCT`, `ALLOW_LIVE_TRADING`, `EMERGENCY_STOP`, `LIVE_MAX_ORDERS_*`, `MAX_CONSECUTIVE_LOSSES`, `MAX_DAILY_LOSS_PCT`, `QUOTE_STALENESS_SEC`, `SIGNAL_STALENESS_SEC` 전부 그대로.

워크포워드에서 `STOP_LOSS_PCT` 등을 **탐색**하지만 이는 백테스트 내부 지역 변수이며 `config` 값을 쓰지 않는다. 탐색 결과로 config 기본값을 바꾸는 것은 **별도 사람 승인 사항**이다 (CLAUDE.md §4.3).

`config.MOCK_MODE` / `config.OPERATING_STAGE` / `SafetyService.ensure_order_allowed()` 영향: **없음.** 백테스트는 주문 경로를 전혀 건드리지 않는다.

## 검증 시나리오 (테스트)

1. 알려진 상승 시계열 입력 → 매수 후 수익, 비용만큼 정확히 차감되는지 산술 검증
2. 알려진 하락 시계열 → `STOP_LOSS_PCT` 손절이 발동하고 손실이 기록되는지
3. **룩어헤드 회귀 테스트**: t일 종가를 인위적으로 조작해도 t일 매수 판단이 바뀌지 않아야 함
4. OHLCV 데이터 0행 / `period+1` 미만 → 크래시 없이 빈 결과 (CLAUDE.md §5)
5. `NaN`/`None`/0/음수 종가 혼재 → 해당 봉 제외, 크래시 없음
6. 비용 0으로 설정 시 vs 기본 비용 → 수익률 차이가 회전율 × 비용률과 일치
7. 동일 시드 2회 실행 → 완전히 동일한 결과 (재현성)
8. `sentiment_oracle` 수익률 ≥ `tech_only` ≥ 랜덤 하한 (시나리오 순서 정합성)
9. 벤치마크 계산이 유니버스 변경에 따라 올바르게 갱신되는지
10. 워크포워드 분할에서 검증 구간이 학습 구간과 겹치지 않는지

---

# P9 판정 결과 — ❌ 실패 (2026-08-27)

사전 등록 기준(P9 "사전 등록 성공/실패 판정 기준")에 따라 판정한다. **결과를 본 뒤 기준을 바꾸지 않았다.**

## 판정: 실패

> 실패 조건: `tech_only` 시나리오의 워크포워드 검증 구간 수익률이 비용 반영 후 KOSPI 매수후보유보다 낮음 → 전략 재설계. **P6/P8(자동화) 진행 중단.**

| 지표 | 결과 |
|---|---|
| tech_only 전체구간 (실비용) | **-82.09%** |
| KOSPI 매수후보유 | **+116.53%** |
| 유니버스 동일가중 매수후보유 | +180.91% |
| 워크포워드 OOS 평균 (7폴드) | **-21.89%** |
| 양(+) OOS 폴드 | **0 / 7** |
| tech_only 전체구간 (**무비용**) | **-58.87%** |

## 근거

**1. 비용만의 문제가 아니다.** 수수료·세금·슬리피지를 전부 0으로 놔도 -58.87%다. 전략 자체에 음의 엣지가 있다.

**2. 모든 폴드·모든 연도에서 음수.** 레짐 의존이 아니라 구조적 결함이다.

| 연도 | 전략 | KOSPI |
|---|---|---|
| 2021 | -14.29% | -5.30% |
| 2022 | -33.29% | -25.19% |
| 2023 | -36.25% | **+19.30%** |
| 2024 | -45.62% | -10.13% |
| 2025 | -30.12% | **+75.67%** |
| 2026 | -39.91% | **+57.98%** |

KOSPI가 +75%, +58% 오른 해에 -30%, -40%를 잃었다. 불운이 아니라 엣지가 뒤집혀 있다.

**3. 거래당 기대값 분해 — 실제 사인**

```
거래당 평균  -0.6030%
평균이익     +1.795%  (1,877건)
평균손실     -1.757%  (3,901건)
승률          32.5%
기댓값 = 0.325 × 1.795 + 0.675 × (-1.757) = -0.603%   ✓
```

**손익 크기가 거의 대칭(+1.795 vs -1.757)인데 승률이 32.5%다.** 대칭 페이오프에서는 승률 50% 초과가 필요하다. 수학적으로 불가능한 조합이다.

**왜 대칭인가** — 청산 규칙에 비대칭성이 없다. 손절은 전체의 11.8%만 발동하므로 `STOP_LOSS_PCT`(4%)는 사실상 구속력이 없고, 이익 실현 목표가나 트레일링이 없어 `KR_SELL_TIME` 종가 청산이 상방을 잘라버린다.

**진단**: **장중 강세(전일 레인지의 절반만큼 오른 지점)에 매수해서 종가에 파는 것이 KR 대형주에서 체계적으로 음수다.** 진입 타이밍 자체가 불리하다. 왕복 비용 0.38%를 빼도 -0.223%/거래로 여전히 음수다.

**4. 회전율 269배(연 54배).** 비용 530만원 = 초기자본의 53%가 마찰로 소각.

**5. `sentiment_oracle` +617%는 반증이 아니다.** 오라클은 "종가 > 진입가"인 날만 고르므로 정의상 이긴다. 유일한 용도는 천장 측정이며, 그 천장은 **승률을 32.5% → 70~92%로 끌어올려야 한다**고 말한다. 뉴스 감성 분석이 달성할 수 있는 범위가 아니다.

## 부수 발견

1. **전일 레인지=0 퇴화 케이스 실재**: 192건/5,778건(3.3%). 전일 고가=저가면 목표가가 시가로 붕괴해 무조건 체결된다. 주 원인은 아니지만 `calc_volatility_target()`에 하한 가드가 없다.
2. **`ohlcv.py:61` `_to_yf_ticker()` `.KS` 하드코딩 버그 실증**: KOSDAQ 4종목(`086520`,`196170`,`041510`,`035900`)이 `.KS`로 조회 시 빈 결과가 아니라 **28행짜리 오염 데이터**를 반환했다. `.KQ` 폴백으로 1,225행 복구. P7 예상이 맞았다.
3. **US 종목 백테스트 불가**: `calc_volatility_target(int(open), int(prev_high), int(prev_low))`의 정수 절단이 $50대 종목에서 전일 레인지를 뭉갠다. **이는 백테스트가 아니라 라이브 코드의 결함**이며 `ENABLE_KIS_US_ORDERS` 활성화 전 반드시 수정해야 한다.

## 후속 조치 (P6 설계 수정 필요)

**P6의 "교집합 규칙"을 그대로 쓰면 안 된다.** 해당 규칙은 `buy_signal=true`를 건전한 게이트로 가정했으나, 실측 결과 `buy_signal`은 거래당 -0.603%의 **입증된 음의 엣지**다. 고배당 전략을 이 게이트에 통과시키면 검증된 손실원에 오염된다.

P6 재설계 시 선택지:
- (a) 고배당 전략을 `buy_signal`과 **독립적인** 별도 경로로 두고, 안전게이트(`ensure_order_allowed()`)만 공유
- (b) 모멘텀 전략을 폐기하고 배당 전략으로 대체
- (c) `buy_signal`을 재설계한 뒤 P9를 재실행

어느 쪽이든 사람 결정이 필요하다. **P6/P8은 이 결정 전까지 착수하지 않는다.**

---

# 전략 방향 결정 (2026-08-27) — (b) 모멘텀 폐기, 배당 전략으로 대체

**사람 결정**: P9 판정 결과의 세 선택지 중 **(b) 모멘텀 전략을 폐기하고 배당 전략으로 대체**를 채택.

## 즉시 발효되는 사항

1. **`buy_signal`(뉴스감성 + RSI/MA + 변동성돌파)은 주문 생성 신호에서 은퇴한다.** 거래당 -0.603%의 실측 음의 엣지이므로 어떤 신규 주문 경로도 이것을 게이트로 삼지 않는다.
2. **P6의 "교집합 규칙" 폐기.** 배당 전략은 `buy_signal`과 독립적인 경로가 되며, 공유하는 것은 `SafetyService.ensure_order_allowed()` 안전게이트뿐이다.
3. **운영 단계 동결.** 검증된 전략이 없는 상태이므로 `OPERATING_STAGE`는 `mock`/`shadow`를 벗어나지 않는다. `auto_buy_from_signals()`가 살아있는 한 `paper` 이상에서 워커를 돌리면 **입증된 손실 전략이 그대로 실행된다** — P12 통과 전까지 자동 주문을 켜지 않는다.
4. 모멘텀 코드는 **삭제하지 않는다.** 백테스트 하니스와 회귀 테스트가 의존하고, 재설계 시 비교 기준으로 필요하다.

---

# P12: 배당 전략 설계 및 검증 — 🔲 사람 승인 대기

## 데이터 가용성 실측 (2026-08-27, yfinance)

스펙을 쓰기 전에 전제를 검증했다. P9의 교훈 — 검증되지 않은 가정 위에 설계하지 않는다.

| 항목 | KR | US | 백테스트 가능? |
|---|---|---|---|
| 배당 지급 이력 (`.dividends`) | ✓ 삼성 60건 / SKT 48건 / KT 36건 | ✓ O 381건 | **✓ point-in-time 가능** |
| `dividendYield` (`.info`) | ✓ 삼성 0.57 / SKT 3.33 / KT 4.5 | ✓ | ✗ 현재값만 (룩어헤드) |
| `payoutRatio` (`.info`) | ✓ 0.075 / 0.486 / 0.449 | ✓ | ✗ 현재값만 (룩어헤드) |
| `exDividendDate` | ✓ | ✓ | ✗ 현재값만 |
| `trailingEps` | **✗ 전 종목 None** | ✓ | ✗ |
| 과거 EPS (`income_stmt`) | △ **연 4개 포인트뿐**(2022~2025) | △ | ✗ 리밸런스 시점별 불가 |

### 결정적 제약: 배당성향 필터는 백테스트할 수 없다

`.info["payoutRatio"]`는 **오늘 값**이다. 과거 리밸런스 시점에 이 값을 쓰면 룩어헤드다. `income_stmt`의 연 4개 포인트로는 point-in-time 재구성이 불가능하다.

**따라서 "배당성향 85% 초과 제외"(n8n 프롬프트 규칙 4)는 라이브에서는 적용 가능하지만 백테스트로 검증할 수 없다.** 검증되지 않은 필터를 검증된 것처럼 다루지 않는다.

백테스트 가능한 배당 지표는 `.dividends` 이력에서 파생되는 것뿐이다:
- 후행 12개월 배당 / 시점 주가 = **후행 배당수익률** ✓
- 배당 연속성 (최근 N년 무삭감) ✓
- 배당 성장률 ✓

### `trailingEps`가 KR 전 종목 None

P7 스펙의 "적자 기업 제외"는 KR에서 구현 불가다. 차선책으로 `payoutRatio`가 음수이면 적자를 시사하지만, 위와 같이 point-in-time이 아니라 라이브 전용이다.

### REIT 충돌

Realty Income(`O`)의 `payoutRatio`는 **2.364(236%)** 다. REIT은 EPS가 아니라 FFO 기준으로 배당하므로 정상이다. n8n 프롬프트의 "85% 초과 제외" 규칙을 그대로 적용하면 **프롬프트가 명시적으로 원한 리츠가 전부 배제된다.** REIT은 별도 임계값이 필요하다.

### auto_adjust 이중계상 위험

현재 `ohlcv.db`는 `auto_adjust=True`로 수집됐다 — 종가에 **배당 재투자가 이미 반영**돼 있다. 여기에 배당 수익을 또 더하면 이중계상이다. P12 백테스트는 조정 종가 기준 총수익률만 쓰고 배당을 별도 가산하지 않는다.

### 배당락 타이밍 전략은 채택하지 않는다

n8n 프롬프트 규칙 3("배당락 3~5일 전 우선 배분")은 채택하지 않는다. 두 가지 이유:

1. **구조적으로 기대값이 음수다.** 배당락일에 주가는 배당액만큼 하락한다. 배당소득세(국내 15.4%)와 왕복 거래비용을 더하면 확정 손실에 가깝다.
2. **조정 종가로는 검증 자체가 불가능하다.** `auto_adjust=True`가 배당락 하락을 이미 상쇄해버렸다.

## 전략 정의 (검증 대상)

P9가 죽은 원인은 **고회전 + 예측 의존**이었다. 그 반대로 설계한다.

- **유니버스**: `config.KR_STOCKS` 중 후행 12개월 배당 이력이 있는 종목
- **선정**: 후행 배당수익률 상위 N종목 (기본 N=10), 최근 3년 배당 무삭감 조건
- **비중**: 동일가중. `MAX_POSITION_PCT`(6%) 상한 준수
- **리밸런스**: 분기 1회 (연 4회 → 회전율 P9의 269배 대비 ~1/60)
- **청산**: 리밸런스 시 유니버스 이탈 종목만 매도. **당일 청산 없음**
- **손절**: 적용하지 않는다 — 배당 전략에서 4% 손절은 배당 수취 전 강제 이탈을 유발한다 (사람 확인 필요 항목)

## 사전 등록 성공/실패 판정 기준

**결과를 본 뒤 기준을 바꾸지 않는다.**

벤치마크는 실측으로 5년 전체 확보 완료:

| 벤치마크 | 티커 | 데이터 |
|---|---|---|
| ARIRANG 고배당주 | `161510.KS` | 1,207행 ✓ |
| KODEX 고배당 | `279530.KS` | 1,207행 ✓ |
| TIGER 배당성장 | `211900.KS` | 1,206행 ✓ |
| KODEX 200 (시장) | `069500.KS` | 1,207행 ✓ |

- **실패**: 워크포워드 OOS 평균이 비용 반영 후 **고배당 ETF(161510/279530 중 높은 쪽)보다 낮음** → 전략 폐기. 결론은 "직접 고르지 말고 고배당 ETF를 사라"이며, 그것도 유효한 결과다.
- **실패**: KODEX 200(시장)을 못 이김 → 폐기.
- **보류**: 이기지만 MDD가 `MAX_DRAWDOWN_PCT`(15%) 초과 → 사이징 재조정 후 재검증.
- **조건부 통과**: 비용 반영 후 고배당 ETF + KODEX 200 **양쪽 초과** + MDD 15% 이내 + 슬리피지 20bps에서 부호 유지 → **paper 관찰 단계로만** 진행.

**종목 선택이 고배당 ETF를 못 이기면 이 시스템의 존재 이유가 없다.** 이 기준을 완화하지 않는다.

## 영향받는 파일

- **`dividends.py`** (P7, 신규): 배당 이력 수집·저장. `data/dividends.db`
- **`backtest.py`**: 배당 전략 진입/청산 규칙 추가. **P9 하니스(비용모델·워크포워드·룩어헤드 차단·벤치마크) 재사용**
- **`config/__init__.py`**: 배당 전략 상수
- **`tests/test_dividends.py`**, **`tests/test_backtest.py`** 확장
- **무변경**: `order_engine.py`, `market_adapters.py`, `SafetyService`, `TradingService`, `risk_manager.py`, `technical.py`

## 리스크/게이트 파라미터 변경 여부

**없음.** 손절 미적용은 백테스트 내부 전략 규칙이며 `config.STOP_LOSS_PCT`를 변경하지 않는다. 실제 주문 경로에 반영하려면 별도 사람 승인이 필요하다 (CLAUDE.md §4.3).

---

# P12 판정 결과 — ❌ 실패 (2026-08-27)

사전 등록 기준을 그대로 적용한다. **결과를 본 뒤 기준을 바꾸지 않았다.**

## 판정: 실패 (독립적인 두 기준에서)

| 기준 | 결과 | 판정 |
|---|---|---|
| 워크포워드 OOS 평균 ≥ 고배당 ETF | 전략 **+16.26%** vs ETF **+17.28%** | ❌ 실패 |
| 전체구간 ≥ KODEX 200 (시장) | 전략 **+165.49%** vs **+191.08%** | ❌ 실패 |
| MDD ≤ 15% | **-15.50%** | ❌ 초과 |
| 슬리피지 20bps 부호 유지 | +161.39% | ✅ |

OOS 폴드 승패: **3승 4패**. 전체구간 +165.49%는 ARIRANG 고배당(+165.16%)과 사실상 **동률**이며 노이즈 범위다.

## 상세 (고배당 유니버스 18종목, 분기 리밸런스)

| 구성 | 수익 | MDD | 거래 | 회전 | 투자비중 | 비용 |
|---|---|---|---|---|---|---|
| N=10, 6% 상한 | +74.84% | -16.16% | 87 | 3.59배 | 50.9% | 156,785 |
| N=17, 상한 비구속 | **+165.49%** | -15.50% | 108 | 9.25배 | 91.2% | 396,464 |

벤치마크(5년 매수 후 보유): KODEX 200 **+191.08%** / ARIRANG 고배당 +165.16% / KODEX 고배당 +124.31% / TIGER 배당성장 +109.21%

## 핵심 결론

**종목 선택이 고배당 ETF에 아무것도 더하지 않는다.** 성과는 동률인데 회전율 9.25배, 비용 396,464원, 운영 리스크가 추가된다. 같은 결과를 ETF 한 종목 매수로 얻을 수 있다.

**그리고 시장지수(KODEX 200 +191.08%)가 배당 전략과 모든 배당 ETF를 이겼다.** 이 기간 고배당 팩터 자체가 시장 대비 열위였다.

## P9 판정 정정 — 실제로는 더 나빴다

P9에서 벤치마크로 쓴 `^KS11`은 **배당이 포함되지 않은 가격지수**다(+116.53%). 배당 재투자를 포함한 실제 투자 가능 벤치마크는 KODEX 200 **+191.08%** 다.

즉 P9의 모멘텀 전략은 -82.09% vs **+191.08%** 로, 보고했던 것보다 격차가 약 75%p 더 크다. 판정(실패)은 변하지 않는다.

## 참고: 성장주 유니버스 결과는 채택하지 않는다

`config.KR_STOCKS` 36종목에 같은 로직을 적용하면 N=17에서 +247.67%로 KODEX 200을 이긴다. **그러나 채택하지 않는다:**

1. **MDD -33.61%** 로 `MAX_DRAWDOWN_PCT`(15%)의 두 배를 넘는다 — 사전 등록 기준상 즉시 탈락.
2. **생존 편향이 치명적이다.** `config.KR_STOCKS`는 2026년 시점에 큐레이션된 목록으로 SK하이닉스·한미반도체 등 AI 사이클 승자가 포함돼 있다. 2021년에 이 목록을 알 수 없었다.
3. 배당 전략이 아니라 성장주 유니버스에 대한 밸류 스크린이다.

결과를 본 뒤 유리한 구성을 사후 채택하는 것은 사전 등록의 취지를 무너뜨린다.

## 수정된 버그 (판정 전에 발견)

**1차 실행은 버그에 오염돼 있었다.** 기록 목적으로 남긴다.

- **`calc_dividend_streak_years` 달력연도 버킷 결함**: 한국은 2023년 배당절차 개선으로 배당락일이 12월 → 익년 2~4월로 이동한 사례가 많다. SK텔레콤은 2024년이 3회분(2,490원)만 잡혀 2023년(3,540원) 대비 **삭감으로 오판**됐고, 삼성화재는 2023년 배당이 **0원**으로 잡혔다. 그 결과 2025년부터 선정 종목이 0~1개로 붕괴해 전략이 ETF 급등 구간(+35%, +37%)에 현금만 보유했다.
  - **수정**: 달력연도 버킷 폐기 → asof에서 1년씩 거슬러 올라가는 **TTM 비교**. 분기배당 1회분(연 25%)의 경계 이동을 흡수하도록 `DIVIDEND_CUT_TOLERANCE`(0.30) 도입.
  - **회귀 테스트 3개 추가**: SK텔레콤·삼성화재 실제 이력 고정, 진짜 삭감(-80%)은 여전히 탐지되는지 확인.
- **실행 스크립트에서 `respect_position_cap` 미전달**: N=10과 N=17이 동일 결과로 나왔다. 코드가 아닌 러너 결함.

## 후속

- P6/P8(n8n 자동화) **계속 차단.** 검증 통과한 전략이 없다.
- 다음 검토 대상은 "직접 고르기"가 아니라 **지수/ETF 매수 후 보유의 자동화**다. 이 기간 KODEX 200이 모든 능동 전략을 이겼다.

---

# P5 완료 — ✅ (2026-08-27)

## 구현

| 항목 | 내용 |
|---|---|
| `config.API_AUTH_TOKEN` | 기본 `""` |
| `config.API_CORS_ORIGINS` | 기본 `localhost:5173, 127.0.0.1:5173, localhost:8000` — **와일드카드 제거** |
| `main.ensure_bind_is_safe(host, token)` | 루프백 밖 바인딩 + 토큰 없음 → `RuntimeError`로 **기동 거부** |
| `main.verify_token` | 앱 전역 의존성. 토큰 설정 시 `/api/*`에 Bearer 강제. `secrets.compare_digest`로 타이밍 공격 방지 |
| 면제 경로 | `/api/health`, `/api/ready` (컨테이너 헬스체크) + 비 `/api/` 경로(SPA 정적 파일) |

## 위협 모델에 맞춘 설계 근거

게이트를 `MOCK_MODE`가 아니라 **`WEB_HOST` 바인딩**에 걸었다. 위험의 원천은 모의/실전 여부가 아니라 **네트워크 노출**이기 때문이다. 루프백 전용이면 토큰 없이도 기동 가능해 기존 개발 흐름이 깨지지 않고, `ALPHA_GEN_HOST=0.0.0.0`(n8n 연동 시나리오)으로 여는 순간 토큰이 강제된다.

토큰 미설정 시 요청은 그대로 통과한다 — 하위호환. 토큰을 설정하는 순간 전면 강제된다.

테스트 10개 (`tests/test_backend_auth.py`). 가장 위험한 세 경로(`/api/orders/manual`, `/api/safety/emergency-stop`, `/api/safety/stage`)가 401로 막히는지 명시적으로 검증한다.

**회귀**: `1 failed, 103 passed, 3 skipped` — 기존 실패 1건(`.env` 미설정)만 유지.

---

# P13: 인덱스 매수후보유 자동화 검증 — 🔲 사람 승인 대기

## 배경

P9(모멘텀 -82.09%)와 P12(배당 +165.49%)가 모두 KODEX 200(**+191.08%**)에 졌다. 두 번의 정직한 검증에서 능동적 종목 선택이 시장지수를 이기지 못했다.

따라서 다음 질문은 **"무엇을 살까"가 아니라 "그냥 사서 보유하는 것에 무언가를 더할 수 있는가"** 이다.

## 검증 대상

| 구성 | 규칙 |
|---|---|
| **기준선** | KODEX 200 일시 매수 후 보유 (거래 1회) |
| **A: MA200 추세 필터** | 종가 > 200일 이동평균이면 보유, 아니면 현금 |
| **B: 적립식(DCA)** | 매월 일정액 매수, 매도 없음 |
| **C: 2자산 분기 리밸런스** | KODEX 200 + ARIRANG 고배당 50:50 |

룩어헤드 차단은 P9 하니스 불변식을 그대로 적용한다 — t일 판단에 t일 종가를 쓰지 않는다(MA는 t-1까지로 계산, 체결은 t일 시가).

## 사전 등록 성공/실패 판정 기준

**결과를 본 뒤 기준을 바꾸지 않는다.**

- **실패(A/C)**: 워크포워드 OOS 평균이 비용 반영 후 **기준선(일시 매수후보유)보다 낮음** → 해당 규칙 폐기. 결론은 **"타이밍을 시도하지 말고 그냥 사서 보유하라"** 이며, 그것이 이 프로젝트의 최종 답이 된다.
- **조건부 통과(A/C)**: 기준선 초과 + MDD가 기준선 이하 + 슬리피지 20bps에서 우위 유지.
- **B(DCA)는 수익률로 판정하지 않는다.** 자본 투입 시점이 달라 일시 매수와 직접 비교가 성립하지 않는다. MDD와 투입 자본 대비 최종 가치만 참고 지표로 보고한다.

## 예상 (기록용)

**A와 C 모두 실패할 가능성이 높다고 본다.** 추세 필터는 횡보장에서 휩쏘로 비용만 발생시키고, 2자산 리밸런스는 열위 자산(고배당 +165%)을 섞어 기대수익을 낮춘다. 이 예상을 미리 적는 이유는, 예상과 결과가 어긋날 때 사후에 해석을 바꾸지 않기 위해서다.

## 영향받는 파일

- **`backtest.py`**: `run_index_backtest()` 추가. P9 하니스 재사용
- **`tests/test_backtest.py`**: 확장
- **무변경**: `config` 리스크 상수, `SafetyService`, `TradingService`, `order_engine.py`

## 리스크/게이트 파라미터 변경 여부

**없음.**

---

# P13 판정 결과 — ❌ A/C 모두 실패 (2026-08-27)

사전 등록 기준 적용. **결과를 본 뒤 기준을 바꾸지 않았다.** 스펙에 미리 적어둔 예상("A와 C 모두 실패할 가능성이 높다")과 결과가 일치한다.

## 판정

| 규칙 | 워크포워드 OOS 평균 | 기준선 대비 | 승리 폴드 | 판정 |
|---|---|---|---|---|
| **기준선: 매수후보유** | **+26.25%** | — | — | — |
| A: MA200 추세필터 | +23.22% | **-3.03%p** | 2/7 | ❌ 실패 |
| C: 2자산 50:50 리밸런스 | +21.61% | **-4.64%p** | 4/7 | ❌ 실패 |

**결론: 타이밍을 시도하지 말고 그냥 사서 보유하라.**

## 전체구간이 OOS와 어긋난다 — 사전 등록의 존재 이유

| 구성 | 전체구간(5년) | MDD | 거래 | 비용 |
|---|---|---|---|---|
| 기준선 | +187.81% | -40.81% | 1 | 87,958 |
| MA200 | **+206.31%** | -38.40% | 216 | 743,396 |
| 2자산 | +184.75% | **-25.29%** | 17 | 113,578 |

전체구간만 보면 MA200이 기준선을 18%p 이긴다. 그러나 **OOS 평균은 3%p 진다.**

원인은 경로 의존성이다. 전체구간은 2021-08 시작이라 MA 필터가 2022년 하락을 회피한 이득이 통째로 반영되는 반면, OOS는 2022-09부터 여러 시작점에서 검증한다. **시작점 하나에 의존하는 우위는 우위가 아니다.** 전체구간 수치를 근거로 채택했다면 잘못된 결론에 도달했을 것이며, 이것이 사전 등록을 한 이유다.

## 2자산 구성에 대한 정직한 부기

2자산은 **7폴드 중 4폴드를 이겼고 MDD가 -25.29%로 기준선(-40.81%)보다 크게 낫다.** 그럼에도 OOS 평균이 낮은 이유는 상승 폴드에서 크게 뒤처지기 때문이다(폴드6 49.75% vs 67.21%, 폴드7 71.81% vs 105.32%).

사전 등록 기준은 "기준선 초과 **그리고** MDD 이하"였고 첫 조건에서 탈락한다. 다만 **드로우다운을 낮추는 것이 목적이라면 재검토할 가치가 있다** — 이는 별도 목표이므로 별도 사전 등록이 필요하다.

## 표본의 한계 (반드시 함께 읽을 것)

마지막 두 폴드가 6개월 만에 **+67%, +105%** 다. 이 5년 표본은 2025~2026년 한국 시장의 이례적 급등이 지배한다. OOS 평균은 이 두 폴드에 크게 끌려간다. **다른 레짐에서 같은 결론이 나온다는 보장이 없다.**

## 운영상 치명적 발견 — 15% 드로우다운 가드와 인덱스 보유는 양립 불가

기준선(단순 매수후보유)의 MDD가 **-40.81%** 다. 그런데 `config.MAX_DRAWDOWN_PCT`는 **0.15(15%)** 이고, `risk_manager.check_max_drawdown()`이 초과 시 `SLEEP_MODE`를 켜며 `SafetyService.ensure_order_allowed()`가 매수를 차단한다.

즉 **이 시스템으로 인덱스 매수후보유를 운용하면 하락장에서 휴면 모드가 켜져 바닥 근처에서 매수가 막힌다.** 적립식(P13-B)을 자동화할 때 정확히 최악의 시점에 적립이 중단된다.

이는 리스크 상수를 완화해야 한다는 뜻이 **아니다**. 15% 가드는 개별종목 고회전 전략을 전제로 설계된 것이고, 인덱스 장기보유는 다른 리스크 프로파일을 갖는다. **전략과 가드가 서로 맞지 않는 상태**이며, 어느 쪽을 바꿀지는 사람 결정 사항이다 (CLAUDE.md §4.3).

## 참고: 적립식(B)

월 20만원 적립, 총투입 12,400,000원 → +193.32%, MDD -38.51%.
사전 등록대로 **수익률로 판정하지 않았다** (자본 투입 시점이 달라 일시매수와 직접 비교 불가).

---

# P14: 코어-새틀라이트 배분 검증 — 🔲 사람 승인 대기

## 배경

**사람 요구 (2026-08-27)**: "시장분석 매수를 하고 싶다."

P9/P12/P13에서 능동 전략이 세 번 다 인덱스에 졌다. 그러나 이는 "능동 매수를 하지 말라"는 지시가 될 수 없다 — 자본 배분은 사람의 결정이다. 에이전트가 할 일은 **선택지를 없애는 것이 아니라 가격표를 붙이는 것**이다.

따라서 질문을 바꾼다: "능동 매수를 할까 말까"가 아니라 **"새틀라이트 비중 w에서 전체 성과가 어떻게 변하는가"**.

## 구조

```
전체 자본
├── 코어 (1-w): KODEX 200 매수후보유          ← 검증된 부분이 수익 담당
└── 새틀라이트 (w): 능동 전략                  ← 하고 싶은 것, 단 한도 고정
```

두 슬리브는 **현금을 공유하지 않는다** (실제 코어-새틀라이트 운용 방식). 각자 배분받은 자본으로 독립 운용하고 자산곡선을 합산한다. 슬리브 간 리밸런스는 하지 않는다 — 하면 코어에서 새틀라이트로 자금이 흘러 한도가 무너진다.

## 측정 대상

새틀라이트 비중 **w ∈ {0%, 10%, 20%, 30%, 50%}** 에서:

| 새틀라이트 전략 | 근거 |
|---|---|
| P9 모멘텀 (뉴스감성 + 기술적) | 사용자가 원하는 "시장분석 매수"에 가장 가까움. 단독 -82.09% |
| P12 배당 (분기 리밸런스) | 단독 +165.49% |

각 조합에 대해 총수익률·MDD·비용을 보고한다.

## 사전 등록 판정 기준

**이번에는 합격/불합격 판정이 아니라 용량 권고를 산출한다.** 자본 배분은 사람 결정이므로 에이전트가 채택 여부를 판정하지 않는다.

권고 상한 w*를 다음 조건을 모두 만족하는 최대 w로 정의한다:

1. 혼합 포트폴리오 총수익률이 **코어 단독(w=0)의 80% 이상**
2. 혼합 MDD가 **코어 단독 MDD보다 악화되지 않음**

두 조건을 만족하는 w가 없으면 **w\* = 0** 으로 보고하고, 그 사실을 그대로 전달한다.

## 예상 (기록용)

모멘텀 새틀라이트는 w=10%에서도 조건 1을 위협할 것으로 본다(단독 -82%이므로 10% 비중이 전체를 약 -8%p 끌어내림). 배당 새틀라이트는 단독 성과가 코어와 근접(+165% vs +191%)하므로 w=30%까지도 조건을 만족할 가능성이 있다.

## 영향받는 파일

- **`backtest.py`**: `blend_sleeves()` 추가
- **`tests/test_backtest.py`**: 확장
- **무변경**: `config` 리스크 상수, `SafetyService`, `TradingService`, `order_engine.py`

## 리스크/게이트 파라미터 변경 여부

**없음.** `MAX_DRAWDOWN_PCT` 충돌(P13 발견)은 이 스펙에서 건드리지 않는다 — 사람 결정 대기 항목으로 유지한다.

---

# P14 판정 결과 — 용량 권고 산출 (2026-08-27)

사전 등록대로 **합격/불합격 판정이 아니라 용량 권고**를 산출한다. 자본 배분은 사람 결정이다.

## 결과 — 새틀라이트 용량-반응 곡선

코어 단독(w=0): **+188.57%, MDD -40.81%**

### 새틀라이트 = 모멘텀 (뉴스감성 + 기술적)

| w | 총수익 | MDD | 코어 대비 | 조건1(≥80%) | 조건2(MDD) |
|---|---|---|---|---|---|
| 10% | +166.76% | -39.95% | 88.4% | ✅ | ✅ |
| 20% | +140.80% | -39.56% | 74.7% | ❌ | ✅ |
| 30% | +113.68% | -39.09% | 60.3% | ❌ | ✅ |
| 50% | +57.73% | -43.37% | 30.6% | ❌ | ❌ |

**권고 상한 w\* = 10%**

### 새틀라이트 = 배당 (분기 리밸런스)

| w | 총수익 | MDD | 코어 대비 | 조건1 | 조건2 |
|---|---|---|---|---|---|
| 10% | +181.68% | -38.34% | 96.3% | ✅ | ✅ |
| 20% | +178.06% | -35.52% | 94.4% | ✅ | ✅ |
| 30% | +176.95% | -32.18% | 93.8% | ✅ | ✅ |
| 50% | +175.17% | **-25.61%** | 92.9% | ✅ | ✅ |

**권고 상한 w\* = 50%**

## 해석 — 모멘텀의 MDD "개선"은 착시다

모멘텀 새틀라이트에서 w가 커질수록 MDD가 소폭 개선되는 것처럼 보이지만(-39.95% → -39.09%), **이는 분산 효과가 아니라 자본 파괴의 결과다.** 모멘텀 슬리브는 단독 -82.09%로 초반에 대부분 녹아버리므로, 이후 위험에 노출된 자본 자체가 줄어든다. "변동성이 낮아졌다"가 아니라 "잃을 돈이 없어졌다"이다.

조건2를 통과했다고 해서 이를 장점으로 읽으면 안 된다.

## 해석 — 배당 새틀라이트는 실제로 값어치가 있다

w=50%에서 총수익은 **7.1%p 감소**(188.57 → 175.17)하는 데 그치는 반면 **MDD는 15.2%p 개선**(-40.81% → -25.61%)된다. 드로우다운 1%p를 수익 0.47%p로 사는 셈이다.

이는 P12에서 배당 전략을 **단독으로** 평가했을 때(ETF에 패배)와 다른 결론이다. 단독 성과가 열위여도 **상관관계가 낮으면 혼합 시 기여할 수 있다.** P12 판정(단독 채택 불가)과 P14 결과(혼합 시 유용)는 모순이 아니다.

## 사용자 요구와의 정합성

사용자 요구는 "시장분석 매수"였다. **배당 스크린(후행 배당수익률 + 무삭감 연속연수로 종목을 선별하고 분기마다 교체)은 그 자체가 분석 기반 능동 매수다.** 뉴스감성 모멘텀만이 "분석"인 것은 아니다.

따라서 요구를 포기하지 않으면서 비용을 최소화하는 구성이 존재한다.

## 표본 한계 (P13과 동일)

5년 표본이 2025~2026 급등에 지배된다. 특히 w별 MDD 개선폭은 2022년 하락 구간에 크게 의존하므로 다른 레짐에서 재현된다는 보장이 없다.

## 수정한 버그 (판정 전 발견)

**`blend_sleeves` 날짜 정렬 결함.** 슬리브마다 거래일 집합이 달라(코어 1,206일 vs 새틀라이트 1,226일) 단순 날짜별 합산 시 한쪽에만 있는 날짜에서 나머지 자본이 사라진 것처럼 계산됐다. 그 결과 MDD가 **-92.33%** 라는 불가능한 값으로 나왔다(개별 슬리브 최악값은 -40.81%).

**수정**: 전체 날짜 합집합에 대해 각 슬리브를 전진보간한 뒤 합산. 첫 관측 이전은 원금으로 본다.
**회귀 테스트 2개 추가**: 거래일 불일치 시 MDD가 생기지 않을 것, 혼합 MDD가 개별 슬리브 최악값을 넘지 않을 것.

---

# 최종 확정 (2026-08-27)

## 1. 자산 배분 — 확정

**KODEX 200 (069500) 60% / ARIRANG 고배당주 (161510) 25% / 직접선별 15%**

실측 (5년, 실비용): **+173.52%, MDD(고점대비) -29.75%**, 슬리피지 40bps에서도 +169.74%.

워크포워드 OOS 7폴드: 혼합 **+21.93%** vs 코어단독 +26.59%. **MDD는 7/7 폴드에서 혼합이 우세.**
→ "덜 벌고 덜 흔들리는" 구성임을 인지한 상태에서 사람이 선택했다.

## 2. `MAX_DRAWDOWN_PCT` 15% → 30% — 사람 확정

세션 중 사람이 직접 변경했고 확정했다.

근거: 확정 배분의 실측 최저점이 **7,874,009원 (2022-09-30), 기준자본 대비 -21.26%**.
- 30% 설정(발동선 700만원) → **SLEEP_MODE 발동일수 0일 / 1,219일**
- 15% 설정(발동선 850만원) → 2022년 하락 구간에서 발동, 바닥 부근 적립 중단

**정정 기록**: 이 가드는 고점 대비가 아니라 `INITIAL_CAPITAL` 대비로 판정한다(`risk_manager.py:91`).
세션 중 에이전트가 "고점 대비 40% 하락 시 발동"이라고 잘못 설명했다.

**⚠️ 미결 항목**: CLAUDE.md §4.2가 아직 `MAX_DRAWDOWN_PCT 15%`로 기재돼 있어 코드(30%)와 불일치한다.
가드레일 문서 편집은 사람이 직접 수행해야 한다.

## 3. n8n 연동 — 폐기. P6 / P8 취소

**결정: n8n을 도입하지 않는다.**

1. n8n의 원래 목적은 Claude 노드로 종목을 고르는 것이었다. P9/P12/P13/P14에서 **종목 선택이 가치를 더하지 못함**이 확인되어 목적 자체가 사라졌다.
2. 확정 전략은 고정 비율 적립이다. **고정 규칙에는 LLM도 워크플로우 엔진도 필요 없다.**
3. 필요한 부품이 이미 저장소에 있다 — `AgentWorker`(스케줄러), `notifier.py`(텔레그램), `TradingService`(주문), `SafetyService`(게이트), FastAPI, docker-compose.
4. 도입 시 순증가분은 기능이 아니라 **네트워크 노출과 부품 수**뿐이다.

**P6(외부 제안 경로) / P8(n8n 셀프호스팅)을 취소한다.** 두 스펙은 감사 기록으로 남긴다.
**P5(API 인증)는 유지** — n8n과 무관하게 유효한 보안 결함 수정이었고 완료됐다.

---

# P15: 정기 적립 실행 — 🔲 사람 승인 대기

## 배경

확정 배분을 실행할 경로가 없다. 현재 `AgentWorker.start()`는 `agent_service.run_cycle()`을
호출하고, 이는 `auto_buy_from_signals()`로 **P9에서 -82.09%로 입증된 모멘텀 전략**을 실행한다.
**워커를 그대로 켜면 폐기된 전략이 돌아간다.**

## 설계 (구현 전 사람 승인 필요)

- **대상**: `069500`(KODEX 200), `161510`(ARIRANG 고배당주) — 둘 다 `config.KR_STOCKS`에 **없다**.
  커스텀 종목(`store.add_custom_stock`) 등록 필요. ETF는 KRX에서 주식과 동일하게 거래되므로
  `order_engine.kis_buy()` 경로를 쓸 수 있을 것으로 보이나 **검증 필요**.
- **주기**: 월 1회. `AgentWorker` 재사용하되 `run_cycle()`이 아닌 신규 적립 함수 호출.
- **비율**: 매수 가능 금액을 60:25로 배분 (직접선별 15%는 자동화하지 않는다).
- **경로**: 반드시 `TradingService.place_paper_order()` / `place_live_order()` 경유.
  `SafetyService.ensure_order_allowed()`를 우회하는 신규 경로를 만들지 않는다 (CLAUDE.md §4.2).
- **직접선별 15%**: **자동화하지 않는다.** 사람이 `/api/orders/manual`로 직접 실행한다.
  사용자가 원한 "시장분석 매수"가 바로 이 부분이므로 자동화 대상이 아니다.

## 선행 차단 사항

`auto_buy_from_signals()` 경로가 살아있는 한 워커를 `paper` 이상에서 켜면 폐기 전략이 실행된다.
P15 구현 시 **적립 모드와 기존 시그널 모드를 명시적으로 분리**하고 기본값을 적립 모드로 둔다.

## 리스크/게이트 파라미터 변경 여부

**없음.**

---

# P15 완료 — ✅ (2026-08-28)

## 구현

**`AccumulationService`** (services.py). 확정 배분을 **목표 비중**으로 삼아 **부족분만 매수**한다.

- 목표: `total_asset × weight`. 보유 평가액과의 차이가 `ACCUMULATION_MIN_ORDER_KRW`(5만원)
  이상일 때만 매수. **매도하지 않는다** — 청산은 별도 결정이며 이 경로의 책임이 아니다.
- 경로: `execution_mode()`에 따라 기존 `place_paper_order`/`place_shadow_order`/
  `place_live_order`를 호출한다. 따라서 `ensure_order_allowed()`를 반드시 통과한다.
  **신규 우회 경로를 만들지 않았다** (CLAUDE.md §4.2).
- 멱등 키: `accum:{YYYY-MM}:{session}:{code}:buy`. 이중 방어 —
  (1) 목표 비중 달성 시 매수 안 함, (2) `order_events.client_order_id` UNIQUE.

## 폐기 전략 차단 (P15의 핵심 목적)

- `AgentWorker.start(mode=...)` 신설. **기본값 `"accumulation"`**.
- `mode="signal"`은 `ValueError`로 거부하며 메시지에 P9 판정(-82.09%)을 명시한다.
- `WorkerRequest.mode`를 `Literal["accumulation"]`으로 좁혀 **API 스키마 단계에서 차단**(422).
- `resume_if_interrupted()`도 기본값을 쓰므로 자동 재개 시에도 적립 모드로 뜬다.
- `auto_buy_from_signals()` 코드는 **삭제하지 않았다** — 백테스트 하니스와 회귀 테스트가
  참조하며, 재설계 시 비교 기준으로 필요하다. 호출 경로만 끊었다.

## `config.KR_STOCKS`에 ETF를 추가하지 않은 이유

`market_data.get_target_stocks_for_session()`이 `KR_STOCKS`를 그대로 반환하므로, 여기에
`069500`/`161510`을 넣으면 **시그널 생성 유니버스에 편입되어 폐기된 모멘텀 전략이 ETF까지
매매**하게 된다. 별도 상수 `config.ACCUMULATION_PLAN`으로 분리했다.

## 실서버 검증 (mock 모드)

| 항목 | 결과 |
|---|---|
| 목표 산출 | 069500 → 6,000,000원(60%) / 161510 → 2,500,000원(25%) |
| dry_run | 주문 미생성, 계획만 반환 |
| 실행 | 120주 + 50주, 둘 다 `filled` |
| 재실행 | **신규 0건** ("부족분 0원 < 최소주문") |
| `mode="signal"` | **HTTP 422** 차단 |
| 잔여 현금 | **1,500,000원 = 정확히 15%** (직접선별 몫 보존) |

주의: mock 모드의 50,000원은 `MOCK_SEED_PRICES` 미등록 코드의 폴백값이다. paper/live에서는
KIS 실시세를 쓴다. **KIS ETF 주문 가능 여부는 여전히 미검증** — paper 단계에서 확인해야 한다.

## 신규 API

- `POST /api/accumulation/run` — `{period?, dry_run?}`
- `GET /api/accumulation/plan` — 계획·목표금액·실행모드 조회

## 테스트

`tests/test_accumulation.py` 11건. 전체 회귀 `1 failed, 123 passed, 3 skipped`
(기존 실패 1건은 `.env` 미설정).

## 리스크/게이트 파라미터 변경 여부

**없음.**
