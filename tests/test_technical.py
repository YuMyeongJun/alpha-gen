"""technical.py 단위 테스트"""

import config
import technical


def test_calc_rsi_range():
    prices = [100 + i * 0.5 for i in range(30)]
    rsi = technical.calc_rsi(prices, period=14)
    assert rsi is not None
    assert 0 <= rsi <= 100


def test_calc_ma():
    prices = list(range(100, 130))
    ma = technical.calc_ma(prices, period=20)
    assert ma == sum(prices[-20:]) / 20


def test_volatility_target():
    target = technical.calc_volatility_target(100_000, 105_000, 95_000)
    # 100000 + (10000 * 0.5) = 105000
    assert target == 105_000


def test_evaluate_buy_technicals_without_breakout(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_VOLATILITY_BREAKOUT", False)
    history = [100_000.0] * 30
    quote = {"current_price": 100_000, "open_price": 100_000}
    result = technical.evaluate_buy_technicals("005930", history, quote)
    assert result["volatility"] is None
    assert "RSI" in result["reason"]


def test_evaluate_buy_technicals_breakout_blocks():
    history = [100_000.0] * 30
    quote = {"current_price": 90_000, "open_price": 100_000}
    prev_day = {"prev_high": 105_000, "prev_low": 95_000}
    result = technical.evaluate_buy_technicals(
        "005930", history, quote, prev_day=prev_day
    )
    # target = 100000 + 5000 = 105000, current 90000 < target
    assert result["signal"] is False
    assert "변동성 미돌파" in result["reason"]
