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
    # ── 반도체 / 메모리 ────────────────────────────────────────────────────
    "005930": {"name": "삼성전자",        "keywords": ["Samsung", "Samsung Semiconductor", "HBM", "삼성"]},
    "000660": {"name": "SK하이닉스",      "keywords": ["SK Hynix", "HBM", "반도체"]},
    "042700": {"name": "한미반도체",      "keywords": ["한미반도체", "HBM bonding", "TC Bonder"]},
    "000990": {"name": "DB하이텍",        "keywords": ["DB HiTek", "파운드리", "foundry Korea"]},
    "009150": {"name": "삼성전기",        "keywords": ["Samsung Electro-Mechanics", "MLCC", "반도체부품"]},
    "034730": {"name": "SK스퀘어",        "keywords": ["SK Square", "SK하이닉스", "반도체 지주"]},
    # ── 2차전지 / 소재 ─────────────────────────────────────────────────────
    "006400": {"name": "삼성SDI",         "keywords": ["Samsung SDI", "배터리", "EV battery"]},
    "373220": {"name": "LG에너지솔루션",  "keywords": ["LG Energy", "LGES", "배터리 셀"]},
    "247540": {"name": "에코프로비엠",    "keywords": ["에코프로", "EcoPro BM", "양극재", "cathode"]},
    "005490": {"name": "POSCO홀딩스",     "keywords": ["POSCO", "리튬", "lithium steel"]},
    "086520": {"name": "에코프로",        "keywords": ["에코프로", "EcoPro", "배터리소재", "KOSDAQ"]},
    # ── 바이오 / 제약 ──────────────────────────────────────────────────────
    "068270": {"name": "셀트리온",        "keywords": ["Celltrion", "바이오시밀러", "biosimilar"]},
    "207940": {"name": "삼성바이오로직스", "keywords": ["Samsung Biologics", "CDMO", "바이오의약품"]},
    "128940": {"name": "한미약품",        "keywords": ["Hanmi Pharm", "한미약품", "oncology Korea"]},
    "000100": {"name": "유한양행",        "keywords": ["Yuhan", "유한양행", "항암제", "pharma"]},
    "196170": {"name": "알테오젠",        "keywords": ["Alteogen", "알테오젠", "ADC", "biotech KOSDAQ"]},
    # ── IT / 플랫폼 / 통신 ────────────────────────────────────────────────
    "035720": {"name": "카카오",          "keywords": ["Kakao", "카카오", "Korea platform"]},
    "035420": {"name": "네이버",          "keywords": ["Naver", "네이버", "Korea AI search"]},
    "066570": {"name": "LG전자",          "keywords": ["LG Electronics", "LG전자", "가전", "스마트폰"]},
    "030200": {"name": "KT",              "keywords": ["KT Corp", "KT", "5G", "통신"]},
    "017670": {"name": "SK텔레콤",        "keywords": ["SK Telecom", "SKT", "5G", "통신"]},
    # ── 자동차 / 모빌리티 ─────────────────────────────────────────────────
    "005380": {"name": "현대차",          "keywords": ["Hyundai", "HMG", "현대 EV"]},
    "000270": {"name": "기아",            "keywords": ["Kia", "기아", "EV autonomous"]},
    # ── 에너지 / 화학 ──────────────────────────────────────────────────────
    "051910": {"name": "LG화학",          "keywords": ["LG Chem", "LG화학", "battery material", "화학"]},
    "096770": {"name": "SK이노베이션",    "keywords": ["SK Innovation", "SK배터리", "석유화학"]},
    "010950": {"name": "S-Oil",           "keywords": ["S-Oil", "에쓰오일", "정유", "refinery"]},
    "009830": {"name": "한화솔루션",      "keywords": ["Hanwha Solutions", "한화솔루션", "태양광", "solar"]},
    "011170": {"name": "롯데케미칼",      "keywords": ["Lotte Chemical", "롯데케미칼", "석유화학"]},
    "010130": {"name": "고려아연",        "keywords": ["Korea Zinc", "고려아연", "아연", "배터리소재"]},
    # ── 엔터 / 게임 / 콘텐츠 ─────────────────────────────────────────────
    "041510": {"name": "에스엠",          "keywords": ["SM Entertainment", "에스엠", "K-pop", "아이돌"]},
    "035900": {"name": "JYP엔터",         "keywords": ["JYP Entertainment", "K-pop", "JYP"]},
    "352820": {"name": "하이브",          "keywords": ["HYBE", "하이브", "BTS", "K-pop"]},
    "036570": {"name": "엔씨소프트",      "keywords": ["NCsoft", "엔씨소프트", "MMORPG", "Lineage"]},
    "259960": {"name": "크래프톤",        "keywords": ["Krafton", "크래프톤", "PUBG", "게임"]},
    "251270": {"name": "넷마블",          "keywords": ["Netmarble", "넷마블", "모바일게임"]},
    # ── KOSDAQ 성장 (핀테크 / 로봇 / 소재) ───────────────────────────────
    "323410": {"name": "카카오뱅크",      "keywords": ["Kakao Bank", "카카오뱅크", "인터넷은행", "핀테크"]},
    "377300": {"name": "카카오페이",      "keywords": ["Kakao Pay", "카카오페이", "간편결제", "fintech"]},
    "277810": {"name": "레인보우로보틱스","keywords": ["Rainbow Robotics", "레인보우로보틱스", "로봇"]},
    "357780": {"name": "솔브레인",        "keywords": ["Soulbrain", "솔브레인", "반도체소재", "식각액"]},
}

