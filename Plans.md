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

---

# P5: 백엔드 API 인증 게이트 추가

`spec.md`의 P5 섹션 참조. **승인 상태: 사람 승인 대기 중.**

P6(n8n 연동)의 **차단 조건**이다. P5 없이 P6를 구현하지 않는다.

## 단계 (TDD, HARNESS_WORKFLOW.md §2)

1. **실패 테스트 작성** (`tests/test_backend_api.py`)
   - 토큰 없이 `POST /api/orders/manual` → 401
   - 잘못된 토큰 → 401
   - 올바른 토큰 → 기존 동작 유지
   - `GET /api/health` → 토큰 없이도 200 (면제 확인)
   - `API_AUTH_REQUIRED=True` + `API_AUTH_TOKEN=""` → 기동 실패 (조용히 인증 꺼지지 않음)
2. **최소 구현**: `config/__init__.py`에 상수 3개 → `main.py`에 인증 의존성 + CORS origin 제한
3. **리팩터**: 인증 의존성을 라우터 레벨로 정리 (읽기 면제 라우트만 예외)
4. **훅/회귀**: `post_edit_check.sh`, `pytest -q` 전체
5. **독립 리뷰**: 별도 서브에이전트, diff만 보고 체크리스트

## 스코프 경계

- `backend/app/services.py`는 건드리지 않는다 (인증은 라우트 계층 관심사).
- 기존 라우트의 요청/응답 스키마를 바꾸지 않는다.
- 리스크/게이트 상수 변경 없음.

---

# P6: n8n → TradingService 연동 (외부 제안 경로)

`spec.md`의 P6 섹션 참조. **승인 상태: 사람 승인 대기 중.**

CLAUDE.md §4.3 "신규 주문 경로 추가 — 반드시 `TradingService`를 경유하도록 설계해야 하며, 설계 자체를 스펙에 명시" 해당 항목. **P5 완료 후에만 착수.**

## 사람이 결정해야 하는 항목 (구현 전 답이 필요)

1. 배당 데이터 소스를 alpha-gen에 들일 것인가, n8n 쪽에 둘 것인가? (spec P6 "구현 불가" 표 참조)
2. 교집합 규칙(`buy_signal=true`인 종목만 실행)을 수용하는가? 수용 시 "배당은 좋으나 감성 점수 낮은 종목"은 영구 미주문이 된다.
3. `EXTERNAL_PROPOSAL_ALLOWED_SESSIONS` 초기값을 `"KR"`로 둘 것인가? (US는 `ENABLE_KIS_US_ORDERS`도 별도로 필요)
4. n8n이 같은 호스트에서 도는가, 별도 호스트인가? (`ALPHA_GEN_HOST` 노출 범위 결정)

## 단계 (TDD)

1. **실패 테스트 작성** (`tests/test_external_proposals.py` 신규)
   - spec P6 "검증 시나리오" 10개를 그대로 테스트로 옮긴다
   - 추가: `analyzed_at`/`quote_collected_at`/`sentiment_score` 주입 시도 → 422
   - 추가: `side="sell"` 주입 시도 → 422
2. **최소 구현**
   - `config/__init__.py`: 신규 상수 5개
   - `backend/app/models.py`: `ExternalProposalRequest`
   - `backend/app/services.py`: `ExternalProposalService` 신규 클래스 + `build_service_bundle()` 등록
   - `backend/app/main.py`: 라우트 1개
3. **리팩터**: `auto_buy_from_signals()`와 중복되는 사이징/디스패치 로직을 공통 헬퍼로 추출 검토 (단, `auto_buy_from_signals()` 동작은 무변경 유지)
4. **훅/회귀**: `pytest -q` 전체 + `python scripts/live_mode_checklist.py`
5. **승격 검증** (HARNESS_WORKFLOW.md §4): `mock` → `paper`에서만 관찰. `shadow`/`live_*` 승격은 사람이 별도 판단.
6. **독립 리뷰**: 체크리스트 중 특히 "**`ensure_order_allowed()`를 우회하는 새 주문 경로가 생기지 않았는가**" 항목을 집중 검토

## 스코프 경계

