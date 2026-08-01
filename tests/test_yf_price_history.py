"""market_data.yf_get_price_history() NaN 필터링 테스트 (P2, spec.md 참고).

yfinance는 상장정지/거래정지/데이터 공백일에 NaN 종가를 반환할 수 있는데, 이게 그대로
technical.py의 RSI/MA/변동성 계산으로 흘러들어가는 걸 막기 위한 회귀 테스트."""

import pandas as pd

import market_data


class _FakeTicker:
    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def history(self, period: str = "30d", interval: str = "1d") -> pd.DataFrame:
        return self._df


def test_yf_get_price_history_filters_nan_closes(monkeypatch):
    import yfinance as yf

    df = pd.DataFrame({"Close": [100.0, float("nan"), 102.0, float("nan"), 104.0]})
    monkeypatch.setattr(yf, "Ticker", lambda ticker: _FakeTicker(df))
    monkeypatch.setattr(market_data, "fetch_usd_krw", lambda: 1.0)

    result = market_data.yf_get_price_history("PLTR", days=5)

    assert result == [100.0, 102.0, 104.0]
    assert all(value == value for value in result)  # NaN != NaN


def test_yf_get_price_history_all_nan_returns_empty_list(monkeypatch):
    import yfinance as yf

    df = pd.DataFrame({"Close": [float("nan"), float("nan")]})
    monkeypatch.setattr(yf, "Ticker", lambda ticker: _FakeTicker(df))
    monkeypatch.setattr(market_data, "fetch_usd_krw", lambda: 1.0)

    result = market_data.yf_get_price_history("PLTR", days=5)

    assert result == []


def test_yf_get_price_history_no_nan_unaffected(monkeypatch):
    import yfinance as yf

    df = pd.DataFrame({"Close": [100.0, 101.0, 102.0]})
    monkeypatch.setattr(yf, "Ticker", lambda ticker: _FakeTicker(df))
    monkeypatch.setattr(market_data, "fetch_usd_krw", lambda: 2.0)

    result = market_data.yf_get_price_history("PLTR", days=3)

    assert result == [200.0, 202.0, 204.0]


def test_get_price_history_falls_back_to_mock_when_all_nan(monkeypatch):
    """호출자(get_price_history)의 기존 길이체크가 NaN 제거로 짧아진 리스트도
    mock 폴백으로 처리하는지 확인 — 이번 변경으로 새로 생긴 분기가 아니라 기존
    로직이 그대로 커버함을 검증하는 회귀 테스트."""
    import yfinance as yf
    import config

    monkeypatch.setattr(config, "MOCK_MODE", False)
    df = pd.DataFrame({"Close": [float("nan")] * 5})
    monkeypatch.setattr(yf, "Ticker", lambda ticker: _FakeTicker(df))
    monkeypatch.setattr(market_data, "fetch_usd_krw", lambda: 1.0)

    result = market_data.get_price_history("PLTR", session="US", days=30)

    assert len(result) >= config.RSI_PERIOD + 1
