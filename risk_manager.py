"""
risk_manager.py — 자금 관리 및 리스크 제어 모듈

[규칙]
  - 종목당 최대: 총자산의 6% (Claude 신뢰도로 조절)
  - 개별 손절: -4% 도달 시 즉시 매도
  - 드로우다운: -15% 도달 시 휴면 모드
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
import config

KST = ZoneInfo("Asia/Seoul")

# ──────────────────────────────────────────────
# 전역 상태
# ──────────────────────────────────────────────
SLEEP_MODE: bool = False
SLEEP_REASON: str = ""
INITIAL_CAPITAL: int = config.TOTAL_CAPITAL


# ──────────────────────────────────────────────
# 포지션 사이징
# ──────────────────────────────────────────────

def get_position_size(total_asset: int, sentiment_score: int, current_price: int) -> int:
    """
    Claude 감성 점수에 따라 종목당 투자 금액 결정.

    Returns:
        매수 주식 수량 (정수)
    """
    confidence_ratio = config.CONFIDENCE_SIZING.get(sentiment_score, 0.0)
    if confidence_ratio == 0.0 or total_asset <= 0 or current_price <= 0:
        return 0

    max_amount = int(total_asset * config.MAX_POSITION_PCT * confidence_ratio)
    qty = max(0, max_amount // current_price)
    return qty


def get_max_buy_amount(total_asset: int, sentiment_score: int) -> int:
    """종목당 최대 매수 금액 (원)"""
    ratio = config.CONFIDENCE_SIZING.get(sentiment_score, 0.0)
    return int(total_asset * config.MAX_POSITION_PCT * ratio)


# ──────────────────────────────────────────────
# 손절 체크
# ──────────────────────────────────────────────

def check_stop_loss(holdings: list[dict]) -> list[dict]:
    """
    개별 종목 손절 대상 반환.

    Args:
        holdings: [{"code":, "name":, "qty":, "avg_price":, "eval_price":}, ...]

    Returns:
        손절 대상 종목 리스트 (loss_pct 포함)
    """
    to_sell = []
    for h in holdings:
        avg = h.get("avg_price", 0)
        cur = h.get("eval_price", avg)
        if avg <= 0:
            continue
        loss_pct = (cur - avg) / avg * 100
        if loss_pct <= -config.STOP_LOSS_PCT * 100:
            to_sell.append({**h, "loss_pct": round(loss_pct, 2)})
    return to_sell


# ──────────────────────────────────────────────
# 드로우다운 체크
# ──────────────────────────────────────────────

def check_max_drawdown(current_total_asset: int) -> bool:
    """
    전체 드로우다운이 한계(-15%)를 초과하면 True.
    초과 시 SLEEP_MODE를 활성화.
    """
    global SLEEP_MODE, SLEEP_REASON

    if INITIAL_CAPITAL <= 0:
        return False

    drawdown_pct = (current_total_asset - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100

    if drawdown_pct <= -config.MAX_DRAWDOWN_PCT * 100:
        SLEEP_MODE = True
        SLEEP_REASON = f"전체 드로우다운 {drawdown_pct:.2f}% (한계: -{config.MAX_DRAWDOWN_PCT*100:.0f}%)"
        return True
    return False


def get_drawdown_pct(current_total_asset: int) -> float:
    """현재 드로우다운 % 반환"""
    if INITIAL_CAPITAL <= 0:
        return 0.0
    return (current_total_asset - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100


def enter_sleep_mode(reason: str) -> None:
    """수동으로 휴면 모드 진입"""
    global SLEEP_MODE, SLEEP_REASON
    SLEEP_MODE = True
    SLEEP_REASON = reason


def exit_sleep_mode() -> None:
    """휴면 모드 해제 (수동 재시작)"""
    global SLEEP_MODE, SLEEP_REASON
    SLEEP_MODE = False
    SLEEP_REASON = ""


def set_initial_capital(amount: int) -> None:
    """초기 자본금 설정 (프로그램 시작 시 실제 잔고로 초기화)"""
    global INITIAL_CAPITAL
    INITIAL_CAPITAL = amount


# ──────────────────────────────────────────────
# 리스크 대시보드 요약
# ──────────────────────────────────────────────

def get_risk_summary(current_total_asset: int, holdings: list[dict]) -> dict:
    """대시보드용 리스크 현황 요약"""
    drawdown = get_drawdown_pct(current_total_asset)
    stop_targets = check_stop_loss(holdings)
    remaining_capital_ratio = current_total_asset / INITIAL_CAPITAL * 100 if INITIAL_CAPITAL else 100

    return {
        "sleep_mode": SLEEP_MODE,
        "sleep_reason": SLEEP_REASON,
        "initial_capital": INITIAL_CAPITAL,
        "current_total": current_total_asset,
        "drawdown_pct": round(drawdown, 2),
        "drawdown_limit_pct": -config.MAX_DRAWDOWN_PCT * 100,
        "remaining_capital_pct": round(remaining_capital_ratio, 2),
        "stop_loss_targets": stop_targets,
        "stop_loss_count": len(stop_targets),
        "max_position_pct": config.MAX_POSITION_PCT * 100,
        "stop_loss_pct": config.STOP_LOSS_PCT * 100,
    }
