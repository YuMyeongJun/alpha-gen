from __future__ import annotations

import importlib
import platform
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import config
import market_data
import news_analyzer
import risk_manager
import technical
from backtest import run_backtest

from .store import SQLiteStore


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_timestamp_after(seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=seconds)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_session(session: str) -> str:
    if session == "AUTO":
        detected = market_data.get_market_session()
        return "KR" if detected == "CLOSED" else detected
    return session


class RiskService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self._sync_from_store()

    def _sync_from_store(self) -> None:
        risk_manager.SLEEP_MODE = bool(self.store.get_state("sleep_mode", False))
        risk_manager.SLEEP_REASON = str(self.store.get_state("sleep_reason", ""))
        initial_capital = int(self.store.get_state("initial_capital", config.TOTAL_CAPITAL))
        risk_manager.set_initial_capital(initial_capital)

    def _sync_to_store(self) -> None:
        self.store.set_state("sleep_mode", risk_manager.SLEEP_MODE)
        self.store.set_state("sleep_reason", risk_manager.SLEEP_REASON)
        self.store.set_state("initial_capital", risk_manager.INITIAL_CAPITAL)

    def get_total_asset(self) -> float:
        cash = self.store.get_paper_cash()
        positions = self.store.list_positions()
        return cash + sum(float(item["last_price"]) * int(item["qty"]) for item in positions)

    def get_summary(self) -> dict[str, Any]:
        self._sync_from_store()
        positions = self.store.list_positions()
        holdings = [
            {
                "code": item["stock_code"],
                "name": item["stock_name"],
                "qty": item["qty"],
                "avg_price": item["avg_price"],
                "eval_price": item["last_price"],
            }
            for item in positions
        ]
        summary = risk_manager.get_risk_summary(int(self.get_total_asset()), holdings)
        self._sync_to_store()
        return summary

    def update_drawdown(self) -> dict[str, Any]:
        self._sync_from_store()
        risk_manager.check_max_drawdown(int(self.get_total_asset()))
        self._sync_to_store()
        return self.get_summary()

    def can_trade(self) -> bool:
        self._sync_from_store()
        return not risk_manager.SLEEP_MODE


class AnalyticsService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def analyze_market(self, session: str = "AUTO", force_refresh: bool = False) -> dict[str, Any]:
        resolved = resolve_session(session)
        if force_refresh:
            topic_results = {
                topic: news_analyzer.analyze_topic(topic, force_refresh=True)
                for topic in config.NEWS_TOPICS
            }
        else:
            topic_results = news_analyzer.analyze_all_topics()
        self.store.save_sentiments(topic_results)
        self.store.set_state("last_news_fetch", utc_timestamp())

        signals: list[dict[str, Any]] = []
        for stock_code, stock_info in market_data.get_target_stocks_for_session(resolved).items():
            quote = market_data.get_price(stock_code, resolved)
            history = market_data.get_price_history(stock_code, session=resolved, days=30)
            prev_day = (
                market_data.get_prev_day(stock_code, resolved)
                if config.ENABLE_VOLATILITY_BREAKOUT
                else None
            )
            sentiment = news_analyzer.get_stock_sentiment(stock_code, topic_results)
            technicals = technical.evaluate_buy_technicals(
                stock_code,
                history,
                quote,
                prev_day=prev_day,
            )
            signal = {
                "stock_code": stock_code,
                "stock_name": stock_info["name"],
                "session": resolved,
                "sentiment_score": sentiment["score"],
                "sentiment_label": sentiment["label"],
                "sentiment_reason": sentiment["reason"],
                "technical_signal": technicals["signal"],
                "technical_reason": technicals["reason"],
                "buy_signal": sentiment["score"] >= config.SENTIMENT_BUY_THRESHOLD and technicals["signal"],
                "current_price": quote["current_price"],
                "quote": quote,
                "sentiment": sentiment,
                "technical": technicals,
                "analyzed_at": utc_timestamp(),
            }
            self.store.update_position_price(resolved, stock_code, quote["current_price"])
            signals.append(signal)

        self.store.save_signals(signals)
        self.store.record_equity(
            total_asset=self._total_asset(),
            cash=self.store.get_paper_cash(),
            session=resolved,
            note="analysis_refresh" if force_refresh else "analysis_cycle",
        )
        return {
            "session": resolved,
            "signals": signals,
            "topics": topic_results,
            "force_refresh": force_refresh,
        }

    def _total_asset(self) -> float:
        cash = self.store.get_paper_cash()
        positions = self.store.list_positions()
        return cash + sum(float(item["last_price"]) * int(item["qty"]) for item in positions)

    def get_dashboard_data(self) -> dict[str, Any]:
        latest_signals = self.store.list_recent_signals(limit=20)
        positions = self.store.list_positions()
        for position in positions:
            try:
                quote = market_data.get_price(position["stock_code"], position["session"])
                self.store.update_position_price(position["session"], position["stock_code"], quote["current_price"])
                position["last_price"] = quote["current_price"]
            except Exception:
                continue
        cash = self.store.get_paper_cash()
        total = cash + sum(float(item["last_price"]) * int(item["qty"]) for item in positions)
        return {
            "signals": latest_signals,
            "sentiments": self.store.latest_sentiments(),
            "positions": positions,
            "cash": cash,
            "total_asset": total,
            "equity": self.store.list_equity(limit=120),
            "orders": self.store.list_recent_orders(limit=20),
            "worker": self.store.get_state("worker_state", {}),
        }


