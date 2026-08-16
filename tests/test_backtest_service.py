"""backend/app/services.py의 BacktestService 래퍼 테스트 (기존 커버리지 0건).

backtest.run_backtest()는 monkeypatch로 대체해 실네트워크(yfinance) 호출 없이
서비스 계층의 책임(종목 유니버스 필터링, summary 계산, DB 영속화)만 검증한다.
run_backtest 자체의 워크포워드/손절 로직은 tests/test_backtest.py가 커버한다.
"""

from __future__ import annotations

import pytest

import backend.app.services as services
import config
from backend.app.store import SQLiteStore
from backtest import BacktestResult, BacktestTrade


@pytest.fixture()
def store(tmp_path):
    return SQLiteStore(db_path=str(tmp_path / "alpha_gen.sqlite3"), bootstrap_legacy=False)


def test_run_filters_stock_universe_to_requested_codes(monkeypatch, store):
    captured = {}

    def fake_run_backtest(*, stocks, sentiment_scores, days, initial_cash):
        captured["stocks"] = stocks
        return BacktestResult(initial_cash=initial_cash or 0, final_cash=initial_cash or 0)

    monkeypatch.setattr(services, "run_backtest", fake_run_backtest)

    svc = services.BacktestService(store)
    svc.run(stocks=["005930"], sentiment_scores=None, days=30, initial_cash=1_000_000)

    assert list(captured["stocks"].keys()) == ["005930"]


def test_run_ignores_unknown_stock_codes(monkeypatch, store):
    captured = {}

    def fake_run_backtest(*, stocks, sentiment_scores, days, initial_cash):
        captured["stocks"] = stocks
        return BacktestResult(initial_cash=initial_cash or 0, final_cash=initial_cash or 0)

    monkeypatch.setattr(services, "run_backtest", fake_run_backtest)

    svc = services.BacktestService(store)
    svc.run(stocks=["NOT_A_REAL_CODE"], sentiment_scores=None, days=30, initial_cash=1_000_000)

    assert captured["stocks"] == {}


def test_run_uses_full_universe_when_stocks_omitted(monkeypatch, store):
    captured = {}

    def fake_run_backtest(*, stocks, sentiment_scores, days, initial_cash):
        captured["stocks"] = stocks
        return BacktestResult(initial_cash=initial_cash or 0, final_cash=initial_cash or 0)

    monkeypatch.setattr(services, "run_backtest", fake_run_backtest)

    svc = services.BacktestService(store)
    svc.run(stocks=None, sentiment_scores=None, days=30, initial_cash=1_000_000)

    assert captured["stocks"] is None


def test_run_computes_summary_from_trades(monkeypatch, store):
    trades = [
        BacktestTrade(
            code="005930", name="삼성전자", entry_date="2024-01-02", exit_date="2024-01-05",
            buy_price=70_000, sell_price=72_000, qty=10, pnl=20_000, status="open_marked", reason="r",
        ),
        BacktestTrade(
            code="000660", name="SK하이닉스", entry_date="2024-01-02", exit_date="2024-01-04",
            buy_price=150_000, sell_price=144_000, qty=5, pnl=-30_000, status="stop_loss", reason="r",
        ),
    ]
    result = BacktestResult(
        initial_cash=10_000_000, final_cash=9_990_000, trades=trades,
        win_rate=50.0, total_return_pct=-0.1, closed_count=1, open_count=1,
    )
    monkeypatch.setattr(services, "run_backtest", lambda **kw: result)

    svc = services.BacktestService(store)
    stored = svc.run(stocks=None, sentiment_scores=None, days=30, initial_cash=10_000_000)

    summary = stored["summary"]
    assert summary["trade_count"] == 2
    assert summary["gross_pnl"] == -10_000
    assert summary["best_trade"] == 20_000
    assert summary["worst_trade"] == -30_000
    assert summary["win_rate"] == 50.0


def test_run_persists_record_retrievable_from_store(monkeypatch, store):
    monkeypatch.setattr(
        services, "run_backtest",
        lambda **kw: BacktestResult(initial_cash=1_000_000, final_cash=1_000_000),
    )

    svc = services.BacktestService(store)
    stored = svc.run(stocks=None, sentiment_scores=None, days=15, initial_cash=1_000_000)

    assert "id" in stored
    runs = store.list_backtest_runs()
    assert any(r["id"] == stored["id"] for r in runs)
