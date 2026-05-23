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


def notify_custom(msg: str) -> None:
    _send(msg)
