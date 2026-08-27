"""
backtest.py — 실데이터 백테스트 (P9)

spec.md P9 참조. 이전 버전은 랜덤워크 가격에 모든 거래를 +2%로 하드코딩해
구조적으로 손실이 불가능했다. 이 버전은 ohlcv.db의 실봉을 바-바이-바로 재생한다.

핵심 원칙:
  1. 라이브 경로(services.py analyze_market)와 동일한 인자로 technical/risk_manager를 호출한다.
     특히 prev_day에 '실제 전일 고저'를 넘긴다 — 넘기지 않으면 technical.py가
     price_history[-15:-1] 14일 프록시로 폴백해 다른 전략을 검증하게 된다.
  2. 룩어헤드 차단: t일 판단에는 t-1일까지의 종가 + t일 시가만 쓴다.
     t일 고가는 '돌파 목표가에 지정가가 체결됐는가' 판정에만 쓴다(예측 아님).
  3. 청산은 라이브와 동일하게 당일 종가(main.py:148 KR_SELL_TIME 전량청산).
     단 장중 손절선(STOP_LOSS_PCT)이 먼저 닿으면 손절가로 청산한다.

실행: python backtest.py
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Sequence
from zoneinfo import ZoneInfo

import pandas as pd

import config
import ohlcv
import risk_manager
import technical

KST = ZoneInfo("Asia/Seoul")

SCENARIOS = ("tech_only", "sentiment_random", "sentiment_oracle")
BENCHMARK_KR = "^KS11"
BENCHMARK_US = "^GSPC"


# ──────────────────────────────────────────────
# 비용 모델
# ──────────────────────────────────────────────

@dataclass
class BacktestCosts:
    """전부 bps(만분율). 매수: 수수료+슬리피지 / 매도: 수수료+거래세+슬리피지."""

    fee_bps_buy: float
    fee_bps_sell: float
    tax_bps_sell: float
    slippage_bps: float

    @classmethod
    def from_config(cls) -> "BacktestCosts":
        return cls(
            fee_bps_buy=config.BACKTEST_FEE_BPS_BUY,
            fee_bps_sell=config.BACKTEST_FEE_BPS_SELL,
            tax_bps_sell=config.BACKTEST_TAX_BPS_SELL_KR,
            slippage_bps=config.BACKTEST_SLIPPAGE_BPS,
        )

    def buy_cost(self, notional: float) -> float:
        return notional * (self.fee_bps_buy + self.slippage_bps) / 10_000

    def sell_cost(self, notional: float) -> float:
        return notional * (self.fee_bps_sell + self.tax_bps_sell + self.slippage_bps) / 10_000


@dataclass
class BacktestTrade:
    code: str
    name: str
    date: str
    buy_price: float
    sell_price: float
    qty: int
    pnl: float
    cost: float
    exit_reason: str
    reason: str


@dataclass
class BacktestResult:
    initial_cash: int
    final_cash: float
    trades: list[BacktestTrade] = field(default_factory=list)
    win_rate: float = 0.0
    total_return_pct: float = 0.0
    total_cost: float = 0.0
    mdd_pct: float = 0.0
    turnover: float = 0.0
    scenario: str = "tech_only"
    equity_curve: list[tuple[str, float]] = field(default_factory=list)
    benchmarks: dict[str, Optional[float]] = field(default_factory=dict)
    excluded: list[str] = field(default_factory=list)
    costs: dict[str, float] = field(default_factory=dict)


# ──────────────────────────────────────────────
# 데이터 정제
# ──────────────────────────────────────────────

def clean_bars(df: pd.DataFrame) -> pd.DataFrame:
    """NaN·0·음수·high<low 봉을 제거한다 (CLAUDE.md §5 데이터 무결성)."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    out = df.copy()
    for col in ("open", "high", "low", "close"):
        if col not in out.columns:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close"])
    out = out[(out[["open", "high", "low", "close"]] > 0).all(axis=1)]
    out = out[out["high"] >= out["low"]]
    return out.sort_index()


def _stock_name(code: str) -> str:
    for table in (config.KR_STOCKS, config.US_STOCKS):
        if code in table:
            return table[code]["name"]
    return code


def _is_kr(code: str) -> bool:
    return code.isdigit() and len(code) == 6


