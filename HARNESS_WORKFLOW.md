# HARNESS_WORKFLOW.md — 계획 → 구현 → 백테스팅 검증 프로세스 (v2, 실제 서비스 계층 기준)

이 문서는 alpha-gen 저장소에서 AI 에이전트와 사람이 협업하는 3단계 워크플로우와, `technical.py`(진입 신호) ↔ `risk_manager.py`(리스크 통제) ↔ `SafetyService`(실거래 게이트)를 상호 교차검증하는 파이프라인을 정의한다. `CLAUDE.md`의 가드레일을 위반하는 어떤 단계도 승인 없이 진행하지 않는다.

> v1은 4개 저수준 파일만 보고 작성되어 `backend/app/services.py`의 서비스 계층(`SafetyService`/`RiskService`/`BacktestService` 등)과 `docs/operating_stages.md`에 이미 정의된 5단계 승격 프로세스(mock→paper→shadow→live_limited→live_full)를 놓치고 있었다. v2는 이를 반영한다.

---

## 0. 왜 이 프로젝트에 특히 엄격한 워크플로우가 필요한가

이 저장소는 실제 자금(KIS 실전 계좌)을 매매하는 코드다. 버그의 대가가 "테스트 실패"가 아니라 "손실"이다. 따라서 일반적인 "계획 없이 바로 구현"이 아니라, **명세 승인 → 스코프 제한 TDD 구현 → 독립 리뷰 → 백테스트/승격 검증**의 4중 게이트를 강제한다.

---

## 1. `/harness-plan` — 명세 작성 및 승인

트리거: 새 기능/버그 수정/리스크 파라미터 조정 등 어떤 작업이든 구현 전 필수.

절차:
1. 요구사항을 분석해 저장소 루트에 `spec.md`(무엇을/왜) 와 `Plans.md`(어떻게, 단계별)를 작성한다.
2. `spec.md`에 반드시 아래 항목을 명시한다:
   - 영향받는 파일 목록 — 저수준(`market_data.py`/`risk_manager.py`/`technical.py`/`order_engine.py`/`market_adapters.py`) vs 서비스 계층(`backend/app/services.py`의 어느 `*Service`) 구분해서 명시
   - **리스크/게이트 파라미터 변경 여부** — `config/__init__.py`의 `MAX_POSITION_PCT`, `STOP_LOSS_PCT`, `MAX_DRAWDOWN_PCT`, `ALLOW_LIVE_TRADING`, `EMERGENCY_STOP`, `LIVE_MAX_ORDERS_PER_CYCLE`, `LIVE_MAX_ORDERS_PER_DAY`, `MAX_CONSECUTIVE_LOSSES`, `MAX_DAILY_LOSS_PCT`, `QUOTE_STALENESS_SEC`, `SIGNAL_STALENESS_SEC` 중 변경 있으면 완화/강화 방향 명시 (**루트 `config.py`가 아니라 `config/__init__.py`를 대상으로 함 — CLAUDE.md §7-1 참조**)
   - `config.MOCK_MODE` / `config.OPERATING_STAGE` / `SafetyService.ensure_order_allowed()`에 대한 영향 여부 (기본값: 영향 없음이어야 함)
   - 필요한 백테스트/승격 시나리오 (§4 참조)
3. `Plans.md`에는 TDD 순서로 구현 단계를 쪼갠다 (테스트 작성 → 최소 구현 → 리팩터).
4. **사람 승인 없이 2단계로 넘어가지 않는다.** 리스크 상수를 완화하는 변경은 사람이 `Plans.md`에 `RISK LIMIT CHANGE APPROVED` 문구와 서명을 남겨야만 훅(`.claude/hooks/post_edit_check.sh`)이 차단하지 않는다.

---

## 2. `/harness-work` — 스코프 제한 TDD 구현

트리거: 승인된 `spec.md`/`Plans.md`가 존재할 때만.

규칙:
1. **명세에 명시된 파일 외에는 수정하지 않는다.** 특히 `order_engine.py`(주문 실행)와 `backend/app/services.py`의 `SafetyService`/`TradingService`는 `spec.md`에 명시적으로 포함되지 않는 한 절대 건드리지 않는다.
2. TDD 순서 고정: (a) 실패하는 테스트 작성(`tests/` 아래, 기존 8개 파일과 같은 컨벤션) → (b) 최소 구현으로 통과 → (c) 리팩터 → (d) `post_edit_check.sh` 훅 통과 확인.
3. 신규/수정 로직에는 반드시 다음 케이스의 테스트를 포함한다:
   - 정상 케이스
   - `price_history`가 짧거나(`period+1` 미만) 비어있는 경계 케이스
   - `NaN`/`None`/0/음수가 섞인 입력 (CLAUDE.md §5 참조)
   - `avg_price<=0`, `INITIAL_CAPITAL<=0` 같은 0-분모 케이스
   - 시그널을 다루는 코드라면 `analyzed_at`/`quote_collected_at`이 `None`이거나 `SIGNAL_STALENESS_SEC`/`QUOTE_STALENESS_SEC`를 초과한 케이스 (`ensure_signal_freshness`가 차단하는지)