- `SafetyService.ensure_order_allowed()` 내부 무변경.
- `order_engine.py` / `market_adapters.py` / `order_registry.py` / `risk_manager.py` / `market_data.py` 무변경.
- `place_paper_order` / `place_shadow_order` / `place_live_order` / `place_manual_order` / `auto_buy_from_signals` 무변경 (호출만).
- 기존 리스크/게이트 상수 무변경.
- 섹터 집중 제한, 현금 2% 보존, 배당 데이터 레이어는 **이번 스코프 밖** (별도 spec).

---

# P7: 배당 데이터 레이어 (`dividends.py`)

`spec.md`의 P7 섹션 참조. **승인 상태: 사람 승인 대기 중.**

## 구현 순서 (P5 → P7 → P6)

P7이 P6보다 먼저다. 배당 데이터가 서버에 있어야 P6의 배당 필터를 "권고"가 아닌 "게이트"로 만들 수 있다.

## 단계 (TDD)

1. **실패 테스트 작성** (`tests/test_dividends.py` 신규) — spec P7 검증 시나리오 7개
2. **최소 구현**: `dividends.py` (`ohlcv.py` 컨벤션 복제) + `config/__init__.py` 상수 5개
3. **리팩터**: `ohlcv.py`와 중복되는 SQLite 연결/upsert 패턴 검토 (단 `ohlcv.py` 무변경)
4. **훅/회귀**: `pytest -q` 전체
5. **독립 리뷰**: NaN/None 가드, fail-closed 동작, KOSDAQ 폴백 집중 검토

## 스코프 경계

- `ohlcv.py` 무변경 (`_to_yf_ticker()` `.KS` 하드코딩 버그는 별도 항목으로 남김).
- `market_data.py` / `risk_manager.py` / `order_engine.py` 무변경.
- 배당 데이터는 **수집·조회만** 한다. 이 단계에서 주문 경로에 연결하지 않는다 (연결은 P6).

---

# P8: n8n 셀프호스팅 + 백엔드 서비스 컨테이너화

**승인 상태: 사람 승인 대기 중.** P5/P6/P7 완료 후 착수.

## 배경

**사람 결정 (2026-08-27 대화)**: 집 컴퓨터를 상시 가동 서버로 운영한다.

현재 `docker-compose.yml`에는 `agent`(main.py)와 `dashboard`(streamlit) 두 서비스만 있고 **FastAPI 백엔드(`python -m backend.app`) 서비스가 없다.** n8n이 호출할 대상이 컨테이너로 안 떠 있으므로 먼저 추가해야 한다.

## 구성 원칙 — 인바운드 포트를 인터넷에 열지 않는다

n8n을 같은 호스트에 셀프호스팅하고 docker 내부 네트워크로만 통신시킨다. 백엔드 포트를 `127.0.0.1`에만 바인딩해 외부 노출을 0으로 유지한다.

```yaml
  backend:
    build: .
    command: python -m backend.app
    ports:
      - "127.0.0.1:8000:8000"   # 루프백 전용 — 인터넷 노출 없음
    environment:
      - ALPHA_GEN_HOST=0.0.0.0  # 컨테이너 내부 바인딩. 외부 노출은 위 ports가 통제

  n8n:
    image: n8nio/n8n
    ports:
      - "127.0.0.1:5678:5678"
    volumes:
      - ./data/n8n:/home/node/.n8n
```

n8n 워크플로우에서 백엔드 주소는 `http://backend:8000` (docker 내부 DNS).

## 단계

1. `docker-compose.yml`에 `backend` 서비스 추가 → `curl -H "Authorization: Bearer $TOKEN" localhost:8000/api/health` 확인
2. `n8n` 서비스 추가 → `localhost:5678` 접속 확인
3. n8n에서 `http://backend:8000/api/health` 호출 성공 확인 (인증 헤더 포함)
4. Cron → GET 컨텍스트 → Claude 노드 → `POST /api/external/proposals` 워크플로우 구성
5. `EXTERNAL_PROPOSAL_ENABLED=true` + `OPERATING_STAGE=paper`로 관찰 운영

## 스코프 경계