# ──────────────────────────────────────────────
# 진입 판단 (룩어헤드 차단 지점)
# ──────────────────────────────────────────────

def decide_entry(code: str, df: pd.DataFrame, i: int) -> Optional[tuple[float, str]]:
    """
    t=i일의 진입 판단. 반환 (진입가, 사유) 또는 None.

    룩어헤드 불변식:
      - price_history = 종가[..i-1]  (i일 종가는 쓰지 않는다)
      - quote.open_price = 시가[i]   (09:00에 알 수 있다)
      - quote.current_price = 고가[i] → 돌파 목표가 체결 여부 판정 전용
    """
    if i < 1 or i >= len(df):
        return None

    history = df["close"].iloc[:i].astype(float).tolist()
    if len(history) < config.MA_LONG + 1:
        return None

    row = df.iloc[i]
    prev = df.iloc[i - 1]
    open_p, high_p = float(row["open"]), float(row["high"])
    prev_high, prev_low = float(prev["high"]), float(prev["low"])

    quote = {"current_price": high_p, "open_price": open_p}
    prev_day = {"prev_high": int(prev_high), "prev_low": int(prev_low)}

    try:
        tech = technical.evaluate_buy_technicals(code, history, quote, prev_day=prev_day)
    except Exception:
        return None
    if not tech.get("signal"):
        return None

    target = float(technical.calc_volatility_target(int(open_p), int(prev_high), int(prev_low)))
    entry = max(target, open_p)          # 갭 상승 시 시가 체결
    if high_p < entry:                   # 장중 목표가 미도달 → 미체결
        return None
    return entry, str(tech.get("reason", ""))[:120]


def _sentiment_passes(scenario: str, rng: random.Random, entry: float, close_p: float,
                      pass_rate: float) -> bool:
    if scenario == "tech_only":
        return True
    if scenario == "sentiment_random":
        return rng.random() < pass_rate
    if scenario == "sentiment_oracle":
        return close_p > entry          # 명시적 상한선 — 미래를 아는 감성
    raise ValueError(f"알 수 없는 시나리오: {scenario}")


# ──────────────────────────────────────────────
# 워크포워드 분할
# ──────────────────────────────────────────────

def make_walk_forward_folds(
    dates: Sequence[Any], train_days: int, test_days: int
) -> list[tuple[list, list]]:
    """검증 구간이 서로 겹치지 않는 롤링 분할. 반환 [(학습일자, 검증일자), ...]"""
    dates = list(dates)
    folds: list[tuple[list, list]] = []
    i = 0
    while i + train_days + test_days <= len(dates):
        folds.append((dates[i:i + train_days], dates[i + train_days:i + train_days + test_days]))
        i += test_days
    return folds


# ──────────────────────────────────────────────
# 벤치마크
# ──────────────────────────────────────────────

def _buy_and_hold_pct(df: pd.DataFrame) -> Optional[float]:
    df = clean_bars(df)
    if len(df) < 2:
        return None
    first, last = float(df["close"].iloc[0]), float(df["close"].iloc[-1])
    return (last - first) / first * 100 if first > 0 else None


def _benchmarks(bars: dict[str, pd.DataFrame], days: int) -> dict[str, Optional[float]]:
    per_stock = [p for p in (_buy_and_hold_pct(df) for df in bars.values()) if p is not None]
    out: dict[str, Optional[float]] = {
        "universe_buy_and_hold_pct": round(sum(per_stock) / len(per_stock), 4) if per_stock else None
    }
    for key, ticker in (("kospi_buy_and_hold_pct", BENCHMARK_KR),
                        ("sp500_buy_and_hold_pct", BENCHMARK_US)):
        try:
            out[key] = _buy_and_hold_pct(ohlcv.load_ohlcv(ticker, days=days))
        except Exception:
            out[key] = None
        if out[key] is not None:
            out[key] = round(out[key], 4)
    return out


# ──────────────────────────────────────────────
# 메인 시뮬레이션
# ──────────────────────────────────────────────

