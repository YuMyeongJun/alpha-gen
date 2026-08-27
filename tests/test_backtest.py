"""backtest.py 단위 테스트 (P9 — 실데이터 백테스트)

spec.md P9 "검증 시나리오" 10항목을 그대로 옮긴다.
DB에 의존하지 않도록 합성 봉 데이터를 주입(`bars=`)해서 검증한다.
"""

from __future__ import annotations

import pandas as pd
import pytest

import backtest
import config


# ── 합성 봉 생성 헬퍼 ──────────────────────────────────────────────────────

def make_bars(rows: list[tuple], start: str = "2024-01-02") -> pd.DataFrame:
    """rows: [(open, high, low, close), ...] → OHLCV DataFrame (영업일 인덱스)"""
    idx = pd.bdate_range(start=start, periods=len(rows))
    return pd.DataFrame(
        [{"open": o, "high": h, "low": lo, "close": c, "volume": 1_000_000} for o, h, lo, c in rows],
        index=idx,
    )


# 워밍업 봉: 종가는 일정하되 레인지가 있어 '돌파가 발생하지 않는' 봉.
# 완전 평탄(o=h=l=c)으로 만들면 전일 레인지=0 → 목표가=시가 → 매일 돌파가 성립해버린다.
WARM = (100_000.0, 100_500.0, 99_000.0, 100_000.0)
WARM_RANGE = WARM[1] - WARM[2]          # 1,500


def expected_entry(open_p: float) -> float:
    """워밍업 봉 직후 날의 진입가 = max(시가 + 전일레인지*K, 시가)"""
    return max(open_p + WARM_RANGE * config.K_VALUE, open_p)


def flat_then(rows: list[tuple], n_flat: int = 40) -> pd.DataFrame:
    """지표 워밍업 구간(무돌파) + 실제 시나리오 구간."""
    return make_bars([WARM] * n_flat + rows)


@pytest.fixture(autouse=True)
def _deterministic_signal(monkeypatch):
    """RSI/MA 게이트를 무력화해 실행·비용 산술만 격리 검증한다."""
    monkeypatch.setattr(config, "RSI_OVERBOUGHT", 100)
    monkeypatch.setattr(config, "K_VALUE", 0.5)
    monkeypatch.setattr(config, "ENABLE_VOLATILITY_BREAKOUT", True)


ZERO_COST = backtest.BacktestCosts(0.0, 0.0, 0.0, 0.0)


# ── 1. 상승 시계열: 매수 후 수익 + 비용 정확 차감 ──────────────────────────

def test_winning_trade_costs_are_exact():
    # 워밍업 마지막 봉 레인지 1,500 → 목표가 = 100,000 + 750 = 100,750
    bars = flat_then([(100_000, 112_000, 98_000, 111_000)])
    res = backtest.run_backtest(bars={"TEST": bars}, initial_cash=10_000_000, costs=ZERO_COST)

    assert len(res.trades) == 1, "워밍업 구간에서 체결이 발생하면 안 된다"
    t = res.trades[0]
    assert t.buy_price == pytest.approx(expected_entry(100_000))
    assert t.sell_price == pytest.approx(111_000)   # 당일 종가 청산
    assert t.pnl == pytest.approx((111_000 - expected_entry(100_000)) * t.qty)

    # 동일 시나리오에 비용을 넣으면 정확히 그만큼 줄어야 한다
    costs = backtest.BacktestCosts(
        fee_bps_buy=1.5, fee_bps_sell=1.5, tax_bps_sell=15.0, slippage_bps=10.0
    )
    res_c = backtest.run_backtest(bars={"TEST": bars}, initial_cash=10_000_000, costs=costs)
    tc = res_c.trades[0]
    expected_cost = (
        tc.buy_price * tc.qty * (1.5 + 10.0) / 10_000
        + tc.sell_price * tc.qty * (1.5 + 15.0 + 10.0) / 10_000
    )
    assert tc.cost == pytest.approx(expected_cost, rel=1e-9)
    assert tc.pnl == pytest.approx((tc.sell_price - tc.buy_price) * tc.qty - tc.cost, rel=1e-9)


# ── 2. 하락 시계열: 손절 발동 ──────────────────────────────────────────────

def test_stop_loss_triggers_and_records_loss():
    entry = expected_entry(100_000)
    stop = entry * (1 - config.STOP_LOSS_PCT)
    bars = flat_then([(100_000, 112_000, stop - 5_000, stop - 1_000)])
    res = backtest.run_backtest(bars={"TEST": bars}, initial_cash=10_000_000, costs=ZERO_COST)

    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_reason == "stop_loss"
    assert t.sell_price == pytest.approx(stop)      # 종가가 아니라 손절선에서 청산
    assert t.pnl < 0


# ── 3. 룩어헤드 회귀 (가장 중요) ────────────────────────────────────────────

