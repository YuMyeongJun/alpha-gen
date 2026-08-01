# Plans.md

harness 작업 항목별 섹션 누적.

---

# P0: `place_manual_order()` 안전게이트 우회 수정

`spec.md` 참조. TDD 순서(HARNESS_WORKFLOW.md §2) 고정.

## 진행 상황 (2026-08-01)

- [x] 1단계 실패 테스트 작성 — 4개 신규 케이스 작성, 실행 결과 3개가 "잘못된 이유(RuntimeError)"로 실패함을 발견 → spec.md에 게이트/시세조회 순서 수정 반영
- [x] 2단계 최소 구현 — `ensure_order_allowed()` 호출을 `market_data.get_price()` 이전으로 배치
- [x] 3단계 리팩터 — 불필요, 기존 헬퍼 재사용 범위 내에서 완료
- [x] 4단계 훅/회귀 — `post_edit_check.sh` 통과, `pytest -q` 42 passed / 3 skipped (신규 8개 포함, 회귀 없음)
- [x] 5단계 독립 리뷰 — 1차 REJECT(테스트 커버리지 누락 2건 + 낡은 docstring) → 전부 반영 → 재검토 **APPROVE** (2026-08-01)

## 완료

P0 완료. `place_manual_order()`는 이제 다른 모든 주문 경로와 동일하게 `SafetyService.ensure_order_allowed()`를 통과해야 한다. `git diff`는 `backend/app/services.py`(로직), `backend/app/main.py`(docstring), `tests/test_backend_api.py`(테스트 8개 추가)에 국한되며, `ensure_order_allowed()` 내부/`config/__init__.py`/`risk_manager.py`는 전혀 건드리지 않았다. 커밋은 P0~P4 전체 완료 후 한 번에 하기로 함 (사람 결정).

---

# P1: 대시보드 휴면 상태 표시 DB 소스 수정

`spec.md`의 P1 섹션 참조. **승인 상태: 사람 승인 대기 중** — spec 범위를 원래 승인받은 "sleep_mode 등 공유 개념 전체 제거"에서 "대시보드 휴면 표시만 수정"으로 좁혔으므로, 이 좁혀진 범위에 대해 재확인 필요.

## 단계

### 1단계 — 실패하는 테스트 작성

신규 테스트 파일 또는 기존 파일에 추가(구현 시점에 `tests/` 기존 구조 확인 후 결정) — `market_data.get_live_sleep_state()` 대상:

1. `test_get_live_sleep_state_returns_false_when_not_sleeping` — MOCK_MODE=False, DB sleep_mode=False → `(False, "")`.
2. `test_get_live_sleep_state_returns_true_with_reason` — MOCK_MODE=False, DB sleep_mode=True + reason 설정 → 그대로 반환.
3. `test_get_live_sleep_state_forces_false_in_mock_mode` — MOCK_MODE=True, DB sleep_mode=True(잔재) → `(False, "")` 강제.
4. `test_get_live_sleep_state_handles_empty_db` — 빈 tmp DB → 기본값, 예외 없음.

이 시점에는 함수가 없으므로 전부 `ImportError`/`AttributeError`로 실패해야 정상(1단계 red).

### 2단계 — 최소 구현

1. `market_data.py`에 `get_live_sleep_state(db_path: str | None = None) -> tuple[bool, str]` 추가:
   - `from backend.app.store import SQLiteStore` (함수 내부 import로, 기존 `market_data.py`가 `market_adapters`를 함수 내부에서 임포트하는 패턴과 일관되게)
   - `store = SQLiteStore(db_path or config.DB_PATH, bootstrap_legacy=False)`
   - `if config.MOCK_MODE: return False, ""`
   - `return bool(store.get_state("sleep_mode", False)), str(store.get_state("sleep_reason", ""))`
2. `dashboard.py` L450, L455의 `risk_manager.SLEEP_MODE`/`risk_manager.SLEEP_REASON`을 `is_sleep, sleep_reason = market_data.get_live_sleep_state()` 결과로 교체.

### 3단계 — 리팩터

없음 예상 (함수가 작고 독립적).

### 4단계 — 훅/회귀

- `post_edit_check.sh` 통과 확인 (market_data.py는 risk_manager.py가 아니므로 리스크 상수 감지 규칙에 안 걸림 — 정상).
- `pytest -q` 전체 회귀.

### 5단계 — 독립 리뷰

체크리스트(HARNESS_WORKFLOW.md §3) 그대로 + 특별히: `SQLiteStore`를 읽기 전용으로만 쓰는지(쓰기 메서드 호출 없는지), `agent_state.db`를 전혀 건드리지 않는지 확인.

## 스코프 경계

- `state_store.py`/`agent_state.db`의 `bought_today`/`equity_history`/`sentiments` 필드는 건드리지 않는다.
- `RiskService`/`SafetyService` 내부 로직 무변경.
- `main.py`는 이미 서비스 계층 경유이므로 무변경.

## 진행 상황 (2026-08-01)

