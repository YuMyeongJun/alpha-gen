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
LIVE_MAX_ORDERS_PER_CYCLE = _env_int("LIVE_MAX_ORDERS_PER_CYCLE", 3)
LIVE_MAX_ORDERS_PER_DAY = _env_int("LIVE_MAX_ORDERS_PER_DAY", 10)
MAX_CONSECUTIVE_LOSSES = _env_int("MAX_CONSECUTIVE_LOSSES", 3)
MAX_DAILY_LOSS_PCT = _env_float("MAX_DAILY_LOSS_PCT", 0.02)
ENABLE_AUTO_LIQUIDATION = _env_bool("ENABLE_AUTO_LIQUIDATION", True)
BROKER_SYNC_INTERVAL_SEC = _env_int("BROKER_SYNC_INTERVAL_SEC", 60)
PAPER_BROKER_SYNC_INTERVAL_SEC = _env_int("PAPER_BROKER_SYNC_INTERVAL_SEC", 300)
KIS_TOKEN_COOLDOWN_SEC = _env_int("KIS_TOKEN_COOLDOWN_SEC", 300)
KIS_API_DEGRADED_COOLDOWN_SEC = _env_int("KIS_API_DEGRADED_COOLDOWN_SEC", 300)
KIS_API_MIN_INTERVAL_MS = _env_int("KIS_API_MIN_INTERVAL_MS", 250)
KIS_API_RETRY_COUNT = _env_int("KIS_API_RETRY_COUNT", 3)

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
    # ── 반도체 / 장비 ──────────────────────────────────────────────────────
    "005930": {"name": "삼성전자",       "keywords": ["Samsung", "Samsung Semiconductor", "삼성"]},
    "000660": {"name": "SK하이닉스",     "keywords": ["SK Hynix", "HBM", "반도체"]},
    "042700": {"name": "한미반도체",     "keywords": ["한미반도체", "HBM bonding", "TC Bonder"]},
    "000990": {"name": "DB하이텍",       "keywords": ["DB HiTek", "파운드리", "foundry Korea"]},
    # ── 2차전지 / 소재 ─────────────────────────────────────────────────────
    "006400": {"name": "삼성SDI",        "keywords": ["Samsung SDI", "배터리", "EV battery"]},
    "373220": {"name": "LG에너지솔루션", "keywords": ["LG Energy", "LGES", "배터리 셀"]},
    "247540": {"name": "에코프로비엠",   "keywords": ["에코프로", "EcoPro BM", "양극재", "cathode"]},
    "005490": {"name": "POSCO홀딩스",    "keywords": ["POSCO", "리튬", "lithium steel"]},
    # ── 바이오 / 헬스케어 ──────────────────────────────────────────────────
    "068270": {"name": "셀트리온",       "keywords": ["Celltrion", "바이오시밀러", "biosimilar"]},
    "207940": {"name": "삼성바이오로직스","keywords": ["Samsung Biologics", "CDMO", "바이오의약품"]},
    "128940": {"name": "한미약품",       "keywords": ["Hanmi Pharm", "한미약품", "oncology Korea"]},
    # ── IT / 플랫폼 ────────────────────────────────────────────────────────
    "035720": {"name": "카카오",         "keywords": ["Kakao", "카카오", "Korea platform"]},
    "035420": {"name": "네이버",         "keywords": ["Naver", "네이버", "Korea AI search"]},
    # ── 자동차 ─────────────────────────────────────────────────────────────
    "005380": {"name": "현대차",         "keywords": ["Hyundai", "HMG", "현대 EV"]},
    "000270": {"name": "기아",           "keywords": ["Kia", "기아", "EV autonomous"]},
}

US_STOCKS = {
    # ── AI / 빅테크 ────────────────────────────────────────────────────────
    "NVDA": {"name": "Nvidia",     "exchange": "NASD", "keywords": ["Nvidia", "AI chip", "GPU data center"]},
    "MSFT": {"name": "Microsoft",  "exchange": "NASD", "keywords": ["Microsoft", "Azure", "OpenAI", "Copilot"]},
    "GOOGL":{"name": "Alphabet",   "exchange": "NASD", "keywords": ["Google", "Alphabet", "Gemini AI"]},
    "META": {"name": "Meta",       "exchange": "NASD", "keywords": ["Meta", "Llama", "AI social"]},
    "AMD":  {"name": "AMD",        "exchange": "NASD", "keywords": ["AMD", "Ryzen", "Radeon AI GPU"]},
    "AAPL": {"name": "Apple",      "exchange": "NASD", "keywords": ["Apple", "iPhone", "Apple Intelligence"]},
    "AMZN": {"name": "Amazon",     "exchange": "NASD", "keywords": ["Amazon", "AWS", "AI cloud"]},
    # ── EV ─────────────────────────────────────────────────────────────────
    "TSLA": {"name": "Tesla",      "exchange": "NASD", "keywords": ["Elon Musk", "Tesla", "EV Autopilot"]},
    "RIVN": {"name": "Rivian",     "exchange": "NASD", "keywords": ["Rivian", "electric truck", "Amazon delivery van"]},
    # ── 방산 ───────────────────────────────────────────────────────────────
    "PLTR": {"name": "Palantir",   "exchange": "NYSE", "keywords": ["Palantir", "AI defense", "government AI"]},
    "LMT":  {"name": "Lockheed",   "exchange": "NYSE", "keywords": ["Lockheed Martin", "F-35", "defense contract"]},
    "RTX":  {"name": "RTX",        "exchange": "NYSE", "keywords": ["Raytheon", "RTX", "missile defense"]},
    "NOC":  {"name": "Northrop",   "exchange": "NYSE", "keywords": ["Northrop Grumman", "B-21", "space defense"]},
}