US_STOCKS = {
    # ── AI / 반도체 ────────────────────────────────────────────────────────
    "NVDA": {"name": "Nvidia",     "exchange": "NASD", "keywords": ["Nvidia", "AI chip", "GPU data center", "Blackwell"]},
    "AMD":  {"name": "AMD",        "exchange": "NASD", "keywords": ["AMD", "Ryzen", "Radeon AI GPU"]},
    "QCOM": {"name": "Qualcomm",   "exchange": "NASD", "keywords": ["Qualcomm", "Snapdragon", "mobile chip AI"]},
    "ARM":  {"name": "Arm",        "exchange": "NASD", "keywords": ["Arm Holdings", "ARM chip", "architecture royalty"]},
    "MU":   {"name": "Micron",     "exchange": "NASD", "keywords": ["Micron", "DRAM", "HBM memory"]},
    "TSM":  {"name": "TSMC",       "exchange": "NYSE", "keywords": ["TSMC", "Taiwan Semiconductor", "foundry fab"]},
    # ── 빅테크 ─────────────────────────────────────────────────────────────
    "MSFT": {"name": "Microsoft",  "exchange": "NASD", "keywords": ["Microsoft", "Azure", "OpenAI", "Copilot"]},
    "GOOGL":{"name": "Alphabet",   "exchange": "NASD", "keywords": ["Google", "Alphabet", "Gemini AI"]},
    "META": {"name": "Meta",       "exchange": "NASD", "keywords": ["Meta", "Llama", "AI social"]},
    "AAPL": {"name": "Apple",      "exchange": "NASD", "keywords": ["Apple", "iPhone", "Apple Intelligence"]},
    "AMZN": {"name": "Amazon",     "exchange": "NASD", "keywords": ["Amazon", "AWS", "AI cloud"]},
    "NFLX": {"name": "Netflix",    "exchange": "NASD", "keywords": ["Netflix", "streaming", "content subscription"]},
    "CRM":  {"name": "Salesforce", "exchange": "NYSE", "keywords": ["Salesforce", "CRM", "enterprise AI cloud"]},
    "ORCL": {"name": "Oracle",     "exchange": "NYSE", "keywords": ["Oracle", "cloud database", "enterprise"]},
    "SNOW": {"name": "Snowflake",  "exchange": "NYSE", "keywords": ["Snowflake", "data cloud", "AI analytics"]},
    # ── EV / 자율주행 ──────────────────────────────────────────────────────
    "TSLA": {"name": "Tesla",      "exchange": "NASD", "keywords": ["Elon Musk", "Tesla", "EV Autopilot"]},
    "RIVN": {"name": "Rivian",     "exchange": "NASD", "keywords": ["Rivian", "electric truck", "Amazon delivery van"]},
    # ── 방산 / 항공우주 ────────────────────────────────────────────────────
    "PLTR": {"name": "Palantir",   "exchange": "NYSE", "keywords": ["Palantir", "AI defense", "government AI"]},
    "LMT":  {"name": "Lockheed",   "exchange": "NYSE", "keywords": ["Lockheed Martin", "F-35", "defense contract"]},
    "RTX":  {"name": "RTX",        "exchange": "NYSE", "keywords": ["Raytheon", "RTX", "missile defense"]},
    "NOC":  {"name": "Northrop",   "exchange": "NYSE", "keywords": ["Northrop Grumman", "B-21", "space defense"]},
    # ── 헬스케어 / 바이오 ──────────────────────────────────────────────────
    "LLY":  {"name": "Eli Lilly",  "exchange": "NYSE", "keywords": ["Eli Lilly", "GLP-1", "Mounjaro", "obesity drug"]},
    "ABBV": {"name": "AbbVie",     "exchange": "NYSE", "keywords": ["AbbVie", "Humira", "immunology oncology"]},
    "MRK":  {"name": "Merck",      "exchange": "NYSE", "keywords": ["Merck", "Keytruda", "oncology"]},
    "JNJ":  {"name": "J&J",        "exchange": "NYSE", "keywords": ["Johnson Johnson", "medtech pharma"]},
    "PFE":  {"name": "Pfizer",     "exchange": "NYSE", "keywords": ["Pfizer", "vaccine oncology", "pharma"]},
    "MRNA": {"name": "Moderna",    "exchange": "NASD", "keywords": ["Moderna", "mRNA", "vaccine biotech"]},
    "BMY":  {"name": "Bristol-Myers","exchange":"NYSE", "keywords": ["Bristol-Myers", "Opdivo", "oncology"]},
    "UNH":  {"name": "UnitedHealth","exchange":"NYSE",  "keywords": ["UnitedHealth", "managed care", "health insurance"]},
    "GILD": {"name": "Gilead",     "exchange": "NASD", "keywords": ["Gilead", "HIV antiviral", "oncology biotech"]},
    "ISRG": {"name": "Intuitive",  "exchange": "NASD", "keywords": ["Intuitive Surgical", "da Vinci", "robotic surgery"]},
    # ── 에너지 / 원자재 ────────────────────────────────────────────────────
    "XOM":  {"name": "ExxonMobil", "exchange": "NYSE", "keywords": ["ExxonMobil", "oil gas", "energy"]},
    "CVX":  {"name": "Chevron",    "exchange": "NYSE", "keywords": ["Chevron", "oil gas", "energy"]},
    "OXY":  {"name": "Occidental", "exchange": "NYSE", "keywords": ["Occidental", "OXY", "oil shale Buffett"]},
    "NEE":  {"name": "NextEra",    "exchange": "NYSE", "keywords": ["NextEra Energy", "renewable wind solar"]},
    "ENPH": {"name": "Enphase",    "exchange": "NASD", "keywords": ["Enphase Energy", "solar microinverter"]},
    "FSLR": {"name": "First Solar","exchange": "NASD", "keywords": ["First Solar", "solar panel thin film"]},
    "CCJ":  {"name": "Cameco",     "exchange": "NYSE", "keywords": ["Cameco", "uranium nuclear fuel"]},
}

