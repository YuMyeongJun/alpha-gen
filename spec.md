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