- Python 코드 무변경. 인프라 설정만.
- 포트를 `0.0.0.0`으로 열거나 포트포워딩/터널을 설정하지 않는다 (사람이 별도 판단할 사항).

---

# P9: 실데이터 백테스트 재작성

`spec.md`의 P9 섹션 참조. **승인 상태: 사람 승인 대기 중.**

## 우선순위 재조정 제안

**P9를 P6/P8보다 먼저 한다.** 검증되지 않은 전략을 무인 자동화하면 손실이 무인으로 발생한다. `ensure_order_allowed()`는 손실 속도를 늦출 뿐 방향을 바꾸지 못한다.

권장 순서: **P5(인증) → P9(백테스트) → [판정] → P7(배당) → P6(외부 제안) → P8(n8n)**

P9 판정이 "실패"로 나오면 P6/P8은 착수하지 않는다 (spec P9 "사전 등록 판정 기준").

## 0단계 — 선행 작업 (구현 전)

- [ ] `ohlcv.refresh_all()` 실행해 실데이터 확보. 현재 `data/` 디렉터리 자체가 없음
- [ ] `fetch_and_store(days=...)`를 200 → 최소 3~5년치로 늘려 워크포워드 구간 확보
- [ ] 사용자가 **실제 KIS 수수료율·현행 증권거래세율**을 확인해 `BACKTEST_*_BPS` 기본값 교체
- [ ] KOSDAQ 종목은 `_to_yf_ticker()` `.KS` 하드코딩으로 데이터 확보 실패 예상 → 제외 목록 확정

## 단계 (TDD, HARNESS_WORKFLOW.md §2)

1. **실패 테스트 작성** (`tests/test_backtest.py` 신규) — spec P9 검증 시나리오 10개.
   특히 **3번(룩어헤드 회귀)** 을 먼저 작성한다. 이게 가장 틀리기 쉽고 가장 치명적이다.
2. **최소 구현**
   - `config/__init__.py`: 비용 상수 4개
   - `backtest.py` 전면 재작성 — `ohlcv.load_ohlcv()` 기반 바-바이-바 재생
   - `evaluate_buy_technicals(..., prev_day=<실제 전일 고저>)` 로 라이브 경로와 일치시킴
3. **리팩터**: 시나리오(`tech_only`/`sentiment_random`/`sentiment_oracle`) 축을 전략 로직과 분리
4. **훅/회귀**: `pytest -q` 전체. `BacktestService.run()` 하위 호환 확인 (`test_backend_api.py` 회귀 없어야 함)
5. **독립 리뷰**: 별도 서브에이전트. 집중 검토 항목:
   - 룩어헤드가 정말 없는가 (t일 종가가 t일 판단에 새어들지 않는가)
   - 비용이 매수·매도 양쪽에 모두 적용됐는가
   - 워크포워드 검증 구간이 학습 구간과 겹치지 않는가
   - 리포트에 학습 구간 성과가 섞여 들어가지 않았는가
6. **결과 판정**: spec P9 "사전 등록 성공/실패 판정 기준"에 따라 사람이 판정. **결과를 본 뒤 기준을 바꾸지 않는다.**

## 스코프 경계

- `technical.py` / `risk_manager.py` / `market_data.py` / `ohlcv.py` **무변경** (호출·읽기만).
- `order_engine.py` / `market_adapters.py` / `SafetyService` / `TradingService` **무변경**. 백테스트는 주문 경로를 건드리지 않는다.
- 워크포워드로 찾은 파라미터를 `config` 기본값에 반영하지 않는다 — 별도 사람 승인 사항.
- 생존 편향(유니버스 고정) 해결은 이번 스코프 밖. 한계로 리포트에 명시만 한다.

---

# P9 완료 — 판정: ❌ 실패 (2026-08-27)

`spec.md`의 "P9 판정 결과" 섹션 참조.

## 수행 내역

