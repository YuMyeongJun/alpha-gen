from __future__ import annotations

import importlib
import platform
import shutil
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import config
import market_data
import news_analyzer
import ohlcv as ohlcv_module
import risk_manager
import technical
from backtest import run_backtest

from .store import SQLiteStore


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_timestamp_after(seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=seconds)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def timestamp_age_seconds(value: str | None) -> int | None:
    parsed = parse_utc_timestamp(value)
    if parsed is None:
        return None
    return max(int((datetime.now(UTC) - parsed).total_seconds()), 0)


def get_display_cash(store: SQLiteStore) -> float:
    cash = store.get_paper_cash()
    if config.MOCK_MODE or not config.KIS_CREDENTIALS_CONFIGURED:
        return cash
    broker_cash = store.get_state("live_balance:KR", {}) or {}
    if "cash" in broker_cash:
        return float(broker_cash["cash"])
    return cash


def resolve_session(session: str) -> str:
    if session == "AUTO":
        detected = market_data.get_market_session()
        return "KR" if detected == "CLOSED" else detected
    return session


class TradingSafetyError(ValueError):
    pass


@dataclass(slots=True)
class ServiceBundle:
    store: SQLiteStore
    risk_service: "RiskService"
    safety_service: "SafetyService"
    analytics_service: "AnalyticsService"
    trading_service: "TradingService"
    backtest_service: "BacktestService"
    diagnostics_service: "DiagnosticsService"
    agent_service: "AgentService"
    worker: "AgentWorker"


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
        cash = get_display_cash(self.store)
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