- [x] 1단계 실패 테스트 작성 — `tests/test_market_data_state.py` 4개, `AttributeError`로 정상 실패(red) 확인
- [x] 2단계 최소 구현 — `market_data.get_live_sleep_state()` 추가, `dashboard.py` 교체
- [x] 4단계 훅/회귀 — 통과, `pytest -q` 47 passed / 3 skipped
- [x] 5단계 독립 리뷰 — 1차 APPROVE(스코프 자체는 승인) + 비차단 지적(`SQLiteStore(bootstrap_legacy=False)`가 매 호출마다 실제로 쓰기를 한다 — "읽기 전용" 주장과 모순, 대시보드가 재실행될 때마다 운영 DB에 락 경합 위험) → `sqlite3 mode=ro` 직접 연결로 재구현, 부작용 없음을 검증하는 테스트 2개 추가 → 재검토 **APPROVE** (2026-08-01)

## 완료

P1 완료.

---

# P2: `yf_get_price_history` NaN 필터링 추가

`spec.md`의 P2 섹션 참조. 리스크 상수/게이트 무변경, 단일 라인 수정이라 별도 사람 승인 없이 진행 (CLAUDE.md §6 중단조건 어디에도 해당 없음 — 표준 harness 프로세스로 spec→구현→독립리뷰만 거침).

## 단계

1. **실패 테스트**: `yf.Ticker.history()`를 monkeypatch해 NaN 섞인 `Close` 컬럼 DataFrame 반환 → `market_data.yf_get_price_history()` 결과에 NaN이 없는지 검증하는 테스트 작성 (현재 코드로는 실패해야 정상).
2. **최소 구현**: `hist["Close"].tolist()` → `hist["Close"].dropna().tolist()`.
3. **리팩터**: 불필요.
4. **훅/회귀**: `post_edit_check.sh` + `pytest -q`.
5. **독립 리뷰**: 별도 에이전트, diff만 보고 체크리스트 검토.

## 진행 상황 (2026-08-01)

- [x] 1단계 실패 테스트 — `tests/test_yf_price_history.py` 4개, NaN 관련 2개 정상 실패(red) 확인
- [x] 2단계 최소 구현 — `hist["Close"].tolist()` → `hist["Close"].dropna().tolist()`
- [x] 4단계 훅/회귀 — 통과, `pytest -q` 51 passed / 3 skipped
- [x] 5단계 독립 리뷰 — **APPROVE** (비차단 나이트픽 1건: 4번째 테스트가 old/new를 실제로 구분 못 하는 케이스라는 지적, docstring에 이미 명시돼 있어 문제 아님)

## 완료

P2 완료.

---

# P3: 세이프티 크리티컬 함수 테스트 커버리지 추가

`spec.md`의 P3 섹션 참조. 프로덕션 코드 변경 없음(테스트만 추가) — 사람 승인 불필요 (CLAUDE.md §6 어디에도 해당 없음).

## 진행 상황 (2026-08-01)

- [x] `tests/test_order_registry.py` 신규 — 6개 (make_order_key 포맷 2개, idempotent_buy/sell 중복차단 3개, FAILED 후 재시도 허용 1개) — 전부 최초 실행에 통과 (order_registry.py 자체는 무결함 확인됨, 테스트만 누락돼 있었음)
- [x] `tests/test_backend_api.py`에 8개 추가 — `_ensure_idempotent`/`_create_intent` 멱등성 2개, `ensure_signal_freshness` 4개(누락/analyzed_at stale/quote stale/정상), `can_trade` 1개, `set_emergency_stop(disable)` 1개
- [x] 훅/회귀 — `pytest -q` 65 passed / 3 skipped (기존 51 + 신규 14, 회귀 없음)
- [x] 독립 리뷰 — **APPROVE** (실제 data/ 파일 mtime 불변 확인 포함, 이슈 없음)

## 완료

P3 완료.

---

# P4: 경미한 정리 항목

`spec.md`의 P4 섹션 참조. 인프라 설정 + 고아 파일 이동, 프로덕션 코드/리스크 상수 무변경 — 사람 승인 불필요.

## 진행 상황 (2026-08-01)

- [x] `docker-compose.yml` — `config.py`/`mock_state.json` 마운트를 `env_file: .env` + `./data:/app/data`로 교체 (agent/dashboard 서비스 둘 다)
- [x] `migrate_to_sqlite.py` → `archive/migrate_to_sqlite.py` (`git mv`, 코드 참조 없음 재확인)
- [x] `pytest -q` 65 passed / 3 skipped (무관한 변경이므로 회귀 없음 확인)
- [x] 훅 통과
- [x] 독립 리뷰 — **APPROVE** (비차단 나이트픽: Dockerfile의 낡은 주석 → 반영 완료)

## 완료

P4 완료. **P0~P4 전체 완료.**

## 승인 상태

- 리스크/게이트 상수 변경: **없음** → `RISK LIMIT CHANGE APPROVED` 서명 불필요.
- `SafetyService`/`TradingService` 관련 변경 → 사람 승인 필요 (CLAUDE.md §4.3). **사용자 승인 대기 중.**

## 단계

### 1단계 — 실패하는 테스트 작성 (`tests/test_backend_api.py`)

