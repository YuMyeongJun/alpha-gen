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


def test_store_tracks_order_transitions_and_audit_events(tmp_path):
    store = SQLiteStore(tmp_path / "alpha_gen.sqlite3", bootstrap_legacy=False)

    order = store.create_order(
        stock_code="005930",
        stock_name="삼성전자",
        session="KR",
        side="buy",
        mode="paper",
        qty=1,
        requested_price=75_000,
        client_order_id="paper:005930:1",
        metadata={"source": "test"},
    )
    assert order["status"] == "intent"

    updated = store.transition_order(
        order["id"],
        to_status="filled",
        event_type="paper_filled",
        message="Paper order filled",
        attempt_count=1,
        executed_price=75_000,
        realized_pnl=None,
        metadata={"source": "test", "paper_fill": True},
    )
    assert updated["status"] == "filled"

    transitions = store.list_order_transitions(order_id=order["id"])
    assert transitions[0]["to_status"] == "filled"
    assert transitions[-1]["to_status"] == "intent"

    event = store.add_audit_event(
        scope="safety",
        event_type="promotion_stage_changed",
        severity="info",
        message="운영 단계 변경: paper",
        payload={"stage": "paper"},
    )
    events = store.list_audit_events(limit=10)
    assert events[0]["event_type"] == event["event_type"]