class SafetyService:
    LIVE_STAGES = {"live_limited", "live_full"}

    def __init__(self, store: SQLiteStore, risk_service: RiskService) -> None:
        self.store = store
        self.risk_service = risk_service
        self._bootstrap_state()

    def _bootstrap_state(self) -> None:
        if self.store.get_state("promotion_stage") is None:
            self.store.set_state("promotion_stage", config.OPERATING_STAGE)
        if self.store.get_state("emergency_stop") is None:
            self.store.set_json_state(
                "emergency_stop",
                {
                    "enabled": bool(config.EMERGENCY_STOP),
                    "reason": "config_default" if config.EMERGENCY_STOP else "",
                    "updated_at": utc_timestamp(),
                },
            )

    def get_emergency_stop(self) -> dict[str, Any]:
        self._bootstrap_state()
        return self.store.get_state(
            "emergency_stop",
            {
                "enabled": bool(config.EMERGENCY_STOP),
                "reason": "",
                "updated_at": utc_timestamp(),
            },
        )

    def set_emergency_stop(self, enabled: bool, reason: str = "", actor: str = "ui") -> dict[str, Any]:
        payload = {
            "enabled": bool(enabled),
            "reason": reason.strip(),
            "updated_at": utc_timestamp(),
            "actor": actor,
        }
        self.store.set_json_state("emergency_stop", payload)
        self.store.add_audit_event(
            scope="safety",
            event_type="emergency_stop_enabled" if enabled else "emergency_stop_cleared",
            severity="critical" if enabled else "info",
            message=reason.strip() or ("Emergency stop enabled" if enabled else "Emergency stop cleared"),
            payload=payload,
        )
        return payload

    def get_stage(self) -> str:
        self._bootstrap_state()
        stage = str(self.store.get_state("promotion_stage", config.OPERATING_STAGE))
        return stage if stage in config.OPERATING_STAGES else config.OPERATING_STAGE

    def set_stage(self, stage: str, actor: str = "ui") -> str:
        normalized = stage.strip().lower()
        if normalized not in config.OPERATING_STAGES:
            raise TradingSafetyError(f"지원하지 않는 운영 단계입니다: {stage}")
        if config.MOCK_MODE and normalized != "mock":
            raise TradingSafetyError("MOCK_MODE=True 에서는 운영 단계를 mock 이외로 변경할 수 없습니다.")
        self.store.set_state("promotion_stage", normalized)
        self.store.add_audit_event(
            scope="safety",
            event_type="promotion_stage_changed",
            severity="info",
            message=f"운영 단계 변경: {normalized}",
            payload={"stage": normalized, "actor": actor},
        )
        return normalized

    def get_policy(self) -> dict[str, Any]:
        stop_state = self.get_emergency_stop()
        stage = self.get_stage()
        return {
            "stage": stage,
            "stage_sequence": list(config.OPERATING_STAGES),
            "mock_mode": config.MOCK_MODE,
            "allow_live_trading": config.ALLOW_LIVE_TRADING,
            "shadow_mode": stage == "shadow",
            "auto_orders_enabled": config.AUTO_ORDER_ENABLED and stage not in {"mock", "shadow"} and not stop_state["enabled"],
            "live_orders_enabled": stage in self.LIVE_STAGES and config.ALLOW_LIVE_TRADING and not stop_state["enabled"],
            "emergency_stop": stop_state,
            "limits": {
                "quote_staleness_sec": config.QUOTE_STALENESS_SEC,
                "signal_staleness_sec": config.SIGNAL_STALENESS_SEC,
                "live_max_orders_per_cycle": config.LIVE_MAX_ORDERS_PER_CYCLE,
                "live_max_orders_per_day": config.LIVE_MAX_ORDERS_PER_DAY,
                "max_consecutive_losses": config.MAX_CONSECUTIVE_LOSSES,
                "max_daily_loss_pct": config.MAX_DAILY_LOSS_PCT,
            },
            "usage": self._policy_usage(),
        }

    def _policy_usage(self) -> dict[str, Any]:
        cycle_count, live_daily = self._count_live_orders()
        orders_today = self._orders_today()
        return {
            "orders_today": len(orders_today),
            "live_orders_today": live_daily,
            "live_orders_cycle": cycle_count,
        }

    def execution_mode(self) -> str:
        stage = self.get_stage()
        if stage in self.LIVE_STAGES:
            return "live"
        if stage == "shadow":
            return "shadow"
        return "paper"

    def ensure_signal_freshness(self, signal: dict[str, Any]) -> None:
        analyzed_age = timestamp_age_seconds(signal.get("analyzed_at"))
        quote_age = timestamp_age_seconds(signal.get("quote_collected_at"))
        if analyzed_age is None or analyzed_age > config.SIGNAL_STALENESS_SEC:
            raise TradingSafetyError("시그널이 너무 오래되어 주문을 차단했습니다.")
        if quote_age is None or quote_age > config.QUOTE_STALENESS_SEC:
            raise TradingSafetyError("시세가 너무 오래되어 주문을 차단했습니다.")

    def _orders_today(self) -> list[dict[str, Any]]:
        today = datetime.now(UTC).date().isoformat()
        return [
            order
            for order in self.store.list_recent_orders(limit=500)
            if str(order.get("created_at", "")).startswith(today)
        ]

    def _daily_realized_loss(self) -> float:
        total = 0.0
        for order in self._orders_today():
            realized = float(order.get("realized_pnl") or 0)
            if realized < 0:
                total += abs(realized)
        return total

    def _consecutive_losses(self) -> int:
        streak = 0
        for order in self.store.list_recent_orders(limit=50):
            if str(order.get("status")) != "filled" or order.get("realized_pnl") is None:
                continue
            pnl = float(order["realized_pnl"])
            if pnl < 0:
                streak += 1
                if streak >= config.MAX_CONSECUTIVE_LOSSES:
                    return streak
            elif pnl > 0:
                break
        return streak

    def _count_live_orders(self) -> tuple[int, int]:
        orders = [order for order in self._orders_today() if order.get("mode") == "live"]
        cycle_orders = [
            order
            for order in orders
            if order.get("metadata", {}).get("cycle_id") == self.store.get_state("active_cycle_id")
        ]
        return len(cycle_orders), len(orders)

    def ensure_order_allowed(
        self,
        *,
        mode: str,
        session: str,
        side: str,
        signal: dict[str, Any] | None = None,
    ) -> None:
        policy = self.get_policy()
        stop_state = policy["emergency_stop"]
        if stop_state["enabled"]:
            raise TradingSafetyError(stop_state.get("reason") or "긴급 정지 상태입니다.")
        if not self.risk_service.can_trade() and side == "buy":
            raise TradingSafetyError("리스크 휴면 모드이므로 신규 주문을 차단했습니다.")

        if signal is not None:
            self.ensure_signal_freshness(signal)

        if mode == "live":
            if self.get_stage() not in self.LIVE_STAGES:
                raise TradingSafetyError("현재 운영 단계에서는 실거래를 허용하지 않습니다.")
            if not config.ALLOW_LIVE_TRADING:
                raise TradingSafetyError("ALLOW_LIVE_TRADING=false 이므로 실거래를 차단했습니다.")
            if session == "US" and not config.ENABLE_KIS_US_ORDERS:
                raise TradingSafetyError("미국장 실거래는 ENABLE_KIS_US_ORDERS=true 가 필요합니다.")

            cycle_count, daily_count = self._count_live_orders()
            if cycle_count >= config.LIVE_MAX_ORDERS_PER_CYCLE:
                raise TradingSafetyError("사이클당 최대 실거래 주문 수를 초과했습니다.")
            if daily_count >= config.LIVE_MAX_ORDERS_PER_DAY:
                raise TradingSafetyError("일일 최대 실거래 주문 수를 초과했습니다.")

            daily_loss_limit = self.risk_service.get_total_asset() * config.MAX_DAILY_LOSS_PCT
            if self._daily_realized_loss() >= daily_loss_limit:
                raise TradingSafetyError("일일 손실 한도를 초과해 실거래를 차단했습니다.")
            if self._consecutive_losses() >= config.MAX_CONSECUTIVE_LOSSES:
                raise TradingSafetyError("연속 손실 한도를 초과해 실거래를 차단했습니다.")

    def shadow_recommendation(self, signal: dict[str, Any]) -> dict[str, Any]:
        return {
            "shadow": True,
            "reason": "shadow mode - broker submission skipped",
            "stock_code": signal["stock_code"],
            "session": signal["session"],
            "generated_at": utc_timestamp(),
        }