- [x] 0단계 선행작업 — uv로 Python 3.11.16 환경 구축(시스템 3.9 무영향), 83종목×5년 실봉 102,484행 확보, KOSPI/S&P500 벤치마크 확보
- [x] KOSDAQ 4종목 오염 데이터 수리(`.KS` → `.KQ` 폴백, 기존 행 DELETE 후 재삽입)
- [x] 1단계 실패 테스트 10개 작성 (`tests/test_backtest.py`) — 룩어헤드 회귀 테스트 우선 작성
- [x] 2단계 구현 — `config/__init__.py` `[G-2]` 비용 상수 4개, `backtest.py` 전면 재작성
- [x] 4단계 회귀 — 베이스라인 `1 failed, 64 passed, 3 skipped` → `1 failed, 74 passed, 3 skipped`. 기존 실패 1건은 `.env` 미설정에 의한 것으로 변동 없음. **회귀 없음**
- [x] 6단계 판정 — 사전 등록 기준 적용, 결과 확인 후 기준 변경 없음

## 미수행 (판정이 실패로 나와 불필요)

- 3단계 리팩터 및 5단계 독립 리뷰 — 전략이 폐기 대상이므로 코드 품질 개선의 실익이 없다. 재설계 후 재실행 시 수행한다.
- 워크포워드 **파라미터 탐색** — 고정 파라미터 7폴드 전부 음수(OOS 평균 -21.89%, 양의 폴드 0/7)이고 벤치마크와 약 200%p 격차라, 합리적 그리드 내 어떤 파라미터도 부호를 뒤집지 못한다. 고정 파라미터 폴드별 OOS만 수행했음을 명시한다.

## 차단된 항목

- **P6 (n8n 외부 제안 경로)**: 교집합 규칙이 입증된 음의 엣지에 의존하므로 재설계 필요. 사람 결정 대기.
- **P8 (n8n 셀프호스팅)**: P6에 종속.
- **P5 (API 인증)**: P9 결과와 **무관하게 여전히 유효**하다. 인증 부재는 전략과 별개의 보안 결함이므로 단독 진행 가능.

## 신규 항목 후보

- **P10**: `calc_volatility_target()` 정수 절단 결함 — US 종목에서 전일 레인지가 뭉개진다. `ENABLE_KIS_US_ORDERS` 활성화 전 필수.
- **P11**: `ohlcv.py:_to_yf_ticker()` `.KQ` 폴백 (P7에 포함 예정이었으나 라이브 시그널 생성에도 영향).

---

# 전략 방향 결정 (b) 채택 — 후속 계획 재편 (2026-08-27)

`spec.md` "전략 방향 결정" 및 "P12" 섹션 참조.

## 재편된 우선순위

| 순서 | 항목 | 상태 |
|---|---|---|
| 1 | **P7** 배당 데이터 레이어 (`dividends.py`) | 착수 — P12의 선행 조건 |
| 2 | **P12** 배당 전략 백테스트 + 판정 | P7 종속 |
| 3 | **P5** API 인증 | P12와 **무관하게 유효**, 병행 가능 |
| 4 | P6 재설계 → P8 | **P12 통과 시에만** |
| — | P10/P11 (정수절단, `.KQ` 폴백) | P7에 흡수 또는 별도 |

## 운영 안전 조치 (즉시)

검증된 전략이 없으므로 `OPERATING_STAGE`를 `mock`/`shadow`에서 올리지 않는다.
`auto_buy_from_signals()`가 살아있어 `paper` 이상에서 워커를 돌리면 **P9에서 -82%로 입증된 전략이 실제로 실행된다.**
현재 `.env`가 없어 `MOCK_MODE=True`(기본값)이므로 즉각적 위험은 없으나, `.env` 작성 시 `ALPHA_GEN_STAGE`를 올리지 않도록 주의.

## P7 단계 (TDD)

1. 실패 테스트 작성 (`tests/test_dividends.py`) — spec P7 시나리오 + 아래 실측 제약 반영
   - `trailingEps`가 None인 KR 종목에서 크래시 없이 처리
   - `payoutRatio`가 None/음수/2.0 초과(REIT)일 때 각각의 처리
   - `.KQ` 폴백 (P9에서 실증된 `.KS` 오염 데이터 케이스)
   - 배당 이력 0건 종목 → 후보 제외 (fail-closed)
   - 후행 12개월 배당수익률 계산의 0-분모/NaN 가드
2. 구현 — `dividends.py`, `ohlcv.py` 컨벤션 복제. `data/dividends.db`
3. 회귀 — `pytest -q` (베이스라인 `1 failed, 74 passed, 3 skipped` 악화 없을 것)

