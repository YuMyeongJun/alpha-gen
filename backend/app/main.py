from __future__ import annotations

import secrets
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config

from .models import (
    AddStockRequest,
    AdminActionRequest,
    AgentCycleRequest,
    AnalysisRequest,
    BacktestRequest,
    EmergencyStopRequest,
    ManualOrderRequest,
    ManualPositionRequest,
    PaperOrderRequest,
    PromotionStageRequest,
    WorkerRequest,
)
from .services import SystemAdminService, TradingSafetyError, build_service_bundle



# ── 인증 (P5) ──────────────────────────────────────────────────────────────

AUTH_EXEMPT_PATHS = frozenset({"/api/health", "/api/ready"})
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", ""})


def ensure_bind_is_safe(host: str, token: str) -> None:
    """
    루프백 밖으로 바인딩하는데 토큰이 없으면 기동을 거부한다.

    이 API는 `/api/orders/manual`(실계좌 주문)과 `/api/safety/emergency-stop`
    (긴급정지 해제)을 노출한다. 인증 없이 네트워크에 열면 곧바로 자산 탈취 경로다.
    """
    if str(host).strip().lower() in _LOOPBACK_HOSTS:
        return
    if not token:
        raise RuntimeError(
            f"ALPHA_GEN_HOST={host} 는 루프백이 아닙니다. "
            "API_AUTH_TOKEN 을 설정하지 않으면 기동할 수 없습니다."
        )


async def verify_token(request: Request) -> None:
    """`API_AUTH_TOKEN`이 설정된 경우에만 강제한다 (미설정 시 기존 동작 유지)."""
    token = config.API_AUTH_TOKEN
    if not token:
        return
    path = request.url.path
    if not path.startswith("/api/") or path in AUTH_EXEMPT_PATHS:
        return
    header = request.headers.get("Authorization", "")
    scheme, _, presented = header.partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(presented.strip(), token):
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")