def test_entry_decision_ignores_same_day_close():
    """t일 종가를 바꿔도 t일 진입 판단·진입가는 변하지 않아야 한다."""
    base = [(100_000, 112_000, 98_000, 111_000)]
    bars_a = flat_then(base)
    bars_b = flat_then([(100_000, 112_000, 98_000, 101_000)])   # 종가만 변경

    a = backtest.run_backtest(bars={"TEST": bars_a}, initial_cash=10_000_000, costs=ZERO_COST)
    b = backtest.run_backtest(bars={"TEST": bars_b}, initial_cash=10_000_000, costs=ZERO_COST)

    assert len(a.trades) == len(b.trades) == 1
    assert a.trades[0].date == b.trades[0].date
    assert a.trades[0].buy_price == pytest.approx(b.trades[0].buy_price)
    assert a.trades[0].qty == b.trades[0].qty
    # 청산가는 달라야 한다 (종가를 바꿨으므로) — 진입만 불변
    assert a.trades[0].sell_price != pytest.approx(b.trades[0].sell_price)


# ── 4. 데이터 부족 / 빈 데이터 ─────────────────────────────────────────────

def test_empty_and_short_data_return_empty_result():
    empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    res = backtest.run_backtest(bars={"TEST": empty}, initial_cash=10_000_000)
    assert res.trades == []
    assert res.final_cash == res.initial_cash

    short = make_bars([(100_000, 101_000, 99_000, 100_500)] * 3)   # MA_LONG 미만
    res2 = backtest.run_backtest(bars={"TEST": short}, initial_cash=10_000_000)
    assert res2.trades == []


# ── 5. NaN / None / 0 / 음수 혼재 ──────────────────────────────────────────

def test_dirty_bars_are_skipped_without_crash():
    bars = flat_then([(100_000, 112_000, 98_000, 111_000)])
    bars.loc[bars.index[5], "close"] = float("nan")
    bars.loc[bars.index[6], "close"] = 0.0
    bars.loc[bars.index[7], "low"] = -1.0
    res = backtest.run_backtest(bars={"TEST": bars}, initial_cash=10_000_000, costs=ZERO_COST)
    assert isinstance(res.trades, list)   # 크래시 없이 완주


# ── 6. 비용 0 vs 기본 비용 차이 = 회전율 × 비용률 ──────────────────────────

def test_cost_difference_matches_turnover():
    bars = flat_then([(100_000, 112_000, 98_000, 111_000)] * 3)
    free = backtest.run_backtest(bars={"TEST": bars}, initial_cash=10_000_000, costs=ZERO_COST)
    costs = backtest.BacktestCosts(1.5, 1.5, 15.0, 10.0)
    paid = backtest.run_backtest(bars={"TEST": bars}, initial_cash=10_000_000, costs=costs)

    assert paid.total_cost > 0
    assert free.total_cost == pytest.approx(0.0)
    # 수량이 갈리면 아래 항등식이 성립하지 않는다 — 원인을 먼저 드러낸다
    assert [t.qty for t in free.trades] == [t.qty for t in paid.trades]
    assert free.final_cash - paid.final_cash == pytest.approx(paid.total_cost, rel=1e-6)


# ── 7. 재현성 ──────────────────────────────────────────────────────────────

def test_same_seed_reproduces_identical_result():
    bars = flat_then([(100_000, 112_000, 98_000, 111_000)] * 5)
    kw = dict(bars={"TEST": bars}, initial_cash=10_000_000, scenario="sentiment_random", seed=42)
    a = backtest.run_backtest(**kw)
    b = backtest.run_backtest(**kw)
    assert a.total_return_pct == pytest.approx(b.total_return_pct)
    assert [t.date for t in a.trades] == [t.date for t in b.trades]


# ── 8. 시나리오 순서 정합성: oracle ≥ tech_only ────────────────────────────

def test_scenario_ordering_oracle_beats_tech_only():
    win = (100_000, 112_000, 98_000, 111_000)
    lose = (100_000, 112_000, 98_000, 92_000)
    bars = flat_then([win, lose, win, lose, win, lose])
    oracle = backtest.run_backtest(bars={"TEST": bars}, initial_cash=10_000_000,
                                   scenario="sentiment_oracle", costs=ZERO_COST)
    tech = backtest.run_backtest(bars={"TEST": bars}, initial_cash=10_000_000,
                                 scenario="tech_only", costs=ZERO_COST)
    assert oracle.total_return_pct >= tech.total_return_pct


# ── 9. 벤치마크가 유니버스를 반영 ──────────────────────────────────────────

