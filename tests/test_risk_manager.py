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


def test_drawdown_limit_matches_approved_policy():
    """
    승인된 리스크 한도를 코드에 고정한다.

    이 값 변경은 사람 승인 사항이다 (CLAUDE.md §4.2/§4.3). 이 테스트가 깨지면
    한도가 조용히 바뀐 것이므로, 테스트 숫자를 맞추기 전에 변경 경위부터 확인해야 한다.
    2026-08-27 사람이 15% → 30%로 변경·확정 (spec.md "최종 확정" 참조).
    """
    assert config.MAX_DRAWDOWN_PCT == 0.30
    assert config.STOP_LOSS_PCT == 0.04
    assert config.MAX_POSITION_PCT == 0.06


def test_max_drawdown_enters_sleep():
    """한도를 넘으면 휴면 모드가 켜진다 (한도값은 config에서 유도 — 메커니즘 검증)."""
    risk_manager.set_initial_capital(10_000_000)
    breach = int(10_000_000 * (1 - config.MAX_DRAWDOWN_PCT) - 1)   # 한도 바로 아래
    triggered = risk_manager.check_max_drawdown(breach)
    assert triggered is True
    assert risk_manager.SLEEP_MODE is True


def test_max_drawdown_does_not_trigger_within_limit():
    """한도 안쪽에서는 발동하지 않는다 (오탐 방지)."""
    risk_manager.exit_sleep_mode()
    risk_manager.set_initial_capital(10_000_000)
    within = int(10_000_000 * (1 - config.MAX_DRAWDOWN_PCT) + 100_000)
    assert risk_manager.check_max_drawdown(within) is False
    assert risk_manager.SLEEP_MODE is False


def test_drawdown_pct():
    risk_manager.set_initial_capital(10_000_000)
    assert risk_manager.get_drawdown_pct(9_500_000) == -5.0