## P7 스코프 정정 (실측 반영)

`spec.md` P7 초안 대비 다음을 정정한다:

- `DIVIDEND_MIN_YIELD` 단위: yfinance `dividendYield`가 **퍼센트**로 반환된다(KT 4.5 = 4.5%). 초안의 `0.03`(소수) 가정은 틀렸다 — 정규화 후 사용하고 단위 테스트로 고정한다.
- `trailingEps` 기반 적자 필터: **KR 전 종목 None이라 구현 불가.** 삭제한다.
- `payoutRatio` 기반 배당함정 필터: **라이브 전용**으로 격하. 백테스트 검증 불가(point-in-time 불가)이므로 P12 판정 근거에 넣지 않는다.
- REIT 예외: `payoutRatio > 1.0`인 종목은 REIT일 수 있으므로 일괄 배제하지 않고 별도 임계값을 둔다.

---

# P12 완료 — 판정: ❌ 실패 (2026-08-27)

`spec.md`의 "P12 판정 결과" 섹션 참조.

## 수행 내역

- [x] P7 `dividends.py` 구현 + 테스트 14개 (회귀 3개 포함)
- [x] 고배당 유니버스 18종목 OHLCV·배당 이력 확보 (`config.KR_STOCKS` **무변경**)
- [x] 배당 ETF 벤치마크 4종 확보
- [x] `backtest.run_dividend_backtest()` 구현 + 테스트 5개
- [x] 실데이터 판정 — 사전 등록 기준 적용, 결과 확인 후 기준 변경 없음
- [x] 회귀 — `1 failed, 93 passed, 3 skipped` (기존 실패 1건은 `.env` 미설정, 변동 없음)

## 판정 요약

워크포워드 OOS 전략 +16.26% < 고배당 ETF +17.28% → 실패.
전체구간 +165.49% < KODEX 200 +191.08% → 실패.
MDD -15.50% > 15% → 초과.

**종목 선택이 ETF에 아무것도 더하지 않으며, 시장지수가 둘 다 이겼다.**

## 차단 유지

- P6 / P8 (n8n 자동화): 검증 통과 전략 부재로 계속 차단.
- `OPERATING_STAGE`는 `mock`/`shadow` 유지.

## 다음 후보 (사람 결정 필요)

- **P13**: 지수/ETF 매수 후 보유 + 정기 적립의 자동화. 이 기간 KODEX 200이 모든 능동 전략을 이겼으므로, "무엇을 살까"가 아니라 "규칙대로 계속 사기"를 자동화하는 방향. 종목 선택 알파를 요구하지 않으므로 검증 부담이 낮고 회전율·비용이 최소다.
- **P5**: API 인증 — 전략과 무관하게 여전히 유효. 즉시 착수 가능.

---

# P5 완료 ✅ / P13 완료 — 판정 ❌ (2026-08-27)

## P5 (API 인증) — 완료

`spec.md` "P5 완료" 참조. 게이트를 `MOCK_MODE`가 아닌 **`WEB_HOST` 바인딩**에 걸었다.
`tests/test_backend_auth.py` 10개. 회귀 `1 failed, 103 passed, 3 skipped`.

## P13 — A/C 모두 실패

OOS 평균: 기준선 +26.25% / MA200 +23.22% / 2자산 +21.61%.
**타이밍·자산배분 규칙이 단순 매수후보유를 이기지 못했다.**

## 세 번의 검증 요약

| 항목 | 결과 | 벤치마크(KODEX200 +191%) 대비 |
|---|---|---|
| P9 모멘텀 (뉴스감성+기술적) | -82.09% | 완패 |
| P12 배당 (분기 리밸런스) | +165.49% | 패 |
| P13 인덱스 타이밍/배분 | OOS에서 매수후보유에 패 | — |

**능동적 개입이 세 번 다 졌다.**

## 사람 결정이 필요한 항목

