"""
KIS 모의투자 E2E 스모크 테스트

실행 조건:
  - config.MOCK_MODE = False
  - KIS_APP_KEY / KIS_APP_SECRET / ACCOUNT_NO 가 placeholder 가 아님

로컬 E2E:
  MOCK_MODE=False 로 config 설정 후
  python -m pytest tests/test_kis_integration.py -v -s
  또는 python scripts/kis_smoke_test.py
"""

import pytest

import config


def _kis_credentials_configured() -> bool:
    placeholders = ("여기에", "your_", "YOUR_")
    fields = (config.KIS_APP_KEY, config.KIS_APP_SECRET, config.ACCOUNT_NO)
    if config.MOCK_MODE:
        return False
    return all(f and not any(p in str(f) for p in placeholders) for f in fields)


def _require_kis_integration() -> None:
    if not _kis_credentials_configured():
        pytest.skip("KIS 모의투자 API 키 미설정 (MOCK_MODE=True 또는 placeholder)")


def test_kis_oauth_token():
    _require_kis_integration()
    import market_data

    token = market_data._get_kis_token()
    assert token
    assert len(token) > 20


def test_kis_balance_smoke():
    _require_kis_integration()
    import market_data

    cash, holdings = market_data.kis_get_balance()
    assert isinstance(cash, int)
    assert cash >= 0
    assert isinstance(holdings, list)


def test_kis_price_and_history_smoke():
    _require_kis_integration()
    import market_data

    code = next(iter(config.KR_STOCKS))
    quote = market_data.kis_get_price(code)
    assert quote["current_price"] > 0

    hist = market_data.kis_get_price_history(code, days=10)
    assert isinstance(hist, list)
    assert len(hist) >= 1


def test_kis_e2e_skip_message_when_mock():
    """Mock 모드에서는 integration 테스트가 skip 되는 것이 정상"""
    if config.MOCK_MODE:
        assert not _kis_credentials_configured()
