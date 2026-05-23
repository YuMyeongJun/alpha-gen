"""
config.example.py — alpha-gen 설정 템플릿 (Git 추적용)

사용법:
  cp config.example.py config.py
  config.py 에 API 키·계좌 정보 입력
"""

# ════════════════════════════════════════════════
# [A] 거래 환경
# ════════════════════════════════════════════════

MOCK_MODE        = True    # True = 전체 모의 실행 (API 불필요)
IS_REAL_TRADING  = False   # False = 모의투자 / True = 실전 (반드시 Mock 검증 후!)
MOCK_CONTINUOUS  = True    # Mock 장외에도 루프 유지 (대시보드·equity 테스트용)

# ════════════════════════════════════════════════
# [B] 한국투자증권 API
# ════════════════════════════════════════════════

KIS_APP_KEY    = "여기에_APP_KEY"
KIS_APP_SECRET = "여기에_APP_SECRET"
ACCOUNT_NO     = "여기에_계좌번호_앞8자리"
ACCOUNT_CODE   = "01"

KIS_URL = (
    "https://openapi.koreainvestment.com:9443"
    if IS_REAL_TRADING else
    "https://openapivts.koreainvestment.com:29443"
)

# ════════════════════════════════════════════════
# [C] Claude API
# ════════════════════════════════════════════════

ANTHROPIC_API_KEY = "여기에_Claude_API_키"
CLAUDE_MODEL = "claude-3-5-haiku-20241022"

# ════════════════════════════════════════════════
# [D] 종목 설정
# ════════════════════════════════════════════════

KR_STOCKS = {
    "005930": {"name": "삼성전자",   "keywords": ["Samsung", "Samsung Semiconductor", "삼성"]},
    "000660": {"name": "SK하이닉스", "keywords": ["SK Hynix", "HBM", "반도체"]},
    "005380": {"name": "현대차",     "keywords": ["Hyundai", "HMG AI", "현대"]},
}

US_STOCKS = {
    "TSLA":  {"name": "Tesla",           "exchange": "NASD", "keywords": ["Elon Musk", "Tesla", "EV"]},
    "SPCE":  {"name": "Virgin Galactic", "exchange": "NYSE", "keywords": ["Space", "SpaceX", "Rocket"]},
    "NVDA":  {"name": "Nvidia",          "exchange": "NASD", "keywords": ["Nvidia", "AI chip", "GPU"]},
    "PLTR":  {"name": "Palantir",        "exchange": "NYSE", "keywords": ["Palantir", "AI", "Defense"]},
}

ENABLE_KIS_US_ORDERS = False

# ════════════════════════════════════════════════
# [E] 뉴스 감성 분석
# ════════════════════════════════════════════════

NEWS_TOPICS = [
    "Elon Musk",
    "SpaceX",
    "Samsung Semiconductor",
    "SK Hynix HBM",
    "HMG AI Hyundai",
    "Tesla stock",
    "Nvidia AI chip",
    "Palantir defense AI",
]

STOCK_TOPIC_MAP = {
    "005930": ["Samsung Semiconductor"],
    "000660": ["SK Hynix HBM"],
    "005380": ["HMG AI Hyundai"],
    "TSLA":   ["Elon Musk", "Tesla stock"],
    "SPCE":   ["SpaceX"],
    "NVDA":   ["Nvidia AI chip"],
    "PLTR":   ["Palantir defense AI"],
}

NEWS_FETCH_INTERVAL_MIN = 60
NEWS_MAX_PER_TOPIC      = 5
SENTIMENT_BUY_THRESHOLD = 1
CLAUDE_BATCH_SENTIMENT  = True

# ════════════════════════════════════════════════
# [F] 기술 지표
# ════════════════════════════════════════════════

RSI_PERIOD      = 14
RSI_OVERBOUGHT  = 70
MA_SHORT        = 5
MA_LONG         = 20
K_VALUE         = 0.5
ENABLE_VOLATILITY_BREAKOUT = True

# ════════════════════════════════════════════════
# [G] 리스크
# ════════════════════════════════════════════════

TOTAL_CAPITAL         = 10_000_000
MAX_POSITION_PCT      = 0.06
STOP_LOSS_PCT         = 0.04
MAX_DRAWDOWN_PCT      = 0.15

CONFIDENCE_SIZING = {
    2: 1.00,
    1: 0.60,
    0: 0.00,
   -1: 0.00,
   -2: 0.00,
}

# ════════════════════════════════════════════════
# [H] 장 시간 (KST)
# ════════════════════════════════════════════════

KR_MARKET_OPEN    = "09:00"
KR_MARKET_CLOSE   = "15:30"
KR_BUY_START      = "09:05"
KR_SELL_TIME      = "15:15"
US_MARKET_OPEN    = "22:30"
US_MARKET_CLOSE   = "05:00"

# ════════════════════════════════════════════════
# [I] 텔레그램
# ════════════════════════════════════════════════

TELEGRAM_ENABLED   = True
TELEGRAM_BOT_TOKEN = "여기에_봇_토큰"
TELEGRAM_CHAT_ID   = "여기에_채팅_ID"

# ════════════════════════════════════════════════
# [J] Mock 시드
# ════════════════════════════════════════════════

MOCK_INITIAL_CASH = 10_000_000

MOCK_SEED_PRICES = {
    "005930": 75_000,
    "000660": 180_000,
    "005380": 240_000,
    "TSLA":  390_000,
    "SPCE":   4_000,
    "NVDA": 1_500_000,
    "PLTR":  105_000,
}