def run_backtest(
    stocks: dict | None = None,
    sentiment_scores: dict[str, int] | None = None,
    days: int = 30,
    initial_cash: int | None = None,
    *,
    bars: dict[str, pd.DataFrame] | None = None,
    scenario: str = "tech_only",
    costs: BacktestCosts | None = None,
    seed: int = 42,
    sentiment_pass_rate: float = 0.5,
    dates: Sequence[Any] | None = None,
) -> BacktestResult:
    """
    일봉 바-바이-바 재생. 라이브(main.py)와 동일하게 당일 진입 → 당일 청산.

    stocks/sentiment_scores/days/initial_cash는 BacktestService 하위호환용.
    bars를 직접 주면 DB를 읽지 않는다(테스트용).
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario는 {SCENARIOS} 중 하나여야 합니다: {scenario}")

    cash = float(initial_cash or config.MOCK_INITIAL_CASH)
    init = int(initial_cash or config.MOCK_INITIAL_CASH)
    costs = costs or BacktestCosts.from_config()
    rng = random.Random(seed)

    # ── 봉 데이터 확보 ────────────────────────────────────────────────────
    if bars is None:
        universe = stocks if stocks else {**config.KR_STOCKS, **config.US_STOCKS}
        bars = {}
        for code in universe:
            try:
                bars[code] = ohlcv.load_ohlcv(code, days=days)
            except Exception:
                continue

    cleaned: dict[str, pd.DataFrame] = {}
    excluded: list[str] = []
    for code, df in bars.items():
        c = clean_bars(df)
        if len(c) < config.MA_LONG + 2:
            excluded.append(code)
            continue
        cleaned[code] = c

    if not cleaned:
        return BacktestResult(
            initial_cash=init, final_cash=float(init), scenario=scenario,
            benchmarks=_benchmarks(bars, days), excluded=excluded,
            costs=costs.__dict__.copy(),
        )

    # ── 거래일 축 (전 종목 합집합, 정렬) ──────────────────────────────────
    if dates is None:
        all_dates = sorted({d for df in cleaned.values() for d in df.index})
    else:
        all_dates = sorted(dates)

    trades: list[BacktestTrade] = []
    equity_curve: list[tuple[str, float]] = []
    total_cost = 0.0
    buy_notional_sum = 0.0

    for day in all_dates:
        day_asset = cash                     # 오버나이트 포지션 없음 → 총자산 = 현금
        for code in sorted(cleaned):
            df = cleaned[code]
            if day not in df.index:
                continue
            i = df.index.get_loc(day)
            if not isinstance(i, int):
                continue

            decision = decide_entry(code, df, i)
            if decision is None:
                continue
            entry, reason = decision

            row = df.iloc[i]
            close_p, low_p = float(row["close"]), float(row["low"])
            score = int((sentiment_scores or {}).get(code, 2))
            if not _sentiment_passes(scenario, rng, entry, close_p, sentiment_pass_rate):
                continue

            qty = risk_manager.get_position_size(int(day_asset), score, int(entry))
            if qty <= 0:
                continue
            gross_buy = entry * qty
            buy_fee = costs.buy_cost(gross_buy)
            if gross_buy + buy_fee > cash:                   # 예수금 초과 방지
                qty = int((cash * 0.98) // entry)
                if qty <= 0:
                    continue
                gross_buy = entry * qty
                buy_fee = costs.buy_cost(gross_buy)

            # 청산: 장중 손절선 우선, 아니면 당일 종가 (라이브 KR_SELL_TIME 전량청산)
            stop_price = entry * (1 - config.STOP_LOSS_PCT)
            if low_p <= stop_price:
                exit_price, exit_reason = stop_price, "stop_loss"
            else:
                exit_price, exit_reason = close_p, "eod_close"

            sell_fee = costs.sell_cost(exit_price * qty)
            trade_cost = buy_fee + sell_fee
            pnl = (exit_price - entry) * qty - trade_cost

            cash += pnl
            total_cost += trade_cost
            buy_notional_sum += gross_buy
            trades.append(BacktestTrade(
                code=code, name=_stock_name(code),
                date=pd.Timestamp(day).strftime("%Y-%m-%d"),
                buy_price=round(entry, 4), sell_price=round(exit_price, 4), qty=qty,
                pnl=round(pnl, 4), cost=round(trade_cost, 4),
                exit_reason=exit_reason, reason=reason,
            ))
        equity_curve.append((pd.Timestamp(day).strftime("%Y-%m-%d"), round(cash, 2)))

    wins = sum(1 for t in trades if t.pnl > 0)
    win_rate = (wins / len(trades) * 100) if trades else 0.0
    total_return = (cash - init) / init * 100 if init else 0.0

    peak, mdd = float("-inf"), 0.0
    for _, v in equity_curve:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, (v - peak) / peak * 100)

    return BacktestResult(
        initial_cash=init,
        final_cash=round(cash, 4),
        trades=trades,
        win_rate=round(win_rate, 2),
        total_return_pct=round(total_return, 4),
        total_cost=round(total_cost, 4),
        mdd_pct=round(mdd, 4),
        turnover=round(buy_notional_sum / init, 4) if init else 0.0,
        scenario=scenario,
        equity_curve=equity_curve,
        benchmarks=_benchmarks(cleaned, days),
        excluded=excluded,
        costs=costs.__dict__.copy(),
    )


# ──────────────────────────────────────────────
# 리포트
# ──────────────────────────────────────────────

def print_report(result: BacktestResult) -> None:
    print("=" * 68)
    print(f"alpha-gen 백테스트 리포트 — 시나리오: {result.scenario}")
    print(f"생성: {datetime.now(KST).strftime('%Y-%m-%d %H:%M')}")
    print("-" * 68)
    print(f"초기 자본 : {result.initial_cash:,}원")
    print(f"최종 자본 : {result.final_cash:,.0f}원")
    print(f"수익률    : {result.total_return_pct:+.2f}%   승률 {result.win_rate:.1f}%   "
          f"거래 {len(result.trades)}건")
    print(f"MDD       : {result.mdd_pct:.2f}%   회전율 {result.turnover:.1f}배   "
          f"총비용 {result.total_cost:,.0f}원")
    print("-" * 68)
    print("벤치마크")
    for k, v in result.benchmarks.items():
        print(f"  {k:32s}: {v if v is None else f'{v:+.2f}%'}")
    if result.excluded:
        print(f"\n제외 종목({len(result.excluded)}) — 데이터 부족: {', '.join(result.excluded[:12])}"
              + (" ..." if len(result.excluded) > 12 else ""))
    print("=" * 68)


if __name__ == "__main__":
    for sc in SCENARIOS:
        res = run_backtest(days=1825, scenario=sc)
        print_report(res)
        print()
    with open("backtest_result.json", "w", encoding="utf-8") as f:
        base = run_backtest(days=1825, scenario="tech_only")
        json.dump({
            "scenario": base.scenario,
            "initial_cash": base.initial_cash,
            "final_cash": base.final_cash,
            "total_return_pct": base.total_return_pct,
            "win_rate": base.win_rate,
            "mdd_pct": base.mdd_pct,
            "turnover": base.turnover,
            "total_cost": base.total_cost,
            "benchmarks": base.benchmarks,
            "excluded": base.excluded,
            "costs": base.costs,
            "trades": [t.__dict__ for t in base.trades],
        }, f, ensure_ascii=False, indent=2)
    print("결과 저장: backtest_result.json")


# ══════════════════════════════════════════════════════════════════════════
# 배당 전략 (P12) — P9 하니스(비용모델·워크포워드·벤치마크) 재사용
# ══════════════════════════════════════════════════════════════════════════

DIVIDEND_BENCHMARKS = {
    "arirang_high_div": "161510.KS",
    "kodex_high_div": "279530.KS",
    "tiger_div_growth": "211900.KS",
    "kodex_200": "069500.KS",
}


def _dividend_benchmarks(days: int) -> dict[str, Optional[float]]:
    out: dict[str, Optional[float]] = {}
    for key, ticker in DIVIDEND_BENCHMARKS.items():
        try:
            v = _buy_and_hold_pct(ohlcv.load_ohlcv(ticker, days=days))
        except Exception:
            v = None
        out[key] = None if v is None else round(v, 4)
    return out


def select_dividend_universe(
    div_records: dict[str, list], bars: dict[str, pd.DataFrame], asof, top_n: int,
    min_yield_pct: float, min_streak: int,
) -> list[tuple[str, float]]:
    """
    asof 시점의 배당 상위 종목 선정. 반환 [(종목코드, 후행배당수익률%), ...].

    룩어헤드 차단: 배당은 asof '이전' 이력만, 가격은 asof '직전 종가'만 쓴다.
    """
    import dividends as div_mod

    ranked: list[tuple[str, float]] = []
    for code, records in div_records.items():
        df = bars.get(code)
        if df is None or df.empty:
            continue
        prior = df.loc[df.index < asof]          # asof 당일 종가는 쓰지 않는다
        if prior.empty:
            continue
        price = float(prior["close"].iloc[-1])
        prev_day = prior.index[-1]

        y = div_mod.calc_trailing_yield(records, prev_day, price)
        if y is None or y < min_yield_pct:
            continue
        if div_mod.calc_dividend_streak_years(records, prev_day) < min_streak:
            continue
        ranked.append((code, y))

    ranked.sort(key=lambda x: (-x[1], x[0]))     # 수익률 desc, 동률은 코드순(결정적)
    return ranked[:top_n]


def run_dividend_backtest(
    *,
    bars: dict[str, pd.DataFrame],
    div_records: dict[str, list],
    initial_cash: int = 10_000_000,
    costs: BacktestCosts | None = None,
    top_n: int | None = None,
    rebalance_days: int | None = None,
    min_yield_pct: float | None = None,
    min_streak: int | None = None,
    respect_position_cap: bool = True,
    days: int = 1825,
    dates: Sequence[Any] | None = None,
) -> BacktestResult:
    """
    분기 리밸런스 배당 전략. 당일 청산·손절 없음 (P9 실패 원인의 정반대 설계).

    respect_position_cap=True 면 종목당 비중을 MAX_POSITION_PCT로 제한한다.
    top_n이 커서 1/top_n < MAX_POSITION_PCT 면 상한은 구속력이 없다.
    """
    costs = costs or BacktestCosts.from_config()
    top_n = top_n or config.DIVIDEND_TOP_N
    rebalance_days = rebalance_days or config.DIVIDEND_REBALANCE_DAYS
    min_yield_pct = min_yield_pct if min_yield_pct is not None else config.DIVIDEND_MIN_YIELD_PCT
    min_streak = min_streak if min_streak is not None else config.DIVIDEND_MIN_STREAK_YEARS

    cleaned: dict[str, pd.DataFrame] = {}
    excluded: list[str] = []
    for code, df in bars.items():
        c = clean_bars(df)
        if len(c) < 2:
            excluded.append(code)
            continue
        cleaned[code] = c
    if not cleaned:
        return BacktestResult(initial_cash=initial_cash, final_cash=float(initial_cash),
                              scenario="dividend", excluded=excluded, costs=costs.__dict__.copy())

    all_dates = sorted(dates) if dates is not None else sorted(
        {d for df in cleaned.values() for d in df.index}
    )

    cash = float(initial_cash)
    positions: dict[str, tuple[int, float]] = {}      # code -> (qty, avg_price)
    trades: list[BacktestTrade] = []
    equity_curve: list[tuple[str, float]] = []
    total_cost = 0.0
    buy_notional_sum = 0.0
    invested_fracs: list[float] = []

    def price_at(code: str, day, field: str = "close") -> Optional[float]:
        df = cleaned.get(code)
        if df is None or day not in df.index:
            return None
        v = float(df.loc[day, field])
        return v if v > 0 else None

    for n, day in enumerate(all_dates):
        # ── 리밸런스 ────────────────────────────────────────────────────
        if n % rebalance_days == 0:
            picks = select_dividend_universe(
                div_records, cleaned, day, top_n, min_yield_pct, min_streak
            )
            target_codes = {c for c, _ in picks}

            # 1) 이탈 종목 매도 (당일 시가 체결)
            for code in list(positions):
                if code in target_codes:
                    continue
                qty, avg = positions.pop(code)
                px = price_at(code, day, "open") or price_at(code, day, "close")
                if px is None:
                    positions[code] = (qty, avg)      # 가격 없으면 보유 유지
                    continue
                fee = costs.sell_cost(px * qty)
                cash += px * qty - fee
                total_cost += fee
                trades.append(BacktestTrade(
                    code=code, name=_stock_name(code), date=pd.Timestamp(day).strftime("%Y-%m-%d"),
                    buy_price=round(avg, 4), sell_price=round(px, 4), qty=qty,
                    pnl=round((px - avg) * qty - fee, 4), cost=round(fee, 4),
                    exit_reason="rebalance_exit", reason="유니버스 이탈",
                ))

            # 2) 목표 비중 재조정
            if picks:
                equity = cash + sum(
                    (price_at(c, day, "close") or avg) * q for c, (q, avg) in positions.items()
                )
                weight = 1.0 / len(picks)
                if respect_position_cap:
                    weight = min(weight, config.MAX_POSITION_PCT)
                for code, _y in picks:
                    px = price_at(code, day, "open") or price_at(code, day, "close")
                    if px is None:
                        continue
                    want_qty = int((equity * weight) // px)
                    have_qty, have_avg = positions.get(code, (0, 0.0))
                    delta = want_qty - have_qty
                    if delta > 0:
                        gross = px * delta
                        fee = costs.buy_cost(gross)
                        if gross + fee > cash:
                            delta = int((cash * 0.98) // px)
                            if delta <= 0:
                                continue
                            gross = px * delta
                            fee = costs.buy_cost(gross)
                        cash -= gross + fee
                        total_cost += fee
                        buy_notional_sum += gross
                        new_qty = have_qty + delta
                        positions[code] = (
                            new_qty, ((have_avg * have_qty) + (px * delta)) / new_qty
                        )
                    elif delta < 0 and have_qty > 0:
                        sell_qty = min(-delta, have_qty)
                        fee = costs.sell_cost(px * sell_qty)
                        cash += px * sell_qty - fee
                        total_cost += fee
                        remaining = have_qty - sell_qty
                        trades.append(BacktestTrade(
                            code=code, name=_stock_name(code),
                            date=pd.Timestamp(day).strftime("%Y-%m-%d"),
                            buy_price=round(have_avg, 4), sell_price=round(px, 4), qty=sell_qty,
                            pnl=round((px - have_avg) * sell_qty - fee, 4), cost=round(fee, 4),
                            exit_reason="rebalance_trim", reason="비중 축소",
                        ))
                        if remaining > 0:
                            positions[code] = (remaining, have_avg)
                        else:
                            positions.pop(code, None)

        # ── 일일 평가 ───────────────────────────────────────────────────
        holdings_value = sum(
            (price_at(c, day, "close") or avg) * q for c, (q, avg) in positions.items()
        )
        equity = cash + holdings_value
        equity_curve.append((pd.Timestamp(day).strftime("%Y-%m-%d"), round(equity, 2)))
        if equity > 0:
            invested_fracs.append(holdings_value / equity)

    # 최종 청산 (평가 기준 통일)
    if all_dates and positions:
        last = all_dates[-1]
        for code, (qty, avg) in list(positions.items()):
            px = price_at(code, last, "close") or avg
            fee = costs.sell_cost(px * qty)
            cash += px * qty - fee
            total_cost += fee
            trades.append(BacktestTrade(
                code=code, name=_stock_name(code), date=pd.Timestamp(last).strftime("%Y-%m-%d"),
                buy_price=round(avg, 4), sell_price=round(px, 4), qty=qty,
                pnl=round((px - avg) * qty - fee, 4), cost=round(fee, 4),
                exit_reason="final_liquidation", reason="백테스트 종료 청산",
            ))
        positions.clear()

    wins = sum(1 for t in trades if t.pnl > 0)
    peak, mdd = float("-inf"), 0.0
    for _, v in equity_curve:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, (v - peak) / peak * 100)

    bench = _dividend_benchmarks(days)
    bench["universe_buy_and_hold_pct"] = (
        round(sum(p for p in (_buy_and_hold_pct(d) for d in cleaned.values()) if p is not None)
              / max(1, sum(1 for d in cleaned.values() if _buy_and_hold_pct(d) is not None)), 4)
    )
    bench["avg_invested_pct"] = (
        round(sum(invested_fracs) / len(invested_fracs) * 100, 2) if invested_fracs else 0.0
    )

    return BacktestResult(
        initial_cash=initial_cash,
        final_cash=round(cash, 4),
        trades=trades,
        win_rate=round(wins / len(trades) * 100, 2) if trades else 0.0,
        total_return_pct=round((cash - initial_cash) / initial_cash * 100, 4),
        total_cost=round(total_cost, 4),
        mdd_pct=round(mdd, 4),
        turnover=round(buy_notional_sum / initial_cash, 4),
        scenario="dividend",
        equity_curve=equity_curve,
        benchmarks=bench,
        excluded=excluded,
        costs=costs.__dict__.copy(),
    )


# ══════════════════════════════════════════════════════════════════════════
# 인덱스 매수후보유 / 타이밍 규칙 (P13)
# ══════════════════════════════════════════════════════════════════════════

def _sma(values: list[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def run_index_backtest(
    *,
    bars: dict[str, pd.DataFrame],
    weights: dict[str, float] | None = None,
    initial_cash: int = 10_000_000,
    costs: BacktestCosts | None = None,
    mode: str = "buy_and_hold",       # buy_and_hold | ma_filter | dca
    ma_period: int = 200,
    rebalance_days: int = 0,          # 0 = 리밸런스 없음
    dca_amount: int = 0,
    dca_interval_days: int = 21,      # 월 ≈ 21 영업일
    dates: Sequence[Any] | None = None,
) -> BacktestResult:
    """
    인덱스/ETF 규칙 백테스트.

    룩어헤드 차단: 이동평균은 t-1일까지의 종가로 계산하고 체결은 t일 시가로 한다
    (P9 하니스 불변식과 동일).
    """
    costs = costs or BacktestCosts.from_config()
    cleaned = {c: clean_bars(df) for c, df in bars.items()}
    cleaned = {c: df for c, df in cleaned.items() if len(df) >= 2}
    if not cleaned:
        return BacktestResult(initial_cash=initial_cash, final_cash=float(initial_cash),
                              scenario=f"index:{mode}", costs=costs.__dict__.copy())

    weights = weights or {c: 1.0 / len(cleaned) for c in cleaned}
    all_dates = sorted(dates) if dates is not None else sorted(
        {d for df in cleaned.values() for d in df.index}
    )

    cash = float(initial_cash)
    contributed = float(initial_cash)
    positions: dict[str, tuple[int, float]] = {}
    trades: list[BacktestTrade] = []
    equity_curve: list[tuple[str, float]] = []
    total_cost = 0.0
    buy_notional_sum = 0.0

    def px(code: str, day, field: str) -> Optional[float]:
        df = cleaned.get(code)
        if df is None or day not in df.index:
            return None
        v = float(df.loc[day, field])
        return v if v > 0 else None

    def in_market(code: str, df: pd.DataFrame, day) -> bool:
        if mode != "ma_filter":
            return True
        prior = df.loc[df.index < day, "close"]     # t일 종가는 쓰지 않는다
        ma = _sma(prior.astype(float).tolist(), ma_period)
        if ma is None:
            return False
        return float(prior.iloc[-1]) > ma

    def trade_to(code: str, day, target_value: float, reason: str) -> None:
        nonlocal cash, total_cost, buy_notional_sum
        p = px(code, day, "open") or px(code, day, "close")
        if p is None:
            return
        have_qty, have_avg = positions.get(code, (0, 0.0))
        want_qty = max(0, int(target_value // p))
        delta = want_qty - have_qty
        if delta > 0:
            gross = p * delta
            fee = costs.buy_cost(gross)
            if gross + fee > cash:
                delta = int((cash * 0.98) // p)
                if delta <= 0:
                    return
                gross, fee = p * delta, costs.buy_cost(p * delta)
            cash -= gross + fee
            total_cost += fee
            buy_notional_sum += gross
            nq = have_qty + delta
            positions[code] = (nq, ((have_avg * have_qty) + (p * delta)) / nq)
        elif delta < 0 and have_qty > 0:
            sell_qty = min(-delta, have_qty)
            fee = costs.sell_cost(p * sell_qty)
            cash += p * sell_qty - fee
            total_cost += fee
            trades.append(BacktestTrade(
                code=code, name=code, date=pd.Timestamp(day).strftime("%Y-%m-%d"),
                buy_price=round(have_avg, 4), sell_price=round(p, 4), qty=sell_qty,
                pnl=round((p - have_avg) * sell_qty - fee, 4), cost=round(fee, 4),
                exit_reason=reason, reason=reason,
            ))
            rem = have_qty - sell_qty
            if rem > 0:
                positions[code] = (rem, have_avg)
            else:
                positions.pop(code, None)

    for n, day in enumerate(all_dates):
        if mode == "dca" and dca_amount > 0 and n > 0 and n % dca_interval_days == 0:
            cash += dca_amount
            contributed += dca_amount

        first_day = (n == 0)
        rebalance_due = rebalance_days > 0 and n % rebalance_days == 0
        dca_due = mode == "dca" and (first_day or (n > 0 and n % dca_interval_days == 0))
        ma_due = mode == "ma_filter"

        if first_day or rebalance_due or dca_due or ma_due:
            equity = cash + sum(
                (px(c, day, "close") or avg) * q for c, (q, avg) in positions.items()
            )
            for code, w in weights.items():
                df = cleaned.get(code)
                if df is None:
                    continue
                target = equity * w if in_market(code, df, day) else 0.0
                trade_to(code, day, target, "ma_exit" if target == 0 else "rebalance")

        holdings = sum((px(c, day, "close") or avg) * q for c, (q, avg) in positions.items())
        equity_curve.append((pd.Timestamp(day).strftime("%Y-%m-%d"), round(cash + holdings, 2)))

    if all_dates and positions:
        last = all_dates[-1]
        for code, (qty, avg) in list(positions.items()):
            p = px(code, last, "close") or avg
            fee = costs.sell_cost(p * qty)
            cash += p * qty - fee
            total_cost += fee
            trades.append(BacktestTrade(
                code=code, name=code, date=pd.Timestamp(last).strftime("%Y-%m-%d"),
                buy_price=round(avg, 4), sell_price=round(p, 4), qty=qty,
                pnl=round((p - avg) * qty - fee, 4), cost=round(fee, 4),
                exit_reason="final_liquidation", reason="종료 청산",
            ))
        positions.clear()

    peak, mdd = float("-inf"), 0.0
    for _, v in equity_curve:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, (v - peak) / peak * 100)

    return BacktestResult(
        initial_cash=initial_cash,
        final_cash=round(cash, 4),
        trades=trades,
        win_rate=round(sum(1 for t in trades if t.pnl > 0) / len(trades) * 100, 2) if trades else 0.0,
        total_return_pct=round((cash - contributed) / contributed * 100, 4),
        total_cost=round(total_cost, 4),
        mdd_pct=round(mdd, 4),
        turnover=round(buy_notional_sum / max(1.0, contributed), 4),
        scenario=f"index:{mode}",
        equity_curve=equity_curve,
        benchmarks={"contributed": round(contributed, 2)},
        costs=costs.__dict__.copy(),
    )


def blend_sleeves(
    curves: list[tuple[list[tuple[str, float]], float]]
) -> dict[str, Any]:
    """
    독립 슬리브들의 자산곡선을 합산한다 (코어-새틀라이트, P14).

    curves: [(equity_curve, contributed_capital), ...]
    슬리브 간 현금 이동은 없다 — 있으면 새틀라이트 한도가 무너진다.

    ⚠️ 슬리브마다 거래일 집합이 다를 수 있다(유니버스가 다르므로). 날짜별로 단순
    합산하면 한쪽에만 있는 날짜에서 나머지 자본이 사라진 것처럼 보여 MDD가 폭주한다.
    따라서 **전체 날짜의 합집합에 대해 각 슬리브를 전진보간**한 뒤 합산한다.
    """
    curves = [(c, cap) for c, cap in curves if c]
    if not curves:
        return {"total_return_pct": 0.0, "mdd_pct": 0.0, "final_value": 0.0,
                "capital": 0.0, "curve": []}

    all_days = sorted({day for curve, _ in curves for day, _ in curve})
    total_capital = sum(cap for _, cap in curves)

    filled: list[list[float]] = []
    for curve, cap in curves:
        lookup = dict(curve)
        series, last = [], float(cap)      # 첫 관측 이전에는 원금 그대로 본다
        for day in all_days:
            last = float(lookup.get(day, last))
            series.append(last)
        filled.append(series)

    totals = [sum(col) for col in zip(*filled)]

    peak, mdd = float("-inf"), 0.0
    for v in totals:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, (v - peak) / peak * 100)

    final = totals[-1]
    return {
        "total_return_pct": round((final - total_capital) / total_capital * 100, 4)
        if total_capital > 0 else 0.0,
        "mdd_pct": round(mdd, 4),
        "final_value": round(final, 2),
        "capital": round(total_capital, 2),
        "curve": list(zip(all_days, [round(v, 2) for v in totals])),
    }
