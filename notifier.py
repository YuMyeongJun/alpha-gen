"""
notifier.py — 텔레그램 알림 모듈
이유(reason)가 포함된 상세 알림 발송
"""

import requests
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo
import config

KST = ZoneInfo("Asia/Seoul")


def _ts() -> str:
    return datetime.now(KST).strftime("%m/%d %H:%M")


def _send(text: str) -> None:
    """텔레그램 메시지 발송 (실패해도 프로그램 계속)"""
    if not config.TELEGRAM_ENABLED:
        return
    if "여기에" in config.TELEGRAM_BOT_TOKEN or "여기에" in config.TELEGRAM_CHAT_ID:
        print(f"[TG-SKIP] 텔레그램 미설정 → 콘솔 출력:\n{text}\n")
        return
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        res = requests.post(
            url,
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        res.raise_for_status()
    except Exception as e:
        print(f"[TG-ERROR] 텔레그램 발송 실패: {e}")


# ──────────────────────────────────────────────
# 공개 알림 함수
# ──────────────────────────────────────────────

def notify_start(mode: str) -> None:
    _send(
        f"🚀 <b>alpha-gen 시작</b> [{_ts()}]\n"
        f"모드: {mode}\n"
        f"국장 종목: {', '.join(v['name'] for v in config.KR_STOCKS.values())}\n"
        f"미장 종목: {', '.join(v['name'] for v in config.US_STOCKS.values())}"
    )


def notify_sentiment(stock_name: str, score: int, label: str,
                     keywords: list, reason: str) -> None:
    emoji = {2: "🔥", 1: "🟢", 0: "⚪", -1: "🔴", -2: "💀"}.get(score, "❓")
    kw = ", ".join(keywords[:5]) if keywords else "-"
    _send(
        f"{emoji} <b>감성 분석 결과</b> [{_ts()}]\n"
        f"종목: {stock_name}\n"
        f"점수: {score:+d} ({label})\n"
        f"키워드: {kw}\n"
        f"근거: {reason[:200]}"
    )


def notify_buy(stock_name: str, code: str, price: int, qty: int,
               sentiment_score: int, reason: str,
               market: str = "KR", mock: bool = False) -> None:
    tag = "🤖[MOCK] " if mock else ""
    mkt = "🇰🇷 국장" if market == "KR" else "🇺🇸 미장"
    _send(
        f"{tag}🟢 <b>매수 체결</b> [{_ts()}]\n"
        f"시장: {mkt}\n"
        f"종목: {stock_name} ({code})\n"
        f"체결가: {price:,}원 × {qty}주\n"
        f"금액: {price * qty:,}원\n"
        f"AI 점수: {sentiment_score:+d}\n"
        f"매수 근거: {reason[:200]}"
    )


def notify_sell(stock_name: str, code: str, price: int, qty: int,
                pnl: int, reason: str,
                market: str = "KR", mock: bool = False) -> None:
    tag = "🤖[MOCK] " if mock else ""
    pnl_emoji = "📈" if pnl >= 0 else "📉"
    _send(
        f"{tag}🔴 <b>매도 체결</b> [{_ts()}]\n"
        f"종목: {stock_name} ({code})\n"
        f"체결가: {price:,}원 × {qty}주\n"
        f"실현손익: {pnl:+,}원 {pnl_emoji}\n"
        f"매도 사유: {reason}"
    )


def notify_stop_loss(stock_name: str, code: str, loss_pct: float) -> None:
    _send(
        f"⚠️ <b>손절 발동</b> [{_ts()}]\n"
        f"종목: {stock_name} ({code})\n"
        f"손실률: {loss_pct:.2f}%\n"
        f"→ 시장가 전량 매도 실행"
    )


def notify_sleep_mode(reason: str, drawdown_pct: float) -> None:
    _send(
        f"🛑 <b>휴면 모드 진입</b> [{_ts()}]\n"
        f"사유: {reason}\n"
        f"전체 드로우다운: {drawdown_pct:.2f}%\n"
        f"→ 모든 자동매매 중단. 수동 재시작 필요."
    )


def notify_news_summary(topic: str, count: int, avg_score: float) -> None:
    emoji = "🔥" if avg_score >= 1 else ("⚪" if avg_score >= 0 else "❄️")
    _send(
        f"{emoji} <b>뉴스 수집 완료</b> [{_ts()}]\n"
        f"키워드: {topic}\n"
        f"기사 수: {count}건\n"
        f"평균 감성: {avg_score:+.2f}"
    )


def _krw_usd(krw: float, usd_rate: float) -> str:
    """KRW 가격을 '₩X,XXX (≈$Y.YY)' 형태로 반환. usd_rate=0 이면 원화만."""
    if usd_rate > 0:
        return f"₩{int(krw):,} (≈${krw / usd_rate:,.2f})"
    return f"₩{int(krw):,}"


def _format_tech(tech: dict, usd_rate: float = 0.0) -> str:
    """
    technical dict → 텔레그램용 기술 신호 설명 문자열.
    usd_rate: KRW/USD 환율 (예: 1360). 양수이면 모든 원화 가격에 달러 병기.

    technical dict 구조 (evaluate_buy_technicals 반환값):
      rsi, ma5, ma20, current_price, signal, reason,
      volatility: {target_price, open_price, breakout, current_price, ...}
    """
    lines: list[str] = []

    # ── RSI ──────────────────────────────────────
    rsi = tech.get("rsi")
    if rsi is not None:
        if rsi > config.RSI_OVERBOUGHT:
            lines.append(f"  ❌ RSI {rsi:.1f} — 과매수 ({config.RSI_OVERBOUGHT} 초과, 추가 상승 부담)")
        elif rsi < 30:
            lines.append(f"  ✅ RSI {rsi:.1f} — 과매도 구간 (반등 기대)")
        else:
            lines.append(f"  ✅ RSI {rsi:.1f} — 정상 범위 (매수 여력 있음)")

    # ── 이동평균 ──────────────────────────────────
    current = tech.get("current_price")
    ma20 = tech.get("ma20")
    if current and ma20:
        if current >= ma20:
            lines.append(f"  ✅ 이동평균 골든크로스 — 단기선이 장기선(MA20) 위 → 상승추세")
        else:
            lines.append(f"  ❌ 이동평균 데드크로스 — 단기선이 장기선(MA20) 아래 → 하락추세")

    # ── 변동성 돌파 ───────────────────────────────
    vol = tech.get("volatility")
    if vol:
        target = float(vol.get("target_price", 0))
        cur_p = float(vol.get("current_price") or current or 0)
        breakout = vol.get("breakout", False)
        open_p = float(vol.get("open_price", 0))
        k = config.K_VALUE
        if breakout:
            lines.append(
                f"  ✅ 변동성 돌파 — 오늘 진입 기준선 돌파 ✓\n"
                f"      진입 기준선: {_krw_usd(target, usd_rate)}\n"
                f"      현재가:      {_krw_usd(cur_p, usd_rate)}\n"
                f"      ※ 기준선 = 시가({_krw_usd(open_p, usd_rate)}) + 전일등락폭×{k}"
            )
        else:
            diff = target - cur_p
            lines.append(
                f"  ❌ 변동성 미돌파 — 기준선 {_krw_usd(target, usd_rate)}까지 {_krw_usd(diff, usd_rate)} 부족"
            )

    return "\n".join(lines) if lines else "  기술 데이터 없음"


def notify_us_buy_recommendation(
    stock_name: str,
    ticker: str,
    price_usd: float,
    suggested_qty: int,
    sentiment_score: int,
    sentiment_reason: str,
    technical: Optional[dict] = None,
    exchange: str = "NASD",
    usd_rate: float = 0.0,
) -> None:
    """미장 매수 추천 알림 — 시스템이 직접 주문하지 않고 사용자에게 KIS 앱 주문 유도."""
    score_emoji = {2: "🔥", 1: "🟢"}.get(sentiment_score, "🟢")
    exch_label = "NASDAQ" if exchange == "NASD" else exchange

    # 현재가 양쪽 표기
    price_krw = int(price_usd * usd_rate) if usd_rate > 0 else 0
    price_line = (
        f"<b>${price_usd:,.2f}</b> (≈₩{price_krw:,})"
        if price_krw > 0 else f"<b>${price_usd:,.2f}</b>"
    )

    tech_section = ""
    if technical:
        tech_section = f"\n\n📈 <b>기술 신호</b>\n{_format_tech(technical, usd_rate)}"

    _send(
        f"{score_emoji} <b>미장 매수 추천</b> [{_ts()}]\n\n"
        f"🇺🇸 <b>{stock_name}</b> ({ticker} · {exch_label})\n"
        f"현재가: {price_line}  │  추천 수량: <b>{suggested_qty}주</b>\n\n"
        f"📊 <b>AI 감성: {sentiment_score:+d}점</b>\n"
        f"{sentiment_reason[:350]}"
        f"{tech_section}\n\n"
        f"→ KIS 앱에서 직접 매수하세요 📱"
    )


def notify_us_sell_recommendation(
    stock_name: str,
    ticker: str,
    price_usd: float,
    held_qty: int,
    pnl_pct: float,
    reason: str,
    technical: Optional[dict] = None,
    trigger: str = "signal",  # "signal" | "stop_loss"
    usd_rate: float = 0.0,
) -> None:
    """미장 매도 추천 / 손절 알림 — 사용자에게 KIS 앱 매도 유도."""
    pnl_emoji = "📈" if pnl_pct >= 0 else "📉"

    if trigger == "stop_loss":
        header = f"⛔ <b>손절 발동 — 즉시 매도 권고</b> [{_ts()}]"
    else:
        header = f"🔻 <b>미장 매도 추천</b> [{_ts()}]"

    price_krw = int(price_usd * usd_rate) if usd_rate > 0 else 0
    price_line = (
        f"<b>${price_usd:,.2f}</b> (≈₩{price_krw:,})"
        if price_krw > 0 else f"<b>${price_usd:,.2f}</b>"
    )

    tech_section = ""
    if technical and trigger != "stop_loss":
        tech_section = f"\n\n📈 <b>기술 현황</b>\n{_format_tech(technical, usd_rate)}"

    _send(
        f"{header}\n\n"
        f"🇺🇸 <b>{stock_name}</b> ({ticker})\n"
        f"현재가: {price_line}  │  보유: <b>{held_qty}주</b>\n"
        f"평가손익: <b>{pnl_pct:+.2f}%</b> {pnl_emoji}\n\n"
        f"📋 {reason[:350]}"
        f"{tech_section}\n\n"
        f"→ KIS 앱에서 직접 매도하세요 📱"
    )


def notify_custom(msg: str) -> None:
    _send(msg)
