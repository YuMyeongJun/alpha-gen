"""
agent_logging.py — alpha-gen 표준 로깅 설정
콘솔 + RotatingFileHandler (logs/alpha_gen.log)
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "alpha_gen.log")
_LOGGER_NAME = "alpha_gen"

_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "BUY": logging.INFO,
    "SELL": logging.INFO,
    "MONEY": logging.INFO,
    "AI": logging.INFO,
    "NEWS": logging.INFO,
    "RISK": logging.WARNING,
    "SLEEP": logging.WARNING,
    "KR": logging.INFO,
    "US": logging.INFO,
}


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """루트 alpha_gen 로거 초기화 (중복 핸들러 방지)"""
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    return logger


def get_logger() -> logging.Logger:
    return setup_logging()


def log_agent(msg: str, level: str = "INFO", mock: bool = False) -> None:
    """main.py 호환 로그 (아이콘 + MOCK 태그 유지)"""
    icons = {
        "INFO": "ℹ️ ",
        "BUY": "🟢",
        "SELL": "🔴",
        "WARN": "⚠️ ",
        "ERROR": "❌",
        "MONEY": "💰",
        "AI": "🤖",
        "NEWS": "📰",
        "RISK": "🛡️",
        "SLEEP": "😴",
        "KR": "🇰🇷",
        "US": "🇺🇸",
    }
    icon = icons.get(level, "▶")
    mode_tag = "[MOCK] " if mock else ""
    text = f"{icon} [{level}] {mode_tag}{msg}"
    logger = get_logger()
    logger.log(_LEVEL_MAP.get(level, logging.INFO), text)
