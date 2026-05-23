"""
main.py — alpha-gen 글로벌 테마 자율 에이전트 메인 루프

[아키텍처]
  뉴스 수집(1h) → Claude 감성 분석 → 기술 지표 검증
  → 리스크 승인 → 주문 실행 → 텔레그램 알림 → 손절 감시 루프

[모드]
  config.MOCK_MODE = True  → 전체 시뮬레이션 (API 없이 테스트)
  config.MOCK_MODE = False → 실제 API 연동
"""

import time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

import config
import news_analyzer
import market_data
import technical
import risk_manager
import notifier
import order_engine
import agent_logging

KST = ZoneInfo("Asia/Seoul")

agent_logging.setup_logging()

# ──────────────────────────────────────────────
# 로거
# ──────────────────────────────────────────────

def log(msg: str, level: str = "INFO") -> None:
    agent_logging.log_agent(msg, level=level, mock=config.MOCK_MODE)


# ──────────────────────────────────────────────
# 상태 추적 (영속화: mock_state.json)
# ──────────────────────────────────────────────
last_sentiment_results: dict = {}        # topic → sentiment


# ══════════════════════════════════════════════
# [1] 뉴스 + 감성 분석 (1시간 주기)
# ══════════════════════════════════════════════

def should_refresh_news() -> bool:
    last = market_data.get_last_news_fetch()
    if last is None:
        return True
    elapsed = (datetime.now(KST) - last).total_seconds() / 60
    return elapsed >= config.NEWS_FETCH_INTERVAL_MIN


def refresh_news_sentiment() -> None:
    global last_sentiment_results
    log("뉴스 수집 및 감성 분석 시작...", "NEWS")
    results = news_analyzer.analyze_all_topics()
    last_sentiment_results = results
    market_data.set_last_news_fetch(datetime.now(KST))

    for topic, r in results.items():
        cached_tag = "[캐시]" if r.get("cached") else "[신규]"
        log(f"  {cached_tag} {topic}: {r['score']:+d} ({r['label']}) | {r.get('reason','')[:60]}", "NEWS")

    market_data._shared_sentiments = results
    market_data.save_agent_state()


# ══════════════════════════════════════════════
# [2] 종합 매수 판단
# ══════════════════════════════════════════════

def evaluate_buy_signal(
    stock_code: str,
    stock_info: dict,
    session: str,
) -> tuple[bool, dict]:
    """
    감성 점수 + 기술 지표를 종합하여 매수 여부 결정.

    Returns:
        (should_buy: bool, detail: dict)
    """
    sentiment = news_analyzer.get_stock_sentiment(stock_code, last_sentiment_results)
    s_score = sentiment["score"]
    s_label = sentiment["label"]

    log(f"[{stock_info['name']}] 감성: {s_score:+d} ({s_label})", "AI")

    if s_score < config.SENTIMENT_BUY_THRESHOLD:
        return False, {
            "reason": f"감성 점수 부족({s_score}<{config.SENTIMENT_BUY_THRESHOLD})",
            "sentiment": sentiment,
        }

    quote = market_data.get_price(stock_code, session)
    price_history = market_data.get_price_history(stock_code, session=session, days=30)
    prev_day = (
        market_data.get_prev_day(stock_code, session)
        if config.ENABLE_VOLATILITY_BREAKOUT
        else None
    )
    tech = technical.evaluate_buy_technicals(
        stock_code, price_history, quote, prev_day=prev_day
    )
    vol = tech.get("volatility") or {}
    if vol:
        log(
            f"[{stock_info['name']}] 기술지표: RSI={tech['rsi']} | "
            f"목표가={vol.get('target_price', '-'):,} | {tech['reason']}",
            "AI",
        )
    else:
        log(f"[{stock_info['name']}] 기술지표: RSI={tech['rsi']} | {tech['reason']}", "AI")

    if not tech["signal"]:
        return False, {
            "reason": f"기술 지표 매수 불가: {tech['reason']}",
            "sentiment": sentiment,
            "technical": tech,
        }

    return True, {
        "reason": f"{s_label} 뉴스 감지 + 기술 지표 확인",
        "sentiment": sentiment,
        "technical": tech,
    }


# ══════════════════════════════════════════════
# [3] 주문 실행 (매수)
# ══════════════════════════════════════════════