def test_benchmark_reflects_universe():
    up = flat_then([(100_000, 112_000, 98_000, 111_000)] * 3)
    flat = flat_then([(100_000, 100_000, 100_000, 100_000)] * 3)
    res = backtest.run_backtest(bars={"UP": up, "FLAT": flat}, initial_cash=10_000_000,
                                costs=ZERO_COST)
    bh = res.benchmarks["universe_buy_and_hold_pct"]
    res_flat = backtest.run_backtest(bars={"FLAT": flat}, initial_cash=10_000_000, costs=ZERO_COST)
    assert bh != pytest.approx(res_flat.benchmarks["universe_buy_and_hold_pct"])


# ── 10. 워크포워드 분할이 겹치지 않음 ──────────────────────────────────────

def test_walk_forward_folds_do_not_overlap():
    dates = pd.bdate_range("2022-01-03", periods=500)
    folds = backtest.make_walk_forward_folds(dates, train_days=120, test_days=60)
    assert len(folds) >= 2
    for train, test in folds:
        assert train[-1] < test[0], "학습 구간이 검증 구간보다 앞서야 한다"
    for i in range(len(folds) - 1):
        assert folds[i][1][-1] < folds[i + 1][1][0], "검증 구간끼리 겹치면 안 된다"


# ══════════════════════════════════════════════════════════════════════════
# P12 배당 전략
# ══════════════════════════════════════════════════════════════════════════

def _rising_bars(n: int = 300, start_price: float = 10_000.0, drift: float = 0.0002):
    rows = []
    px = start_price
    for _ in range(n):
        px *= (1 + drift)
        rows.append((px, px * 1.01, px * 0.99, px))
    return make_bars(rows, start="2023-01-02")


def _quarterly_divs(dates_amounts):
    return [(d, a) for d, a in dates_amounts]


def test_dividend_selection_ignores_asof_day_close():
    """선정 시점 당일 종가가 바뀌어도 선정 결과가 달라지면 안 된다 (룩어헤드 차단)."""
    bars_a = _rising_bars()
    bars_b = bars_a.copy()
    asof = bars_a.index[100]
    bars_b.loc[asof, "close"] = bars_a.loc[asof, "close"] * 5      # 당일 종가만 왜곡

    divs = {"A": [(str(d.date()), 300.0) for d in bars_a.index[:100:20]]}
    pick_a = backtest.select_dividend_universe({"A": divs["A"]}, {"A": bars_a}, asof,
                                               top_n=5, min_yield_pct=0.0, min_streak=0)
    pick_b = backtest.select_dividend_universe({"A": divs["A"]}, {"A": bars_b}, asof,
                                               top_n=5, min_yield_pct=0.0, min_streak=0)
    assert pick_a == pick_b, "asof 당일 종가가 선정에 영향을 주면 룩어헤드다"


def test_dividend_selection_applies_yield_and_streak_filters():
    bars = _rising_bars()
    asof = bars.index[200]
    # 수익률이 낮은 종목은 min_yield_pct에 걸려야 한다
    tiny = {"LOW": [(str(d.date()), 1.0) for d in bars.index[:200:40]]}
    assert backtest.select_dividend_universe(tiny, {"LOW": bars}, asof, 5, 3.0, 0) == []
    # 배당 이력이 없으면 제외
    assert backtest.select_dividend_universe({"NONE": []}, {"NONE": bars}, asof, 5, 0.0, 0) == []


def test_dividend_backtest_respects_position_cap():
    bars = {c: _rising_bars() for c in ("A", "B", "C")}
    divs = {c: [(str(d.date()), 400.0) for d in bars[c].index[:250:30]] for c in bars}
    res = backtest.run_dividend_backtest(
        bars=bars, div_records=divs, initial_cash=10_000_000,
        costs=ZERO_COST, top_n=3, rebalance_days=63, min_yield_pct=0.0, min_streak=0,
        respect_position_cap=True,
    )
    # 3종목 × 6% 상한 = 최대 18% 투자
    assert res.benchmarks["avg_invested_pct"] <= 20.0
    assert res.scenario == "dividend"


def test_dividend_backtest_has_no_daily_liquidation():
    """P9와 달리 당일 청산이 없어야 한다 — 거래 수가 리밸런스 횟수 수준이어야 한다."""
    bars = {c: _rising_bars() for c in ("A", "B")}
    divs = {c: [(str(d.date()), 400.0) for d in bars[c].index[:250:30]] for c in bars}
    res = backtest.run_dividend_backtest(
        bars=bars, div_records=divs, initial_cash=10_000_000, costs=ZERO_COST,
        top_n=2, rebalance_days=63, min_yield_pct=0.0, min_streak=0,
    )
    n_days = len(res.equity_curve)
    assert len(res.trades) < n_days / 10, "거래 수가 일수에 비례하면 데이트레이딩이다"
    assert all(t.exit_reason != "stop_loss" for t in res.trades), "배당 전략에 손절은 없다"


