"""backtest.py 워크포워드 엔진 단위 테스트.

technical.evaluate_buy_technicals()의 신호 정확성은 tests/test_technical.py가 이미
커버하므로, 여기서는 monkeypatch로 신호를 고정해두고 백테스트 엔진 자체(진입/청산
walk-forward, 포지션 사이징, 손절 트리거, 현금 정산, 리스크 파라미터 override의
비침습성)를 검증한다.
"""

from __future__ import annotations

import pandas as pd
import pytest

import backtest
import config


def _ohlc(closes: list[float], highs=None, lows=None, opens=None, start="2024-01-02") -> pd.DataFrame:
    n = len(closes)
    idx = pd.bdate_range(start=start, periods=n)
    opens = opens or closes
    highs = highs or [c * 1.005 for c in closes]
    lows = lows or [c * 0.995 for c in closes]
    return pd.DataFrame({"Open": opens, "High": highs, "Low": lows, "Close": closes}, index=idx)


def _flat_history(n: int, price: float = 10_000.0) -> pd.DataFrame:
    return _ohlc([price] * n)


def _stocks_one(code: str = "TEST", name: str = "테스트종목") -> dict:
    return {code: {"name": name}}


@pytest.fixture(autouse=True)
def _signal_true(monkeypatch):
    """기본값: 기술적 신호 True로 고정 (개별 테스트에서 필요 시 override)."""
    monkeypatch.setattr(
        backtest.technical,
        "evaluate_buy_technicals",
        lambda code, price_history, quote, prev_day=None: {"signal": True, "reason": "forced-signal"},
    )


def test_sentiment_below_threshold_skips_without_fetching():
    calls = []

    def provider(code, total_days):
        calls.append(code)
        return _flat_history(total_days)

    result = backtest.run_backtest(
        stocks=_stocks_one(),
        sentiment_scores={"TEST": 0},  # SENTIMENT_BUY_THRESHOLD 기본값 1 미만
        days=20,
        hold_days=5,
        history_provider=provider,
    )
    assert result.trades == []
    assert result.skipped == []
    assert calls == []  # 임계값 미달이면 히스토리 조회 자체를 하지 않아야 함


def test_insufficient_history_is_recorded_as_skipped():
    def provider(code, total_days):
        return _flat_history(3)  # days+hold_days보다 훨씬 부족

    result = backtest.run_backtest(
        stocks=_stocks_one(),
        sentiment_scores={"TEST": 2},
        days=20,
        hold_days=5,
        history_provider=provider,
    )
    assert result.trades == []
    assert len(result.skipped) == 1
    assert result.skipped[0]["code"] == "TEST"
    assert result.skipped[0]["reason"] == "insufficient_price_data"


def test_no_technical_signal_produces_no_trade_and_no_skip(monkeypatch):
    monkeypatch.setattr(
        backtest.technical,
        "evaluate_buy_technicals",
        lambda *a, **k: {"signal": False, "reason": "no-signal"},
    )

    def provider(code, total_days):
        return _flat_history(total_days)

    result = backtest.run_backtest(
        stocks=_stocks_one(),
        sentiment_scores={"TEST": 2},
        days=20,
        hold_days=5,
        history_provider=provider,
    )
    assert result.trades == []
    assert result.skipped == []  # 신호 없음은 "스킵"이 아니라 단순 미거래


def test_stop_loss_triggers_on_forward_window_low_breach():
    # signal_window: 20영업일 평평한 10,000. forward_window: 진입가 10,000에서
    # 3일차 저가가 손절선(STOP_LOSS_PCT=4%) 아래로 떨어짐.
    signal_closes = [10_000.0] * 20
    forward_closes = [10_000.0, 9_900.0, 9_500.0, 9_400.0, 9_300.0]
    forward_lows = [9_950.0, 9_850.0, 9_550.0, 9_350.0, 9_250.0]  # 3일차(9,550) 손절선(9,600) 하회
    full = pd.concat([_ohlc(signal_closes), _ohlc(forward_closes, lows=forward_lows, start="2024-02-01")])

    def provider(code, total_days):
        return full

    result = backtest.run_backtest(
        stocks=_stocks_one(),
        sentiment_scores={"TEST": 2},
        days=20,
        hold_days=5,
        initial_cash=10_000_000,
        history_provider=provider,
    )
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.status == "stop_loss"
    expected_stop_price = 10_000.0 * (1 - config.STOP_LOSS_PCT)
    assert trade.sell_price == round(expected_stop_price, 2)
    assert trade.pnl < 0
    assert result.closed_count == 1
    assert result.open_count == 0