def try_buy(stock_code: str, stock_info: dict, session: str) -> None:
    """조건 충족 시 매수 실행"""
    if market_data.is_bought_today(stock_code):
        return

    if risk_manager.SLEEP_MODE:
        log(f"[{stock_info['name']}] 휴면 모드 → 매수 건너뜀", "SLEEP")
        return

    should_buy, detail = evaluate_buy_signal(stock_code, stock_info, session)
    if not should_buy:
        log(f"[{stock_info['name']}] 매수 보류: {detail['reason']}", "INFO")
        return

    price_data = market_data.get_price(stock_code, session)
    cur_price = price_data["current_price"]

    cash, holdings = market_data.get_balance(session)
    total_asset = cash + sum(h["eval_price"] * h["qty"] for h in holdings)

    s_score = detail["sentiment"]["score"]
    qty = risk_manager.get_position_size(total_asset, s_score, cur_price)
    if qty == 0:
        log(f"[{stock_info['name']}] 매수 수량 0주 → 건너뜀 (잔고/한도 부족)", "WARN")
        return

    required = cur_price * qty
    if cash < required:
        log(f"[{stock_info['name']}] 잔고 부족 (필요:{required:,} / 보유:{cash:,})", "WARN")
        return

    ok, msg = order_engine.execute_buy(stock_code, qty, cur_price, session)
    if ok:
        market_data.add_bought_today(stock_code)
        market_data.save_agent_state()
        reason = (
            f"{'[MOCK]' if config.MOCK_MODE else ''} "
            f"{detail['sentiment'].get('reason','')[:100]}"
        )
        log(f"[{stock_info['name']}] 매수 완료: {qty}주 × {cur_price:,}원", "BUY")
        notifier.notify_buy(
            stock_name=stock_info["name"],
            code=stock_code,
            price=cur_price,
            qty=qty,
            sentiment_score=s_score,
            reason=reason,
            market=session,
            mock=config.MOCK_MODE,
        )
        if s_score == 2:
            notifier.notify_sentiment(
                stock_name=stock_info["name"],
                score=s_score,
                label=detail["sentiment"]["label"],
                keywords=detail["sentiment"].get("keywords", []),
                reason=detail["sentiment"].get("reason", ""),
            )
    else:
        log(f"[{stock_info['name']}] 매수 실패: {msg}", "ERROR")


# ══════════════════════════════════════════════
# [4] 전량 매도 (장 마감)
# ══════════════════════════════════════════════

def sell_all_positions(session: str, reason: str = "장 마감 자동 매도") -> None:
    log(f"📤 전량 매도 시작 (사유: {reason})", "SELL")
    _, holdings = market_data.get_balance(session)
    target_codes = set(market_data.get_target_stocks_for_session(session).keys())

    for h in holdings:
        if h["code"] not in target_codes:
            continue
        price_data = market_data.get_price(h["code"], session)
        cur_price = price_data["current_price"]
        ok, pnl, msg = order_engine.execute_sell(h["code"], h["qty"], cur_price, session)
        if ok:
            log(f"[{h['name']}] 매도 완료: {h['qty']}주 @ {cur_price:,} | 손익: {pnl:+,}", "SELL")
            market_data.save_agent_state()
            notifier.notify_sell(
                stock_name=h["name"], code=h["code"],
                price=cur_price, qty=h["qty"], pnl=pnl,
                reason=reason, market=session, mock=config.MOCK_MODE,
            )
        time.sleep(0.3 if config.MOCK_MODE else 0.5)


# ══════════════════════════════════════════════
# [5] 손절 감시 루프
# ══════════════════════════════════════════════

def check_and_execute_stop_loss(session: str) -> None:
    _, holdings = market_data.get_balance(session)
    stop_targets = risk_manager.check_stop_loss(holdings)
    for h in stop_targets:
        log(f"[{h['name']}] 손절 발동! {h['loss_pct']:.2f}%", "RISK")
        notifier.notify_stop_loss(h["name"], h["code"], h["loss_pct"])
        price_data = market_data.get_price(h["code"], session)
        ok, pnl, _ = order_engine.execute_sell(
            h["code"], h["qty"], price_data["current_price"], session
        )
        if ok:
            log(f"[{h['name']}] 손절 매도 완료 | 손익: {pnl:+,}원", "SELL")
            market_data.remove_bought_today(h["code"])
            market_data.save_agent_state()


# ══════════════════════════════════════════════
# [6] 드로우다운 감시
# ══════════════════════════════════════════════