1. **15% 드로우다운 가드 vs 인덱스 보유 충돌** — 인덱스 매수후보유 MDD는 -40.81%인데
   `MAX_DRAWDOWN_PCT=0.15`가 하락장에서 `SLEEP_MODE`를 켜 바닥에서 매수를 막는다.
   상수 완화는 **에이전트가 임의로 하지 않는다** (CLAUDE.md §4.2). 전략을 바꿀지 가드를 바꿀지 사람이 결정.
2. **2자산 구성 재검토 여부** — OOS 평균은 졌으나 MDD가 -25.29%로 크게 낫다.
   드로우다운 축소가 목표라면 별도 사전 등록 후 재검증.
3. **표본 한계** — 5년 표본이 2025~2026 급등에 지배된다. 다른 레짐 검증 불가.

## 차단 유지

P6 / P8 (n8n 자동화): 여전히 차단. 다만 검증 결과가 가리키는 자동화 대상이 바뀌었다 —
"무엇을 살까"(종목 선택)가 아니라 **"규칙대로 계속 사기"(적립 실행)** 이며, 이는 P6의
외부 제안 경로가 아니라 훨씬 단순한 스케줄 실행이면 충분하다.

---

# P14 완료 — 용량 권고 산출 (2026-08-27)

`spec.md` "P14 판정 결과" 참조.

## 권고

| 새틀라이트 | 권고 상한 w* | 비고 |
|---|---|---|
| 배당 (분기 리밸런스) | **50%** | 수익 -7.1%p, MDD -15.2%p 개선. 실질적 값어치 있음 |
| 모멘텀 (뉴스감성+기술적) | **10%** | 10%에서 수익 22%p 손실. MDD 개선은 자본 파괴 착시 |

## 다음 단계 (사람 승인 필요)

1. 배분 확정 — 코어 KODEX 200 : 배당 새틀라이트 비중
2. `MAX_DRAWDOWN_PCT` 충돌 해소 (P13 발견, 여전히 미해결)
3. 확정 후 P6 재설계 → P8 (n8n 자동화)

## 버그 수정

`blend_sleeves` 날짜 정렬 결함 → 전진보간으로 수정, 회귀 테스트 2개 추가.

---

# 최종 확정 (2026-08-27) — n8n 폐기, P15 신설

`spec.md` "최종 확정" / "P15" 참조.

## 확정

1. 배분: KODEX200 60% / ARIRANG 고배당 25% / 직접선별 15%
2. `MAX_DRAWDOWN_PCT` 30% — 사람 확정
3. **n8n 도입하지 않음. P6 / P8 취소** (스펙은 감사 기록으로 보존)

## 사람이 직접 해야 할 것

- [ ] CLAUDE.md §4.2의 `MAX_DRAWDOWN_PCT 15%` → `30%` 갱신 (가드레일 문서라 에이전트 편집 차단됨)

## 다음 (P15)

- [ ] `069500` / `161510` 종목 등록 + KIS ETF 주문 가능 여부 확인
- [ ] 적립 실행 함수 (TradingService 경유, ensure_order_allowed 준수)
- [ ] `AgentWorker`에 적립 모드 추가, **기본값을 적립 모드로**
- [ ] 폐기된 `auto_buy_from_signals()` 경로와 명시적 분리
- [ ] 직접선별 15%는 자동화하지 않음 — 사람이 `/api/orders/manual`로 수행

---

# P15 완료 ✅ (2026-08-28)

`spec.md` "P15 완료" 참조.

- [x] `AccumulationService` — 목표 비중 부족분만 매수, 매도 없음
- [x] `AgentWorker.start(mode=)` 기본값 `accumulation`, `signal`은 ValueError + API 422 차단
- [x] `config.ACCUMULATION_PLAN` 분리 (KR_STOCKS 오염 방지)
- [x] `POST /api/accumulation/run`, `GET /api/accumulation/plan`
- [x] 테스트 11건, 실서버 검증 완료

## 남은 것

1. **CLAUDE.md §4.2 `MAX_DRAWDOWN_PCT` 15% → 30%** (사람이 직접 — 에이전트 편집 차단됨)
2. **KIS ETF 주문 가능 여부 검증** — paper 단계에서 확인 필요. mock으로는 알 수 없다
3. `.env` 작성 → `scripts/live_mode_checklist.py` → paper 관찰
