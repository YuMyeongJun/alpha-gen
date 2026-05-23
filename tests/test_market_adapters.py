"""market_adapters.py 단위 테스트"""

import config
import market_data
import market_adapters


def setup_function():
    market_adapters.reset_adapters()
    market_data._mock_cash = config.MOCK_INITIAL_CASH
    market_data._mock_holdings = {}


def teardown_function():
    market_adapters.reset_adapters()


def test_mock_adapter_buy_sell(monkeypatch):
    monkeypatch.setattr(config, "MOCK_MODE", True)
    adapter = market_adapters.get_adapter("KR")
    ok, msg = adapter.execute_buy("005930", 2, 75_000)
    assert ok is True
    cash, holdings = adapter.get_balance()
    assert cash == config.MOCK_INITIAL_CASH - 150_000
    assert len(holdings) == 1
    ok, pnl, msg = adapter.execute_sell("005930", 2, 80_000)
    assert ok is True
    assert pnl == 10_000
