from backend.app.store import SQLiteStore


def test_store_initializes_defaults(tmp_path):
    store = SQLiteStore(tmp_path / "alpha_gen.sqlite3", bootstrap_legacy=False)

    assert store.get_paper_cash() == 10_000_000
    assert store.list_positions() == []

    guard = store.get_daily_trade_guard()
    assert guard["codes"] == []
    assert "date" in guard


def test_store_persists_signals_and_backtests(tmp_path):
    store = SQLiteStore(tmp_path / "alpha_gen.sqlite3", bootstrap_legacy=False)

    store.save_signals(
        [
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "session": "KR",
                "sentiment_score": 2,
                "sentiment_label": "매우긍정",
                "technical_signal": True,
                "buy_signal": True,
                "current_price": 75000,
                "technical_reason": "RSI 정상",
            }
        ]
    )
    signals = store.list_recent_signals()
    assert len(signals) == 1
    assert signals[0]["stock_code"] == "005930"

    run = store.save_backtest_run({"days": 30}, {"trade_count": 3, "total_return_pct": 5.5})
    runs = store.list_backtest_runs()
    assert runs[0]["id"] == run["id"]
    assert runs[0]["summary"]["trade_count"] == 3
