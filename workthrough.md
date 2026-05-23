# alpha-gen 프로젝트 개발 완료 및 연동 가이드

본 문서는 지금까지 진행된 주식 자동매매 프로그램 **'alpha-gen'** 개발 프로젝트의 주요 구현 내용과 시스템 아키텍처, 각 모듈의 역할, 실행 방법 및 기술 부채를 정리한 최종 산출물 가이드입니다.

---

## 1. 프로젝트 개요

**alpha-gen**은 글로벌 시장 테마와 한국/미국의 핵심 산업군을 연결하여 자율적으로 판단하고 거래하는 **하이브리드 자율 트레이딩 에이전트**입니다.

- **핵심 컨셉**: 뉴스 감성 분석(Sentiment) + 기술적 지표(Technical Indicators) 필터링 + 엄격한 리스크 관리 규칙(Risk Management)
- **대상 시장**: 한국 주식 시장(국내장, 실전/모의 KIS API 연동) & 미국 주식 시장(미국장, yfinance 시세 기반 모의 체결)
- **모드 분기**: API 키 및 계좌 없이도 실행 흐름을 완전히 검증할 수 있는 **가상 테스트(Mock) 모드** 지원

---

## 2. 시스템 아키텍처 및 모듈 구성

본 시스템은 각 기능이 고도로 모듈화되어 설계되었으며, `main.py`가 전체 제어 흐름을 제어하고 `dashboard.py`가 현황을 실시간 시각화합니다.

```
                    ┌────────────────────────┐
                    │  config.py (통합 설정)  │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │      main.py           │◀──────────────────┐
                    │  (메인 에이전트 루프)    │                   │
                    └──────┬───────────┬─────┘                   │
                           │           │                         │
            ┌──────────────┘           └──────────────┐          │ (상태 공유)
            ▼                                         ▼          │
   ┌─────────────────┐                       ┌─────────────────┐ │
   │  news_analyzer  │                       │   technical     │ │
   │ (RSS + Claude)  │                       │ (RSI, MA 계산)   │ │
   └────────┬────────┘                       └────────┬────────┘ │
            │                                         │          │
            └──────────────────┬──────────────────────┘          │
                               ▼                                 │
                     ┌──────────────────┐                        │
                     │   risk_manager   │                        │
                     │ (사이징/손절/MDD)  │                        │
                     └─────────┬────────┘                        │
                               ▼                                 │
                     ┌──────────────────┐                        │
                     │   order_engine   │                        │
                     │  (KIS / Mock)    │                        │
                     └─────────┬────────┘                        │
                               ▼                                 │
                     ┌──────────────────┐                        │
                     │   market_data    │                        │
                     │ (시세/잔고/세션)   │                        │
                     └─────────┬────────┘                        │
                               ▼                                 │
                     ┌──────────────────┐                        │
                     │ mock_state.json  ├────────────────────────┘
                     │  (상태 파일 저장)  │
                     └─────────┬────────┘
                               ▼
                     ┌──────────────────┐      ┌─────────────────┐
                     │   dashboard.py   │ ───► │   notifier.py   │
                     │   (Streamlit)    │      │  (텔레그램 알림)  │
                     └──────────────────┘      └─────────────────┘
```

### 2.1 파일별 상세 역할

1. **`config.py`** : API 키, 계좌번호, 매매 파라미터, 장 시작/종료 시각, Mock 종목 시드 가격 등 모든 설정을 중앙 제어하는 설정 파일입니다.
2. **`main.py`** : 매매 시그널 판단, 매수/매도 지시, 자산 평가 및 리스크 관리 등을 매 루프마다 오케스트레이션하는 자율 에이전트 메인 루프입니다.
3. **`news_analyzer.py`** : Google News RSS를 1시간 주기로 수집하고 Claude API를 통해 각 헤드라인별 감성(Sentiment) 점수를 분석하여 특정 주식 종목과 매핑합니다.
4. **`technical.py`** : 가격 데이터를 바탕으로 RSI(14), MA5, MA20 등의 기술적 지표를 산출하고 매수 진입 시점 필터를 제공합니다.
5. **`risk_manager.py`** : 최대 손실 한도(-4%), 자산 대비 최대 드로우다운(-15%), 점수 비례 포지션 사이징(최대 6%)을 통제하여 파산을 예방합니다.
6. **`market_data.py`** : 현재 시간에 따라 한국 세션(KST 09:00~15:30)과 미국 세션(KST 22:30~05:00)을 감지하고, 해당 시장의 실시간 시세 및 잔고 조회를 통합 수행합니다.
7. **`order_engine.py`** : 국내장 실전/모의주식 주문(KIS API 호출)과 미국장 모의주식 주문(Mock Execution)을 대행하여 실행합니다.
8. **`notifier.py`** : 매수/매도 체결 내역, 일일 수익, 한도 도달 알림을 이유(Reason)와 함께 텔레그램 채널로 발송합니다.
9. **`dashboard.py`** : Streamlit 기반 실시간 자산 현황판으로, 현재 잔고, 보유 종목, 뉴스 감성 분석 추이 및 매매 이력을 시각화합니다.

---

## 3. 핵심 매매 로직 (Decision Pipeline)

### 3.1 매수 결정 흐름

매 루프마다 종목별로 다음의 **2단계 필터**를 모두 만족하는 경우에만 시장가 매수가 실행됩니다.

