"""
dividends.py — 배당 데이터 레이어 (P7)

spec.md P7 / P12 참조. `ohlcv.py` 컨벤션을 따른다 (전용 SQLite, 티커 변환, refresh_all).

설계 원칙:
  1. **순수 계산 함수와 저장 계층을 분리한다.** point-in-time 지표는 DB 없이 검증 가능해야 한다.
  2. **룩어헤드 차단**: 후행 지표는 asof 시점 이전 배당만 합산한다.
  3. **fail-closed**: 데이터가 없거나 검증 불가면 후보에서 제외한다 (통과시키지 않는다).
  4. **payout_ratio는 라이브 전용.** yfinance `.info`는 '오늘 값'만 주므로 과거 시점 재구성이
     불가능하다. 백테스트 판정 근거로 쓰면 룩어헤드다 — `PAYOUT_IS_LIVE_ONLY` 참조.

알려진 제약 (2026-08-27 실측):
  - KR 종목은 `trailingEps`가 전부 None → 적자 필터 구현 불가
  - `dividendYield`는 **퍼센트**로 반환된다 (KT 4.5 = 4.5%)
  - REIT은 FFO 기준 배당이라 payout_ratio가 100%를 넘는 게 정상 (Realty Income 236%)
"""

from __future__ import annotations

import math
import sqlite3
import threading
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Optional, Sequence
from zoneinfo import ZoneInfo

import config

KST = ZoneInfo("Asia/Seoul")
_DB_PATH = config.DATA_DIR / "dividends.db"
_local = threading.local()

TRAILING_WINDOW_DAYS = 365

