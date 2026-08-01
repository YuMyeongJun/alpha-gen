import pytest
from fastapi.testclient import TestClient

import config
import market_data
from backend.app.main import create_app
from backend.app.services import TradingSafetyError, build_service_bundle


def _reload_config() -> None:
    import importlib

    importlib.reload(config)
    from market_adapters import reset_adapters

    reset_adapters()


def make_client(tmp_path):
    app = create_app(
        db_path=str(tmp_path / "alpha_gen.sqlite3"),
        bootstrap_legacy=False,
    )
    return TestClient(app)


def _configure_paper_kis_env(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("AUTO_MOCK_ON_MISSING_KIS", "false")
    monkeypatch.setenv("ALPHA_GEN_STAGE", "paper")
    monkeypatch.setenv("KIS_APP_KEY", "test-app-key")
    monkeypatch.setenv("KIS_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("ACCOUNT_NO", "12345678")
    _reload_config()
    market_data.reset_kis_token_cache()
    market_data._kis_token_blocked_until = None
    market_data._kis_api_degraded_until = None


def test_health_and_ready_endpoints(tmp_path):
    client = make_client(tmp_path)

    health = client.get("/api/health")
    ready = client.get("/api/ready")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["status"] in {"ready", "not_ready"}


def test_analysis_and_portfolio_endpoints(tmp_path):
    client = make_client(tmp_path)

    analysis = client.post("/api/analysis/refresh", json={"session": "KR", "force_refresh": True})
    assert analysis.status_code == 200
    payload = analysis.json()
    assert payload["session"] == "KR"
    assert len(payload["signals"]) >= 1

    portfolio = client.get("/api/portfolio")
    assert portfolio.status_code == 200
    assert "cash" in portfolio.json()


def test_paper_order_and_backtest_endpoints(tmp_path):
    client = make_client(tmp_path)

    order = client.post(
        "/api/orders/paper",
        json={"stock_code": "005930", "session": "KR", "side": "buy", "qty": 1},
    )
    assert order.status_code == 200
    assert order.json()["status"] == "filled"

    backtest = client.post("/api/backtests/run", json={"days": 30, "initial_cash": 10000000})
    assert backtest.status_code == 200
    assert backtest.json()["summary"]["trade_count"] >= 0


def test_safety_and_audit_endpoints(tmp_path):
    client = make_client(tmp_path)

    safety = client.get("/api/safety")
    assert safety.status_code == 200
    assert "policy" in safety.json()

    stop = client.post(
        "/api/safety/emergency-stop",
        json={"enabled": True, "reason": "테스트 정지"},
    )
    assert stop.status_code == 200
    assert stop.json()["emergency_stop"]["enabled"] is True

    blocked = client.post(
        "/api/orders/paper",
        json={"stock_code": "005930", "session": "KR", "side": "buy", "qty": 1},
    )
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "rejected"

    audit = client.get("/api/audit")
    assert audit.status_code == 200
    assert len(audit.json()["events"]) >= 1

    stage = client.post("/api/safety/stage", json={"stage": "paper"})
    assert stage.status_code == 400


def test_order_transition_endpoint(tmp_path):
    client = make_client(tmp_path)

    order = client.post(
        "/api/orders/paper",
        json={"stock_code": "005930", "session": "KR", "side": "buy", "qty": 1},
    )
    order_id = order.json()["id"]

    transitions = client.get(f"/api/orders/{order_id}/transitions")
    assert transitions.status_code == 200
    assert len(transitions.json()["transitions"]) >= 2


def test_paper_stage_portfolio_syncs_kis_balance(tmp_path, monkeypatch):
    _configure_paper_kis_env(monkeypatch)

    def fake_get_balance(session: str):
        assert session == "KR"
        return 7_500_000, [
            {
                "code": "005930",
                "name": "삼성전자",
                "qty": 10,
                "avg_price": 70000,
                "eval_price": 72000,
            }
        ]

    monkeypatch.setattr(market_data, "get_balance", fake_get_balance)

    client = make_client(tmp_path)
    sync = client.post("/api/broker/sync", params={"session": "KR"})
    assert sync.status_code == 200
    portfolio = client.get("/api/portfolio")

    assert portfolio.status_code == 200
    payload = portfolio.json()
    assert payload["cash"] == 7_500_000
    assert len(payload["positions"]) == 1
    assert payload["positions"][0]["stock_code"] == "005930"
    assert payload["positions"][0]["qty"] == 10


def test_mock_mode_portfolio_uses_internal_paper_cash(tmp_path, monkeypatch):
    _configure_paper_kis_env(monkeypatch)
    monkeypatch.setenv("MOCK_MODE", "true")
    _reload_config()

    def fake_get_balance(_session: str):
        raise AssertionError("mock mode must not call broker balance sync")

    monkeypatch.setattr(market_data, "get_balance", fake_get_balance)

    client = make_client(tmp_path)
    sync = client.post("/api/broker/sync", params={"session": "KR"})
    assert sync.status_code == 200
    portfolio = client.get("/api/portfolio")

    assert portfolio.status_code == 200
    assert portfolio.json()["cash"] == 10_000_000


def test_paper_stage_broker_sync_failure_emits_audit(tmp_path, monkeypatch):
    _configure_paper_kis_env(monkeypatch)

    def failing_get_balance(_session: str):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(market_data, "get_balance", failing_get_balance)

    client = make_client(tmp_path)
    sync = client.post("/api/broker/sync", params={"session": "KR"})
    assert sync.status_code == 200
    portfolio = client.get("/api/portfolio")

    assert portfolio.status_code == 200
    assert portfolio.json()["cash"] == 10_000_000

    audit = client.get("/api/audit")
    assert audit.status_code == 200
    events = audit.json()["events"]
    assert any(event["event_type"] == "position_sync_failed" for event in events)


def test_safety_policy_includes_usage(tmp_path):
    client = make_client(tmp_path)
    safety = client.get("/api/safety")
    usage = safety.json()["policy"]["usage"]
    assert "orders_today" in usage
    assert "live_orders_today" in usage
    assert "live_orders_cycle" in usage


def test_system_admin_endpoints(tmp_path, monkeypatch):
    import news_analyzer

    client = make_client(tmp_path)
    payload = {"confirm": True, "reason": "테스트"}

    cache = client.post("/api/system/cache/clear", json=payload)
    assert cache.status_code == 200
    assert cache.json()["cleared"] >= 0

    news_analyzer._cache["test"] = {"expires_at": news_analyzer.datetime.now(news_analyzer.KST), "result": {}}
    cache2 = client.post("/api/system/cache/clear", json=payload)
    assert cache2.status_code == 200
    assert cache2.json()["cleared"] >= 1

    token = client.post("/api/system/kis/token/refresh", json=payload)
    assert token.status_code == 200

    order = client.post(
        "/api/orders/paper",
        json={"stock_code": "005930", "session": "KR", "side": "buy", "qty": 1},
    )
    assert order.status_code == 200

    reset = client.post("/api/system/db/reset", json=payload)
    assert reset.status_code == 200
    assert "backup_path" in reset.json()

    portfolio = client.get("/api/portfolio")
    assert portfolio.json()["cash"] == 10_000_000

    audit = client.get("/api/audit")
    event_types = {event["event_type"] for event in audit.json()["events"]}
    assert "cache_cleared" in event_types
    assert "kis_token_refreshed" in event_types
    assert "db_reset" in event_types


def test_manual_order_still_succeeds_when_all_gates_pass(tmp_path):
    client = make_client(tmp_path)

    order = client.post(
        "/api/orders/manual",
        json={"stock_code": "005930", "session": "KR", "side": "buy", "qty": 1},
    )
    assert order.status_code == 200
    assert order.json()["status"] == "filled"


def test_manual_order_blocked_by_emergency_stop(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/safety/emergency-stop", json={"enabled": True, "reason": "테스트 정지"})

    order = client.post(
        "/api/orders/manual",
        json={"stock_code": "005930", "session": "KR", "side": "buy", "qty": 1},
    )
    assert order.status_code == 400


def test_manual_order_buy_blocked_when_sleep_mode(tmp_path):
    bundle = build_service_bundle(
        db_path=str(tmp_path / "alpha_gen.sqlite3"), bootstrap_legacy=False, auto_resume_worker=False
    )
    bundle.store.set_state("sleep_mode", True)
    bundle.store.set_state("sleep_reason", "테스트 드로우다운")

    with pytest.raises(TradingSafetyError):
        bundle.trading_service.place_manual_order(stock_code="005930", session="KR", side="buy", qty=1)

    assert bundle.store.get_paper_cash() == 10_000_000
    assert bundle.store.get_position("KR", "005930") is None


def test_manual_order_blocked_when_stage_not_live(tmp_path, monkeypatch):
    _configure_paper_kis_env(monkeypatch)  # MOCK_MODE=false + KIS 자격증명 → mode="live" 판정, stage 기본값 "paper"
    import order_engine

    def _must_not_be_called(*_args, **_kwargs):
        raise AssertionError("live 게이트가 브로커 호출 전에 차단해야 합니다")

    monkeypatch.setattr(order_engine, "kis_buy", _must_not_be_called)

    client = make_client(tmp_path)
    order = client.post(
        "/api/orders/manual",
        json={"stock_code": "005930", "session": "KR", "side": "buy", "qty": 1},
    )
    assert order.status_code == 400
    assert "실거래를 허용하지 않습니다" in order.json()["detail"]

    portfolio = client.get("/api/portfolio")
    assert portfolio.json()["cash"] == 10_000_000
    assert portfolio.json()["positions"] == []


def test_manual_order_blocked_when_allow_live_trading_false(tmp_path, monkeypatch):
    _configure_paper_kis_env(monkeypatch)
    import order_engine

    def _must_not_be_called(*_args, **_kwargs):
        raise AssertionError("live 게이트가 브로커 호출 전에 차단해야 합니다")

    monkeypatch.setattr(order_engine, "kis_buy", _must_not_be_called)

    client = make_client(tmp_path)
    stage = client.post("/api/safety/stage", json={"stage": "live_limited"})
    assert stage.status_code == 200

    order = client.post(
        "/api/orders/manual",
        json={"stock_code": "005930", "session": "KR", "side": "buy", "qty": 1},
    )
    assert order.status_code == 400
    assert "ALLOW_LIVE_TRADING" in order.json()["detail"]

    portfolio = client.get("/api/portfolio")
    assert portfolio.json()["cash"] == 10_000_000
    assert portfolio.json()["positions"] == []


def test_manual_order_blocked_when_live_order_limit_exceeded(tmp_path, monkeypatch):
    _configure_paper_kis_env(monkeypatch)
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")
    monkeypatch.setenv("LIVE_MAX_ORDERS_PER_DAY", "1")
    _reload_config()
    import order_engine

    def _must_not_be_called(*_args, **_kwargs):
        raise AssertionError("live 게이트가 브로커 호출 전에 차단해야 합니다")

    monkeypatch.setattr(order_engine, "kis_buy", _must_not_be_called)

    bundle = build_service_bundle(
        db_path=str(tmp_path / "alpha_gen.sqlite3"), bootstrap_legacy=False, auto_resume_worker=False
    )
    bundle.store.set_state("promotion_stage", "live_limited")
    existing = bundle.store.create_order(
        stock_code="005930",
        stock_name="삼성전자",
        session="KR",
        side="buy",
        mode="live",
        qty=1,
        requested_price=70000.0,
    )
    bundle.store.transition_order(
        existing["id"],
        to_status="filled",
        event_type="live_filled",
        message="filled",
        attempt_count=1,
        executed_price=70000.0,
    )

    with pytest.raises(TradingSafetyError):
        bundle.trading_service.place_manual_order(stock_code="005930", session="KR", side="buy", qty=1)

    assert bundle.store.get_position("KR", "005930") is None


def test_manual_order_blocked_when_daily_loss_limit_exceeded(tmp_path, monkeypatch):
    _configure_paper_kis_env(monkeypatch)
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")
    _reload_config()
    import order_engine

    def _must_not_be_called(*_args, **_kwargs):
        raise AssertionError("live 게이트가 브로커 호출 전에 차단해야 합니다")

    monkeypatch.setattr(order_engine, "kis_buy", _must_not_be_called)

    bundle = build_service_bundle(
        db_path=str(tmp_path / "alpha_gen.sqlite3"), bootstrap_legacy=False, auto_resume_worker=False
    )
    bundle.store.set_state("promotion_stage", "live_limited")
    # 기본 total_asset(10,000,000) * MAX_DAILY_LOSS_PCT(기본 0.02) = 200,000원 한도를 넘는 손실 기록
    loss_order = bundle.store.create_order(
        stock_code="005930",
        stock_name="삼성전자",
        session="KR",
        side="sell",
        mode="live",
        qty=1,
        requested_price=70000.0,
    )
    bundle.store.transition_order(
        loss_order["id"],
        to_status="filled",
        event_type="live_filled",
        message="filled",
        attempt_count=1,
        executed_price=70000.0,
        realized_pnl=-250_000.0,
    )

    with pytest.raises(TradingSafetyError):
        bundle.trading_service.place_manual_order(stock_code="005930", session="KR", side="buy", qty=1)

    assert bundle.store.get_position("KR", "005930") is None


def test_manual_order_blocked_when_consecutive_losses_exceeded(tmp_path, monkeypatch):
    _configure_paper_kis_env(monkeypatch)
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "true")
    monkeypatch.setenv("MAX_CONSECUTIVE_LOSSES", "2")
    _reload_config()
    import order_engine

    def _must_not_be_called(*_args, **_kwargs):
        raise AssertionError("live 게이트가 브로커 호출 전에 차단해야 합니다")

    monkeypatch.setattr(order_engine, "kis_buy", _must_not_be_called)

    bundle = build_service_bundle(
        db_path=str(tmp_path / "alpha_gen.sqlite3"), bootstrap_legacy=False, auto_resume_worker=False
    )
    bundle.store.set_state("promotion_stage", "live_limited")
    for i in range(2):
        loss_order = bundle.store.create_order(
            stock_code="005930",
            stock_name="삼성전자",
            session="KR",
            side="sell",
            mode="live",
            qty=1,
            requested_price=70000.0,
            client_order_id=f"loss-{i}",
        )
        bundle.store.transition_order(
            loss_order["id"],
            to_status="filled",
            event_type="live_filled",
            message="filled",
            attempt_count=1,
            executed_price=68000.0,
            realized_pnl=-2_000.0,
        )

    with pytest.raises(TradingSafetyError):
        bundle.trading_service.place_manual_order(stock_code="005930", session="KR", side="buy", qty=1)

    assert bundle.store.get_position("KR", "005930") is None


def test_db_reset_blocked_when_emergency_stop(tmp_path):
    client = make_client(tmp_path)
    stop = client.post(
        "/api/safety/emergency-stop",
        json={"enabled": True, "reason": "DB reset 차단 테스트"},
    )
    assert stop.status_code == 200
    reset = client.post(
        "/api/system/db/reset",
        json={"confirm": True, "reason": "긴급정지 중 reset 시도"},
    )
    assert reset.status_code == 400
