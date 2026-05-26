from fastapi.testclient import TestClient

from backend.app.main import create_app


def make_client(tmp_path):
    app = create_app(
        db_path=str(tmp_path / "alpha_gen.sqlite3"),
        bootstrap_legacy=False,
    )
    return TestClient(app)


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
