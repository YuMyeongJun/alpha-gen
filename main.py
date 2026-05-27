"""
main.py — alpha-gen 글로벌 테마 자율 에이전트 메인 루프

[아키텍처]
  ServiceBundle(services.py) 위임 구조:
  분석(AnalyticsService) → 안전 검증(SafetyService) → 주문(TradingService)
  → 손절(run_stop_loss_cycle) → 텔레그램 알림 → 루프 반복

[모드]
  config.MOCK_MODE = True  → 전체 시뮬레이션 (API 없이 테스트)
  config.MOCK_MODE = False → 실제 API 연동
"""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import market_data
import risk_manager
import notifier
import agent_logging
from backend.app.services import build_service_bundle

KST = ZoneInfo("Asia/Seoul")

agent_logging.setup_logging()

# ──────────────────────────────────────────────
# 로거
# ──────────────────────────────────────────────

def log(msg: str, level: str = "INFO") -> None:
    agent_logging.log_agent(msg, level=level, mock=config.MOCK_MODE)


# ══════════════════════════════════════════════
# [1] 잔고 출력
# ══════════════════════════════════════════════


def log_portfolio_snapshot(snapshot: dict) -> None:
    cash = int(snapshot.get("cash", 0))
    total = int(snapshot.get("total_asset", 0))
    drawdown = float(snapshot.get("risk", {}).get("drawdown_pct", 0))
    log(f"💵 예수금: {cash:,}원 | 총자산: {total:,}원 | 드로우다운: {drawdown:.2f}%", "MONEY")
    for position in snapshot.get("positions", []):
        avg_price = float(position.get("avg_price", 0))
        last_price = float(position.get("last_price", 0))
        pnl_pct = ((last_price - avg_price) / avg_price * 100) if avg_price else 0
        log(
            f"  📦 {position['stock_name']}({position['stock_code']}) {position['qty']}주 | "
            f"평균:{int(avg_price):,} → 현재:{int(last_price):,} | {pnl_pct:+.2f}%",
            "MONEY",
        )


def emit_order_notifications(orders: list[dict]) -> None:
    for order in orders:
        if order.get("status") not in {"filled", "reconciled"}:
            continue
        metadata = order.get("metadata", {}) or {}
        signal = metadata.get("signal_snapshot", {}) or {}
        session = order.get("session", "KR")
        price = int(order.get("executed_price") or order.get("requested_price") or 0)
        qty = int(order.get("qty", 0))
        if order.get("side") == "buy":
            notifier.notify_buy(
                stock_name=order.get("stock_name", order.get("stock_code", "")),
                code=order.get("stock_code", ""),
                price=price,
                qty=qty,
                sentiment_score=int(signal.get("sentiment_score", 0)),
                reason=signal.get("sentiment_reason") or metadata.get("reason") or metadata.get("source", "agent_cycle"),
                market=session,
                mock=config.MOCK_MODE,
            )
        else:
            if metadata.get("source") == "stop_loss":
                notifier.notify_stop_loss(
                    order.get("stock_name", order.get("stock_code", "")),
                    order.get("stock_code", ""),
                    float(metadata.get("loss_pct", 0)),
                )
            notifier.notify_sell(
                stock_name=order.get("stock_name", order.get("stock_code", "")),
                code=order.get("stock_code", ""),
                price=price,
                qty=qty,
                pnl=int(order.get("realized_pnl") or 0),
                reason=metadata.get("reason") or metadata.get("source", "sell"),
                market=session,
                mock=config.MOCK_MODE,
            )


# ══════════════════════════════════════════════
# [2] 메인 에이전트 루프
# ══════════════════════════════════════════════

