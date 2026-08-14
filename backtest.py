"""
backtest.py — 실데이터(yfinance) 워크포워드 백테스트

실행: python backtest.py

설계 (2026-08 리라이트):
  - 신호 판단은 진입일 이전 데이터(signal_window)만 사용 — 미래 데이터 참조 없음.
  - 진입 후 hold_days 영업일 동안 일별 저가로 손절선(STOP_LOSS_PCT) 도달 여부를 확인.
    도달하면 그 시점 손절 청산(status=stop_loss), 도달 못 하면 창 종료 시점 종가로
    평가(미실현, status=open_marked).
  - max_position_pct/stop_loss_pct를 인자로 넘기면 이 실행에서만 override됨 —
    config.MAX_POSITION_PCT/STOP_LOSS_PCT(실거래 리스크 상수)는 절대 건드리지 않는다.
    (리스크 상수 민감도 비교용. 실제 값 변경은 사람 승인 후 config/__init__.py에서만.)
  - 이전 버전은 랜덤 합성 가격(generate_mock_price_history) + 무조건 +2% 청산이었음 —
    실제 시장 데이터가 아니라 파라미터 튜닝 결과가 의미 없었다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

import pandas as pd

import config
import ohlcv
import technical

KST = ZoneInfo("Asia/Seoul")

HistoryProvider = Callable[[str, int], pd.DataFrame]


@dataclass
class BacktestTrade:
    code: str
    name: str
    entry_date: str
    exit_date: str
    buy_price: float
    sell_price: float
    qty: int
    pnl: float
    status: str  # "stop_loss" | "open_marked"
    reason: str


@dataclass
class BacktestResult:
    initial_cash: int
    final_cash: float
    trades: list[BacktestTrade] = field(default_factory=list)
    win_rate: float = 0.0
    total_return_pct: float = 0.0
    skipped: list[dict[str, str]] = field(default_factory=list)
    closed_count: int = 0
    open_count: int = 0


def _fetch_ohlc_history(code: str, total_days: int) -> pd.DataFrame:
    """실데이터 OHLC 히스토리 (yfinance). 실패/데이터부족 시 빈 DataFrame."""
    try:
        import yfinance as yf
    except ImportError:
        return pd.DataFrame()

    ticker = ohlcv._to_yf_ticker(code)
    calendar_days = int(total_days * 1.6) + 5  # 주말/휴장일 버퍼
    try:
        hist = yf.Ticker(ticker).history(period=f"{calendar_days}d", interval="1d")
    except Exception:
        return pd.DataFrame()
    if hist.empty:
        return pd.DataFrame()

    hist = hist.dropna(subset=["Open", "High", "Low", "Close"])
    return hist[["Open", "High", "Low", "Close"]].tail(total_days)


def run_backtest(
    stocks: dict | None = None,
    sentiment_scores: dict[str, int] | None = None,
    days: int = 30,
    initial_cash: int | None = None,
    hold_days: int = 10,
    max_position_pct: float | None = None,
    stop_loss_pct: float | None = None,
    history_provider: Optional[HistoryProvider] = None,
) -> BacktestResult:
    """
    실데이터 워크포워드 백테스트.
    sentiment_scores: {code: score} — score >= SENTIMENT_BUY_THRESHOLD 인 종목만 매수 시도.
    """
    stocks = stocks or {**config.KR_STOCKS, **config.US_STOCKS}
    cash: float = initial_cash or config.MOCK_INITIAL_CASH
    pos_pct = max_position_pct if max_position_pct is not None else config.MAX_POSITION_PCT
    sl_pct = stop_loss_pct if stop_loss_pct is not None else config.STOP_LOSS_PCT
    fetch = history_provider or _fetch_ohlc_history

    default_scores = {code: 2 for code in stocks}
    scores = {**default_scores, **(sentiment_scores or {})}

    trades: list[BacktestTrade] = []
    skipped: list[dict[str, str]] = []

    for code, info in stocks.items():
        score = scores.get(code, 0)
        if score < config.SENTIMENT_BUY_THRESHOLD:
            continue

        hist = fetch(code, days + hold_days)
        if hist is None or len(hist) < days + 2:
            skipped.append({"code": code, "name": info.get("name", code), "reason": "insufficient_price_data"})
            continue

        signal_window = hist.iloc[:-hold_days] if hold_days > 0 else hist
        forward_window = hist.iloc[-hold_days:] if hold_days > 0 else hist.iloc[-1:]
        if len(signal_window) < 2 or forward_window.empty:
            skipped.append({"code": code, "name": info.get("name", code), "reason": "insufficient_price_data"})
            continue

        price_history = signal_window["Close"].tolist()
        entry_row = forward_window.iloc[0]
        prev_row = signal_window.iloc[-1]
        quote = {"current_price": float(entry_row["Close"]), "open_price": float(entry_row["Open"])}
        prev_day = {"prev_high": float(prev_row["High"]), "prev_low": float(prev_row["Low"])}

        tech = technical.evaluate_buy_technicals(code, price_history, quote, prev_day=prev_day)
        if not tech["signal"]:
            continue

        buy_price = quote["current_price"]
        confidence_ratio = config.CONFIDENCE_SIZING.get(score, 0.0)
        qty = int(cash * pos_pct * confidence_ratio // buy_price) if buy_price > 0 else 0
        if qty <= 0:
            continue
        cost = buy_price * qty
        if cost > cash:
            continue

        stop_price = buy_price * (1 - sl_pct)
        sell_price: Optional[float] = None
        status = "open_marked"
        exit_date = str(forward_window.index[-1].date())

        for idx, row in forward_window.iloc[1:].iterrows():
            if float(row["Low"]) <= stop_price:
                sell_price = stop_price
                status = "stop_loss"
                exit_date = str(idx.date())
                break
        if sell_price is None:
            sell_price = float(forward_window["Close"].iloc[-1])

        pnl = (sell_price - buy_price) * qty
        cash = cash - cost + sell_price * qty
        trades.append(
            BacktestTrade(
                code=code,
                name=info.get("name", code),
                entry_date=str(forward_window.index[0].date()),
                exit_date=exit_date,
                buy_price=round(buy_price, 2),
                sell_price=round(sell_price, 2),
                qty=qty,
                pnl=round(pnl, 2),
                status=status,
                reason=tech["reason"][:80],
            )
        )

    wins = sum(1 for t in trades if t.pnl > 0)
    win_rate = (wins / len(trades) * 100) if trades else 0.0
    init = initial_cash or config.MOCK_INITIAL_CASH
    ret = (cash - init) / init * 100 if init else 0.0

    return BacktestResult(
        initial_cash=init,
        final_cash=cash,
        trades=trades,
        win_rate=win_rate,
        total_return_pct=ret,
        skipped=skipped,
        closed_count=sum(1 for t in trades if t.status == "stop_loss"),
        open_count=sum(1 for t in trades if t.status == "open_marked"),
    )


def print_report(result: BacktestResult) -> None:
    print("=" * 70)
    print("alpha-gen 백테스트 리포트 (실데이터 워크포워드)")
    print(f"생성 시각: {datetime.now(KST).strftime('%Y-%m-%d %H:%M')}")
    print(f"초기 자본: {result.initial_cash:,}원 → 최종(청산+평가): {result.final_cash:,.0f}원")
    print(f"수익률: {result.total_return_pct:+.2f}% | 승률: {result.win_rate:.1f}% | 거래 {len(result.trades)}건"
          f" (손절청산 {result.closed_count} / 미실현평가 {result.open_count})")
    print("-" * 70)
    for t in result.trades:
        print(
            f"  [{t.status:11s}] {t.name}({t.code}) {t.qty}주 "
            f"{t.buy_price:,.0f}→{t.sell_price:,.0f} ({t.entry_date}→{t.exit_date}) "
            f"손익 {t.pnl:+,.0f}원"
        )
    if result.skipped:
        print("-" * 70)
        print(f"데이터 부족으로 스킵된 종목: {len(result.skipped)}개")
        for s in result.skipped:
            print(f"  - {s['name']}({s['code']}): {s['reason']}")
    print("=" * 70)


if __name__ == "__main__":
    res = run_backtest()
    print_report(res)
    with open("backtest_result.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "initial_cash": res.initial_cash,
                "final_cash": res.final_cash,
                "total_return_pct": res.total_return_pct,
                "win_rate": res.win_rate,
                "closed_count": res.closed_count,
                "open_count": res.open_count,
                "trades": [t.__dict__ for t in res.trades],
                "skipped": res.skipped,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print("결과 저장: backtest_result.json")