def test_open_marked_when_stop_never_breached():
    signal_closes = [10_000.0] * 20
    forward_closes = [10_000.0, 10_050.0, 10_100.0, 10_150.0, 10_200.0]
    full = pd.concat([_ohlc(signal_closes), _ohlc(forward_closes, start="2024-02-01")])

    def provider(code, total_days):
        return full

    result = backtest.run_backtest(
        stocks=_stocks_one(),
        sentiment_scores={"TEST": 2},
        days=20,
        hold_days=5,
        initial_cash=10_000_000,
        history_provider=provider,
    )
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.status == "open_marked"
    assert trade.sell_price == round(forward_closes[-1], 2)
    assert trade.pnl > 0
    assert result.closed_count == 0
    assert result.open_count == 1


def test_position_sizing_matches_confidence_formula():
    signal_closes = [10_000.0] * 20
    forward_closes = [10_000.0] * 5
    full = pd.concat([_ohlc(signal_closes), _ohlc(forward_closes, start="2024-02-01")])

    def provider(code, total_days):
        return full

    result = backtest.run_backtest(
        stocks=_stocks_one(),
        sentiment_scores={"TEST": 2},  # CONFIDENCE_SIZING[2] == 1.00
        days=20,
        hold_days=5,
        initial_cash=10_000_000,
        history_provider=provider,
    )
    expected_qty = int(10_000_000 * config.MAX_POSITION_PCT * 1.00 // 10_000.0)
    assert result.trades[0].qty == expected_qty


def test_override_params_do_not_mutate_global_config():
    signal_closes = [10_000.0] * 20
    forward_closes = [10_000.0] * 5
    full = pd.concat([_ohlc(signal_closes), _ohlc(forward_closes, start="2024-02-01")])

    def provider(code, total_days):
        return full

    original_pos_pct = config.MAX_POSITION_PCT
    original_sl_pct = config.STOP_LOSS_PCT

    result = backtest.run_backtest(
        stocks=_stocks_one(),
        sentiment_scores={"TEST": 2},
        days=20,
        hold_days=5,
        initial_cash=10_000_000,
        max_position_pct=0.20,
        stop_loss_pct=0.01,
        history_provider=provider,
    )

    # override가 이 실행에는 반영되지만
    expected_qty = int(10_000_000 * 0.20 * 1.00 // 10_000.0)
    assert result.trades[0].qty == expected_qty
    # 전역 config 상수는 절대 바뀌지 않아야 함 (실거래 리스크 상수 보호)
    assert config.MAX_POSITION_PCT == original_pos_pct
    assert config.STOP_LOSS_PCT == original_sl_pct


def test_zero_qty_when_price_exceeds_budget_produces_no_trade():
    signal_closes = [10_000_000_000.0] * 20  # 극단적으로 비싼 가격
    forward_closes = [10_000_000_000.0] * 5
    full = pd.concat([_ohlc(signal_closes), _ohlc(forward_closes, start="2024-02-01")])

    def provider(code, total_days):
        return full

    result = backtest.run_backtest(
        stocks=_stocks_one(),
        sentiment_scores={"TEST": 2},
        days=20,
        hold_days=5,
        initial_cash=10_000_000,
        history_provider=provider,
    )
    assert result.trades == []


def test_win_rate_and_total_return_aggregate_across_stocks():
    winner_signal = [10_000.0] * 20
    winner_forward = [10_000.0, 10_050.0, 10_100.0, 10_150.0, 10_200.0]
    winner = pd.concat([_ohlc(winner_signal), _ohlc(winner_forward, start="2024-02-01")])

    loser_signal = [10_000.0] * 20
    loser_forward_closes = [10_000.0, 9_900.0, 9_500.0, 9_400.0, 9_300.0]
    loser_forward_lows = [9_950.0, 9_850.0, 9_550.0, 9_350.0, 9_250.0]
    loser = pd.concat(
        [_ohlc(loser_signal), _ohlc(loser_forward_closes, lows=loser_forward_lows, start="2024-02-01")]
    )

    data = {"WIN": winner, "LOSE": loser}

    def provider(code, total_days):
        return data[code]

    result = backtest.run_backtest(
        stocks={"WIN": {"name": "승리"}, "LOSE": {"name": "패배"}},
        sentiment_scores={"WIN": 2, "LOSE": 2},
        days=20,
        hold_days=5,
        initial_cash=10_000_000,
        history_provider=provider,
    )
    assert len(result.trades) == 2
    assert result.win_rate == 50.0
    assert result.final_cash != result.initial_cash
    expected_return = (result.final_cash - result.initial_cash) / result.initial_cash * 100
    assert result.total_return_pct == pytest.approx(expected_return)