기존 파일의 emergency-stop 차단 테스트 패턴(`/api/safety/emergency-stop` → paper order 차단 확인)을 참고해, `/api/orders/manual`(또는 해당 서비스 메서드를 직접 호출하는 방식, 기존 파일 컨벤션에 맞춤)에 대해 아래 케이스를 추가한다. 이 시점에는 아직 구현이 안 되어 있으므로 3~7번은 실패해야 정상.

1. `test_manual_order_still_succeeds_when_all_gates_pass` — 정상 케이스 회귀 (현재도 통과해야 함, before/after 동일 동작 확인용 베이스라인).
2. `test_manual_order_blocked_by_emergency_stop` — 기존 동작 유지 확인.
3. `test_manual_order_buy_blocked_when_sleep_mode` — `risk_manager.SLEEP_MODE=True`(또는 서비스 경유 설정) 상태에서 매수 시도 시 거부되는지.
4. `test_manual_order_blocked_when_stage_not_live` — `config.MOCK_MODE=False` + `KIS_CREDENTIALS_CONFIGURED=True`로 패치해 `mode="live"` 판정을 유도하고, `promotion_stage`가 `mock`/`paper`/`shadow`인 상태에서 차단되는지. `order_engine.kis_buy`를 mock/patch해서 **호출되지 않았음**을 assert.
5. `test_manual_order_blocked_when_allow_live_trading_false` — 4번과 동일하게 live 모드 유도 + `config.ALLOW_LIVE_TRADING=False` → 차단.
6. `test_manual_order_blocked_when_order_limit_exceeded` — 사이클/일일 한도 초과 상태를 미리 만들어두고 차단 확인.
7. `test_manual_order_blocked_when_daily_loss_or_consecutive_loss_exceeded` — 일일 손실/연속 손실 한도 초과 시 차단.
8. 각 차단 케이스에서 응답이 거부(reject) 형태이고, 페이퍼 포지션/잔고가 변경되지 않았는지(폴백 전환 안 됨) 확인.

`pytest tests/test_backend_api.py -k manual_order -v` 실행해 3~7번이 실패(구현 전이므로)하고 1~2번은 통과하는 것을 확인한다.

### 2단계 — 최소 구현

`backend/app/services.py`의 `TradingService.place_manual_order()`만 수정:

1. 기존 `emergency_stop` 단독 체크 블록을 제거.
2. `mode = "live" if (not config.MOCK_MODE and config.KIS_CREDENTIALS_CONFIGURED) else "paper"` 계산.
3. `self.safety_service.ensure_order_allowed(mode=mode, session=session, side=side, signal=None)` 호출을 **`market_data.get_price()` 호출보다 먼저**, qty/session 유효성 검사 직후에 배치 (1단계 테스트에서 발견 — spec.md 참고. 게이트가 막을 주문인데 먼저 실계좌 KIS 시세 조회를 하는 낭비/부작용을 방지).
4. `TradingSafetyError`는 catch하지 않고 그대로 전파 — 기존 emergency_stop 체크와 동일한 `raise` 패턴 유지. API 레이어(`main.py`)가 이미 `except (ValueError, TradingSafetyError)`로 400 변환하므로 추가 처리 불필요.
5. 게이트 통과 시에는 기존 브로커 실행/페이퍼 폴백 로직을 그대로 유지 (로직 자체는 변경하지 않음).
6. docstring 갱신 — "긴급정지만 체크" 문구를 실제 동작(전체 게이트 적용)에 맞게 수정.

### 3단계 — 리팩터

- 중복되는 거부-응답 생성 코드가 `place_live_order`/`place_manual_order` 사이에 생기면, 기존에 이미 있는 헬�퍼(`_reject_order` 등)를 재사용할 수 있는지 확인 — 단, 이 리팩터는 `place_manual_order` 내부로 스코프를 제한하고 `place_live_order`/`place_paper_order`는 건드리지 않는다.

### 4단계 — 훅 통과 확인

- `.claude/hooks/post_edit_check.sh` 통과 확인 (린트 + 회귀 테스트 자동 실행, 리스크 완화 시도 감지 시 차단).
- `pytest -q` 전체 실행 — 기존 8개 파일 전부 통과 + 신규 케이스 통과.

### 5단계 — 독립 리뷰 (`/harness-review`, HARNESS_WORKFLOW.md §3)

구현 세션과 분리된 리뷰 관점(별도 서브에이전트, diff만 보고 컨텍스트 없이 체크리스트 수행):
- `ensure_order_allowed()` 우회 경로가 새로 생기지 않았는지
- mock/paper 두 경로 응답 스키마 동일성
- `.env`/시크릿 노출 없음
- 리스크 상수 변경 없음 재확인
- 테스트가 실제 실패→통과 이력을 가지는지

## 스코프 경계

- `SafetyService.ensure_order_allowed()` 내부는 건드리지 않는다.
- `order_engine.py`/`market_adapters.py`는 건드리지 않는다.
- `POST /api/orders/manual`의 인증 추가는 이번 스코프 밖 (별도 spec).
- `place_paper_order`/`place_live_order`/`place_shadow_order`는 건드리지 않는다.
