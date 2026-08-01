# alpha-gen — 세션 인수인계 문서 (Context Handoff)

> **목적**: 새 Cursor 채팅 / 다른 개발자가 **코드베이스·진행 상황·다음 작업**을 바로 이어갈 수 있도록 정리한 문서  
> **최종 갱신**: 2026-08-01 (하네스 엔지니어링 세션 — §15 참조)  
> **관련 문서**: [README.md](./README.md) (상세 스펙), [workthrough.md](./workthrough.md) (개발 요약), [CLAUDE.md](./CLAUDE.md) (AI 에이전트 가드레일, **새 세션은 이 문서부터 자동으로 읽음**), [HARNESS_WORKFLOW.md](./HARNESS_WORKFLOW.md) (계획→구현→리뷰 프로세스)

---

## 1. 프로젝트 한 줄 요약

**alpha-gen** = 뉴스 감성(Claude) + RSI/MA/변동성 돌파 + 리스크 규칙으로 KR/US 주식을 자동 매매하는 Python 봇.  
`main.py`(엔진) + `dashboard.py`(Streamlit UI) + `mock_state.json`(상태 공유).

---

## 2. 현재 파일 구조 (2026-08-01 갱신)

```
alpha-gen/
├── CLAUDE.md                # ⭐ AI 에이전트 가드레일 (새 세션 시작 시 자동 로드)
├── HARNESS_WORKFLOW.md       # ⭐ plan/work/review + 백테스트 검증 프로세스
├── .claude/
│   ├── settings.json         # 권한(allow/ask/deny) + PostToolUse 훅
│   └── hooks/post_edit_check.sh
├── config/__init__.py        # ⭐ 실제 사용되는 설정 (env-driven, .env에서 값 주입)
├── config.example.py         # 설정 템플릿 (Git 포함)
├── main.py                   # CLI 에이전트 루프 (backend.app.services 경유)
├── backend/app/services.py   # ⭐ 서비스 계층 — SafetyService/RiskService/TradingService/
│                              #   AgentService/BacktestService/DiagnosticsService
├── backend/app/store.py      # SQLiteStore (data/alpha_gen.sqlite3)
├── dashboard.py               # Streamlit 대시보드
├── news_analyzer.py           # RSS + Claude/Mock 감성
├── technical.py                # RSI, MA, 변동성 돌파, evaluate_buy_technicals()
├── market_data.py              # 시세·잔고·세션·상태 영속화·equity_history
├── market_adapters.py          # Mock / KisKR / UsYfinance 어댑터
├── order_engine.py             # KIS 국내·해외 주문 + Mock 체결
├── order_registry.py           # idempotent 주문 키(ticker_side_date)
├── risk_manager.py             # 포지션·손절·드로우다운·휴면
├── notifier.py                 # 텔레그램
├── agent_logging.py            # logging + logs/alpha_gen.log
├── backtest.py                 # 간이 백테스트 (BacktestService와 중복 여부 미확인 — HARNESS_WORKFLOW §4.3)
├── state_store.py              # SQLite 상태 저장소 (data/agent_state.db) — backend의 alpha_gen.sqlite3와 별개 DB (CLAUDE.md §7-2)
├── migrate_to_sqlite.py        # JSON → DB 일회성 마이그레이션 (완료됨)
├── scripts/live_mode_checklist.py  # 실전 전환 전 필수 체크
├── docs/operating_stages.md    # mock→paper→shadow→live_limited→live_full 승격 기준
├── Dockerfile / docker-compose.yml
├── tests/                      # pytest 8개 파일
├── archive/                     # 2026-08-01 정리: mock_state.json(.bak), 루트 config.py,
│                                #   frontend-legacy/, cluade-design/ (모두 사용처 없음 확인 후 이동)
├── README.md / workthrough.md / CONTEXT.md (본 문서)
└── logs/                       # Git 제외
```