def check_drawdown(session: str) -> None:
    if config.MOCK_MODE:
        total = market_data.get_mock_total_asset()
    else:
        cash, holdings = market_data.get_balance(session)
        total = cash + sum(h["eval_price"] * h["qty"] for h in holdings)

    dd = risk_manager.get_drawdown_pct(total)
    if dd < -2:
        log(f"드로우다운 현황: {dd:.2f}% (한계: -{config.MAX_DRAWDOWN_PCT*100:.0f}%)", "RISK")

    if risk_manager.check_max_drawdown(total):
        log("❗ 최대 드로우다운 초과! 휴면 모드 진입", "RISK")
        sell_all_positions(session, "최대 드로우다운 초과 → 긴급 청산")
        market_data.save_agent_state()
        notifier.notify_sleep_mode(risk_manager.SLEEP_REASON, dd)


# ══════════════════════════════════════════════
# [7] 잔고 출력
# ══════════════════════════════════════════════

def print_balance(session: str) -> None:
    cash, holdings = market_data.get_balance(session)
    total = cash + sum(h["eval_price"] * h["qty"] for h in holdings)
    market_data.record_equity_snapshot(total, session=session, cash=cash)
    dd = risk_manager.get_drawdown_pct(total)
    log(f"💵 예수금: {cash:,}원 | 총자산: {total:,}원 | 드로우다운: {dd:.2f}%", "MONEY")
    for h in holdings:
        ap, ep = h["avg_price"], h["eval_price"]
        pnl_pct = (ep - ap) / ap * 100 if ap else 0
        log(f"  📦 {h['name']}({h['code']}) {h['qty']}주 | 평균:{ap:,} → 현재:{ep:,} | {pnl_pct:+.2f}%", "MONEY")


# ══════════════════════════════════════════════
# [8] 메인 에이전트 루프
# ══════════════════════════════════════════════