4. Mock 경로와 실전 경로가 분기하는 함수(`get_price`, `get_balance`, `get_price_history`, `MarketAdapter` 서브클래스)를 수정할 때는 **두 경로 모두** 테스트한다 (`config.MOCK_MODE=True/False` 양쪽, 기존 `tests/test_market_adapters.py` 패턴 참고).
5. 구현 중 스코프를 벗어난 변경이 필요하다고 판단되면, 구현을 멈추고 `/harness-plan`으로 돌아가 spec을 갱신한다 — 즉석에서 스코프를 넓히지 않는다.

---

## 3. `/harness-review` — 독립 리뷰 에이전트 체크리스트

트리거: `/harness-work` 완료 후, 병합 전 필수. **구현을 수행한 에이전트/세션과 분리된 별도 리뷰 관점**에서 수행한다 (예: `Agent` 툴로 별도 서브에이전트를 띄워 구현 컨텍스트 없이 diff만 보고 리뷰).

체크리스트:

- [ ] `.env`, `ACCOUNT_NO`, `KIS_APP_KEY`/`SECRET` 등 시크릿이 diff에 노출되지 않았는가
- [ ] 리스크/게이트 상수 변경이 있다면 `Plans.md`에 승인 서명이 있는가
- [ ] 새 지표/사이징 계산에 `NaN`/빈 리스트/0-분모 가드가 있는가 (CLAUDE.md §5 패턴 준수)
- [ ] Mock ↔ 실전 두 경로의 반환 스키마(dict 키 구성)가 동일하게 유지되는가 — 예: `get_price()`가 반환하는 `current_price/open_price/high_price/low_price` 키셋이 mock/kis/yf 세 구현에서 일치해야 대시보드·리스크 로직이 깨지지 않는다
- [ ] **`SafetyService.ensure_order_allowed()`를 우회하는 새 주문 경로가 생기지 않았는가** (CLAUDE.md §4.2) — `TradingService`를 거치지 않고 `order_engine`/`market_adapters`를 직접 호출하는 코드가 diff에 있으면 반려
- [ ] 상태 저장 변경이 있다면 **어느 DB**(`data/agent_state.db`의 `StateStore` vs `data/alpha_gen.sqlite3`의 `SQLiteStore`)를 건드렸는지 명시하고, 나머지 한쪽과 값이 어긋날 가능성을 검토했는가 (CLAUDE.md §7-2)
- [ ] KIS API 호출부에 재시도/쿨다운/디그레이드 처리가 기존 패턴(`_kis_request_get`)을 우회하지 않는가
- [ ] §4 팬아웃 교차검증 파이프라인을 깨는 변경(기술신호와 리스크사이징을 단일 함수로 합치는 등)이 없는가
- [ ] 테스트가 실제로 실패-후-통과 이력을 가지는가 (구현에 맞춰 짜맞춘 테스트가 아닌지), 그리고 `pytest -q`로 기존 8개 테스트 파일이 모두 여전히 통과하는가

리뷰 결과는 승인/반려로 남기고, 반려 시 구체적 라인 지적과 함께 `/harness-work`로 반송한다.

---

## 4. 기술적 분석 × 리스크 관리 × 실거래 게이트 교차검증 파이프라인

### 4.1 설계 원칙

`technical.py`(진입 신호: RSI/MA/변동성 돌파)와 `risk_manager.py`(자금 배분/손절/드로우다운)는 **서로 독립적으로 평가되어야 하며, 어느 한쪽의 긍정 신호만으로 주문이 나가서는 안 된다.** 실제로는 이 둘의 병합 결과조차 최종 관문이 아니다 — **`SafetyService.ensure_order_allowed()`가 그 위에 한 겹 더 있는 최종 게이트**다 (CLAUDE.md §4.1). 세 계층을 하나로 합치는 리팩터는 금지한다(§3 리뷰 체크리스트 항목).

```
                ┌──────────────────────────┐
   후보 종목 ──▶│ Branch A: technical.py    │──▶ signal: bool, reason
   리스트       │  evaluate_buy_technicals  │
                └──────────────────────────┘
                ┌──────────────────────────┐
   (병렬/독립) ─▶│ Branch B: risk_manager.py │──▶ qty>0, sleep_mode, stop_loss 여부
                │  get_position_size /       │
                │  check_max_drawdown /      │
                │  check_stop_loss           │
                └──────────────────────────┘
                            │
                            ▼
                 merge_signals() — AND 결합 (기술 신호 ∧ qty>0)
                            │
                            ▼
              SafetyService.ensure_order_allowed()  ← 최종 게이트
              (긴급정지 → 휴면모드 → 신선도 → [live일 때만] 스테이지/
               ALLOW_LIVE_TRADING/주문한도/일손실/연속손실)
                            │
                            ▼
                 TradingService가 order_engine.py 경유 실주문
```

### 4.2 병합 규칙 (의사코드, technical × risk_manager 단계만 — SafetyService 게이트는 TradingService가 이미 호출함)

