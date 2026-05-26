from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

try:
    from dotenv import load_dotenv

    # Explicit process env (pytest, CI, shell exports) wins over .env defaults.
    load_dotenv(PROJECT_ROOT / ".env", override=False)
except Exception:
    pass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_choice(name: str, default: str, allowed: set[str]) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    return value if value in allowed else default


PLACEHOLDER_MARKERS = ("여기에", "your_", "YOUR_")


def _has_real_value(raw: str | None) -> bool:
    if not raw:
        return False
    return not any(marker in raw for marker in PLACEHOLDER_MARKERS)


DB_PATH = os.getenv("ALPHA_GEN_DB_PATH", str(DATA_DIR / "alpha_gen.sqlite3"))


# [A] Trading environment
EXPLICIT_MOCK_MODE = _env_bool("MOCK_MODE", True)
IS_REAL_TRADING = _env_bool("IS_REAL_TRADING", False)
MOCK_CONTINUOUS = _env_bool("MOCK_CONTINUOUS", True)
ALLOW_LIVE_TRADING = _env_bool("ALLOW_LIVE_TRADING", False)
AUTO_MOCK_ON_MISSING_KIS = _env_bool("AUTO_MOCK_ON_MISSING_KIS", True)


# [B] KIS
KIS_APP_KEY = os.getenv("KIS_APP_KEY", "여기에_APP_KEY")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "여기에_APP_SECRET")
ACCOUNT_NO = os.getenv("ACCOUNT_NO", "여기에_계좌번호_앞8자리")
ACCOUNT_CODE = os.getenv("ACCOUNT_CODE", "01")
KIS_CREDENTIALS_CONFIGURED = all(
    _has_real_value(value)
    for value in (KIS_APP_KEY, KIS_APP_SECRET, ACCOUNT_NO)
)
MOCK_MODE = EXPLICIT_MOCK_MODE or (AUTO_MOCK_ON_MISSING_KIS and not KIS_CREDENTIALS_CONFIGURED)
MOCK_MODE_REASON = (
    "explicit_mock_mode"
    if EXPLICIT_MOCK_MODE
    else "missing_kis_credentials"
    if not KIS_CREDENTIALS_CONFIGURED
    else "paper_or_live_mode"
)

OPERATING_STAGES = ("mock", "paper", "shadow", "live_limited", "live_full")
DEFAULT_OPERATING_STAGE = (
    "mock"
    if MOCK_MODE
    else "live_limited"
    if ALLOW_LIVE_TRADING
    else "paper"
)
OPERATING_STAGE = _env_choice(
    "ALPHA_GEN_STAGE",
    DEFAULT_OPERATING_STAGE,
    set(OPERATING_STAGES),
)
if MOCK_MODE:
    OPERATING_STAGE = "mock"

AUTO_ORDER_ENABLED = OPERATING_STAGE in {"paper", "live_limited", "live_full"}
SHADOW_MODE = OPERATING_STAGE == "shadow"
LIVE_TRADING_STAGE = OPERATING_STAGE in {"live_limited", "live_full"}
EMERGENCY_STOP = _env_bool("EMERGENCY_STOP", False)
QUOTE_STALENESS_SEC = _env_int("QUOTE_STALENESS_SEC", 120)
SIGNAL_STALENESS_SEC = _env_int("SIGNAL_STALENESS_SEC", 900)
LIVE_MAX_ORDERS_PER_CYCLE = _env_int("LIVE_MAX_ORDERS_PER_CYCLE", 2)
LIVE_MAX_ORDERS_PER_DAY = _env_int("LIVE_MAX_ORDERS_PER_DAY", 6)
MAX_CONSECUTIVE_LOSSES = _env_int("MAX_CONSECUTIVE_LOSSES", 3)
MAX_DAILY_LOSS_PCT = _env_float("MAX_DAILY_LOSS_PCT", 0.02)
ENABLE_AUTO_LIQUIDATION = _env_bool("ENABLE_AUTO_LIQUIDATION", True)
BROKER_SYNC_INTERVAL_SEC = _env_int("BROKER_SYNC_INTERVAL_SEC", 60)
KIS_TOKEN_COOLDOWN_SEC = _env_int("KIS_TOKEN_COOLDOWN_SEC", 300)

KIS_URL = (
    "https://openapi.koreainvestment.com:9443"
    if IS_REAL_TRADING
    else "https://openapivts.koreainvestment.com:29443"
)


# [C] Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "여기에_Claude_API_키")
_CLAUDE_MODEL_RAW = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
_DEPRECATED_CLAUDE_MODELS = {
    "claude-3-5-haiku-20241022": "claude-haiku-4-5-20251001",
    "claude-3-5-sonnet-20241022": "claude-sonnet-4-20250514",
}
CLAUDE_MODEL = _DEPRECATED_CLAUDE_MODELS.get(_CLAUDE_MODEL_RAW, _CLAUDE_MODEL_RAW)
CLAUDE_MODEL_DEPRECATED = _CLAUDE_MODEL_RAW in _DEPRECATED_CLAUDE_MODELS
CLAUDE_CREDENTIALS_CONFIGURED = _has_real_value(ANTHROPIC_API_KEY)


