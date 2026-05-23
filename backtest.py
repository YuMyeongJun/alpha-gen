"""
backtest.py — 간이 백테스트 (Mock 가격 + 고정 감성 시나리오)

실행: python backtest.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import technical
from technical import generate_mock_price_history

KST = ZoneInfo("Asia/Seoul")


@dataclass
class BacktestTrade:
    code: str
    name: str
    buy_price: int
    sell_price: int
    qty: int
    pnl: int
    reason: str


@dataclass
class BacktestResult:
    initial_cash: int
    final_cash: int
    trades: list[BacktestTrade] = field(default_factory=list)
    win_rate: float = 0.0
    total_return_pct: float = 0.0


def run_backtest(
    stocks: dict | None = None,
    sentiment_scores: dict[str, int] | None = None,
    days: int = 30,
    initial_cash: int | None = None,
) -> BacktestResult:
    """
    단순 백테스트: 각 종목 1회 매수→익일 매도 시뮬레이션.
    sentiment_scores: {code: score} — score>=1 인 종목만 매수
    """
    stocks = stocks or {**config.KR_STOCKS, **config.US_STOCKS}
    cash = initial_cash or config.MOCK_INITIAL_CASH
    trades: list[BacktestTrade] = []

    default_scores = {code: 2 for code in stocks}
    scores = {**default_scores, **(sentiment_scores or {})}

    for code, info in stocks.items():
        score = scores.get(code, 0)
        if score < config.SENTIMENT_BUY_THRESHOLD:
            continue

        history = generate_mock_price_history(code, n=days)
        quote = {"current_price": int(history[-1]), "open_price": int(history[0])}
        tech = technical.evaluate_buy_technicals(code, history, quote)
        if not tech["signal"]:
            continue

        buy_price = int(history[-1])
        qty = max(1, int(cash * config.MAX_POSITION_PCT * config.CONFIDENCE_SIZING.get(score, 0.6) // buy_price))
        cost = buy_price * qty
        if cost > cash:
            continue

        sell_price = int(history[-1] * 1.02)  # 단순 +2% 청산 가정
        pnl = (sell_price - buy_price) * qty
        cash = cash - cost + sell_price * qty
        trades.append(
            BacktestTrade(
                code=code,
                name=info["name"],
                buy_price=buy_price,
                sell_price=sell_price,
                qty=qty,
                pnl=pnl,
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
    )


def print_report(result: BacktestResult) -> None:
    print("=" * 60)
    print("alpha-gen 백테스트 리포트")
    print(f"기간 시뮬레이션: {datetime.now(KST).strftime('%Y-%m-%d')}")
    print(f"초기 자본: {result.initial_cash:,}원 → 최종: {result.final_cash:,}원")
    print(f"수익률: {result.total_return_pct:+.2f}% | 승률: {result.win_rate:.1f}%")
    print("-" * 60)
    for t in result.trades:
        print(
            f"  {t.name}({t.code}) {t.qty}주 "
            f"{t.buy_price:,}→{t.sell_price:,} | 손익 {t.pnl:+,}원"
        )
    print("=" * 60)


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
                "trades": [t.__dict__ for t in res.trades],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print("결과 저장: backtest_result.json")