```python
def merge_signals(stock_code: str, price_history: list[float], quote: dict,
                   total_asset: int, sentiment_score: int, prev_day: dict | None) -> dict:
    """technical.py + risk_manager.py 교차검증 후 최종 매수 후보 여부 반환.
    이 결과가 True여도 SafetyService.ensure_order_allowed()를 통과해야
    실제 주문이 나간다 — 이 함수는 그 앞단 필터일 뿐이다.
    """
    import risk_manager, technical

    tech = technical.evaluate_buy_technicals(stock_code, price_history, quote, prev_day)

    if risk_manager.SLEEP_MODE:
        return {"approved": False, "reason": "SLEEP_MODE active", "tech": tech}

    qty = risk_manager.get_position_size(total_asset, sentiment_score, quote["current_price"])

    approved = bool(tech["signal"]) and qty > 0
    return {
        "approved": approved,
        "qty": qty,
        "reason": tech["reason"] if not tech["signal"] else (
            "position size 0 (max_position/confidence 제약)" if qty == 0 else "OK"
        ),
        "tech": tech,
    }
```

이 함수는 신규 파일(예: `signal_merge.py`)에 두고 `technical.py`/`risk_manager.py` 내부는 수정하지 않는다 — 두 모듈의 "독립성"이 교차검증의 핵심이므로. `AgentService.run_cycle()`이 이미 유사한 조합 로직을 갖고 있을 가능성이 높으므로, 새로 만들기 전에 `backend/app/services.py`의 `AgentService`(L1730~)를 먼저 확인해 중복 구현을 피한다.

### 4.3 백테스트 검증 (실전 반영 전 필수 게이트) — 기존 `BacktestService` 재사용

**v1의 실수: 새 백테스트 스크립트를 만들라고 지시했으나, `backend/app/services.py`의 `BacktestService`(L1602~)가 이미 존재한다.** 또한 루트에 `backtest.py`(독립 실행형 "간이 백테스트", Mock 가격 + 고정 감성 시나리오)도 별도로 존재해 **두 백테스트 경로가 중복되어 있을 가능성이 있다** — 새 작업을 시작하기 전에 두 파일의 관계(하나가 다른 하나의 전신인지, 용도가 다른지)를 먼저 확인하고, 불명확하면 사람에게 묻는다. 어느 쪽이든:

1. 리스크 파라미터나 신호 로직을 변경했다면, **먼저 `BacktestService`(가능하면) 또는 `backtest.py`로 회귀 검증**한다 — 새 리플레이 스크립트를 처음부터 작성하지 않는다.
2. 최소 90일치 과거/Mock 종가 시퀀스로 시뮬레이션하고, `risk_manager.check_stop_loss`/`check_max_drawdown`이 매 스텝 정상 발동하는지 확인한다.
3. 결과 지표(누적 수익률, MDD, 손절 발동 횟수, `SLEEP_MODE` 진입 여부)를 기록으로 남긴다.
4. MDD가 `config.MAX_DRAWDOWN_PCT`를 초과할 때 `SLEEP_MODE`가 정상적으로 트리거되는지 반드시 확인한다 — 트리거되지 않으면 리스크 로직 버그로 간주하고 병합을 차단한다.
5. 백테스트 코드 경로는 `order_engine.py`나 `SafetyService.ensure_order_allowed()`를 import/호출하지 않는다 (실주문 코드 경로와 완전 분리 유지).

### 4.4 단계별 승격 — `docs/operating_stages.md` 그대로 따름 (새로 정의하지 않음)

**v1은 "Mock↔실전" 이분법으로 서술했지만, 실제로는 `docs/operating_stages.md`에 이미 5단계 승격 프로세스가 정의돼 있다.** 이 문서를 대체하지 말고 그대로 따른다:

`mock` → `paper` → `shadow` → `live_limited` → `live_full`

- 각 단계 승격 전 **한 단계 아래 환경에서 회귀 테스트와 수동 검증을 먼저 끝낸다** (`docs/operating_stages.md` "승격 규칙" §1)
- `live_limited` 이상으로 승격은 **사람이 운영 콘솔/CLI에서 직접** `SafetyService.set_stage()`를 호출해야 하며, 에이전트가 자율적으로 수행하지 않는다 (CLAUDE.md §4.2)
- 승격 전 `python scripts/live_mode_checklist.py`를 실행해 `ALLOW_LIVE_TRADING`/`OPERATING_STAGE`/`EMERGENCY_STOP`/`LIVE_MAX_ORDERS_PER_DAY`를 사전 점검한다 (CLAUDE.md §1)
- 전체 순서: `/harness-plan` 승인 → `/harness-work` 구현+테스트 → `/harness-review` 통과 → §4.3 백테스트 통과 → `scripts/live_mode_checklist.py` 통과 → **사람이 직접** 단계 승격 및 소액 실거래 파일럿 → 정상 확인 후 `live_full`. 각 화살표는 이전 단계 통과 없이는 건너뛸 수 없다.
