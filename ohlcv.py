"""
ohlcv.py — OHLCV 수집·저장·지표 계산 파이프라인

yfinance 일봉 → SQLite (data/ohlcv.db) → MACD + 볼린저밴드

주요 함수:
    fetch_and_store(ticker, days)  — yfinance 수집 후 upsert
    load_ohlcv(ticker, days)       — DB → DataFrame
    load_with_indicators(ticker)   — OHLCV + MACD + BB 일괄
    get_latest_signals(ticker)     — 매수/매도 신호 dict
    refresh_all(days)              — config 종목 전체 갱신
"""

import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd

import config

KST = ZoneInfo("Asia/Seoul")
_DB_PATH = config.DATA_DIR / "ohlcv.db"

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
            CREATE TABLE IF NOT EXISTS ohlcv (
                ticker  TEXT    NOT NULL,
                date    TEXT    NOT NULL,
                open    REAL    NOT NULL,
                high    REAL    NOT NULL,
                low     REAL    NOT NULL,
                close   REAL    NOT NULL,
                volume  INTEGER NOT NULL,
                PRIMARY KEY (ticker, date)
            );
            CREATE INDEX IF NOT EXISTS idx_ohlcv_td ON ohlcv(ticker, date);
        """)
        c.commit()
        _local.conn = c
    return c


# ── 티커 변환 ──────────────────────────────────────────────────────────────

def _to_yf_ticker(code: str) -> str:
    """KR 6자리 종목코드 → yfinance 형식 (005930 → 005930.KS)"""
    if code.isdigit() and len(code) == 6:
        return f"{code}.KS"
    return code


# ── 수집 · 저장 ────────────────────────────────────────────────────────────

def fetch_and_store(ticker: str, days: int = 200) -> int:
    """
    yfinance에서 일봉 OHLCV 수집 후 SQLite upsert.
    반환: 새로 저장(insert+update)된 행 수.
    """
    import yfinance as yf

    yf_ticker = _to_yf_ticker(ticker)
    end = datetime.now(KST)
    start = end - timedelta(days=days + 10)  # 주말·공휴일 여유분

    hist = yf.Ticker(yf_ticker).history(
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        interval="1d",
        auto_adjust=True,
    )
    if hist.empty:
        return 0

    hist.index = hist.index.tz_localize(None)  # timezone 제거 → 날짜 문자열 변환 단순화
    rows = [
        (
            ticker,
            row.Index.strftime("%Y-%m-%d"),
            round(float(row.Open), 4),
            round(float(row.High), 4),
            round(float(row.Low), 4),
            round(float(row.Close), 4),
            int(row.Volume),
        )
        for row in hist.itertuples()
    ]

    conn = _conn()
    with conn:
        conn.executemany(
            """
            INSERT INTO ohlcv(ticker, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, date) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume
            """,
            rows,
        )
    return len(rows)


# ── 로드 ───────────────────────────────────────────────────────────────────

def load_ohlcv(ticker: str, days: int = 200) -> pd.DataFrame:
    """
    DB에서 ticker의 최근 days일 OHLCV 로드.
    컬럼: date(index), open, high, low, close, volume
    """
    conn = _conn()
    cutoff = (datetime.now(KST) - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT date, open, high, low, close, volume "
        "FROM ohlcv WHERE ticker=? AND date>=? ORDER BY date",
        (ticker, cutoff),
    ).fetchall()

    if not rows:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].astype(float)
    df["volume"] = df["volume"].astype(int)
    return df


# ── 지표 계산 ──────────────────────────────────────────────────────────────

def calc_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """
    MACD 3개 컬럼 추가 (macd, macd_signal, macd_hist).
    최소 slow+signal-1개 행 필요. 부족 시 NaN 허용.
    """
    df = df.copy()
    close = df["close"]
    ema_fast = close.ewm(span=fast, min_periods=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, min_periods=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, min_periods=signal, adjust=False).mean()

    df["macd"]        = macd_line.round(4)
    df["macd_signal"] = signal_line.round(4)
    df["macd_hist"]   = (macd_line - signal_line).round(4)
    return df


def calc_bollinger(
    df: pd.DataFrame,
    window: int = 20,
    n_std: float = 2.0,
) -> pd.DataFrame:
    """
    볼린저밴드 5개 컬럼 추가 (bb_upper, bb_mid, bb_lower, bb_pct_b, bb_width).
    %B: 0 = lower band, 0.5 = mid, 1 = upper band.
    """
    df = df.copy()
    close = df["close"]
    sma = close.rolling(window=window, min_periods=window).mean()
    std = close.rolling(window=window, min_periods=window).std(ddof=0)
    upper = sma + n_std * std
    lower = sma - n_std * std
    bandwidth = (upper - lower) / sma

    df["bb_upper"] = upper.round(4)
    df["bb_mid"]   = sma.round(4)
    df["bb_lower"] = lower.round(4)
    df["bb_pct_b"] = ((close - lower) / (upper - lower)).round(4)
    df["bb_width"] = bandwidth.round(4)
    return df


def load_with_indicators(
    ticker: str,
    days: int = 200,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    bb_window: int = 20,
    bb_std: float = 2.0,
) -> pd.DataFrame:
    """DB 로드 + MACD + 볼린저밴드 일괄 계산."""
    df = load_ohlcv(ticker, days=days)
    if df.empty:
        return df
    df = calc_macd(df, fast=macd_fast, slow=macd_slow, signal=macd_signal)
    df = calc_bollinger(df, window=bb_window, n_std=bb_std)
    return df


# ── 신호 해석 ──────────────────────────────────────────────────────────────

def get_latest_signals(ticker: str) -> dict:
    """
    최신 MACD + 볼린저밴드 신호 반환.

    Returns dict:
      macd_cross   : "golden" | "death" | "none"  (당일 교차 여부)
      macd_bull    : True = MACD > Signal (상승 모멘텀)
      bb_position  : "upper" | "mid" | "lower"
      bb_squeeze   : True = bandwidth < 0.05 (변동성 수축)
      signal_buy   : True = MACD 골든크로스 + BB 중간~하단 (과매도 아님)
      signal_sell  : True = MACD 데드크로스 or BB 상단 돌파
    """
    df = load_with_indicators(ticker, days=200)
    if df.empty or len(df) < 2:
        return {"ticker": ticker, "error": "데이터 부족"}

    cur = df.iloc[-1]
    prev = df.iloc[-2]

    macd_cross = "none"
    if (
        not pd.isna(cur["macd"]) and not pd.isna(cur["macd_signal"])
        and not pd.isna(prev["macd"]) and not pd.isna(prev["macd_signal"])
    ):
        prev_above = prev["macd"] > prev["macd_signal"]
        cur_above = cur["macd"] > cur["macd_signal"]
        if not prev_above and cur_above:
            macd_cross = "golden"
        elif prev_above and not cur_above:
            macd_cross = "death"

    macd_bull = bool(
        not pd.isna(cur["macd"]) and not pd.isna(cur["macd_signal"])
        and cur["macd"] > cur["macd_signal"]
    )

    bb_pct_b = cur["bb_pct_b"]
    if pd.isna(bb_pct_b):
        bb_position = "unknown"
    elif bb_pct_b >= 0.8:
        bb_position = "upper"
    elif bb_pct_b <= 0.2:
        bb_position = "lower"
    else:
        bb_position = "mid"

    bb_squeeze = bool((not pd.isna(cur["bb_width"])) and cur["bb_width"] < 0.05)

    signal_buy = bool(
        macd_cross == "golden"
        and bb_position in ("lower", "mid")
        and not bb_squeeze
    )
    signal_sell = bool(macd_cross == "death" or bb_position == "upper")

    return {
        "ticker":      ticker,
        "date":        str(df.index[-1].date()),
        "close":       cur["close"],
        "macd":        _safe_round(cur["macd"]),
        "macd_signal": _safe_round(cur["macd_signal"]),
        "macd_hist":   _safe_round(cur["macd_hist"]),
        "macd_cross":  macd_cross,
        "macd_bull":   macd_bull,
        "bb_upper":    _safe_round(cur["bb_upper"]),
        "bb_mid":      _safe_round(cur["bb_mid"]),
        "bb_lower":    _safe_round(cur["bb_lower"]),
        "bb_pct_b":    _safe_round(cur["bb_pct_b"]),
        "bb_width":    _safe_round(cur["bb_width"]),
        "bb_position": bb_position,
        "bb_squeeze":  bb_squeeze,
        "signal_buy":  signal_buy,
        "signal_sell": signal_sell,
    }


def _safe_round(v, n: int = 4) -> Optional[float]:
    if pd.isna(v):
        return None
    return round(float(v), n)


# ── 전체 갱신 ──────────────────────────────────────────────────────────────

def refresh_all(days: int = 200) -> dict[str, int]:
    """
    config.KR_STOCKS + US_STOCKS 전 종목 OHLCV 갱신.
    반환: {ticker: 저장된 행 수}
    """
    all_tickers = list(config.KR_STOCKS) + list(config.US_STOCKS)
    results: dict[str, int] = {}
    for ticker in all_tickers:
        try:
            n = fetch_and_store(ticker, days=days)
            results[ticker] = n
        except Exception as e:
            print(f"[ohlcv] {ticker} 수집 실패: {e}")
            results[ticker] = -1
    return results


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    tickers_arg = sys.argv[1:] or (list(config.KR_STOCKS) + list(config.US_STOCKS))
    for t in tickers_arg:
        n = fetch_and_store(t, days=200)
        sig = get_latest_signals(t)
        print(
            f"[{t}] {n}행 저장 | "
            f"MACD {sig.get('macd_cross','?')} | "
            f"BB {sig.get('bb_position','?')} ({sig.get('bb_pct_b','?')}) | "
            f"BUY={sig.get('signal_buy')} SELL={sig.get('signal_sell')}"
        )