# [D] Stocks
KR_STOCKS = {
    "005930": {
        "name": "삼성전자",
        "keywords": ["Samsung", "Samsung Semiconductor", "삼성"],
    },
    "000660": {
        "name": "SK하이닉스",
        "keywords": ["SK Hynix", "HBM", "반도체"],
    },
    "005380": {
        "name": "현대차",
        "keywords": ["Hyundai", "HMG AI", "현대"],
    },
}

US_STOCKS = {
    "TSLA": {
        "name": "Tesla",
        "exchange": "NASD",
        "keywords": ["Elon Musk", "Tesla", "EV"],
    },
    "SPCE": {
        "name": "Virgin Galactic",
        "exchange": "NYSE",
        "keywords": ["Space", "SpaceX", "Rocket"],
    },
    "NVDA": {
        "name": "Nvidia",
        "exchange": "NASD",
        "keywords": ["Nvidia", "AI chip", "GPU"],
    },
    "PLTR": {
        "name": "Palantir",
        "exchange": "NYSE",
        "keywords": ["Palantir", "AI", "Defense"],
    },
}

ENABLE_KIS_US_ORDERS = _env_bool("ENABLE_KIS_US_ORDERS", False)


# [E] News sentiment
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
    "TSLA": ["Elon Musk", "Tesla stock"],
    "SPCE": ["SpaceX"],
    "NVDA": ["Nvidia AI chip"],
    "PLTR": ["Palantir defense AI"],
}

NEWS_FETCH_INTERVAL_MIN = _env_int("NEWS_FETCH_INTERVAL_MIN", 60)
NEWS_MAX_PER_TOPIC = _env_int("NEWS_MAX_PER_TOPIC", 5)
SENTIMENT_BUY_THRESHOLD = _env_int("SENTIMENT_BUY_THRESHOLD", 1)
CLAUDE_BATCH_SENTIMENT = _env_bool("CLAUDE_BATCH_SENTIMENT", True)


# [F] Technical indicators
RSI_PERIOD = _env_int("RSI_PERIOD", 14)
RSI_OVERBOUGHT = _env_int("RSI_OVERBOUGHT", 70)
MA_SHORT = _env_int("MA_SHORT", 5)
MA_LONG = _env_int("MA_LONG", 20)
K_VALUE = _env_float("K_VALUE", 0.5)
ENABLE_VOLATILITY_BREAKOUT = _env_bool("ENABLE_VOLATILITY_BREAKOUT", True)


# [G] Risk
TOTAL_CAPITAL = _env_int("TOTAL_CAPITAL", 10_000_000)
MAX_POSITION_PCT = _env_float("MAX_POSITION_PCT", 0.06)
STOP_LOSS_PCT = _env_float("STOP_LOSS_PCT", 0.04)
MAX_DRAWDOWN_PCT = _env_float("MAX_DRAWDOWN_PCT", 0.15)

CONFIDENCE_SIZING = {
    2: 1.00,
    1: 0.60,
    0: 0.00,
    -1: 0.00,
    -2: 0.00,
}


# [H] Market hours
KR_MARKET_OPEN = os.getenv("KR_MARKET_OPEN", "09:00")
KR_MARKET_CLOSE = os.getenv("KR_MARKET_CLOSE", "15:30")
KR_BUY_START = os.getenv("KR_BUY_START", "09:05")
KR_SELL_TIME = os.getenv("KR_SELL_TIME", "15:15")
US_MARKET_OPEN = os.getenv("US_MARKET_OPEN", "22:30")
US_MARKET_CLOSE = os.getenv("US_MARKET_CLOSE", "05:00")


# [I] Telegram
TELEGRAM_ENABLED = _env_bool("TELEGRAM_ENABLED", False)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "여기에_봇_토큰")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "여기에_채팅_ID")


# [J] Mock seed
MOCK_INITIAL_CASH = _env_int("MOCK_INITIAL_CASH", 10_000_000)
MOCK_SEED_PRICES = {
    "005930": 75_000,
    "000660": 180_000,
    "005380": 240_000,
    "TSLA": 390_000,
    "SPCE": 4_000,
    "NVDA": 1_500_000,
    "PLTR": 105_000,
}


# [K] Product/runtime
WEB_HOST = os.getenv("ALPHA_GEN_HOST", "127.0.0.1")
WEB_PORT = _env_int("ALPHA_GEN_PORT", 8000)
AGENT_INTERVAL_SEC = _env_int("AGENT_INTERVAL_SEC", 60)
SETUP_TIMEOUT_SEC = _env_int("SETUP_TIMEOUT_SEC", 10)