class AnalyticsService:
    _bootstrap_lock = threading.Lock()

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def _signals_need_refresh(self, *, max_age_sec: int = 3600, min_retry_sec: int = 300) -> bool:
        recent = self.store.list_recent_signals(limit=1)
        if recent:
            age = timestamp_age_seconds(recent[0].get("analyzed_at"))
            if age is not None and age < max_age_sec:
                return False

        last_attempt = self.store.get_state("last_auto_analysis_at")
        attempt_age = timestamp_age_seconds(str(last_attempt) if last_attempt else None)
        if attempt_age is not None and attempt_age < min_retry_sec:
            return False
        return True

    def ensure_signals_fresh(
        self,
        *,
        session: str = "AUTO",
        max_age_sec: int = 3600,
        min_retry_sec: int = 300,
    ) -> bool:
        if not self._signals_need_refresh(max_age_sec=max_age_sec, min_retry_sec=min_retry_sec):
            return False

        with self._bootstrap_lock:
            if not self._signals_need_refresh(max_age_sec=max_age_sec, min_retry_sec=min_retry_sec):
                return False
            self.store.set_state("last_auto_analysis_at", utc_timestamp())
            self.analyze_market(session=session, force_refresh=False)
            return True

    def ensure_signals_fresh_background(
        self,
        *,
        session: str = "AUTO",
        max_age_sec: int = 3600,
        min_retry_sec: int = 300,
    ) -> bool:
        if not self._signals_need_refresh(max_age_sec=max_age_sec, min_retry_sec=min_retry_sec):
            return False

        def _runner() -> None:
            try:
                self.ensure_signals_fresh(
                    session=session,
                    max_age_sec=max_age_sec,
                    min_retry_sec=min_retry_sec,
                )
            except Exception as exc:
                self.store.add_audit_event(
                    scope="agent",
                    event_type="auto_analysis_failed",
                    severity="warning",
                    message=f"백그라운드 시그널 분석 실패: {exc}",
                )

        threading.Thread(
            target=_runner,
            daemon=True,
            name="alpha-gen-analysis-bootstrap",
        ).start()
        return True

    def analyze_market(self, session: str = "AUTO", force_refresh: bool = False) -> dict[str, Any]:
        resolved = resolve_session(session)
        analyzed_at = utc_timestamp()
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
            try:
                quote = market_data.get_price(stock_code, resolved)
                history = market_data.get_price_history(stock_code, session=resolved, days=30)
                prev_day = market_data.get_prev_day(stock_code, resolved)
                sentiment = news_analyzer.get_stock_sentiment(stock_code, topic_results)
                technicals = technical.evaluate_buy_technicals(
                    stock_code,
                    history,
                    quote,
                    prev_day=prev_day if config.ENABLE_VOLATILITY_BREAKOUT else None,
                )
                prev_close = float(prev_day.get("prev_close") or 0) if prev_day else 0
                current_price = float(quote["current_price"])
                change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
            except Exception as exc:
                self.store.add_audit_event(
                    scope="agent",
                    event_type="signal_build_failed",
                    severity="warning",
                    message=f"{stock_code} 시그널 생성 실패: {exc}",
                    session=resolved,
                    stock_code=stock_code,
                )
                continue

            # OHLCV (MACD + 볼린저밴드) 신호 — 데이터 없으면 None(차단 안 함)
            ohlcv_signals: dict[str, Any] | None = None
            ohlcv_buy: bool | None = None
            try:
                raw = ohlcv_module.get_latest_signals(stock_code)
                if "error" not in raw:
                    ohlcv_signals = raw
                    ohlcv_buy = bool(raw.get("signal_buy"))
            except Exception:
                pass

            base_buy = sentiment["score"] >= config.SENTIMENT_BUY_THRESHOLD and technicals["signal"]
            # OHLCV 데이터가 있을 때만 추가 필터로 적용
            composite_buy = base_buy and (ohlcv_buy is None or ohlcv_buy)

            signal = {
                "stock_code": stock_code,
                "stock_name": stock_info["name"],
                "session": resolved,
                "sentiment_score": sentiment["score"],
                "sentiment_label": sentiment["label"],
                "sentiment_reason": sentiment["reason"],
                "technical_signal": technicals["signal"],
                "technical_reason": technicals["reason"],
                "ohlcv_buy": ohlcv_buy,
                "ohlcv": ohlcv_signals,
                "buy_signal": composite_buy,
                "current_price": quote["current_price"],
                "change_pct": round(change_pct, 2),
                "quote": quote,
                "sentiment": sentiment,
                "technical": technicals,
                "analyzed_at": analyzed_at,
                "quote_collected_at": utc_timestamp(),
            }
            self.store.update_position_price(resolved, stock_code, quote["current_price"])
            signals.append(signal)

            # 일봉 데이터 없으면 백그라운드 수집 트리거
            if ohlcv_signals is None:
                def _fetch(code: str = stock_code) -> None:
                    try:
                        ohlcv_module.fetch_and_store(code, days=200)
                    except Exception:
                        pass
                threading.Thread(target=_fetch, daemon=True, name=f"ohlcv-fetch-{stock_code}").start()

        self.store.save_signals(signals)
        self.store.record_equity(
            total_asset=self._total_asset(),
            cash=get_display_cash(self.store),
            session=resolved,
            note="analysis_refresh" if force_refresh else "analysis_cycle",
        )
        return {
            "session": resolved,
            "signals": signals,
            "topics": topic_results,
            "force_refresh": force_refresh,
            "analyzed_at": analyzed_at,
        }

    def _total_asset(self) -> float:
        cash = get_display_cash(self.store)
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
        cash = get_display_cash(self.store)
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
            "audit": self.store.list_audit_events(limit=20),
        }