def test_dividend_backtest_is_deterministic():
    bars = {c: _rising_bars() for c in ("A", "B")}
    divs = {c: [(str(d.date()), 400.0) for d in bars[c].index[:250:30]] for c in bars}
    kw = dict(bars=bars, div_records=divs, initial_cash=10_000_000, costs=ZERO_COST,
              top_n=2, rebalance_days=63, min_yield_pct=0.0, min_streak=0)
    a = backtest.run_dividend_backtest(**kw)
    b = backtest.run_dividend_backtest(**kw)
    assert a.total_return_pct == pytest.approx(b.total_return_pct)
    assert len(a.trades) == len(b.trades)


# ══════════════════════════════════════════════════════════════════════════
# P13 인덱스 규칙
# ══════════════════════════════════════════════════════════════════════════

def test_index_buy_and_hold_trades_once():
    bars = {"IDX": _rising_bars(300)}
    r = backtest.run_index_backtest(bars=bars, initial_cash=10_000_000, costs=ZERO_COST,
                                    mode="buy_and_hold")
    assert r.total_return_pct > 0
    assert len(r.trades) == 1, "매수후보유는 종료 청산 1건만 남아야 한다"


def test_ma_filter_ignores_same_day_close():
    """MA 판단에 t일 종가가 새어들면 룩어헤드다."""
    base = _rising_bars(300)
    warped = base.copy()
    tgt = warped.index[250]
    warped.loc[tgt, "close"] = float(base.loc[tgt, "close"]) * 3

    a = backtest.run_index_backtest(bars={"IDX": base}, initial_cash=10_000_000,
                                    costs=ZERO_COST, mode="ma_filter", ma_period=50,
                                    dates=list(base.index[:251]))
    b = backtest.run_index_backtest(bars={"IDX": warped}, initial_cash=10_000_000,
                                    costs=ZERO_COST, mode="ma_filter", ma_period=50,
                                    dates=list(warped.index[:251]))
    # 마지막 날 진입/청산 결정이 같아야 한다 (평가 가치는 종가 왜곡으로 달라질 수 있음)
    assert [t.exit_reason for t in a.trades][:-1] == [t.exit_reason for t in b.trades][:-1]


def test_dca_tracks_contributed_capital():
    bars = {"IDX": _rising_bars(300)}
    r = backtest.run_index_backtest(bars=bars, initial_cash=1_000_000, costs=ZERO_COST,
                                    mode="dca", dca_amount=100_000, dca_interval_days=21)
    assert r.benchmarks["contributed"] > 1_000_000, "적립금이 투입 자본에 반영되어야 한다"
    # 수익률은 총투입 대비로 계산되어야 한다 (적립금을 수익으로 계상하면 안 된다)
    assert r.total_return_pct < 100


def test_blend_sleeves_sums_curves_and_capital():
    core = ([("2024-01-01", 800.0), ("2024-01-02", 900.0)], 800.0)
    sat = ([("2024-01-01", 200.0), ("2024-01-02", 100.0)], 200.0)
    out = backtest.blend_sleeves([core, sat])
    assert out["capital"] == pytest.approx(1000.0)
    assert out["final_value"] == pytest.approx(1000.0)
    assert out["total_return_pct"] == pytest.approx(0.0)


def test_blend_sleeves_handles_empty():
    assert backtest.blend_sleeves([])["total_return_pct"] == 0.0


def test_blend_sleeves_handles_mismatched_date_ranges():
    """슬리브마다 거래일이 다를 때 자본이 사라진 것처럼 보이면 안 된다 (MDD 폭주 회귀)."""
    core = ([("2024-01-01", 800.0), ("2024-01-02", 800.0), ("2024-01-04", 800.0)], 800.0)
    sat = ([("2024-01-01", 200.0), ("2024-01-03", 200.0), ("2024-01-04", 200.0)], 200.0)
    out = backtest.blend_sleeves([core, sat])
    assert out["capital"] == pytest.approx(1000.0)
    assert out["final_value"] == pytest.approx(1000.0)
    # 두 슬리브 모두 평탄한데 MDD가 생기면 정렬 버그다
    assert out["mdd_pct"] == pytest.approx(0.0), f"거래일 불일치로 MDD가 생겼다: {out['mdd_pct']}"


def test_blend_sleeves_mdd_cannot_exceed_worst_sleeve():
    """혼합 MDD는 개별 슬리브 최악값보다 나빠질 수 없다."""
    core = ([("2024-01-01", 800.0), ("2024-01-02", 640.0), ("2024-01-03", 800.0)], 800.0)
    sat = ([("2024-01-01", 200.0), ("2024-01-02", 180.0), ("2024-01-03", 200.0)], 200.0)
    out = backtest.blend_sleeves([core, sat])
    assert out["mdd_pct"] >= -20.0