class TradingService:
    def __init__(self, store: SQLiteStore, risk_service: RiskService) -> None:
        self.store = store
        self.risk_service = risk_service

    def _stock_name(self, stock_code: str, session: str) -> str:
        stocks = market_data.get_target_stocks_for_session(session)
        return stocks.get(stock_code, {}).get("name", stock_code)

    def _guard_live_trading(self) -> None:
        if not config.ALLOW_LIVE_TRADING:
            raise ValueError("실거래는 비활성화되어 있습니다. ALLOW_LIVE_TRADING=true 로 명시적으로 열어야 합니다.")

    def place_paper_order(
        self,
        *,
        stock_code: str,
        session: str,
        side: str,
        qty: int,
        client_order_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if qty <= 0:
            raise ValueError("수량은 1 이상이어야 합니다.")
        if session not in {"KR", "US"}:
            raise ValueError("세션은 KR 또는 US 여야 합니다.")

        quote = market_data.get_price(stock_code, session)
        price = float(quote["current_price"])
        order = self.store.create_order(
            stock_code=stock_code,
            stock_name=self._stock_name(stock_code, session),
            session=session,
            side=side,
            mode="paper",
            qty=qty,
            requested_price=price,
            client_order_id=client_order_id,
            metadata=metadata,
        )

        attempts = 0
        last_error = ""
        while attempts < 2:
            attempts += 1
            try:
                result = self._fill_paper_order(
                    stock_code=stock_code,
                    session=session,
                    side=side,
                    qty=qty,
                    price=price,
                )
                updated = self.store.update_order(
                    order["id"],
                    status="filled",
                    message="Paper order filled",
                    attempt_count=attempts,
                    executed_price=price,
                    realized_pnl=result["realized_pnl"],
                    metadata={**(metadata or {}), "paper_fill": True},
                )
                self.store.add_fill(order["id"], stock_code, qty, price, result["realized_pnl"])
                self.store.record_equity(
                    total_asset=self.risk_service.get_total_asset(),
                    cash=self.store.get_paper_cash(),
                    session=session,
                    note=f"paper_{side}",
                )
                updated["portfolio"] = self.get_portfolio_snapshot()
                return updated
            except ValueError as exc:
                last_error = str(exc)

        return self.store.update_order(
            order["id"],
            status="rejected",
            message=last_error or "Paper order rejected",
            attempt_count=attempts,
            metadata=metadata or {},
        )

    def _fill_paper_order(
        self,
        *,
        stock_code: str,
        session: str,
        side: str,
        qty: int,
        price: float,
    ) -> dict[str, Any]:
        cash = self.store.get_paper_cash()
        stock_name = self._stock_name(stock_code, session)
        position = self.store.get_position(session, stock_code)

        if side == "buy":
            cost = price * qty
            if cash < cost:
                raise ValueError(f"잔고 부족: 필요 {int(cost):,}원 / 보유 {int(cash):,}원")
            current_qty = int(position["qty"]) if position else 0
            current_avg = float(position["avg_price"]) if position else 0.0
            total_qty = current_qty + qty
            avg_price = ((current_avg * current_qty) + (price * qty)) / total_qty
            self.store.set_paper_cash(cash - cost)
            self.store.upsert_position(session, stock_code, stock_name, total_qty, avg_price, price)
            return {"realized_pnl": None}

        if position is None:
            raise ValueError("매도할 보유 수량이 없습니다.")

        held_qty = int(position["qty"])
        if held_qty < qty:
            raise ValueError(f"보유 수량 부족: 보유 {held_qty}주 / 요청 {qty}주")

        avg_price = float(position["avg_price"])
        realized_pnl = (price - avg_price) * qty
        remaining_qty = held_qty - qty
        self.store.set_paper_cash(cash + (price * qty))
        if remaining_qty == 0:
            self.store.remove_position(session, stock_code)
        else:
            self.store.upsert_position(session, stock_code, stock_name, remaining_qty, avg_price, price)
        return {"realized_pnl": realized_pnl}

    def place_live_order(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self._guard_live_trading()
        raise NotImplementedError("실거래 인터페이스는 준비되었지만 1차 범위에서는 비활성화되어 있습니다.")

    def auto_buy_from_signals(self, signals: list[dict[str, Any]], session: str) -> list[dict[str, Any]]:
        if not self.risk_service.can_trade():
            return []
        orders: list[dict[str, Any]] = []
        for signal in signals:
            if not signal["buy_signal"]:
                continue
            if self.store.has_bought_today(signal["stock_code"]):
                continue
            total_asset = int(self.risk_service.get_total_asset())
            qty = risk_manager.get_position_size(
                total_asset,
                signal["sentiment_score"],
                int(signal["current_price"]),
            )
            if qty <= 0:
                continue
            order = self.place_paper_order(
                stock_code=signal["stock_code"],
                session=session,
                side="buy",
                qty=qty,
                metadata={"source": "agent_cycle"},
            )
            if order["status"] == "filled":
                self.store.mark_bought_today(signal["stock_code"])
                orders.append(order)
        return orders

    def run_stop_loss_cycle(self) -> list[dict[str, Any]]:
        positions = self.store.list_positions()
        if not positions:
            return []
        holdings = []
        for position in positions:
            quote = market_data.get_price(position["stock_code"], position["session"])
            self.store.update_position_price(position["session"], position["stock_code"], quote["current_price"])
            holdings.append(
                {
                    "code": position["stock_code"],
                    "name": position["stock_name"],
                    "qty": position["qty"],
                    "avg_price": position["avg_price"],
                    "eval_price": quote["current_price"],
                    "session": position["session"],
                }
            )
        stop_targets = risk_manager.check_stop_loss(holdings)
        executed = []
        for target in stop_targets:
            executed.append(
                self.place_paper_order(
                    stock_code=target["code"],
                    session=target["session"],
                    side="sell",
                    qty=int(target["qty"]),
                    metadata={"source": "stop_loss", "loss_pct": target["loss_pct"]},
                )
            )
        return executed

    def get_portfolio_snapshot(self) -> dict[str, Any]:
        positions = self.store.list_positions()
        cash = self.store.get_paper_cash()
        total_asset = cash + sum(float(item["last_price"]) * int(item["qty"]) for item in positions)
        risk_summary = self.risk_service.get_summary()
        return {
            "cash": cash,
            "positions": positions,
            "total_asset": total_asset,
            "equity": self.store.list_equity(limit=120),
            "orders": self.store.list_recent_orders(limit=50),
            "risk": risk_summary,
        }


class BacktestService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def run(self, *, stocks: list[str] | None, sentiment_scores: dict[str, int] | None, days: int, initial_cash: int | None) -> dict[str, Any]:
        selected_stocks = None
        if stocks:
            universe = {**config.KR_STOCKS, **config.US_STOCKS}
            selected_stocks = {code: universe[code] for code in stocks if code in universe}
        result = run_backtest(
            stocks=selected_stocks,
            sentiment_scores=sentiment_scores,
            days=days,
            initial_cash=initial_cash,
        )
        trades = [trade.__dict__ for trade in result.trades]
        gross_pnl = sum(trade["pnl"] for trade in trades)
        summary = {
            "initial_cash": result.initial_cash,
            "final_cash": result.final_cash,
            "total_return_pct": result.total_return_pct,
            "win_rate": result.win_rate,
            "trade_count": len(trades),
            "gross_pnl": gross_pnl,
            "best_trade": max((trade["pnl"] for trade in trades), default=0),
            "worst_trade": min((trade["pnl"] for trade in trades), default=0),
            "trades": trades,
        }
        stored = self.store.save_backtest_run(
            parameters={
                "stocks": stocks,
                "sentiment_scores": sentiment_scores,
                "days": days,
                "initial_cash": initial_cash,
            },
            summary=summary,
        )
        return stored


class DiagnosticsService:
    REQUIRED_MODULES = [
        "fastapi",
        "uvicorn",
        "pandas",
        "requests",
        "plotly",
    ]

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def run(self) -> dict[str, Any]:
        package_checks = {}
        for module_name in self.REQUIRED_MODULES:
            try:
                importlib.import_module(module_name)
                package_checks[module_name] = {"ok": True}
            except Exception as exc:
                package_checks[module_name] = {"ok": False, "error": str(exc)}

        db_path = config.DB_PATH
        frontend_ok = config.FRONTEND_DIR.joinpath("index.html").exists()
        env_file = config.PROJECT_ROOT / ".env"
        kis_configured = config.KIS_CREDENTIALS_CONFIGURED
        claude_configured = config.CLAUDE_CREDENTIALS_CONFIGURED
        paper_cash = self.store.get_paper_cash()
        overall = all(item["ok"] for item in package_checks.values()) and frontend_ok
        missing_config = []
        if not kis_configured:
            missing_config.append("KIS credentials")
        if not claude_configured:
            missing_config.append("Anthropic API key")

        return {
            "ok": overall,
            "summary": "ready" if overall else "degraded",
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "mock_mode": config.MOCK_MODE,
                "mock_mode_reason": config.MOCK_MODE_REASON,
                "explicit_mock_mode": config.EXPLICIT_MOCK_MODE,
                "allow_live_trading": config.ALLOW_LIVE_TRADING,
                "env_file_present": env_file.exists(),
            },
            "storage": {
                "db_path": db_path,
                "db_exists": self.store.db_path.exists(),
                "paper_cash": paper_cash,
                "positions": len(self.store.list_positions()),
            },
            "integrations": {
                "kis_configured": kis_configured,
                "claude_configured": claude_configured,
                "frontend_present": frontend_ok,
                "missing_config": missing_config,
            },
            "packages": package_checks,
        }

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "alpha-gen-web",
            "mode": "mock" if config.MOCK_MODE else "paper/live",
        }

    def readiness(self) -> dict[str, Any]:
        report = self.run()
        return {
            "status": "ready" if report["ok"] else "not_ready",
            "checks": report,
        }