class TradingService:
    _broker_sync_audit_lock = threading.Lock()

    def __init__(self, store: SQLiteStore, risk_service: RiskService, safety_service: SafetyService) -> None:
        self.store = store
        self.risk_service = risk_service
        self.safety_service = safety_service

    def _stock_name(self, stock_code: str, session: str) -> str:
        stocks = market_data.get_target_stocks_for_session(session)
        return stocks.get(stock_code, {}).get("name", stock_code)

    def _order_metadata(self, metadata: dict[str, Any] | None, **extra: Any) -> dict[str, Any]:
        merged = dict(metadata or {})
        merged.update(extra)
        return merged

    def _ensure_idempotent(self, client_order_id: str | None) -> dict[str, Any] | None:
        if not client_order_id:
            return None
        return self.store.get_order_by_client_order_id(client_order_id)

    def _create_intent(
        self,
        *,
        stock_code: str,
        session: str,
        side: str,
        qty: int,
        price: float,
        mode: str,
        client_order_id: str | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        existing = self._ensure_idempotent(client_order_id)
        if existing is not None:
            return existing
        order = self.store.create_order(
            stock_code=stock_code,
            stock_name=self._stock_name(stock_code, session),
            session=session,
            side=side,
            mode=mode,
            qty=qty,
            requested_price=price,
            client_order_id=client_order_id,
            metadata=metadata,
        )
        self.store.add_audit_event(
            scope="order",
            event_type="intent_created",
            severity="info",
            message=f"{mode} 주문 의도 생성",
            session=session,
            stock_code=stock_code,
            order_id=order["id"],
            payload={"side": side, "qty": qty, "client_order_id": client_order_id, "mode": mode},
        )
        return order

    def _approve_intent(self, order: dict[str, Any], message: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.store.transition_order(
            order["id"],
            to_status="approved",
            event_type="risk_approved",
            message=message,
            attempt_count=order["attempt_count"],
            metadata=metadata,
        )

    def _reject_order(
        self,
        order: dict[str, Any],
        *,
        message: str,
        metadata: dict[str, Any] | None = None,
        event_type: str = "order_rejected",
        attempt_count: int | None = None,
    ) -> dict[str, Any]:
        updated = self.store.transition_order(
            order["id"],
            to_status="rejected",
            event_type=event_type,
            message=message,
            attempt_count=order["attempt_count"] if attempt_count is None else attempt_count,
            executed_price=order.get("executed_price"),
            realized_pnl=order.get("realized_pnl"),
            metadata=metadata,
        )
        self.store.add_audit_event(
            scope="order",
            event_type=event_type,
            severity="warning",
            message=message,
            session=order["session"],
            stock_code=order["stock_code"],
            order_id=order["id"],
            payload=updated.get("metadata", {}),
        )
        return updated

    def _should_sync_broker_positions(self) -> bool:
        if config.MOCK_MODE or not config.KIS_CREDENTIALS_CONFIGURED:
            return False
        return self.safety_service.execution_mode() in {"paper", "live"}

    def sync_live_positions_from_broker(self, session: str, *, source: str = "portfolio") -> None:
        if not self._should_sync_broker_positions():
            return
        if session == "US" and not config.ENABLE_KIS_US_ORDERS:
            return
        if self.safety_service.execution_mode() == "paper" and source not in {"worker", "manual"}:
            return

        blocked = market_data.kis_auth_blocked_reason() or market_data.kis_api_degraded_reason()
        if blocked:
            return

        interval = (
            config.PAPER_BROKER_SYNC_INTERVAL_SEC
            if self.safety_service.execution_mode() == "paper"
            else config.BROKER_SYNC_INTERVAL_SEC
        )
        last_sync_key = f"broker_sync_last_at:{session}"
        last_sync_at = self.store.get_state(last_sync_key)
        sync_age = timestamp_age_seconds(str(last_sync_at) if last_sync_at else None)
        if sync_age is not None and sync_age < interval:
            return

        self.store.set_state(last_sync_key, utc_timestamp())
        try:
            cash, holdings = market_data.get_balance(session)
        except Exception as exc:
            with self._broker_sync_audit_lock:
                fail_audit_key = "broker_sync_last_fail_audit"
                last_fail_audit = self.store.get_state(fail_audit_key)
                fail_audit_age = timestamp_age_seconds(str(last_fail_audit) if last_fail_audit else None)
                if fail_audit_age is None or fail_audit_age >= 300:
                    self.store.set_state(fail_audit_key, utc_timestamp())
                    self.store.add_audit_event(
                        scope="broker",
                        event_type="position_sync_failed",
                        severity="warning",
                        message=f"{session} 잔고 동기화 실패: {exc}",
                        session=session,
                    )
            return
        positions = [
            {
                "stock_code": item["code"],
                "stock_name": item["name"],
                "qty": int(item["qty"]),
                "avg_price": float(item["avg_price"]),
                "last_price": float(item["eval_price"]),
            }
            for item in holdings
        ]
        self.store.replace_positions(session, positions)
        self.store.set_json_state(
            f"live_balance:{session}",
            {"cash": cash, "synced_at": utc_timestamp(), "session": session},
        )

    def _paper_cash_snapshot(self) -> float:
        return self.store.get_paper_cash()

    def _display_cash_snapshot(self) -> float:
        return get_display_cash(self.store)

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
        order = self._create_intent(
            stock_code=stock_code,
            session=session,
            side=side,
            qty=qty,
            price=price,
            mode="paper",
            client_order_id=client_order_id,
            metadata=metadata,
        )

        if order["status"] != "intent":
            order["portfolio"] = self.get_portfolio_snapshot()
            return order

        try:
            self.safety_service.ensure_order_allowed(mode="paper", session=session, side=side)
        except TradingSafetyError as exc:
            return self._reject_order(
                order,
                message=str(exc),
                metadata=metadata or {},
                event_type="safety_blocked",
            )
        order = self._approve_intent(
            order,
            "Paper order approved",
            self._order_metadata(metadata, approval="paper"),
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
                updated = self.store.transition_order(
                    order["id"],
                    to_status="filled",
                    event_type="paper_filled",
                    message="Paper order filled",
                    attempt_count=attempts,
                    executed_price=price,
                    realized_pnl=result["realized_pnl"],
                    metadata=self._order_metadata(metadata, paper_fill=True),
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
                order = self.store.get_order(order["id"]) or order

        return self._reject_order(
            order,
            message=last_error or "Paper order rejected",
            metadata=metadata or {},
            event_type="paper_rejected",
            attempt_count=attempts,
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

    def _submit_live_order(self, *, stock_code: str, session: str, side: str, qty: int) -> tuple[bool, str]:
        import order_engine

        if session == "KR":
            return order_engine.kis_buy(stock_code, qty) if side == "buy" else order_engine.kis_sell(stock_code, qty)
        if session == "US":
            return order_engine.kis_us_buy(stock_code, qty) if side == "buy" else order_engine.kis_us_sell(stock_code, qty)
        raise TradingSafetyError(f"지원하지 않는 세션입니다: {session}")

    def place_shadow_order(
        self,
        *,
        stock_code: str,
        session: str,
        side: str,
        qty: int,
        signal: dict[str, Any],
        client_order_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        quote = market_data.get_price(stock_code, session)
        price = float(quote["current_price"])
        order = self._create_intent(
            stock_code=stock_code,
            session=session,
            side=side,
            qty=qty,
            price=price,
            mode="shadow",
            client_order_id=client_order_id,
            metadata=self._order_metadata(metadata, signal_snapshot=signal),
        )
        if order["status"] != "intent":
            return order

        try:
            self.safety_service.ensure_order_allowed(mode="paper", session=session, side=side, signal=signal)
        except TradingSafetyError as exc:
            return self._reject_order(
                order,
                message=str(exc),
                metadata=self._order_metadata(metadata, signal_snapshot=signal),
                event_type="safety_blocked",
            )
        order = self._approve_intent(order, "Shadow recommendation approved", self._order_metadata(metadata, signal_snapshot=signal))
        reconciled = self.store.transition_order(
            order["id"],
            to_status="reconciled",
            event_type="shadow_recorded",
            message="Shadow mode: broker submission skipped",
            attempt_count=0,
            metadata=self._order_metadata(metadata, signal_snapshot=signal, shadow=True),
        )
        self.store.add_audit_event(
            scope="order",
            event_type="shadow_recorded",
            severity="info",
            message="Shadow recommendation stored without broker submission",
            session=session,
            stock_code=stock_code,
            order_id=order["id"],
            payload=self.safety_service.shadow_recommendation(signal),
        )
        return reconciled

    def place_live_order(
        self,
        *,
        stock_code: str,
        session: str,
        side: str,
        qty: int,
        signal: dict[str, Any] | None = None,
        client_order_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if qty <= 0:
            raise ValueError("수량은 1 이상이어야 합니다.")
        quote = market_data.get_price(stock_code, session)
        price = float(quote["current_price"])
        order = self._create_intent(
            stock_code=stock_code,
            session=session,
            side=side,
            qty=qty,
            price=price,
            mode="live",
            client_order_id=client_order_id,
            metadata=self._order_metadata(metadata, signal_snapshot=signal),
        )
        if order["status"] != "intent":
            order["portfolio"] = self.get_portfolio_snapshot()
            return order

        try:
            self.safety_service.ensure_order_allowed(mode="live", session=session, side=side, signal=signal)
        except TradingSafetyError as exc:
            rejected = self._reject_order(
                order,
                message=str(exc),
                metadata=self._order_metadata(metadata, signal_snapshot=signal),
                event_type="safety_blocked",
            )
            rejected["portfolio"] = self.get_portfolio_snapshot()
            return rejected
        order = self._approve_intent(
            order,
            "Live order approved",
            self._order_metadata(metadata, signal_snapshot=signal, stage=self.safety_service.get_stage()),
        )

        position_before = self.store.get_position(session, stock_code)
        submitted = self.store.transition_order(
            order["id"],
            to_status="submitted",
            event_type="broker_submit_started",
            message="Submitting live broker order",
            attempt_count=1,
            metadata=self._order_metadata(metadata, signal_snapshot=signal),
        )
        ok, broker_message = self._submit_live_order(stock_code=stock_code, session=session, side=side, qty=qty)
        if not ok:
            return self._reject_order(
                submitted,
                message=broker_message,
                metadata=self._order_metadata(metadata, signal_snapshot=signal),
                event_type="broker_rejected",
                attempt_count=1,
            )

        acknowledged = self.store.transition_order(
            order["id"],
            to_status="acknowledged",
            event_type="broker_acknowledged",
            message=broker_message or "Broker acknowledged the order",
            attempt_count=1,
            executed_price=price,
            metadata=self._order_metadata(metadata, signal_snapshot=signal, broker_message=broker_message),
        )
        realized_pnl = None
        if side == "sell" and position_before is not None:
            realized_pnl = (price - float(position_before["avg_price"])) * qty
        filled = self.store.transition_order(
            order["id"],
            to_status="filled",
            event_type="live_filled",
            message="Live order filled",
            attempt_count=1,
            executed_price=price,
            realized_pnl=realized_pnl,
            metadata=self._order_metadata(metadata, signal_snapshot=signal, broker_message=broker_message),
        )
        self.store.add_fill(order["id"], stock_code, qty, price, realized_pnl)
        self.sync_live_positions_from_broker(session)
        reconciled = self.store.transition_order(
            order["id"],
            to_status="reconciled",
            event_type="position_reconciled",
            message="Broker position snapshot synchronized",
            attempt_count=1,
            executed_price=price,
            realized_pnl=realized_pnl,
            metadata=self._order_metadata(metadata, signal_snapshot=signal, broker_message=broker_message),
        )
        self.store.add_audit_event(
            scope="order",
            event_type="live_order_reconciled",
            severity="info",
            message="실거래 주문이 브로커 응답과 동기화되었습니다.",
            session=session,
            stock_code=stock_code,
            order_id=order["id"],
            payload=reconciled.get("metadata", {}),
        )
        reconciled["portfolio"] = self.get_portfolio_snapshot()
        return reconciled

    def auto_buy_from_signals(self, signals: list[dict[str, Any]], session: str) -> list[dict[str, Any]]:
        if not self.risk_service.can_trade():
            return []
        orders: list[dict[str, Any]] = []
        execution_mode = self.safety_service.execution_mode()
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

            client_order_id = (
                f"{execution_mode}:{session}:{signal['stock_code']}:{signal['analyzed_at']}:buy"
            )
            metadata = {
                "source": "agent_cycle",
                "signal_snapshot": signal,
                "cycle_id": self.store.get_state("active_cycle_id"),
            }
            try:
                if execution_mode == "shadow":
                    order = self.place_shadow_order(
                        stock_code=signal["stock_code"],
                        session=session,
                        side="buy",
                        qty=qty,
                        signal=signal,
                        client_order_id=client_order_id,
                        metadata=metadata,
                    )
                elif execution_mode == "live":
                    order = self.place_live_order(
                        stock_code=signal["stock_code"],
                        session=session,
                        side="buy",
                        qty=qty,
                        signal=signal,
                        client_order_id=client_order_id,
                        metadata=metadata,
                    )
                else:
                    order = self.place_paper_order(
                        stock_code=signal["stock_code"],
                        session=session,
                        side="buy",
                        qty=qty,
                        client_order_id=client_order_id,
                        metadata=metadata,
                    )
            except TradingSafetyError as exc:
                self.store.add_audit_event(
                    scope="safety",
                    event_type="order_blocked",
                    severity="warning",
                    message=str(exc),
                    session=session,
                    stock_code=signal["stock_code"],
                    payload={"signal": signal, "mode": execution_mode},
                )
                continue
            if order["status"] in {"filled", "reconciled"}:
                self.store.mark_bought_today(signal["stock_code"])
                orders.append(order)
        return orders

    def run_stop_loss_cycle(self) -> list[dict[str, Any]]:
        for session in ("KR", "US"):
            self.sync_live_positions_from_broker(session)
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
        execution_mode = self.safety_service.execution_mode()
        for target in stop_targets:
            metadata = {"source": "stop_loss", "loss_pct": target["loss_pct"]}
            if execution_mode == "shadow":
                executed.append(
                    self.place_shadow_order(
                        stock_code=target["code"],
                        session=target["session"],
                        side="sell",
                        qty=int(target["qty"]),
                        signal={
                            "stock_code": target["code"],
                            "session": target["session"],
                            "analyzed_at": utc_timestamp(),
                            "quote_collected_at": utc_timestamp(),
                        },
                        client_order_id=f"shadow:{target['session']}:{target['code']}:{int(target['qty'])}:sell",
                        metadata=metadata,
                    )
                )
            elif execution_mode == "live":
                executed.append(
                    self.place_live_order(
                        stock_code=target["code"],
                        session=target["session"],
                        side="sell",
                        qty=int(target["qty"]),
                        signal={
                            "stock_code": target["code"],
                            "session": target["session"],
                            "analyzed_at": utc_timestamp(),
                            "quote_collected_at": utc_timestamp(),
                        },
                        client_order_id=f"live:{target['session']}:{target['code']}:{int(target['qty'])}:sell",
                        metadata=metadata,
                    )
                )
            else:
                executed.append(
                    self.place_paper_order(
                        stock_code=target["code"],
                        session=target["session"],
                        side="sell",
                        qty=int(target["qty"]),
                        client_order_id=f"paper:{target['session']}:{target['code']}:{int(target['qty'])}:sell",
                        metadata=metadata,
                    )
                )
        return executed

    def close_positions(self, session: str, reason: str) -> list[dict[str, Any]]:
        self.sync_live_positions_from_broker(session)
        positions = self.store.list_positions(session=session)
        closed: list[dict[str, Any]] = []
        for position in positions:
            client_order_id = f"close:{session}:{position['stock_code']}:{position['qty']}"
            metadata = {"source": "session_close", "reason": reason}
            if self.safety_service.execution_mode() == "shadow":
                closed.append(
                    self.place_shadow_order(
                        stock_code=position["stock_code"],
                        session=session,
                        side="sell",
                        qty=int(position["qty"]),
                        signal={
                            "stock_code": position["stock_code"],
                            "session": session,
                            "analyzed_at": utc_timestamp(),
                            "quote_collected_at": utc_timestamp(),
                        },
                        client_order_id=client_order_id,
                        metadata=metadata,
                    )
                )
            elif self.safety_service.execution_mode() == "live":
                closed.append(
                    self.place_live_order(
                        stock_code=position["stock_code"],
                        session=session,
                        side="sell",
                        qty=int(position["qty"]),
                        signal={
                            "stock_code": position["stock_code"],
                            "session": session,
                            "analyzed_at": utc_timestamp(),
                            "quote_collected_at": utc_timestamp(),
                        },
                        client_order_id=client_order_id,
                        metadata=metadata,
                    )
                )
            else:
                closed.append(
                    self.place_paper_order(
                        stock_code=position["stock_code"],
                        session=session,
                        side="sell",
                        qty=int(position["qty"]),
                        client_order_id=client_order_id,
                        metadata=metadata,
                    )
                )
        return closed

    def get_portfolio_snapshot(self) -> dict[str, Any]:
        for session in ("KR", "US"):
            self.sync_live_positions_from_broker(session)
        positions = self.store.list_positions()
        cash = self._display_cash_snapshot()
        total_asset = cash + sum(float(item["last_price"]) * int(item["qty"]) for item in positions)
        risk_summary = self.risk_service.get_summary()
        return {
            "cash": cash,
            "positions": positions,
            "total_asset": total_asset,
            "equity": self.store.list_equity(limit=120),
            "orders": self.store.list_recent_orders(limit=50),
            "audit": self.store.list_audit_events(limit=20),
            "policy": self.safety_service.get_policy(),
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

    def __init__(self, store: SQLiteStore, safety_service: SafetyService) -> None:
        self.store = store
        self.safety_service = safety_service

    def run(self) -> dict[str, Any]:
        package_checks = {}
        for module_name in self.REQUIRED_MODULES:
            try:
                importlib.import_module(module_name)
                package_checks[module_name] = {"ok": True}
            except Exception as exc:
                package_checks[module_name] = {"ok": False, "error": str(exc)}

        db_path = config.DB_PATH
        frontend_ok = (
            config.FRONTEND_DIR.joinpath("dist", "index.html").exists()
            or config.FRONTEND_DIR.joinpath("index.html").exists()
        )
        env_file = config.PROJECT_ROOT / ".env"
        kis_configured = config.KIS_CREDENTIALS_CONFIGURED
        claude_configured = config.CLAUDE_CREDENTIALS_CONFIGURED
        kis_token_meta = market_data.get_kis_token_meta()
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
                "claude_model": config.CLAUDE_MODEL,
                "claude_model_deprecated": config.CLAUDE_MODEL_DEPRECATED,
                "allow_live_trading": config.ALLOW_LIVE_TRADING,
                "operating_stage": self.safety_service.get_stage(),
                "env_file_present": env_file.exists(),
            },
            "storage": {
                "db_path": db_path,
                "db_exists": self.store.db_path.exists(),
                "db_size_bytes": self.store.db_path.stat().st_size if self.store.db_path.exists() else 0,
                "paper_cash": paper_cash,
                "positions": len(self.store.list_positions()),
                "audit_events": len(self.store.list_audit_events(limit=200)),
            },
            "integrations": {
                "kis_configured": kis_configured,
                "claude_configured": claude_configured,
                "frontend_present": frontend_ok,
                "missing_config": missing_config,
                "kis_token": kis_token_meta,
            },
            "policy": self.safety_service.get_policy(),
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
        safety_service: SafetyService,
    ) -> None:
        self.store = store
        self.analytics_service = analytics_service
        self.trading_service = trading_service
        self.risk_service = risk_service
        self.safety_service = safety_service

    def run_cycle(self, *, session: str = "AUTO", force_refresh: bool = False, place_orders: bool = True) -> dict[str, Any]:
        resolved = resolve_session(session)
        cycle_id = f"{resolved}:{utc_timestamp()}"
        self.store.set_state("active_cycle_id", cycle_id)
        self.store.add_audit_event(
            scope="agent",
            event_type="cycle_started",
            severity="info",
            message=f"{resolved} 세션 사이클 시작",
            session=resolved,
            payload={
                "cycle_id": cycle_id,
                "force_refresh": force_refresh,
                "place_orders": place_orders,
                "stage": self.safety_service.get_stage(),
            },
        )
        self.trading_service.sync_live_positions_from_broker(resolved, source="worker")
        analysis = self.analytics_service.analyze_market(session=resolved, force_refresh=force_refresh)
        stop_loss_orders = self.trading_service.run_stop_loss_cycle()
        executed_orders = []
        should_place_orders = place_orders and self.safety_service.get_policy()["auto_orders_enabled"]
        if place_orders and not should_place_orders:
            self.store.add_audit_event(
                scope="agent",
                event_type="auto_order_skipped",
                severity="info",
                message="운영 단계 또는 긴급정지 상태로 자동 주문을 생략했습니다.",
                session=resolved,
                payload={"cycle_id": cycle_id, "requested": place_orders, "policy": self.safety_service.get_policy()},
            )
        if should_place_orders:
            executed_orders = self.trading_service.auto_buy_from_signals(analysis["signals"], resolved)
        risk_summary = self.risk_service.update_drawdown()
        cycle_summary = {
            "cycle_id": cycle_id,
            "last_cycle_at": utc_timestamp(),
            "last_session": resolved,
            "last_signal_count": len(analysis["signals"]),
            "last_buy_candidate_count": sum(1 for signal in analysis["signals"] if signal["buy_signal"]),
            "last_order_count": len(executed_orders),
            "last_stop_loss_count": len(stop_loss_orders),
            "last_total_asset": self.risk_service.get_total_asset(),
            "last_sleep_mode": bool(risk_summary.get("sleep_mode", False)),
            "operating_stage": self.safety_service.get_stage(),
            "last_summary": (
                f"{resolved} 세션 · 시그널 {len(analysis['signals'])}건 · "
                f"매수후보 {sum(1 for signal in analysis['signals'] if signal['buy_signal'])}건 · "
                f"주문 {len(executed_orders)}건"
            ),
        }
        worker_state = self.store.get_state("worker_state", {}) or {}
        worker_state.update(cycle_summary)
        self.store.set_state("worker_state", worker_state)
        self.store.add_audit_event(
            scope="agent",
            event_type="cycle_completed",
            severity="info",
            message=f"{resolved} 세션 사이클 완료",
            session=resolved,
            payload=cycle_summary,
        )
        return {
            "session": resolved,
            "analysis": analysis,
            "executed_orders": executed_orders,
            "stop_loss_orders": stop_loss_orders,
            "risk": risk_summary,
            "portfolio": self.trading_service.get_portfolio_snapshot(),
            "cycle_summary": cycle_summary,
            "policy": self.safety_service.get_policy(),
        }


class AgentWorker:
    def __init__(self, store: SQLiteStore, agent_service: AgentService) -> None:
        self.store = store
        self.agent_service = agent_service
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self.interrupted_session: str | None = None
        self.interrupted_interval_sec: int | None = None
        self._recover_stale_state()

    def _recover_stale_state(self) -> None:
        """서버 재시작 시 DB에 running=True가 남아 있으면 정리하고 감사 로그를 기록한다."""
        prev = self.store.get_state("worker_state", {}) or {}
        if not prev.get("running"):
            return
        self.interrupted_session = prev.get("session")
        self.interrupted_interval_sec = prev.get("interval_sec")
        prev["running"] = False
        prev["current_status"] = "interrupted"
        prev["interrupted_at"] = utc_timestamp()
        self.store.set_state("worker_state", prev)
        self.store.add_audit_event(
            scope="system",
            event_type="worker_interrupted",
            severity="warning",
            message=(
                "서버 재시작으로 인해 워커가 비정상 종료되었습니다. "
                f"마지막 세션: {self.interrupted_session}, "
                f"주기: {self.interrupted_interval_sec}s"
            ),
            payload={
                "last_cycle_at": prev.get("last_cycle_at") or prev.get("last_completed_at"),
                "session": self.interrupted_session,
                "interval_sec": self.interrupted_interval_sec,
            },
        )

    def resume_if_interrupted(self, *, place_orders: bool = True) -> bool:
        """이전에 실행 중이던 워커를 복원한다. 반환값: 재시작 여부."""
        if self.interrupted_session is None or self.interrupted_interval_sec is None:
            return False
        session = self.interrupted_session
        interval_sec = self.interrupted_interval_sec
        self.interrupted_session = None
        self.interrupted_interval_sec = None
        self.start(interval_sec=interval_sec, session=session, place_orders=place_orders)
        self.store.add_audit_event(
            scope="system",
            event_type="worker_auto_resumed",
            severity="info",
            message=f"인터럽트된 워커를 자동 재개했습니다. 세션: {session}, 주기: {interval_sec}s",
            payload={"session": session, "interval_sec": interval_sec},
        )
        return True

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


class SystemAdminService:
    def __init__(self, store: SQLiteStore, safety_service: SafetyService, worker: AgentWorker) -> None:
        self.store = store
        self.safety_service = safety_service
        self.worker = worker

    def clear_sentiment_cache(self, *, reason: str) -> dict[str, Any]:
        cleared = news_analyzer.clear_sentiment_cache()
        self.store.add_audit_event(
            scope="system",
            event_type="cache_cleared",
            severity="warning",
            message=f"감성 분석 캐시 {cleared}건 초기화",
            payload={"cleared": cleared, "reason": reason},
        )
        return {"cleared": cleared}

    def refresh_kis_token(self, *, reason: str) -> dict[str, Any]:
        market_data.reset_kis_token_cache()
        token = ""
        error = None
        if config.KIS_CREDENTIALS_CONFIGURED and not config.MOCK_MODE:
            try:
                token = market_data._get_kis_token(force_refresh=True)
            except Exception as exc:
                error = str(exc)
        meta = market_data.get_kis_token_meta()
        self.store.add_audit_event(
            scope="system",
            event_type="kis_token_refreshed",
            severity="info" if not error else "warning",
            message="KIS OAuth 토큰 재발급" if not error else f"KIS OAuth 토큰 재발급 실패: {error}",
            payload={"reason": reason, "cached": bool(token), "meta": meta, "error": error},
        )
        if error:
            raise TradingSafetyError(error)
        return {"token_cached": bool(token), "meta": meta}

    def reset_database(self, *, reason: str) -> dict[str, Any]:
        policy = self.safety_service.get_policy()
        if policy["emergency_stop"]["enabled"]:
            raise TradingSafetyError("긴급정지 상태에서는 DB 초기화를 할 수 없습니다.")
        stage = self.safety_service.get_stage()
        if stage in SafetyService.LIVE_STAGES:
            raise TradingSafetyError("live 단계에서는 DB 초기화를 할 수 없습니다.")

        db_path = self.store.db_path
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        backup_path = db_path.with_name(f"{db_path.stem}_{stamp}.bak{db_path.suffix}")
        if db_path.exists():
            shutil.copy2(db_path, backup_path)
            with self.store._connect() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        self.store.reset_paper_trading_state()
        worker_state = self.store.get_state("worker_state", {}) or {}
        worker_state.update({"running": False, "current_status": "stopped"})
        self.store.set_state("worker_state", worker_state)

        self.store.add_audit_event(
            scope="system",
            event_type="db_reset",
            severity="critical",
            message="페이퍼 트레이딩 DB 스냅샷 후 초기화",
            payload={
                "reason": reason,
                "backup_path": str(backup_path),
                "initial_cash": config.MOCK_INITIAL_CASH,
            },
        )
        return {
            "backup_path": str(backup_path),
            "paper_cash": self.store.get_paper_cash(),
            "positions": len(self.store.list_positions()),
        }


def build_service_bundle(
    db_path: str | None = None,
    bootstrap_legacy: bool = True,
    auto_resume_worker: bool = False,
) -> ServiceBundle:
    store = SQLiteStore(db_path=db_path, bootstrap_legacy=bootstrap_legacy)
    risk_service = RiskService(store)
    safety_service = SafetyService(store, risk_service)
    analytics_service = AnalyticsService(store)
    trading_service = TradingService(store, risk_service, safety_service)
    backtest_service = BacktestService(store)
    diagnostics_service = DiagnosticsService(store, safety_service)
    agent_service = AgentService(store, analytics_service, trading_service, risk_service, safety_service)
    worker = AgentWorker(store, agent_service)
    if auto_resume_worker and not safety_service.get_emergency_stop().get("enabled"):
        worker.resume_if_interrupted()
    return ServiceBundle(
        store=store,
        risk_service=risk_service,
        safety_service=safety_service,
        analytics_service=analytics_service,
        trading_service=trading_service,
        backtest_service=backtest_service,
        diagnostics_service=diagnostics_service,
        agent_service=agent_service,
        worker=worker,
    )
