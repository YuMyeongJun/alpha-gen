"""
technical.py — 기술적 지표 계산 모듈
RSI, 이동평균선, 변동성 돌파 목표가
"""

import random
from typing import Optional
import pandas as pd
import config

try:
    import pandas_ta_classic as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False


# ──────────────────────────────────────────────
# 핵심 지표 계산 함수
# ──────────────────────────────────────────────

def calc_rsi(prices: list[float], period: int = 14) -> Optional[float]:
    """RSI(Relative Strength Index) 계산"""
    if len(prices) < period + 1:
        return None

    if HAS_PANDAS_TA:
        try:
            s = pd.Series(prices)
            rsi_series = ta.rsi(close=s, length=period)
            if rsi_series is not None and not rsi_series.empty:
                val = rsi_series.iloc[-1]
                if not pd.isna(val):
                    return round(float(val), 2)
        except Exception as e:
            print(f"[WARN] pandas_ta RSI 계산 오류: {e} → 수동 폴백 실행")

    # 수동 계산 Fallback
    gains, losses = [], []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calc_ma(prices: list[float], period: int) -> Optional[float]:
    """단순 이동평균(SMA) 계산"""
    if len(prices) < period:
        return None

    if HAS_PANDAS_TA:
        try:
            s = pd.Series(prices)
            ma_series = ta.sma(close=s, length=period)
            if ma_series is not None and not ma_series.empty:
                val = ma_series.iloc[-1]
                if not pd.isna(val):
                    return round(float(val), 2)
        except Exception as e:
            print(f"[WARN] pandas_ta MA 계산 오류: {e} → 수동 폴백 실행")

    # 수동 계산 Fallback
    return round(sum(prices[-period:]) / period, 2)


def calc_volatility_target(open_price: int, prev_high: int, prev_low: int) -> int:
    """변동성 돌파 목표가: 시가 + (전일 고가 - 전일 저가) × K"""
    return int(open_price + (prev_high - prev_low) * config.K_VALUE)


# ──────────────────────────────────────────────
# Mock 가격 히스토리 생성
# ──────────────────────────────────────────────

def generate_mock_price_history(stock_code: str, n: int = 30) -> list[float]:
    """Mock: 랜덤워크 기반 과거 가격 시뮬레이션"""
    base = config.MOCK_SEED_PRICES.get(stock_code, 50_000)
    prices = [float(base)]
    for _ in range(n - 1):
        change = random.uniform(-0.015, 0.015)
        prices.append(max(1000.0, prices[-1] * (1 + change)))
    return prices


# ──────────────────────────────────────────────
# 종합 매수 신호 판단
# ──────────────────────────────────────────────

def get_technical_signal(stock_code: str, price_history: Optional[list[float]] = None) -> dict:
    """
    RSI + 이동평균 기반 기술적 매수 신호 판단.

    Returns:
        {
          "rsi": float,
          "ma5": float,
          "ma20": float,
          "current_price": float,
          "signal": bool,          # True = 기술적 매수 가능
          "reason": str,
        }
    """
    if price_history is None:
        price_history = generate_mock_price_history(stock_code, n=30)

    current = price_history[-1]
    rsi   = calc_rsi(price_history, config.RSI_PERIOD)
    ma5   = calc_ma(price_history, config.MA_SHORT)
    ma20  = calc_ma(price_history, config.MA_LONG)

    reasons = []
    signal = True

    # RSI 과매수 체크
    if rsi is not None:
        if rsi > config.RSI_OVERBOUGHT:
            signal = False
            reasons.append(f"RSI 과매수({rsi:.1f}>{config.RSI_OVERBOUGHT})")
        else:
            reasons.append(f"RSI 정상({rsi:.1f})")
    else:
        reasons.append("RSI 계산 불가(데이터 부족)")

    # 이동평균 상향 배열 체크
    if ma5 and ma20:
        if current >= ma20:
            reasons.append(f"MA 상향배열(현재{current:,.0f}≥MA20:{ma20:,.0f})")
        else:
            signal = False
            reasons.append(f"MA 하향배열(현재{current:,.0f}<MA20:{ma20:,.0f})")
    else:
        reasons.append("MA 계산 불가(데이터 부족)")

    return {
        "rsi": rsi,
        "ma5": ma5,
        "ma20": ma20,
        "current_price": current,
        "signal": signal,
        "reason": " | ".join(reasons),
    }


def get_volatility_target_from_history(
    stock_code: str,
    price_history: Optional[list[float]] = None,
    open_price: Optional[int] = None,
) -> dict:
    """변동성 돌파 목표가 계산 (히스토리 기반)"""
    if price_history is None:
        price_history = generate_mock_price_history(stock_code, n=30)

    # 전일 고저 = 직전 N개 중 최고/최저
    prev_slice = price_history[-15:-1]
    prev_high = int(max(prev_slice)) if prev_slice else int(price_history[-1] * 1.02)
    prev_low  = int(min(prev_slice)) if prev_slice else int(price_history[-1] * 0.98)
    op = open_price or int(price_history[-1])
    target = calc_volatility_target(op, prev_high, prev_low)

    return {
        "target_price": target,
        "open_price":   op,
        "prev_high":    prev_high,
        "prev_low":     prev_low,
        "volatility":   prev_high - prev_low,
    }


def evaluate_buy_technicals(
    stock_code: str,
    price_history: list[float],
    quote: dict,
    prev_day: Optional[dict] = None,
) -> dict:
    """
    RSI/MA + (선택) 변동성 돌파 종합 기술 매수 판단.

    quote: get_price() 결과 (current_price, open_price 등)
    prev_day: get_prev_day() 결과 (prev_high, prev_low) — 있으면 실전 전일 고저 사용
    """
    tech = get_technical_signal(stock_code, price_history)
    signal = tech["signal"]
    reasons = [tech["reason"]]
    vol_info: Optional[dict] = None

    if not getattr(config, "ENABLE_VOLATILITY_BREAKOUT", True):
        return {**tech, "volatility": None}

    current = int(quote.get("current_price", price_history[-1]))
    open_p = int(quote.get("open_price", price_history[-1]))

    if prev_day:
        prev_high = int(prev_day["prev_high"])
        prev_low = int(prev_day["prev_low"])
    else:
        vol_info = get_volatility_target_from_history(
            stock_code, price_history, open_price=open_p
        )
        prev_high = vol_info["prev_high"]
        prev_low = vol_info["prev_low"]

    target = calc_volatility_target(open_p, prev_high, prev_low)
    vol_info = {
        "target_price": target,
        "open_price": open_p,
        "prev_high": prev_high,
        "prev_low": prev_low,
        "current_price": current,
        "breakout": current >= target,
    }

    if current >= target:
        reasons.append(f"변동성 돌파(현재{current:,}≥목표{target:,})")
    else:
        signal = False
        reasons.append(f"변동성 미돌파(현재{current:,}<목표{target:,})")

    return {
        **tech,
        "signal": signal,
        "reason": " | ".join(reasons),
        "volatility": vol_info,
    }