class AgentService:
    def __init__(
        self,
        store: SQLiteStore,
        analytics_service: AnalyticsService,
        trading_service: TradingService,
        risk_service: RiskService,
    ) -> None:
        self.store = store
        self.analytics_service = analytics_service
        self.trading_service = trading_service
        self.risk_service = risk_service

    def run_cycle(self, *, session: str = "AUTO", force_refresh: bool = False, place_orders: bool = True) -> dict[str, Any]:
        resolved = resolve_session(session)
        analysis = self.analytics_service.analyze_market(session=resolved, force_refresh=force_refresh)
        stop_loss_orders = self.trading_service.run_stop_loss_cycle()
        executed_orders = []
        if place_orders:
            executed_orders = self.trading_service.auto_buy_from_signals(analysis["signals"], resolved)
        risk_summary = self.risk_service.update_drawdown()
        cycle_summary = {
            "last_cycle_at": utc_timestamp(),
            "last_session": resolved,
            "last_signal_count": len(analysis["signals"]),
            "last_buy_candidate_count": sum(1 for signal in analysis["signals"] if signal["buy_signal"]),
            "last_order_count": len(executed_orders),
            "last_stop_loss_count": len(stop_loss_orders),
            "last_total_asset": self.risk_service.get_total_asset(),
            "last_sleep_mode": bool(risk_summary.get("sleep_mode", False)),
            "last_summary": (
                f"{resolved} 세션 · 시그널 {len(analysis['signals'])}건 · "
                f"매수후보 {sum(1 for signal in analysis['signals'] if signal['buy_signal'])}건 · "
                f"주문 {len(executed_orders)}건"
            ),
        }
        worker_state = self.store.get_state("worker_state", {}) or {}
        worker_state.update(cycle_summary)
        self.store.set_state("worker_state", worker_state)
        return {
            "session": resolved,
            "analysis": analysis,
            "executed_orders": executed_orders,
            "stop_loss_orders": stop_loss_orders,
            "risk": risk_summary,
            "portfolio": self.trading_service.get_portfolio_snapshot(),
            "cycle_summary": cycle_summary,
        }