ENABLE_KIS_US_ORDERS = _env_bool("ENABLE_KIS_US_ORDERS", False)


# [E] News sentiment
NEWS_TOPICS = [
    # KR 반도체
    "Samsung Electronics semiconductor AI memory",
    "SK Hynix HBM Hanmi Semiconductor packaging",
    "DB HiTek Korea foundry non-memory",
    # KR 배터리/소재
    "Korea EV battery Samsung SDI LG Energy",
    "EcoPro POSCO cathode lithium battery materials",
    # KR 바이오
    "Korea biotech Celltrion Samsung Biologics biosimilar CDMO",
    "Hanmi Pharmaceutical oncology Korea drug",
    # KR IT/플랫폼
    "Kakao Naver Korea internet AI platform",
    # KR 자동차
    "Hyundai Kia HMG EV autonomous driving",
    # US AI/빅테크
    "Nvidia AI GPU data center chip",
    "Microsoft Azure OpenAI Copilot AI",
    "Google Alphabet Gemini AI search cloud",
    "Meta AI Llama social media VR",
    "AMD GPU CPU AI chip server",
    "Apple iPhone AI silicon hardware",
    "Amazon AWS cloud AI e-commerce",
    # US EV
    "Tesla EV Autopilot Elon Musk",
    "Rivian electric truck van fleet delivery",
    # US 방산
    "Palantir AI defense government contract",
    "US defense Lockheed Northrop Raytheon missile",
]

STOCK_TOPIC_MAP = {
    # KR
    "005930": ["Samsung Electronics semiconductor AI memory"],
    "000660": ["SK Hynix HBM Hanmi Semiconductor packaging"],
    "042700": ["SK Hynix HBM Hanmi Semiconductor packaging"],
    "000990": ["DB HiTek Korea foundry non-memory"],
    "006400": ["Korea EV battery Samsung SDI LG Energy"],
    "373220": ["Korea EV battery Samsung SDI LG Energy"],
    "247540": ["EcoPro POSCO cathode lithium battery materials"],
    "005490": ["EcoPro POSCO cathode lithium battery materials"],
    "068270": ["Korea biotech Celltrion Samsung Biologics biosimilar CDMO"],
    "207940": ["Korea biotech Celltrion Samsung Biologics biosimilar CDMO"],
    "128940": ["Hanmi Pharmaceutical oncology Korea drug"],
    "035720": ["Kakao Naver Korea internet AI platform"],
    "035420": ["Kakao Naver Korea internet AI platform"],
    "005380": ["Hyundai Kia HMG EV autonomous driving"],
    "000270": ["Hyundai Kia HMG EV autonomous driving"],
    # US
    "NVDA":  ["Nvidia AI GPU data center chip"],
    "MSFT":  ["Microsoft Azure OpenAI Copilot AI"],
    "GOOGL": ["Google Alphabet Gemini AI search cloud"],
    "META":  ["Meta AI Llama social media VR"],
    "AMD":   ["AMD GPU CPU AI chip server"],
    "AAPL":  ["Apple iPhone AI silicon hardware"],
    "AMZN":  ["Amazon AWS cloud AI e-commerce"],
    "TSLA":  ["Tesla EV Autopilot Elon Musk"],
    "RIVN":  ["Rivian electric truck van fleet delivery"],
    "PLTR":  ["Palantir AI defense government contract"],
    "LMT":   ["US defense Lockheed Northrop Raytheon missile"],
    "RTX":   ["US defense Lockheed Northrop Raytheon missile"],
    "NOC":   ["US defense Lockheed Northrop Raytheon missile"],
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
    # KR (단위: 원)
    "005930":  75_000,   # 삼성전자
    "000660": 200_000,   # SK하이닉스
    "042700":  65_000,   # 한미반도체
    "000990":  28_000,   # DB하이텍
    "006400": 230_000,   # 삼성SDI
    "373220": 310_000,   # LG에너지솔루션
    "247540": 190_000,   # 에코프로비엠
    "005490": 340_000,   # POSCO홀딩스
    "068270": 175_000,   # 셀트리온
    "207940": 850_000,   # 삼성바이오로직스
    "128940": 310_000,   # 한미약품
    "035720":  42_000,   # 카카오
    "035420": 215_000,   # 네이버
    "005380": 240_000,   # 현대차
    "000270":  90_000,   # 기아
    # US (단위: 원, 약 1USD = 1,350원 기준)
    "NVDA": 1_620_000,   # ~$1,200
    "MSFT":   567_000,   # ~$420
    "GOOGL":  236_000,   # ~$175
    "META":   783_000,   # ~$580
    "AMD":    142_000,   # ~$105
    "AAPL":   284_000,   # ~$210
    "AMZN":   263_000,   # ~$195
    "TSLA":   390_000,   # ~$289
    "RIVN":    16_000,   # ~$12
    "PLTR":   105_000,   # ~$78
    "LMT":    641_000,   # ~$475
    "RTX":    169_000,   # ~$125
    "NOC":    716_000,   # ~$530
}


# [K] Product/runtime
WEB_HOST = os.getenv("ALPHA_GEN_HOST", "127.0.0.1")
WEB_PORT = _env_int("ALPHA_GEN_PORT", 8000)
AGENT_INTERVAL_SEC = _env_int("AGENT_INTERVAL_SEC", 60)
SETUP_TIMEOUT_SEC = _env_int("SETUP_TIMEOUT_SEC", 10)