ENABLE_KIS_US_ORDERS = _env_bool("ENABLE_KIS_US_ORDERS", False)


# [E] News sentiment
NEWS_TOPICS = [
    # ── KR 반도체 ──────────────────────────────────────────────────────────
    "Samsung Electronics HBM memory semiconductor AI chip",
    "SK Hynix HBM high bandwidth memory AI server",
    "Hanmi Semiconductor TC Bonder HBM packaging Korea",
    "DB HiTek Samsung Electro-Mechanics Korea foundry MLCC",
    "SK Square Korea semiconductor holding investment",
    # ── KR 2차전지 / 소재 ──────────────────────────────────────────────────
    "Korea EV battery Samsung SDI LG Energy cell",
    "EcoPro POSCO cathode lithium battery material Korea",
    "LG Chem SK Innovation Korea chemical battery material",
    "S-Oil Hanwha Korea Zinc energy chemical refinery",
    # ── KR 바이오 / 제약 ───────────────────────────────────────────────────
    "Celltrion Samsung Biologics biosimilar CDMO Korea",
    "Hanmi Yuhan Alteogen Korea pharma oncology biotech",
    # ── KR IT / 플랫폼 / 통신 ─────────────────────────────────────────────
    "Kakao Naver Korea internet AI platform search",
    "Kakao Bank Kakao Pay Korea fintech mobile payment",
    "LG Electronics KT SK Telecom Korea tech 5G consumer",
    # ── KR 자동차 ──────────────────────────────────────────────────────────
    "Hyundai Kia EV electric vehicle autonomous driving Korea",
    # ── KR 엔터 / 게임 ─────────────────────────────────────────────────────
    "SM JYP HYBE K-pop entertainment idol Korea music",
    "Krafton NCsoft Netmarble Korea game mobile PUBG",
    # ── KR KOSDAQ 성장 ─────────────────────────────────────────────────────
    "Soulbrain Rainbow Robotics Korea semiconductor material robot KOSDAQ",
    # ── US AI / 반도체 ─────────────────────────────────────────────────────
    "Nvidia AI GPU data center chip Blackwell accelerator",
    "AMD Radeon CPU AI chip server computing",
    "Qualcomm ARM chip mobile AI smartphone architecture",
    "Micron TSMC memory chip semiconductor manufacturing fab",
    # ── US 빅테크 ──────────────────────────────────────────────────────────
    "Microsoft Azure OpenAI Copilot AI cloud enterprise",
    "Google Alphabet Gemini AI search advertising cloud",
    "Meta AI Llama social media advertising",
    "Apple iPhone AI silicon consumer hardware",
    "Amazon AWS cloud AI e-commerce logistics",
    "Netflix Salesforce Oracle Snowflake streaming cloud software",
    # ── US EV ──────────────────────────────────────────────────────────────
    "Tesla EV Autopilot Elon Musk energy battery",
    "Rivian electric truck van fleet delivery EV",
    # ── US 방산 ────────────────────────────────────────────────────────────
    "Palantir Lockheed Raytheon Northrop AI defense missile aerospace",
    # ── US 헬스케어 / 바이오 ───────────────────────────────────────────────
    "Eli Lilly GLP-1 obesity diabetes drug blockbuster",
    "AbbVie Merck JNJ pharma oncology immunology drug",
    "Pfizer Moderna Bristol-Myers vaccine biotech mRNA oncology",
    "UnitedHealth Gilead Intuitive Surgical healthcare managed care",
    # ── US 에너지 / 원자재 ─────────────────────────────────────────────────
    "ExxonMobil Chevron Occidental oil gas energy",
    "NextEra Enphase First Solar Cameco clean energy nuclear renewable",
]