> 루트 `config.py`, `mock_state.json`(.bak), `frontend-legacy/`, `cluade-design/`는 2026-08-01에 `archive/`로 이동했다 (코드에서 참조 없음 확인, git 커밋 `cd262dd`). 삭제가 아니라 이동이므로 필요하면 `archive/`에서 그대로 찾을 수 있다.

---

## 3. 지금까지 완료한 개선 (Phase 1~3)

### Phase 1 — 안정성·영속화
| 항목 | 내용 |
|------|------|
| 통합 상태 파일 | `mock_state.json`에 `bought_today`, `sleep_mode`, `sentiments`, `last_news_fetch`, `initial_capital` 추가 |
| KR 실전 시세 | `kis_get_price_history()` + `get_price_history()` |
| 로깅 | `agent_logging.py` → `logs/alpha_gen.log` (RotatingFileHandler) |
| 대시보드 동기화 | `_shared_sentiments` 기본값 `{}`, `load_agent_state()` 공통 |
| 휴면 Mock | **Mock 모드는 파일의 sleep_mode 복원 안 함** (테스트 잔재 방지) |
| CLI | `python main.py --wake` → 실전/모의 휴면 해제 |

### Phase 2 — 전략·아키텍처·테스트
| 항목 | 내용 |
|------|------|
| 변동성 돌파 | `ENABLE_VOLATILITY_BREAKOUT`, `evaluate_buy_technicals()` → main 매수 조건에 연동 |
| MarketAdapter | `MockAdapter`, `KisKRAdapter`, `UsYfinanceAdapter` |
| pytest | `tests/test_*.py` 11개 통과 |

### Phase 3 — 확장
| 항목 | 내용 |
|------|------|
| KIS 해외주문 | `kis_us_buy/sell`, `ENABLE_KIS_US_ORDERS=False` (기본) |
| Claude 배치 | `CLAUDE_BATCH_SENTIMENT=True` → 토픽 7개 1회 호출 |
| 환율 | `fetch_usd_krw()` (yfinance USDKRW=X) |
| backtest.py | Mock 가격 + 기술 필터 간이 시뮬 |
| Docker | `Dockerfile`, `docker-compose.yml` (agent + dashboard) |
| 자산 추이 | `equity_history` + 대시보드 Plotly (기준선·드로우다운) |

### Phase 4 — 대시보드·매핑·E2E (2026-05-23)
| 항목 | 내용 |
|------|------|
| MOCK_CONTINUOUS | Mock 장외 3초 루프 유지 (`False` 시 1회 종료) |
| Plotly equity | 초기 원금 기준선 + 드로우다운 오버레이 |
| STOCK_TOPIC_MAP | 종목↔토픽 명시 매핑 + Palantir 토픽 |
| KIS E2E | `scripts/kis_smoke_test.py`, `tests/test_kis_integration.py` |
| config.example.py | 온보딩 템플릿 |
| pytest | 18개 (15 pass + 3 KIS skip) |

---

## 4. 매매 로직 (현재)

### 매수 조건 (모두 충족)
1. **감성** `score >= SENTIMENT_BUY_THRESHOLD(1)`
2. **RSI** ≤ 70, **현재가 ≥ MA20**
3. **변동성 돌파** (`ENABLE_VOLATILITY_BREAKOUT=True`): 현재가 ≥ 목표가  
   `목표가 = 시가 + (전일고 - 전일저) × K_VALUE(0.5)`

### 매도
- 국장 15:15 / 미장 05:00 KST 전량 청산
- 개별 손절 -4%
- 드로우다운 -15% → 휴면 + 긴급 청산

### Mock 모드 종료 조건 (중요)
| 상황 | 동작 |
|------|------|
| **장외 (CLOSED)** | KR 1사이클 → 전량 매도 → **프로그램 종료** (지금 주말/밤 테스트 시 금방 끝남) |
| **장중 (KR/US)** | **3초마다 루프 계속** (Ctrl+C까지) |
| **국장 3종목 전부 매수** | 매도 후 **자동 종료** |