# 백테스트 판정 근거로 payout_ratio를 쓰면 룩어헤드다. 이 상수는 그 사실을 코드에 못박는다.
PAYOUT_IS_LIVE_ONLY = True


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
            CREATE TABLE IF NOT EXISTS dividends (
                ticker  TEXT NOT NULL,
                ex_date TEXT NOT NULL,
                amount  REAL NOT NULL,
                PRIMARY KEY (ticker, ex_date)
            );
            CREATE INDEX IF NOT EXISTS idx_div_td ON dividends(ticker, ex_date);

            CREATE TABLE IF NOT EXISTS dividend_meta (
                ticker           TEXT PRIMARY KEY,
                dividend_yield   REAL,
                payout_ratio     REAL,
                ex_dividend_date TEXT,
                is_reit          INTEGER NOT NULL DEFAULT 0,
                fetched_at       TEXT NOT NULL
            );
        """)
        c.commit()
        _local.conn = c
    return c


# ── 티커 변환 ──────────────────────────────────────────────────────────────

def yf_ticker_candidates(code: str) -> list[str]:
    """
    KR 6자리 코드는 .KS/.KQ 양쪽을 시도한다.

    P9에서 실증: `.KS`가 KOSDAQ 종목에 대해 빈 결과가 아니라 소량의 오염 데이터를
    반환하는 경우가 있다. 따라서 '먼저 성공한 쪽'이 아니라 '더 많은 쪽'을 채택해야 한다.
    """
    if code.isdigit() and len(code) == 6:
        return [f"{code}.KS", f"{code}.KQ"]
    return [code]


# ── 순수 계산: point-in-time 지표 ──────────────────────────────────────────

def _to_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _valid_amount(value: Any) -> Optional[float]:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(amount) or math.isinf(amount) or amount <= 0:
        return None
    return amount


def calc_trailing_dividend(records: Iterable[Sequence[Any]], asof: Any) -> float:
    """
    [asof - 365일, asof] 구간의 주당 배당금 합계.

    룩어헤드 차단: asof 이후 배당은 절대 포함하지 않는다.
    """
    asof_d = _to_date(asof)
    if asof_d is None:
        return 0.0
    floor = asof_d - timedelta(days=TRAILING_WINDOW_DAYS)

    total = 0.0
    for rec in records or []:
        if not rec or len(rec) < 2:
            continue
        ex_date = _to_date(rec[0])
        amount = _valid_amount(rec[1])
        if ex_date is None or amount is None:
            continue
        if floor <= ex_date <= asof_d:
            total += amount
    return total


def calc_trailing_yield(
    records: Iterable[Sequence[Any]], asof: Any, price: Any
) -> Optional[float]:
    """후행 12개월 배당수익률(**퍼센트**). 검증 불가하면 None (fail-closed)."""
    try:
        px = float(price)
    except (TypeError, ValueError):
        return None
    if math.isnan(px) or math.isinf(px) or px <= 0:
        return None

    total = calc_trailing_dividend(records, asof)
    if total <= 0:
        return None
    return total / px * 100


def calc_dividend_streak_years(
    records: Iterable[Sequence[Any]], asof: Any, tolerance: Optional[float] = None,
    max_lookback: int = 20,
) -> int:
    """
    최근 몇 년 연속으로 배당이 삭감되지 않았는가.

    **달력연도 버킷을 쓰지 않는다.** 한국은 2023년 배당절차 개선으로 배당락일이
    12월 → 익년 2~4월로 이동한 사례가 많아, 달력연도로 묶으면 배당락일 이동을
    '삭감'으로 오판한다 (예: SK텔레콤 2024년이 3회분만 잡힘, 삼성화재 2023년이 0원).

    대신 asof에서 1년씩 거슬러 올라가며 **후행 12개월 합계(TTM)**를 비교한다.
    분기배당 1회분(연간의 25%)이 창 경계를 넘나드는 정도는 `tolerance`로 흡수한다.
    """
    tol = config.DIVIDEND_CUT_TOLERANCE if tolerance is None else tolerance
    asof_d = _to_date(asof)
    if asof_d is None:
        return 0

    streak = 0
    for k in range(1, max_lookback + 1):
        cur = calc_trailing_dividend(records, asof_d - timedelta(days=TRAILING_WINDOW_DAYS * (k - 1)))
        prev = calc_trailing_dividend(records, asof_d - timedelta(days=TRAILING_WINDOW_DAYS * k))
        if cur <= 0 or prev <= 0:
            break
        if cur < prev * (1 - tol):
            break
        streak += 1
    return streak


def normalize_yield_pct(raw: Any) -> Optional[float]:
    """yfinance `dividendYield`(퍼센트) 정규화. 검증 불가하면 None."""
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value) or value < 0:
        return None
    return value


def classify_payout(payout_ratio: Any, is_reit: bool = False) -> str:
    """
    배당 함정 판정. 반환: "ok" | "trap" | "loss_making" | "unknown".

    ⚠️ 라이브 전용. 백테스트에서 쓰면 룩어헤드다 (`PAYOUT_IS_LIVE_ONLY`).
    REIT은 EPS가 아니라 FFO 기준으로 배당하므로 별도(더 높은) 임계값을 쓴다.
    """
    if payout_ratio is None:
        return "unknown"
    try:
        ratio = float(payout_ratio)
    except (TypeError, ValueError):
        return "unknown"
    if math.isnan(ratio) or math.isinf(ratio):
        return "unknown"
    if ratio < 0:
        return "loss_making"

    limit = (
        config.DIVIDEND_REIT_MAX_PAYOUT_RATIO if is_reit else config.DIVIDEND_MAX_PAYOUT_RATIO
    )
    return "trap" if ratio > limit else "ok"


# ── 저장 / 로드 ────────────────────────────────────────────────────────────

def store_dividends(ticker: str, records: Iterable[Sequence[Any]]) -> int:
    rows = []
    for rec in records or []:
        if not rec or len(rec) < 2:
            continue
        ex_date = _to_date(rec[0])
        amount = _valid_amount(rec[1])
        if ex_date is None or amount is None:
            continue
        rows.append((ticker, ex_date.isoformat(), amount))
    if not rows:
        return 0
    conn = _conn()
    with conn:
        conn.executemany(
            "INSERT INTO dividends(ticker, ex_date, amount) VALUES (?,?,?) "
            "ON CONFLICT(ticker, ex_date) DO UPDATE SET amount=excluded.amount",
            rows,
        )
    return len(rows)


def load_dividends(ticker: str) -> list[tuple[str, float]]:
    rows = _conn().execute(
        "SELECT ex_date, amount FROM dividends WHERE ticker=? ORDER BY ex_date", (ticker,)
    ).fetchall()
    return [(r["ex_date"], float(r["amount"])) for r in rows]


def store_meta(ticker: str, *, dividend_yield: Any, payout_ratio: Any,
               ex_dividend_date: Any = None, is_reit: bool = False) -> None:
    conn = _conn()
    with conn:
        conn.execute(
            "INSERT INTO dividend_meta(ticker, dividend_yield, payout_ratio, ex_dividend_date,"
            " is_reit, fetched_at) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(ticker) DO UPDATE SET dividend_yield=excluded.dividend_yield,"
            " payout_ratio=excluded.payout_ratio, ex_dividend_date=excluded.ex_dividend_date,"
            " is_reit=excluded.is_reit, fetched_at=excluded.fetched_at",
            (ticker, normalize_yield_pct(dividend_yield),
             None if payout_ratio is None else float(payout_ratio),
             None if ex_dividend_date is None else str(ex_dividend_date)[:10],
             1 if is_reit else 0, datetime.now(KST).isoformat()),
        )


def load_meta(ticker: str) -> Optional[dict[str, Any]]:
    row = _conn().execute("SELECT * FROM dividend_meta WHERE ticker=?", (ticker,)).fetchone()
    return dict(row) if row else None


# ── 수집 ───────────────────────────────────────────────────────────────────

def fetch_and_store(code: str) -> int:
    """
    yfinance에서 배당 이력 + 메타를 수집한다.
    .KS/.KQ 후보 중 **배당 이력이 더 많은 쪽**을 채택한다 (P9 오염 데이터 교훈).
    """
    import yfinance as yf

    best_records: list[tuple[str, float]] = []
    best_info: dict[str, Any] = {}
    for cand in yf_ticker_candidates(code):
        try:
            t = yf.Ticker(cand)
            series = t.dividends
            records = [(idx.strftime("%Y-%m-%d"), float(v)) for idx, v in series.items()]
        except Exception:
            continue
        if len(records) > len(best_records):
            best_records = records
            try:
                best_info = t.info or {}
            except Exception:
                best_info = {}

    if best_records:
        store_dividends(code, best_records)
    quote_type = str(best_info.get("quoteType", "")).upper()
    sector = str(best_info.get("sector", "")).upper()
    store_meta(
        code,
        dividend_yield=best_info.get("dividendYield"),
        payout_ratio=best_info.get("payoutRatio"),
        ex_dividend_date=best_info.get("exDividendDate"),
        is_reit=("REIT" in quote_type or "REAL ESTATE" in sector),
    )
    return len(best_records)


def refresh_all(codes: Optional[Iterable[str]] = None) -> dict[str, int]:
    import time

    codes = list(codes) if codes else list({**config.KR_STOCKS, **config.US_STOCKS})
    out: dict[str, int] = {}
    for code in codes:
        try:
            out[code] = fetch_and_store(code)
        except Exception:
            out[code] = 0
        time.sleep(0.4)
    return out


if __name__ == "__main__":
    result = refresh_all()
    ok = sum(1 for v in result.values() if v > 0)
    print(f"배당 이력 수집 완료: {ok}/{len(result)}종목")