def run_agent_loop() -> None:
    """세션에 따라 자동 전환되는 메인 루프"""
    market_data.load_agent_state()
    global last_sentiment_results
    if market_data._shared_sentiments:
        last_sentiment_results = market_data._shared_sentiments

    log("=" * 65)
    log("🚀 alpha-gen 글로벌 테마 자율 에이전트 가동")
    log(f"   모드: {'🤖 Mock 테스트' if config.MOCK_MODE else '🔴 실전' if config.IS_REAL_TRADING else '🟡 모의'}")
    log(f"   국장: {', '.join(v['name'] for v in config.KR_STOCKS.values())}")
    log(f"   미장: {', '.join(v['name'] for v in config.US_STOCKS.values())}")
    log(f"   손절: -{config.STOP_LOSS_PCT*100:.0f}% | 드로우다운 한계: -{config.MAX_DRAWDOWN_PCT*100:.0f}%")
    if risk_manager.SLEEP_MODE:
        log(f"   ⚠️ 저장된 휴면 모드 복원: {risk_manager.SLEEP_REASON}", "SLEEP")
    log("=" * 65)

    if config.MOCK_MODE:
        if risk_manager.INITIAL_CAPITAL == config.TOTAL_CAPITAL:
            risk_manager.set_initial_capital(config.MOCK_INITIAL_CASH)
    else:
        try:
            cash, holdings = market_data.get_balance("KR")
            total = cash + sum(h["eval_price"] * h["qty"] for h in holdings)
            if risk_manager.INITIAL_CAPITAL == config.TOTAL_CAPITAL:
                risk_manager.set_initial_capital(total)
            log(f"초기 자본금: {risk_manager.INITIAL_CAPITAL:,}원")
        except Exception as e:
            log(f"잔고 초기화 실패: {e} → config.TOTAL_CAPITAL 사용", "WARN")
            if risk_manager.INITIAL_CAPITAL == config.TOTAL_CAPITAL:
                risk_manager.set_initial_capital(config.TOTAL_CAPITAL)

    notifier.notify_start(
        "Mock 테스트" if config.MOCK_MODE else ("실전투자" if config.IS_REAL_TRADING else "모의투자")
    )

    if should_refresh_news():
        refresh_news_sentiment()
    elif last_sentiment_results:
        log("저장된 감성 분석 결과 사용 (캐시)", "NEWS")

    # 자산 추이 그래프 시작점
    try:
        _cash, _holdings = market_data.get_balance("KR")
        _total = _cash + sum(h["eval_price"] * h["qty"] for h in _holdings)
        market_data.record_equity_snapshot(_total, session="START", cash=_cash)
    except Exception:
        if config.MOCK_MODE:
            market_data.record_equity_snapshot(
                config.MOCK_INITIAL_CASH, session="START", cash=config.MOCK_INITIAL_CASH
            )

    LOOP_INTERVAL = 3 if config.MOCK_MODE else 30

    while True:
        now = datetime.now(KST)
        t = now.strftime("%H:%M")
        session = market_data.get_market_session()

        if risk_manager.SLEEP_MODE:
            log(f"😴 휴면 모드 ({risk_manager.SLEEP_REASON}). 수동 재시작 필요.", "SLEEP")
            market_data.save_agent_state()
            time.sleep(60)
            continue

        if session == "KR":
            log(f"─── 🇰🇷 한국장 세션 ({t})", "KR")
            stocks = config.KR_STOCKS

            if should_refresh_news():
                refresh_news_sentiment()

            if t >= config.KR_SELL_TIME:
                sell_all_positions("KR", f"한국장 마감({config.KR_SELL_TIME})")
                market_data.clear_bought_today()
                market_data.save_agent_state()
                log("국장 매매 완료. 미장 세션 대기중...", "KR")
                time.sleep(LOOP_INTERVAL * 2)
                continue

            if t >= config.KR_BUY_START:
                for code, info in stocks.items():
                    if not risk_manager.SLEEP_MODE:
                        try_buy(code, info, "KR")

            check_and_execute_stop_loss("KR")
            check_drawdown("KR")
            print_balance("KR")

        elif session == "US":
            log(f"─── 🇺🇸 미국장 세션 ({t})", "US")
            stocks = config.US_STOCKS

            if should_refresh_news():
                refresh_news_sentiment()

            us_close_today = ("04:55" <= t <= "05:05")
            if us_close_today:
                sell_all_positions("US", "미국장 마감(05:00 KST)")
                market_data.clear_bought_today()
                market_data.save_agent_state()
                time.sleep(LOOP_INTERVAL * 2)
                continue

            for code, info in stocks.items():
                if not risk_manager.SLEEP_MODE:
                    try_buy(code, info, "US")

            check_and_execute_stop_loss("US")
            check_drawdown("US")
            print_balance("US")

        else:
            log(f"⏸  장외 시간 ({t}). 다음 세션 대기 중...", "INFO")
            if config.MOCK_MODE:
                if getattr(config, "MOCK_CONTINUOUS", False):
                    log("Mock 연속 모드: 장외 시간 KR 세션 시뮬레이션 (루프 유지)", "AI")
                    if should_refresh_news():
                        refresh_news_sentiment()
                    for code, info in config.KR_STOCKS.items():
                        try_buy(code, info, "KR")
                    check_and_execute_stop_loss("KR")
                    check_drawdown("KR")
                    print_balance("KR")
                else:
                    log("Mock 모드: 장외 시간을 무시하고 KR 세션으로 강제 실행", "AI")
                    if should_refresh_news():
                        refresh_news_sentiment()
                    for code, info in config.KR_STOCKS.items():
                        try_buy(code, info, "KR")
                    check_and_execute_stop_loss("KR")
                    check_drawdown("KR")
                    print_balance("KR")

                    log("Mock 사이클 완료 → 전량 매도 후 종료", "AI")
                    sell_all_positions("KR", "Mock 테스트 완료")
                    market_data.clear_bought_today()

                    total = market_data.get_mock_total_asset()
                    profit = total - config.MOCK_INITIAL_CASH
                    log(f"📊 Mock 결과: 초기={config.MOCK_INITIAL_CASH:,} → 최종={total:,} | 손익={profit:+,}원", "AI")
                    market_data.save_agent_state()
                    break

        market_data.save_agent_state()
        time.sleep(LOOP_INTERVAL)

        if config.MOCK_MODE and len(market_data.agent_bought_today) >= len(config.KR_STOCKS):
            log("Mock: 모든 국장 종목 매수 완료 → 매도 후 종료", "AI")
            time.sleep(1)
            sell_all_positions("KR", "Mock 테스트 종료")
            market_data.clear_bought_today()
            total = market_data.get_mock_total_asset()
            profit = total - config.MOCK_INITIAL_CASH
            log(f"📊 최종 결과: 초기={config.MOCK_INITIAL_CASH:,} → 최종={total:,} | 손익={profit:+,}원", "MONEY")
            market_data.save_agent_state()
            break


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
        market_data.load_agent_state()
        risk_manager.exit_sleep_mode()
        market_data.save_agent_state()
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