→ Mock이어도 **장중이면 계속 도는 것이 맞음**. 장외만 1회 테스트 후 종료.

---

## 5. 추천 config 셋팅

### 지금 (학습)
```python
MOCK_MODE = True
MOCK_CONTINUOUS = True   # 장외에도 Mock 루프 유지 (대시보드 테스트)
CLAUDE_MODEL = "claude-3-5-haiku-20241022"
CLAUDE_BATCH_SENTIMENT = True
ENABLE_VOLATILITY_BREAKOUT = True   # Mock 매수 잘 안 되면 False로 테스트
ENABLE_KIS_US_ORDERS = False
TELEGRAM_ENABLED = True  # 토큰 없으면 [TG-SKIP] 콘솔만
```

### 모의투자 (2~4주 후)
```python
MOCK_MODE = False
IS_REAL_TRADING = False
MAX_POSITION_PCT = 0.04
MAX_DRAWDOWN_PCT = 0.10
```

### Claude API 비용 (참고)
- Haiku + 배치: **월 약 1,000~4,000원** (1만 원 이하)
- Cursor 구독과 **별개** (main.py는 `ANTHROPIC_API_KEY` 직접 호출)

---

## 6. 실행 방법

```bash
cd /path/to/alpha-gen
source venv/bin/activate
pip install -r requirements.txt

# 터미널 1
python main.py              # 휴면 해제: python main.py --wake

# 터미널 2
streamlit run dashboard.py    # http://localhost:8501

# 테스트
python -m pytest tests/ -v
python backtest.py

# Docker
docker compose up --build
```

**순서**: `main.py` 먼저 → `dashboard.py` (감성·잔고·equity_history 동기화)

---

## 7. mock_state.json 스키마 (핵심 필드)

```json
{
  "last_updated": "...",
  "bought_today": ["005930"],
  "bought_today_date": "2026-05-23",
  "sleep_mode": false,
  "sleep_reason": "",
  "sentiments": { "Elon Musk": { "score": 2, ... } },
  "last_news_fetch": "2026-05-23T12:31:12+09:00",
  "initial_capital": 10000000,
  "equity_history": [
    { "time": "2026-05-23 12:44:00", "total": 10000000, "cash": 10000000, "session": "KR" }
  ],
  "cash": 10000000,
  "holdings": {},
  "prices": { "005930": 75000.0, ... },
  "trade_log": []
}
```

- `save_agent_state()` / `load_agent_state()` in `market_data.py`
- `record_equity_snapshot()` — `main.print_balance()` 및 시작 시 호출

---

## 8. 알려진 이슈 / 기술 부채 (다음 작업 후보)

| 우선순위 | 이슈 | 메모 |
|----------|------|------|
| ✅ | `mock_state.json` → SQLite 전환 | `state_store.py`, `migrate_to_sqlite.py` 생성, `market_data.py` 패치 완료 |
| 🔴 | Mock **장외 1회 종료** | `MOCK_CONTINUOUS=True`(기본)로 장외 루프 유지. 1회만 테스트하려면 `False` |
| 🟡 | 미장 실주문 | `ENABLE_KIS_US_ORDERS=True` + KIS 해외 API 실계좌 검증 필요 |
| 🟡 | 미장 잔고 | US Mock 체결 vs KIS 국내 잔고 불일치 (기존 구조) |
| 🟢 | PLTR 등 감성 0 | ✅ `STOCK_TOPIC_MAP` + `Palantir defense AI` 토픽 추가 |
| 🟡 | 대시보드 종목 차트 | 아직 랜덤 시뮬 (equity_history는 Plotly 실데이터) |
| 🟢 | Plotly·Sharpe | README Phase 3 장기 항목 |
| 🟢 | tenacity 재시도 | KIS API 견고성 |
| 🟢 | config.example.py | ✅ |

