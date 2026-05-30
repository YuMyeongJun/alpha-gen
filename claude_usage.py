"""
claude_usage.py — Claude API 사용량 실시간 추적 및 비용 계산

[동작 방식]
- news_analyzer.py가 Claude를 호출할 때마다 record()를 호출
- 일별 누적 토큰/비용을 메모리에 보관 (서버 재시작 시 초기화)
- services.py의 사이클에서 일일 비용 vs P&L 을 비교해 텔레그램 알림 트리거
"""
from __future__ import annotations

import threading
from datetime import UTC, date, datetime
from typing import Any

# ── 모델별 가격 ($ / 1M tokens, 2025 기준) ────────────────────────────────────
_MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-5":            {"input": 15.0,  "output": 75.0},
    "claude-sonnet-4-5":          {"input": 3.0,   "output": 15.0},
    "claude-3-7-sonnet-20250219": {"input": 3.0,   "output": 15.0},
    "claude-3-5-sonnet-20241022": {"input": 3.0,   "output": 15.0},
    "claude-3-5-haiku-20241022":  {"input": 0.80,  "output": 4.0},
    "claude-3-haiku-20240307":    {"input": 0.25,  "output": 1.25},
    "claude-3-opus-20240229":     {"input": 15.0,  "output": 75.0},
    "claude-3-sonnet-20240229":   {"input": 3.0,   "output": 15.0},
}
_DEFAULT_PRICING: dict[str, float] = {"input": 3.0, "output": 15.0}

_lock = threading.Lock()

# 일별 누적 (date → stats)
_daily: dict[str, dict[str, Any]] = {}

# 서버 기동 이후 세션 누적
_session: dict[str, Any] = {
    "input_tokens": 0,
    "output_tokens": 0,
    "cost_usd": 0.0,
    "calls": 0,
    "started_at": datetime.now(UTC).isoformat(),
}


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _today() -> str:
    return date.today().isoformat()


def _calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = _MODEL_PRICING.get(model, _DEFAULT_PRICING)
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


# ── 공개 API ──────────────────────────────────────────────────────────────────

def record(model: str, input_tokens: int, output_tokens: int) -> float:
    """Claude API 호출 1건의 사용량을 기록한다. 해당 호출 비용(USD)을 반환."""
    cost = _calc_cost(model, input_tokens, output_tokens)
    today = _today()
    with _lock:
        day = _daily.setdefault(
            today,
            {"date": today, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0},
        )
        day["input_tokens"] += input_tokens
        day["output_tokens"] += output_tokens
        day["cost_usd"] = round(day["cost_usd"] + cost, 6)
        day["calls"] += 1

        _session["input_tokens"] += input_tokens
        _session["output_tokens"] += output_tokens
        _session["cost_usd"] = round(_session["cost_usd"] + cost, 6)
        _session["calls"] += 1
    return cost


def today_cost_usd() -> float:
    """오늘 발생한 Claude API 비용(USD)."""
    with _lock:
        return _daily.get(_today(), {}).get("cost_usd", 0.0)


def today_summary() -> dict[str, Any]:
    """오늘 사용 통계 딕셔너리."""
    with _lock:
        return dict(_daily.get(_today(), {"date": _today(), "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0}))


def session_summary() -> dict[str, Any]:
    """서버 기동 이후 누적 통계."""
    with _lock:
        return dict(_session)


def all_days() -> list[dict[str, Any]]:
    """날짜순 일별 통계 리스트."""
    with _lock:
        return sorted(_daily.values(), key=lambda d: d["date"])


def estimate_monthly_usd() -> float:
    """오늘 하루 비용으로 30일 추산한 월 예상 비용(USD)."""
    return round(today_cost_usd() * 30, 4)