def create_app(db_path: str | None = None, bootstrap_legacy: bool = True, auto_resume_worker: bool = True) -> FastAPI:
    bundle = build_service_bundle(db_path=db_path, bootstrap_legacy=bootstrap_legacy, auto_resume_worker=auto_resume_worker)
    store = bundle.store
    risk_service = bundle.risk_service
    safety_service = bundle.safety_service
    analytics_service = bundle.analytics_service
    trading_service = bundle.trading_service
    backtest_service = bundle.backtest_service
    diagnostics_service = bundle.diagnostics_service
    agent_service = bundle.agent_service
    worker = bundle.worker
    system_admin = SystemAdminService(store, safety_service, worker)

    app = FastAPI(
        dependencies=[Depends(verify_token)],
        title="Alpha-Gen Web",
        version="1.0.0",
        description="AI analytics, backtesting, and paper-trading web backend for alpha-gen.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in config.API_CORS_ORIGINS.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    frontend_dir = Path(config.FRONTEND_DIR)
    dist_dir = frontend_dir / "dist"
    serve_dir = dist_dir if (dist_dir / "index.html").exists() else frontend_dir
    index_path = serve_dir / "index.html" if (serve_dir / "index.html").exists() else None

    if index_path is not None:
        assets_dir = serve_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend_assets")

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
                "mock_mode_reason": config.MOCK_MODE_REASON,
                "claude_model": config.CLAUDE_MODEL,
                "claude_model_deprecated": config.CLAUDE_MODEL_DEPRECATED,
                "allow_live_trading": config.ALLOW_LIVE_TRADING,
                "operating_stage": safety_service.get_stage(),
                "auto_order_enabled": safety_service.get_policy()["auto_orders_enabled"],
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
    async def recent_signals(limit: int = 50) -> dict:
        analytics_service.ensure_signals_fresh_background()
        return {"signals": store.list_recent_signals(limit=limit)}

    @app.get("/api/portfolio")
    async def portfolio() -> dict:
        return trading_service.get_portfolio_snapshot()

    @app.post("/api/broker/sync")
    async def broker_sync(session: str = "KR") -> dict:
        trading_service.sync_live_positions_from_broker(session, source="manual")
        return trading_service.get_portfolio_snapshot()

    @app.get("/api/orders")
    async def orders(limit: int = 50) -> dict:
        return {"orders": store.list_recent_orders(limit=limit)}

    @app.get("/api/orders/{order_id}/transitions")
    async def order_transitions(order_id: str, limit: int = 50) -> dict:
        return {"transitions": store.list_order_transitions(order_id=order_id, limit=limit)}

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

    @app.post("/api/orders/manual")
    async def manual_order(payload: ManualOrderRequest) -> dict:
        """UI에서 사용자가 직접 누르는 매수/매도. ensure_order_allowed()로 전체 안전게이트 적용, KIS 실행 시도."""
        try:
            return trading_service.place_manual_order(
                stock_code=payload.stock_code,
                session=payload.session,
                side=payload.side,
                qty=payload.qty,
                metadata={"source": "manual_ui"},
            )
        except (ValueError, TradingSafetyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/portfolio/position/{session}/{stock_code}")
    async def remove_position(session: str, stock_code: str) -> dict:
        """한투 앱 등 외부에서 이미 매도한 포지션을 DB 추적에서 제거합니다."""
        store.remove_position(session, stock_code.upper())
        return {"removed": True, "session": session, "stock_code": stock_code.upper()}

    @app.post("/api/portfolio/position/import")
    async def import_position(payload: ManualPositionRequest) -> dict:
        """한투 앱 등 외부에서 보유 중인 포지션을 수동으로 시스템에 등록합니다."""
        try:
            return trading_service.import_manual_position(
                stock_code=payload.stock_code,
                session=payload.session,
                qty=payload.qty,
                avg_price=payload.avg_price,
                stock_name=payload.stock_name,
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

    @app.get("/api/safety")
    async def safety_status() -> dict:
        return {
            "policy": safety_service.get_policy(),
            "audit": store.list_audit_events(limit=20),
        }

    @app.post("/api/risk/sleep-mode/exit")
    async def exit_sleep_mode() -> dict:
        """리스크 휴면 모드 수동 해제"""
        return risk_service.exit_sleep_mode()

    @app.post("/api/risk/capital/reset")
    async def reset_initial_capital() -> dict:
        """현재 총자산을 기준 자본으로 재설정 + 휴면 모드 해제
        실제 투자 자본이 페이퍼 초기값(1000만원)과 다를 때 드로우다운 기준을 바로잡는다."""
        return risk_service.reset_initial_capital()

    @app.post("/api/system/equity/clear")
    async def clear_equity(payload: AdminActionRequest) -> dict:
        """자산 추이 기록(가라 데이터 포함) 전체 삭제"""
        if not payload.confirm:
            raise HTTPException(status_code=400, detail="confirm must be true")
        cleared = store.clear_equity_snapshots()
        return {"cleared": cleared, "message": f"자산 추이 {cleared}건 삭제 완료"}

    @app.post("/api/safety/emergency-stop")
    async def update_emergency_stop(payload: EmergencyStopRequest) -> dict:
        return {
            "emergency_stop": safety_service.set_emergency_stop(
                enabled=payload.enabled,
                reason=payload.reason,
            ),
            "policy": safety_service.get_policy(),
        }

    @app.post("/api/safety/stage")
    async def update_stage(payload: PromotionStageRequest) -> dict:
        try:
            stage = safety_service.set_stage(payload.stage)
        except TradingSafetyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"stage": stage, "policy": safety_service.get_policy()}

    @app.get("/api/audit")
    async def audit_events(limit: int = 50) -> dict:
        return {"events": store.list_audit_events(limit=limit)}

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

    @app.post("/api/system/cache/clear")
    async def clear_system_cache(payload: AdminActionRequest) -> dict:
        if not payload.confirm:
            raise HTTPException(status_code=400, detail="confirm must be true")
        return system_admin.clear_sentiment_cache(reason=payload.reason)

    @app.post("/api/system/kis/token/refresh")
    async def refresh_kis_token(payload: AdminActionRequest) -> dict:
        if not payload.confirm:
            raise HTTPException(status_code=400, detail="confirm must be true")
        try:
            return system_admin.refresh_kis_token(reason=payload.reason)
        except TradingSafetyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/system/db/reset")
    async def reset_system_db(payload: AdminActionRequest) -> dict:
        if not payload.confirm:
            raise HTTPException(status_code=400, detail="confirm must be true")
        try:
            return system_admin.reset_database(reason=payload.reason)
        except TradingSafetyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ── Claude API 비용 모니터링 ───────────────────────────────────────────────

    @app.get("/api/system/claude/usage")
    async def claude_usage_stats() -> dict:
        """Claude API 사용량 및 비용 통계 (서버 메모리 기반, 재시작 시 초기화)."""
        try:
            import claude_usage
            today = claude_usage.today_summary()
            session_data = claude_usage.session_summary()
            history = claude_usage.all_days()
            monthly_est = claude_usage.estimate_monthly_usd()
        except Exception:
            today = session_data = {}
            history = []
            monthly_est = 0.0
        return {
            "today": today,
            "session": session_data,
            "history": history,
            "monthly_estimate_usd": monthly_est,
            "alert_threshold_usd": config.CLAUDE_DAILY_COST_ALERT_USD,
        }

    # ── 종목 관리 ──────────────────────────────────────────────────────────────

    @app.get("/api/stocks")
    async def list_stocks() -> dict:
        """config 기본 종목 + 커스텀 추가 종목 전체 목록."""
        custom = store.get_custom_stocks()
        custom_keys = {f"{s['session']}:{s['code']}" for s in custom}

        kr_list = [
            {
                "code": code,
                "name": info["name"],
                "session": "KR",
                "source": "config",
                "keywords": info.get("keywords", []),
            }
            for code, info in config.KR_STOCKS.items()
            if f"KR:{code}" not in custom_keys
        ]
        us_list = [
            {
                "code": code,
                "name": info["name"],
                "session": "US",
                "source": "config",
                "keywords": info.get("keywords", []),
                "exchange": info.get("exchange", "NASD"),
            }
            for code, info in config.US_STOCKS.items()
            if f"US:{code}" not in custom_keys
        ]
        custom_list = [{**s, "source": "custom"} for s in custom]
        return {
            "stocks": kr_list + us_list + custom_list,
            "custom_count": len(custom),
        }

    @app.post("/api/stocks")
    async def add_stock(payload: AddStockRequest) -> dict:
        """커스텀 종목 추가 (코드 중복 시 덮어씀)."""
        stock = store.add_custom_stock(
            code=payload.code,
            name=payload.name,
            session=payload.session,
            keywords=payload.keywords,
            exchange=payload.exchange,
            news_topic=payload.news_topic,
        )
        store.add_audit_event(
            scope="system",
            event_type="custom_stock_added",
            severity="info",
            message=f"커스텀 종목 추가: {payload.name}({payload.code}) [{payload.session}]",
            session=payload.session,
            stock_code=payload.code.upper(),
        )
        return {"added": True, "stock": stock}

    @app.delete("/api/stocks/{session}/{code}")
    async def remove_stock(session: str, code: str) -> dict:
        """커스텀 추가 종목 삭제 (config 기본 종목은 삭제 불가)."""
        removed = store.remove_custom_stock(code=code, session=session.upper())
        if not removed:
            raise HTTPException(status_code=404, detail="커스텀 종목으로 등록된 종목이 아닙니다.")
        store.add_audit_event(
            scope="system",
            event_type="custom_stock_removed",
            severity="info",
            message=f"커스텀 종목 삭제: {code.upper()} [{session.upper()}]",
            session=session.upper(),
            stock_code=code.upper(),
        )
        return {"removed": True, "code": code.upper(), "session": session.upper()}

    if index_path is not None:

        @app.get("/", include_in_schema=False)
        async def serve_index() -> FileResponse:
            return FileResponse(index_path)

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str) -> FileResponse:
            if full_path.startswith("api/") or full_path == "api":
                raise HTTPException(status_code=404, detail="Not found")
            return FileResponse(index_path)

    return app


app = create_app()


def main() -> None:
    ensure_bind_is_safe(config.WEB_HOST, config.API_AUTH_TOKEN)
    uvicorn.run(
        "backend.app.main:app",
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