class AgentWorker:
    def __init__(self, store: SQLiteStore, agent_service: AgentService) -> None:
        self.store = store
        self.agent_service = agent_service
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self, *, interval_sec: int, session: str, place_orders: bool) -> dict[str, Any]:
        if self._thread and self._thread.is_alive():
            return self.status()

        self._stop_event.clear()

        def _runner() -> None:
            self.store.set_state(
                "worker_state",
                {
                    "running": True,
                    "interval_sec": interval_sec,
                    "session": session,
                    "place_orders": place_orders,
                    "started_at": utc_timestamp(),
                    "cycle_count": 0,
                    "current_status": "starting",
                    "next_cycle_at": utc_timestamp(),
                },
            )
            while not self._stop_event.is_set():
                try:
                    state = self.store.get_state("worker_state", {}) or {}
                    state["current_status"] = "running_cycle"
                    state["current_cycle_started_at"] = utc_timestamp()
                    self.store.set_state("worker_state", state)

                    result = self.agent_service.run_cycle(session=session, place_orders=place_orders)
                    state = self.store.get_state("worker_state", {}) or {}
                    state["cycle_count"] = int(state.get("cycle_count", 0)) + 1
                    state["current_status"] = "idle_waiting"
                    state["last_completed_at"] = utc_timestamp()
                    state["next_cycle_at"] = utc_timestamp_after(interval_sec)
                    state["last_error"] = ""
                    state["last_result"] = result.get("cycle_summary", {})
                    self.store.set_state("worker_state", state)
                except Exception as exc:
                    state = self.store.get_state("worker_state", {}) or {}
                    state["last_error"] = str(exc)
                    state["current_status"] = "error"
                    state["next_cycle_at"] = utc_timestamp_after(interval_sec)
                    self.store.set_state("worker_state", state)
                self._stop_event.wait(interval_sec)
            state = self.store.get_state("worker_state", {}) or {}
            state["running"] = False
            state["current_status"] = "stopped"
            state["stopped_at"] = utc_timestamp()
            self.store.set_state("worker_state", state)

        self._thread = threading.Thread(target=_runner, daemon=True, name="alpha-gen-worker")
        self._thread.start()
        time.sleep(0.05)
        return self.status()

    def stop(self) -> dict[str, Any]:
        self._stop_event.set()
        return self.status()

    def status(self) -> dict[str, Any]:
        state = self.store.get_state("worker_state", {}) or {}
        running = bool(self._thread and self._thread.is_alive() and not self._stop_event.is_set())
        state["running"] = running
        return state