1. **감성 분석 필터 (Sentiment Filter)**:
   - Google News RSS 데이터 기반, Claude 3.5 Sonnet(또는 Haiku) 모델이 분석한 감성 점수의 가중평균이 `SENTIMENT_BUY_THRESHOLD` (기본값: `+1` 이상) 이상인 경우에만 통과합니다.
   - `+2`(매우 긍정)인 경우 투자 한도의 100%(총자산의 6%), `+1`(긍정)인 경우 투자 한도의 60%(총자산의 3.6%)로 비중을 차등 조절합니다.
2. **기술 지표 필터 (Technical Filter)**:
   - 과매수 구간 진입을 방지하기 위해 **RSI(14)이 70 이하**이고, 상승 추세를 확인하기 위해 **현재가가 20일 이동평균선(MA20) 이상**인 경우에만 최종 매수가 승인됩니다.

### 3.2 매도 및 리스크 제어 규칙

- **장 마감 전량 청산**: 당일 매수-당일 매도(Day Trading)를 원칙으로 하여, 국장은 15:15 KST 이후, 미장은 04:55 KST 이후 모든 포지션을 일괄 시장가 청산합니다.
- **개별 종목 손절 (Stop-Loss)**: 보유 종목의 평가 손실률이 `-4%` 이하로 떨어질 경우, 즉시 해당 종목을 시장가로 매도합니다.
- **최대 드로우다운 제어 (Max Drawdown)**: 총자산 평가액이 초기 자본금 대비 `-15%`에 도달하면 모든 보유 주식을 전량 매도하고 시스템을 **휴면 모드(Sleep Mode)**로 강제 전환하여 추가 손실을 차단합니다.

---

## 4. 가상 테스트(Mock) 모드 검증 및 구동 가이드

한국투자증권 API 키나 Claude API 키 없이도 로컬 환경에서 모의 동작을 즉시 검증할 수 있습니다.

### 4.1 가상 환경 및 패키지 설치

```bash
# 1. 저장소 폴더 이동
cd /path/to/alpha-gen

# 2. Python 가상환경 생성 (최초 1회)
python3 -m venv venv

# 3. 가상환경 활성화
source venv/bin/activate

# 4. 필수 의존성 라이브러리 설치
pip install -r requirements.txt
```

### 4.2 설정 구성 (`config.py`)

로컬 프로젝트 루트 디렉토리에 다음 내용으로 `config.py` 파일을 생성합니다.

```python
# config.py
MOCK_MODE = True  # True 설정 시 모든 동작이 시뮬레이션 데이터로 구동됩니다.
IS_REAL_TRADING = False

# API 키 설정 (Mock 모드인 경우 더미 값 유지 가능)
KIS_APP_KEY = "your_kis_app_key"
KIS_APP_SECRET = "your_kis_app_secret"
ACCOUNT_NO = "12345678"
ACCOUNT_CODE = "01"

ANTHROPIC_API_KEY = "your_claude_api_key"
CLAUDE_MODEL = "claude-3-5-haiku-20241022"

TELEGRAM_ENABLED = False
TELEGRAM_BOT_TOKEN = "your_telegram_bot_token"
TELEGRAM_CHAT_ID = "your_telegram_chat_id"

# (그 외 세부 리스크 및 주식 목록 등은 본 문서 상단 README의 설정을 준용합니다.)
```

### 4.3 프로그램 실행 단계

두 개의 터미널을 열고 각각 가상환경을 활성화한 후 아래 순서로 실행합니다.

- **터미널 1: 자동매매 코어 실행**

  ```bash
  source venv/bin/activate
  python main.py              # Mock 연속: MOCK_CONTINUOUS=True (기본)
  python main.py --wake       # 휴면 해제

  # KIS 모의투자 스모크 (MOCK_MODE=False + API 키 설정 후)
  python scripts/kis_smoke_test.py
  ```

  - Mock 모드 구동 시, 가상의 뉴스 감성 점수와 가격 변동이 생성되며 `mock_state.json` 파일에 잔고와 보유 종목이 실시간 업데이트됩니다.

- **터미널 2: 웹 대시보드 시각화 실행**
  ```bash
  source venv/bin/activate
  streamlit run dashboard.py
  ```

  - 브라우저가 자동 열리며(`http://localhost:8501`), 자산 변동 곡선, 종목 감성 점수 및 거래 로그가 실시간(5초 갱신) 시각화됩니다.

---

**문서**: [README.md](./README.md) · [CONTEXT.md](./CONTEXT.md) (세션 인수인계) · [workthrough.md](./workthrough.md)

---

## 6. Phase 4 개선 (2026-05-23)

| 항목 | 내용 |
|------|------|
| `MOCK_CONTINUOUS` | Mock 장외에도 3초 루프 유지 (`False` 시 기존 1회 종료) |
| Plotly equity | 초기 원금 기준선 + 드로우다운 오버레이 |
| `STOCK_TOPIC_MAP` | 종목↔뉴스 토픽 명시 매핑 (PLTR 포함) |
| KIS E2E | `scripts/kis_smoke_test.py`, `tests/test_kis_integration.py` |
| `config.example.py` | 온보딩용 설정 템플릿 |

---

## 5. 해결해야 할 기술 부채 및 개선 로드맵

현재 구현 수준에서 추후 실무 투입을 위해 개선해야 할 우선과제입니다. (Phase 1~4 완료 항목은 [CONTEXT.md](./CONTEXT.md) 참고)

1. **대시보드 종목 차트**: equity는 Plotly 실데이터, 종목별 차트는 아직 랜덤 시뮬 → `mock_state.prices` 연동
2. **미국장 실제 API 연동**: `ENABLE_KIS_US_ORDERS=True` 실계좌 검증
3. **Sharpe·성과 지표**: `equity_history` 기반 대시보드 메트릭
4. **KIS API 재시도**: tenacity 등 견고성 보강