---

## 9. 트러블슈팅 (자주 겪은 것)

| 증상 | 원인 | 해결 |
|------|------|------|
| `😴 휴면 모드 (test sleep)` | mock_state에 sleep 잔존 | Mock은 자동 무시됨 / 실전은 `--wake` 또는 JSON 수정 |
| Mock 금방 종료 | **장외** → 1사이클 후 break | 정상. 장중(월~금 09~15:30)에 실행하면 계속 루프 |
| `[TG-SKIP]` | 텔레gram 미설정 | config에 TELEGRAM_* 입력 |
| 대시보드 감성 0 | main 미실행 | main.py 먼저 실행 |
| equity 그래프 비어 있음 | main 한 번도 안 돌림 | main.py 실행 후 5초 refresh |
| ModuleNotFoundError | venv 미활성 | `source venv/bin/activate` |

---

## 10. Gemini 로드맵 대비 진행률

| Gemini 제안 | 상태 |
|-------------|------|
| 상태 영속화 (bought_today, sleep) | ✅ |
| KR KIS 과거 시세 | ✅ |
| logging | ✅ |
| 변동성 돌파 연동 | ✅ |
| MarketAdapter | ✅ |
| pytest | ✅ |
| KIS 미장 실주문 | ⚠️ 코드만, `ENABLE_KIS_US_ORDERS=False` |
| Claude 배치 | ✅ |
| Docker | ✅ |
| 백테스트 | ⚠️ 간이版 (`backtest.py`) |
| Plotly·Sharpe UI | ⚠️ equity Plotly+드로우다운 완료, Sharpe 미구현 |
| AI 비용 Cursor 구독 대체 | ❌ (Anthropic API 별도) |

---

## 11. 다음 세션에서 바로 할 수 있는 작업

1. ~~**market_data.py SQLite 패치 적용**~~ ✅ 완료
2. **KIS 모의투자 실연동** — `MOCK_MODE=False` 후 `python scripts/kis_smoke_test.py`
3. **대시보드 종목 차트** — mock_state `prices` / KIS 시세 연동 (랜덤 시뮬 제거)
4. **Sharpe·성과 지표** — equity_history 기반 대시보드 메트릭
5. **tenacity 재시도** — KIS API 견고성
6. **미장 KIS 실주문** — `ENABLE_KIS_US_ORDERS=True` 실계좌 검증
7. **OHLCV + MACD/BB를 매수 조건에 연동** — `ohlcv.get_latest_signals()` → `main.py evaluate_buy_signal`

**최근 완료 (2026-05-27)**:
- Phase 5: `state_store.py` SQLite 전환, `market_data.py` 패치, `migrate_to_sqlite.py`
- OHLCV 파이프라인: `ohlcv.py` (yfinance 일봉 → SQLite → MACD + 볼린저밴드)
- 실전 전환: `order_registry.py` (idempotent 주문), `scripts/live_mode_checklist.py`

### Phase 5 — SQLite 상태 저장소 전환 (2026-05-27)
| 항목 | 내용 |
|------|------|
| `state_store.py` 신규 | `StateStore` 클래스 — SQLite WAL 모드, thread-safe, 7개 테이블 |
| `migrate_to_sqlite.py` 신규 | `mock_state.json` → `agent_state.db` 일회성 변환 + 검증 + 자동 백업 |
| `market_data.py` 패치 대상 | `save_agent_state`, `load_agent_state`, `add/remove/clear/is_bought_today`, `record_equity_snapshot` 교체 필요 |
| 해결된 문제 | 파일 충돌(main+dashboard 동시 쓰기), `bought_today` 재시작 유실, `equity_history` 휘발, JSON 원자성 없음 |
| 테스트 결과 | 전체 기능 테스트 통과 (sentiments 7개, prices 7개, bought_today CRUD, equity_history, trade_log) |

**✅ market_data.py 패치 완료** — 2026-05-27 Claude Code 적용. pytest 31 passed, 3 skipped.


