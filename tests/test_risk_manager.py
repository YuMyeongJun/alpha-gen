"""risk_manager.py 단위 테스트"""

import config
import risk_manager


def setup_function():
    risk_manager.SLEEP_MODE = False
    risk_manager.SLEEP_REASON = ""
    risk_manager.set_initial_capital(10_000_000)


def test_position_size_positive_sentiment():
    qty = risk_manager.get_position_size(10_000_000, 2, 50_000)
    # 10M * 6% * 1.0 / 50000 = 12
    assert qty == 12


def test_position_size_neutral_returns_zero():
    assert risk_manager.get_position_size(10_000_000, 0, 50_000) == 0


def test_stop_loss_triggers():
    holdings = [
        {"code": "005930", "name": "삼성", "qty": 1, "avg_price": 100_000, "eval_price": 95_000},
    ]
    targets = risk_manager.check_stop_loss(holdings)
    assert len(targets) == 1
    assert targets[0]["loss_pct"] <= -4


def test_max_drawdown_enters_sleep():
    risk_manager.set_initial_capital(10_000_000)
    triggered = risk_manager.check_max_drawdown(8_400_000)  # -16%
    assert triggered is True
    assert risk_manager.SLEEP_MODE is True


def test_drawdown_pct():
    risk_manager.set_initial_capital(10_000_000)
    assert risk_manager.get_drawdown_pct(9_500_000) == -5.0
