"""
order_registry.py — Idempotent 주문 처리

동일 주문 키(ticker_side_date)로 중복 주문 차단.
프로세스 재시작 · 네트워크 재시도 시에도 이중 체결 방지.

사용법:
    from order_registry import idempotent_buy, idempotent_sell

    ok, msg = idempotent_buy("005930", qty=2, price=75000, session="KR")
    ok, pnl, msg = idempotent_sell("005930", qty=2, price=76000, session="KR", reason="EOD")
"""

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import config

KST = ZoneInfo("Asia/Seoul")
_DB_PATH = config.DATA_DIR / "agent_state.db"  # state_store와 동일 DB, 별도 테이블

_local = threading.local()


# ── DB 연결 ────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = getattr(_local, "conn", None)
    if c is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=10)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.row_factory = sqlite3.Row
        c.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                order_key  TEXT PRIMARY KEY,
                ticker     TEXT NOT NULL,
                side       TEXT NOT NULL,
                reason     TEXT NOT NULL DEFAULT '',
                session    TEXT NOT NULL DEFAULT 'KR',
                qty        INTEGER NOT NULL,
                price      INTEGER NOT NULL,
                status     TEXT NOT NULL DEFAULT 'PENDING',
                ack_no     TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_orders_date
                ON orders(created_at);
        """)
        c.commit()
        _local.conn = c
    return c


# ── 키 생성 ────────────────────────────────────────────────────────────────

def make_order_key(ticker: str, side: str, reason: str = "") -> str:
    """
    당일 KST 기준 유니크 주문 키.
    예: '005930_BUY_2026-05-27' / '005930_SELL_2026-05-27_EOD'
    """
    date_str = datetime.now(KST).strftime("%Y-%m-%d")
    parts = [ticker, side, date_str]
    if reason:
        parts.append(reason.upper())
    return "_".join(parts)


# ── 레지스트리 조회·기록 ────────────────────────────────────────────────────

def is_duplicate(order_key: str) -> tuple[bool, str]:
    """
    중복 여부 반환: (is_dup, status).
    FILLED → 이미 체결됨 (진짜 중복).
    PENDING → 이전 시도 결과 불명 (재시도 가능하지만 주의 필요).
    """
    conn = _conn()
    row = conn.execute(
        "SELECT status FROM orders WHERE order_key=?", (order_key,)
    ).fetchone()
    if row is None:
        return False, "NONE"
    return True, row["status"]


def _record(
    order_key: str,
    ticker: str,
    side: str,
    reason: str,
    session: str,
    qty: int,
    price: int,
    status: str,
    ack_no: str = "",
) -> None:
    conn = _conn()
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    with conn:
        conn.execute(
            """
            INSERT INTO orders
                (order_key, ticker, side, reason, session, qty, price, status, ack_no,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(order_key) DO UPDATE SET
                status=excluded.status,
                ack_no=excluded.ack_no,
                updated_at=excluded.updated_at
            """,
            (order_key, ticker, side, reason, session, qty, price, status, ack_no, now, now),
        )


def _update_status(order_key: str, status: str, ack_no: str = "") -> None:
    conn = _conn()
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    with conn:
        conn.execute(
            "UPDATE orders SET status=?, ack_no=?, updated_at=? WHERE order_key=?",
            (status, ack_no, now, order_key),
        )


def today_orders(session: Optional[str] = None) -> list[dict]:
    """오늘 KST 기준 주문 목록"""
    conn = _conn()
    date_str = datetime.now(KST).strftime("%Y-%m-%d")
    if session:
        rows = conn.execute(
            "SELECT * FROM orders WHERE created_at >= ? AND session=? ORDER BY created_at",
            (date_str, session),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM orders WHERE created_at >= ? ORDER BY created_at",
            (date_str,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Idempotent 주문 래퍼 ───────────────────────────────────────────────────

def idempotent_buy(
    ticker: str,
    qty: int,
    price: int,
    session: str = "KR",
    reason: str = "",
) -> tuple[bool, str]:
    """
    중복 안전 매수.
    - 이미 FILLED: (False, "이미 체결된 매수 주문")
    - 이미 PENDING: FILLED로 간주하고 스킵 (재시도 불필요)
    - 신규: 실제 주문 후 상태 기록
    """
    order_key = make_order_key(ticker, side="BUY", reason=reason)
    dup, status = is_duplicate(order_key)

    if dup and status == "FILLED":
        return False, f"[idempotent] {ticker} BUY 이미 체결 (key={order_key})"
    if dup and status == "PENDING":
        # 이전 시도 결과 불명 — 안전을 위해 중단
        return False, f"[idempotent] {ticker} BUY PENDING 상태 — 이전 주문 결과 확인 필요 (key={order_key})"

    _record(order_key, ticker, "BUY", reason, session, qty, price, "PENDING")

    try:
        from order_engine import execute_buy
        ok, msg = execute_buy(ticker, qty, price, session=session)
    except Exception as exc:
        _update_status(order_key, "FAILED")
        return False, f"[idempotent] {ticker} BUY 실패: {exc}"

    if ok:
        _update_status(order_key, "FILLED")
    else:
        _update_status(order_key, "FAILED")

    return ok, msg


def idempotent_sell(
    ticker: str,
    qty: int,
    price: int,
    session: str = "KR",
    reason: str = "EOD",
) -> tuple[bool, int, str]:
    """
    중복 안전 매도.
    reason: "EOD" | "SL" (stop-loss) | "DD" (drawdown) 등
    반환: (ok, realized_pnl, message)
    """
    order_key = make_order_key(ticker, side="SELL", reason=reason)
    dup, status = is_duplicate(order_key)

    if dup and status == "FILLED":
        return False, 0, f"[idempotent] {ticker} SELL/{reason} 이미 체결 (key={order_key})"
    if dup and status == "PENDING":
        return False, 0, f"[idempotent] {ticker} SELL/{reason} PENDING — 이전 결과 확인 필요"

    _record(order_key, ticker, "SELL", reason, session, qty, price, "PENDING")

    try:
        from order_engine import execute_sell
        ok, pnl, msg = execute_sell(ticker, qty, price, session=session)
    except Exception as exc:
        _update_status(order_key, "FAILED")
        return False, 0, f"[idempotent] {ticker} SELL 실패: {exc}"

    if ok:
        _update_status(order_key, "FILLED")
    else:
        _update_status(order_key, "FAILED")

    return ok, pnl, msg


# ── 진단 ───────────────────────────────────────────────────────────────────

def print_today_summary() -> None:
    orders = today_orders()
    if not orders:
        print("[order_registry] 오늘 주문 없음")
        return
    print(f"[order_registry] 오늘 주문 {len(orders)}건:")
    for o in orders:
        print(
            f"  {o['created_at']} | {o['ticker']:8s} {o['side']:4s} {o['reason']:4s}"
            f" | qty={o['qty']} price={o['price']:,} | {o['status']}"
        )


if __name__ == "__main__":
    print_today_summary()