---

## 12. 새 채팅 시작 시 붙여넣을 프롬프트 (복사용)

```
alpha-gen 프로젝트 이어서 작업해줘.
먼저 CONTEXT.md, README.md, workthrough.md를 읽고 현재 상태를 파악해.

최근 완료: Phase1~3 + MOCK_CONTINUOUS, Plotly equity, STOCK_TOPIC_MAP, KIS E2E 스모크.
알려진 이슈: 미장 잔고/주문 미완, 대시보드 종목 차트 랜덤 시뮬.

[여기에 이번에 할 작업 작성]
예: MOCK_CONTINUOUS 옵션 추가 / 대시보드 Plotly equity / KIS 모의투자 연동 테스트
```

---

## 13. Git / 보안 주의

- `config.py` → **.gitignore** (API 키)
- `logs/`, `venv/`, `backtest_result.json` → gitignore
- `mock_state.json` → 로컬 실행 결과 포함 가능 (커밋 여부는 팀 정책에 따름)

---

*이 문서는 대화 세션 종료 시점의 스냅샷입니다. 코드 변경 후 섹션 3·8·10을 함께 업데이트하세요.*

---

## 14. Claude Code 인수인계 — SQLite 패치 즉시 적용

**2026-05-27 claude.ai 세션에서 설계·테스트 완료, 파일 적용은 Claude Code로 진행.**

### 준비된 파일
- `state_store.py` — SQLite 저장소 클래스 (다운로드 후 프로젝트 루트에 배치)
- `migrate_to_sqlite.py` — 마이그레이션 스크립트 (동일)
- `market_data_patch.py` — 교체할 함수 전문 수록

### Claude Code에게 전달할 프롬프트

```
alpha-gen 프로젝트 이어서 작업해줘.
CONTEXT.md, README.md 읽고 현재 상태 파악 후 아래 작업 진행해줘.

[작업] market_data.py SQLite 패치 적용
- state_store.py 가 이미 프로젝트 루트에 있음
- market_data_patch.py 참고해서 market_data.py 를 아래 순서로 수정:
  1. 상단에 `from state_store import StateStore` + `_store = StateStore(config.DATA_DIR / "agent_state.db")` 추가
  2. save_agent_state() 함수를 _store.save(...) 방식으로 교체
  3. load_agent_state() 함수를 _store.load() 방식으로 교체
  4. add_bought_today / remove_bought_today / clear_bought_today / is_bought_today 4개 함수에 _store 동기화 코드 추가
  5. record_equity_snapshot() 함수에 _store.append_equity(...) 호출 추가
  6. MOCK_STATE_FILE 상수 주석 처리
- 수정 완료 후 python migrate_to_sqlite.py 실행
- pytest tests/ -v 통과 확인
```

### 핵심 설계 원칙 (변경하면 안 되는 것)
- `_apply_agent_fields(state: dict)` 함수는 그대로 재사용 — `_store.load()`의 반환 포맷이 기존 JSON과 동일하게 설계되어 있음
- `mock_trade_log`, `equity_history`, `_shared_sentiments` 메모리 전역변수는 유지 (대시보드 실시간 참조용)
- `save_mock_state()` / `load_mock_state()` 하위 호환 별칭 유지

---

## 15. 하네스 엔지니어링 세션 인수인계 (2026-08-01, Cowork)

**목적**: AI 에이전트(Claude Code 등)가 이 저장소에서 자율적으로 작업할 때 실거래 자산을 보호하는 가드레일·워크플로우·권한 체계를 구축.