STOCK_TOPIC_MAP = {
    # ── KR 반도체 ──────────────────────────────────────────────────────────
    "005930": ["Samsung Electronics HBM memory semiconductor AI chip"],
    "000660": ["SK Hynix HBM high bandwidth memory AI server"],
    "042700": ["Hanmi Semiconductor TC Bonder HBM packaging Korea"],
    "000990": ["DB HiTek Samsung Electro-Mechanics Korea foundry MLCC"],
    "009150": ["DB HiTek Samsung Electro-Mechanics Korea foundry MLCC"],
    "034730": ["SK Square Korea semiconductor holding investment"],
    # ── KR 2차전지 / 소재 ──────────────────────────────────────────────────
    "006400": ["Korea EV battery Samsung SDI LG Energy cell"],
    "373220": ["Korea EV battery Samsung SDI LG Energy cell"],
    "247540": ["EcoPro POSCO cathode lithium battery material Korea"],
    "005490": ["EcoPro POSCO cathode lithium battery material Korea"],
    "086520": ["EcoPro POSCO cathode lithium battery material Korea"],
    "051910": ["LG Chem SK Innovation Korea chemical battery material"],
    "096770": ["LG Chem SK Innovation Korea chemical battery material"],
    "011170": ["LG Chem SK Innovation Korea chemical battery material"],
    "010950": ["S-Oil Hanwha Korea Zinc energy chemical refinery"],
    "009830": ["S-Oil Hanwha Korea Zinc energy chemical refinery"],
    "010130": ["S-Oil Hanwha Korea Zinc energy chemical refinery"],
    # ── KR 바이오 / 제약 ───────────────────────────────────────────────────
    "068270": ["Celltrion Samsung Biologics biosimilar CDMO Korea"],
    "207940": ["Celltrion Samsung Biologics biosimilar CDMO Korea"],
    "128940": ["Hanmi Yuhan Alteogen Korea pharma oncology biotech"],
    "000100": ["Hanmi Yuhan Alteogen Korea pharma oncology biotech"],
    "196170": ["Hanmi Yuhan Alteogen Korea pharma oncology biotech"],
    # ── KR IT / 플랫폼 / 통신 ─────────────────────────────────────────────
    "035720": ["Kakao Naver Korea internet AI platform search"],
    "035420": ["Kakao Naver Korea internet AI platform search"],
    "323410": ["Kakao Bank Kakao Pay Korea fintech mobile payment"],
    "377300": ["Kakao Bank Kakao Pay Korea fintech mobile payment"],
    "066570": ["LG Electronics KT SK Telecom Korea tech 5G consumer"],
    "030200": ["LG Electronics KT SK Telecom Korea tech 5G consumer"],
    "017670": ["LG Electronics KT SK Telecom Korea tech 5G consumer"],
    # ── KR 자동차 ──────────────────────────────────────────────────────────
    "005380": ["Hyundai Kia EV electric vehicle autonomous driving Korea"],
    "000270": ["Hyundai Kia EV electric vehicle autonomous driving Korea"],
    # ── KR 엔터 / 게임 ─────────────────────────────────────────────────────
    "041510": ["SM JYP HYBE K-pop entertainment idol Korea music"],
    "035900": ["SM JYP HYBE K-pop entertainment idol Korea music"],
    "352820": ["SM JYP HYBE K-pop entertainment idol Korea music"],
    "036570": ["Krafton NCsoft Netmarble Korea game mobile PUBG"],
    "259960": ["Krafton NCsoft Netmarble Korea game mobile PUBG"],
    "251270": ["Krafton NCsoft Netmarble Korea game mobile PUBG"],
    # ── KR KOSDAQ 성장 ─────────────────────────────────────────────────────
    "277810": ["Soulbrain Rainbow Robotics Korea semiconductor material robot KOSDAQ"],
    "357780": ["Soulbrain Rainbow Robotics Korea semiconductor material robot KOSDAQ"],
    # ── US AI / 반도체 ─────────────────────────────────────────────────────
    "NVDA":  ["Nvidia AI GPU data center chip Blackwell accelerator"],
    "AMD":   ["AMD Radeon CPU AI chip server computing"],
    "QCOM":  ["Qualcomm ARM chip mobile AI smartphone architecture"],
    "ARM":   ["Qualcomm ARM chip mobile AI smartphone architecture"],
    "MU":    ["Micron TSMC memory chip semiconductor manufacturing fab"],
    "TSM":   ["Micron TSMC memory chip semiconductor manufacturing fab"],
    # ── US 빅테크 ──────────────────────────────────────────────────────────
    "MSFT":  ["Microsoft Azure OpenAI Copilot AI cloud enterprise"],
    "GOOGL": ["Google Alphabet Gemini AI search advertising cloud"],
    "META":  ["Meta AI Llama social media advertising"],
    "AAPL":  ["Apple iPhone AI silicon consumer hardware"],
    "AMZN":  ["Amazon AWS cloud AI e-commerce logistics"],
    "NFLX":  ["Netflix Salesforce Oracle Snowflake streaming cloud software"],
    "CRM":   ["Netflix Salesforce Oracle Snowflake streaming cloud software"],
    "ORCL":  ["Netflix Salesforce Oracle Snowflake streaming cloud software"],
    "SNOW":  ["Netflix Salesforce Oracle Snowflake streaming cloud software"],
    # ── US EV ──────────────────────────────────────────────────────────────
    "TSLA":  ["Tesla EV Autopilot Elon Musk energy battery"],
    "RIVN":  ["Rivian electric truck van fleet delivery EV"],
    # ── US 방산 ────────────────────────────────────────────────────────────
    "PLTR":  ["Palantir Lockheed Raytheon Northrop AI defense missile aerospace"],
    "LMT":   ["Palantir Lockheed Raytheon Northrop AI defense missile aerospace"],
    "RTX":   ["Palantir Lockheed Raytheon Northrop AI defense missile aerospace"],
    "NOC":   ["Palantir Lockheed Raytheon Northrop AI defense missile aerospace"],
    # ── US 헬스케어 / 바이오 ───────────────────────────────────────────────
    "LLY":   ["Eli Lilly GLP-1 obesity diabetes drug blockbuster"],
    "ABBV":  ["AbbVie Merck JNJ pharma oncology immunology drug"],
    "MRK":   ["AbbVie Merck JNJ pharma oncology immunology drug"],
    "JNJ":   ["AbbVie Merck JNJ pharma oncology immunology drug"],
    "PFE":   ["Pfizer Moderna Bristol-Myers vaccine biotech mRNA oncology"],
    "MRNA":  ["Pfizer Moderna Bristol-Myers vaccine biotech mRNA oncology"],
    "BMY":   ["Pfizer Moderna Bristol-Myers vaccine biotech mRNA oncology"],
    "UNH":   ["UnitedHealth Gilead Intuitive Surgical healthcare managed care"],
    "GILD":  ["UnitedHealth Gilead Intuitive Surgical healthcare managed care"],
    "ISRG":  ["UnitedHealth Gilead Intuitive Surgical healthcare managed care"],
    # ── US 에너지 / 원자재 ─────────────────────────────────────────────────
    "XOM":   ["ExxonMobil Chevron Occidental oil gas energy"],
    "CVX":   ["ExxonMobil Chevron Occidental oil gas energy"],
    "OXY":   ["ExxonMobil Chevron Occidental oil gas energy"],
    "NEE":   ["NextEra Enphase First Solar Cameco clean energy nuclear renewable"],
    "ENPH":  ["NextEra Enphase First Solar Cameco clean energy nuclear renewable"],
    "FSLR":  ["NextEra Enphase First Solar Cameco clean energy nuclear renewable"],
    "CCJ":   ["NextEra Enphase First Solar Cameco clean energy nuclear renewable"],
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
    # ── KR (단위: 원) ──────────────────────────────────────────────────────
    # 반도체
    "005930":  75_000,   # 삼성전자
    "000660": 200_000,   # SK하이닉스
    "042700":  65_000,   # 한미반도체
    "000990":  28_000,   # DB하이텍
    "009150": 155_000,   # 삼성전기
    "034730":  60_000,   # SK스퀘어
    # 2차전지/소재
    "006400": 230_000,   # 삼성SDI
    "373220": 310_000,   # LG에너지솔루션
    "247540": 190_000,   # 에코프로비엠
    "005490": 340_000,   # POSCO홀딩스
    "086520":  80_000,   # 에코프로
    # 바이오/제약
    "068270": 175_000,   # 셀트리온
    "207940": 850_000,   # 삼성바이오로직스
    "128940": 310_000,   # 한미약품
    "000100":  80_000,   # 유한양행
    "196170": 250_000,   # 알테오젠
    # IT/플랫폼/통신
    "035720":  42_000,   # 카카오
    "035420": 215_000,   # 네이버
    "066570": 110_000,   # LG전자
    "030200":  45_000,   # KT
    "017670":  62_000,   # SK텔레콤
    # 자동차
    "005380": 240_000,   # 현대차
    "000270":  90_000,   # 기아
    # 에너지/화학
    "051910": 280_000,   # LG화학
    "096770": 120_000,   # SK이노베이션
    "010950":  90_000,   # S-Oil
    "009830":  40_000,   # 한화솔루션
    "011170":  80_000,   # 롯데케미칼
    "010130": 800_000,   # 고려아연
    # 엔터/게임
    "041510":  85_000,   # 에스엠
    "035900":  55_000,   # JYP엔터
    "352820": 200_000,   # 하이브
    "036570": 230_000,   # 엔씨소프트
    "259960": 280_000,   # 크래프톤
    "251270":  55_000,   # 넷마블
    # KOSDAQ 성장
    "323410":  30_000,   # 카카오뱅크
    "377300":  25_000,   # 카카오페이
    "277810": 100_000,   # 레인보우로보틱스
    "357780": 250_000,   # 솔브레인
    # ── US (단위: 원, 약 1USD = 1,350원 기준) ─────────────────────────────
    # AI/반도체
    "NVDA": 1_620_000,   # ~$1,200
    "AMD":    142_000,   # ~$105
    "QCOM":   216_000,   # ~$160
    "ARM":    162_000,   # ~$120
    "MU":     135_000,   # ~$100
    "TSM":    270_000,   # ~$200
    # 빅테크
    "MSFT":   567_000,   # ~$420
    "GOOGL":  236_000,   # ~$175
    "META":   783_000,   # ~$580
    "AAPL":   284_000,   # ~$210
    "AMZN":   263_000,   # ~$195
    "NFLX": 1_134_000,   # ~$840
    "CRM":    378_000,   # ~$280
    "ORCL":   243_000,   # ~$180
    "SNOW":   189_000,   # ~$140
    # EV
    "TSLA":   390_000,   # ~$289
    "RIVN":    16_000,   # ~$12
    # 방산
    "PLTR":   105_000,   # ~$78
    "LMT":    641_000,   # ~$475
    "RTX":    169_000,   # ~$125
    "NOC":    716_000,   # ~$530
    # 헬스케어/바이오
    "LLY":  1_080_000,   # ~$800
    "ABBV":   243_000,   # ~$180
    "MRK":    135_000,   # ~$100
    "JNJ":    209_000,   # ~$155
    "PFE":     40_000,   # ~$30
    "MRNA":   121_000,   # ~$90
    "BMY":     74_000,   # ~$55
    "UNH":    756_000,   # ~$560
    "GILD":   108_000,   # ~$80
    "ISRG":   756_000,   # ~$560
    # 에너지/원자재
    "XOM":    162_000,   # ~$120
    "CVX":    176_000,   # ~$130
    "OXY":     74_000,   # ~$55
    "NEE":     81_000,   # ~$60
    "ENPH":   108_000,   # ~$80
    "FSLR":   189_000,   # ~$140
    "CCJ":     74_000,   # ~$55
}


# [K] Product/runtime
WEB_HOST = os.getenv("ALPHA_GEN_HOST", "127.0.0.1")
WEB_PORT = _env_int("ALPHA_GEN_PORT", 8000)
AGENT_INTERVAL_SEC = _env_int("AGENT_INTERVAL_SEC", 60)
SETUP_TIMEOUT_SEC = _env_int("SETUP_TIMEOUT_SEC", 10)