def run_agent_loop() -> None:
    """웹 제어면과 동일한 서비스 코어를 사용하는 CLI 루프"""
    bundle = build_service_bundle()
    store = bundle.store
    trading_service = bundle.trading_service
    agent_service = bundle.agent_service
    safety_service = bundle.safety_service

    log("=" * 65)
    log("🚀 alpha-gen Cursor-Native 에이전트 가동")
    log(f"   운영 단계: {safety_service.get_stage()} | 실거래 허용: {config.ALLOW_LIVE_TRADING}")
    log(f"   국장: {', '.join(v['name'] for v in config.KR_STOCKS.values())}")
    log(f"   미장: {', '.join(v['name'] for v in config.US_STOCKS.values())}")
    log(f"   손절: -{config.STOP_LOSS_PCT*100:.0f}% | 드로우다운 한계: -{config.MAX_DRAWDOWN_PCT*100:.0f}%")
    log("=" * 65)

    notifier.notify_start(
        "Mock 테스트" if config.MOCK_MODE else ("실전투자" if config.IS_REAL_TRADING else "모의투자")
    )

    loop_interval = 3 if config.MOCK_MODE else max(config.AGENT_INTERVAL_SEC, 15)
    last_sleep_notified = False

    while True:
        now = datetime.now(KST)
        t = now.strftime("%H:%M")
        session = market_data.get_market_session()

        if safety_service.get_emergency_stop().get("enabled"):
            reason = safety_service.get_emergency_stop().get("reason") or "긴급 정지"
            log(f"🛑 긴급 정지 상태: {reason}", "SLEEP")
            time.sleep(loop_interval)
            continue

        if not bundle.risk_service.can_trade():
            if not last_sleep_notified:
                summary = bundle.risk_service.get_summary()
                notifier.notify_sleep_mode(summary.get("sleep_reason", "sleep_mode"), summary.get("drawdown_pct", 0))
                last_sleep_notified = True
            log("😴 휴면 모드. 자동 주문을 건너뜁니다.", "SLEEP")
            time.sleep(loop_interval)
            continue

        last_sleep_notified = False

        if session == "KR":
            log(f"─── 🇰🇷 한국장 세션 ({t})", "KR")
            if config.ENABLE_AUTO_LIQUIDATION and t >= config.KR_SELL_TIME:
                closed = trading_service.close_positions("KR", f"한국장 마감({config.KR_SELL_TIME})")
                emit_order_notifications(closed)
                store.clear_bought_today()
                log("국장 마감 청산 완료. 미장 세션 대기중...", "KR")
                time.sleep(loop_interval)
                continue
            result = agent_service.run_cycle(session="KR", force_refresh=False, place_orders=True)
        elif session == "US":
            log(f"─── 🇺🇸 미국장 세션 ({t})", "US")
            if config.ENABLE_AUTO_LIQUIDATION and "04:55" <= t <= "05:05":
                closed = trading_service.close_positions("US", "미국장 마감(05:00 KST)")
                emit_order_notifications(closed)
                store.clear_bought_today()
                time.sleep(loop_interval)
                continue
            result = agent_service.run_cycle(session="US", force_refresh=False, place_orders=True)
        else:
            log(f"⏸  장외 시간 ({t}). 다음 세션 대기 중...", "INFO")
            if config.MOCK_MODE and getattr(config, "MOCK_CONTINUOUS", False):
                result = agent_service.run_cycle(session="KR", force_refresh=False, place_orders=True)
            else:
                time.sleep(loop_interval)
                continue

        emit_order_notifications(result.get("executed_orders", []))
        emit_order_notifications(result.get("stop_loss_orders", []))
        log(result["cycle_summary"]["last_summary"], "INFO")
        log_portfolio_snapshot(result["portfolio"])
        time.sleep(loop_interval)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="alpha-gen 자동매매 에이전트")
    parser.add_argument(
        "--wake",
        action="store_true",
        help="저장된 휴면 모드를 해제하고 시작 (실전/모의투자용)",
    )
    args = parser.parse_args()

    if args.wake:
        bundle = build_service_bundle()
        bundle.store.set_state("sleep_mode", False)
        bundle.store.set_state("sleep_reason", "")
        risk_manager.exit_sleep_mode()
        log("휴면 모드 해제 완료 (--wake)", "INFO")

    try:
        run_agent_loop()
    except KeyboardInterrupt:
        log("사용자 강제 종료 (Ctrl+C). 안전하게 종료합니다.", "WARN")
        market_data.save_agent_state()
    except Exception as e:
        log(f"치명적 오류로 종료: {e}", "ERROR")
        market_data.save_agent_state()
        raise