### 이번 세션에서 만든 것
| 파일 | 내용 |
|---|---|
| `CLAUDE.md` (v2) | 실거래 게이트(`SafetyService.ensure_order_allowed()`) 구조, 절대 금지 사항, 사람 승인 필요 변경 목록, NaN/신선도 데이터 무결성 규칙을 실제 함수·클래스명 기준으로 정리 |
| `HARNESS_WORKFLOW.md` (v2) | `/harness-plan`(명세 승인) → `/harness-work`(스코프 제한 TDD) → `/harness-review`(독립 리뷰) → 백테스트/단계 승격 검증의 4중 게이트. `technical.py`×`risk_manager.py`×`SafetyService` 3계층 교차검증 파이프라인 포함 |
| `.claude/settings.json` + `.claude/hooks/post_edit_check.sh` | 파일 수정 직후 자동으로 린트+회귀테스트 실행, `config/__init__.py`·`risk_manager.py`·`backend/app/services.py`·`.env`에서 리스크 완화/실거래 활성화 시도 감지 시 차단 |

### 처음 분석에서 놓쳤던 것 (v1→v2 갭, 상세는 대화 로그 참조)
1. 실거래 최종 게이트는 `config.IS_REAL_TRADING` 단일 플래그가 아니라 `backend/app/services.py`의 `SafetyService.ensure_order_allowed()` — 긴급정지→휴면모드→신호신선도→(live일 때만) 스테이지/주문한도/일손실/연속손실 순으로 검사
2. `docs/operating_stages.md`에 이미 5단계 승격 프로세스(`mock→paper→shadow→live_limited→live_full`)가 정의돼 있음 (재정의하지 않고 그대로 따름)
3. `tests/` 8개 파일, `BacktestService`, `scripts/live_mode_checklist.py`가 이미 존재 (구버전 CLAUDE.md의 "테스트 없음" 서술은 오류였음)
4. 상태 저장소가 `data/agent_state.db`(`state_store.StateStore`)와 `data/alpha_gen.sqlite3`(`backend/app/store.SQLiteStore`)로 이중화되어 있음 — 아직 미해결 리스크로 남겨둠

### 오늘 정리한 것
- 루트 `config.py`(내용은 `config.example.py`와 동일한 미기재 플레이스홀더, `.gitignore`에도 걸려있고 `config/` 패키지에 가려지는 죽은 파일로 추정), `mock_state.json`(.bak)(SQLite 전환 후 미사용, 코드 어디서도 참조 안 됨), `frontend-legacy/`(React `frontend/`로 대체), `cluade-design/`(디자인 시안, `frontend/`에 포팅 완료 추정) → 모두 삭제가 아니라 `archive/`로 이동 (커밋 `cd262dd`)

### 로컬 Claude Code로 이어서 작업하기
새로 대화 맥락을 설명할 필요 없음 — `CLAUDE.md`가 그 역할을 대신한다. 터미널에서:

```bash
cd <alpha-gen 로컬 경로>
git status          # archive/ 정리 커밋이 반영됐는지 확인
claude               # 시작 시 CLAUDE.md 자동 로드, .claude/settings.json 권한·훅 자동 적용
```

Claude Code가 시작되면 `CLAUDE.md` + `HARNESS_WORKFLOW.md` + 본 문서(`CONTEXT.md`)를 이미 참고할 수 있는 상태이므로, 바로 "[다음 작업 내용]" 형태로 지시하면 된다. 별도의 인수인계 프롬프트가 필요하면 §12 템플릿을 참고하되, 이제는 `CLAUDE.md`/`HARNESS_WORKFLOW.md`를 먼저 읽으라는 문구를 추가하는 것을 권장한다.

### 다음으로 손볼 만한 것 (사람 판단 필요, 자동 진행 금지)
- `data/agent_state.db` vs `data/alpha_gen.sqlite3` 이중화 해소 방향 결정
- 루트 `backtest.py`와 `BacktestService`(backend/app/services.py) 중 실제로 쓰는 쪽 확정, 중복이면 정리
- `README.md`/`workthrough.md`가 CONTEXT.md와 마찬가지로 SQLite 전환 이전(mock_state.json 기준) 서술이 남아있는지 확인 후 필요시 갱신