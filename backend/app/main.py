from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config

from .models import AgentCycleRequest, AnalysisRequest, BacktestRequest, PaperOrderRequest, WorkerRequest
from .services import AgentService, AgentWorker, AnalyticsService, BacktestService, DiagnosticsService, RiskService, TradingService
from .store import SQLiteStore


def create_app(db_path: str | None = None, bootstrap_legacy: bool = True) -> FastAPI:
    store = SQLiteStore(db_path=db_path, bootstrap_legacy=bootstrap_legacy)
    risk_service = RiskService(store)
    analytics_service = AnalyticsService(store)
    trading_service = TradingService(store, risk_service)
    backtest_service = BacktestService(store)
    diagnostics_service = DiagnosticsService(store)
    agent_service = AgentService(store, analytics_service, trading_service, risk_service)
    worker = AgentWorker(store, agent_service)

    app = FastAPI(
        title="Alpha-Gen Web",
        version="1.0.0",
        description="AI analytics, backtesting, and paper-trading web backend for alpha-gen.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    frontend_dir = Path(config.FRONTEND_DIR)
    if frontend_dir.exists():
        app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")

        @app.get("/", include_in_schema=False)
        async def serve_index() -> FileResponse:
            return FileResponse(frontend_dir / "index.html")

    @app.get("/api/health")
    async def health() -> dict:
        return diagnostics_service.health()

    @app.get("/api/ready")
    async def ready() -> dict:
        return diagnostics_service.readiness()

    @app.get("/api/system/status")
    async def system_status() -> dict:
        return {
            "config": {
                "mock_mode": config.MOCK_MODE,
                "allow_live_trading": config.ALLOW_LIVE_TRADING,
                "db_path": str(store.db_path),
                "frontend_dir": str(frontend_dir),
            },
            "diagnostics": diagnostics_service.run(),
            "worker": worker.status(),
        }

    @app.get("/api/dashboard")
    async def dashboard() -> dict:
        return analytics_service.get_dashboard_data()

    @app.post("/api/analysis/refresh")
    async def refresh_analysis(payload: AnalysisRequest) -> dict:
        return analytics_service.analyze_market(
            session=payload.session,
            force_refresh=payload.force_refresh,
        )

    @app.get("/api/signals")
    async def recent_signals(limit: int = 20) -> dict:
        return {"signals": store.list_recent_signals(limit=limit)}

    @app.get("/api/portfolio")
    async def portfolio() -> dict:
        return trading_service.get_portfolio_snapshot()

    @app.get("/api/orders")
    async def orders(limit: int = 50) -> dict:
        return {"orders": store.list_recent_orders(limit=limit)}

    @app.post("/api/orders/paper")
    async def paper_order(payload: PaperOrderRequest) -> dict:
        try:
            return trading_service.place_paper_order(
                stock_code=payload.stock_code,
                session=payload.session,
                side=payload.side,
                qty=payload.qty,
                client_order_id=payload.client_order_id,
                metadata={"source": "manual_ui"},
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/backtests/run")
    async def run_backtest_route(payload: BacktestRequest) -> dict:
        return backtest_service.run(
            stocks=payload.stocks,
            sentiment_scores=payload.sentiment_scores,
            days=payload.days,
            initial_cash=payload.initial_cash,
        )

    @app.get("/api/backtests")
    async def list_backtests(limit: int = 10) -> dict:
        return {"runs": store.list_backtest_runs(limit=limit)}

    @app.get("/api/diagnostics")
    async def diagnostics() -> dict:
        return diagnostics_service.run()

    @app.post("/api/agent/cycle")
    async def agent_cycle(payload: AgentCycleRequest) -> dict:
        return agent_service.run_cycle(
            session=payload.session,
            force_refresh=payload.force_refresh,
            place_orders=payload.place_orders,
        )

    @app.get("/api/agent/worker")
    async def worker_status() -> dict:
        return worker.status()

    @app.post("/api/agent/worker/start")
    async def worker_start(payload: WorkerRequest) -> dict:
        return worker.start(
            interval_sec=payload.interval_sec,
            session=payload.session,
            place_orders=payload.place_orders,
        )

    @app.post("/api/agent/worker/stop")
    async def worker_stop() -> dict:
        return worker.stop()

    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "backend.app.main:app",
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
