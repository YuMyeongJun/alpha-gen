"""
state_store.py — SQLite 기반 에이전트 상태 저장소

mock_state.json 대체. WAL 모드 + threading.local 연결로 thread-safe.
"""

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional


class StateStore:
    def __init__(self, db_path: "Path | str"):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    # ── 연결 관리 ──────────────────────────────────────
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self._path), check_same_thread=False, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _init_db(self) -> None:
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS kv (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bought_today (
                code TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS sentiments (
                topic TEXT PRIMARY KEY,
                data  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS prices (
                code  TEXT PRIMARY KEY,
                price REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS holdings (
                code TEXT PRIMARY KEY,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS equity_history (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                time    TEXT NOT NULL,
                total   INTEGER NOT NULL,
                cash    INTEGER,
                session TEXT
            );
            CREATE TABLE IF NOT EXISTS trade_log (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL
            );
        """)
        conn.commit()

    # ── 전체 저장 / 로드 ───────────────────────────────
    def save(self, state: dict) -> None:
        conn = self._conn()
        with conn:
            scalar_keys = [
                "last_updated", "bought_today_date", "sleep_mode",
                "sleep_reason", "last_news_fetch", "initial_capital", "cash",
            ]
            for k in scalar_keys:
                if k in state:
                    conn.execute(
                        "INSERT OR REPLACE INTO kv(key, value) VALUES (?, ?)",
                        (k, json.dumps(state[k], ensure_ascii=False)),
                    )

            if "bought_today" in state:
                conn.execute("DELETE FROM bought_today")
                for code in state["bought_today"]:
                    conn.execute("INSERT OR IGNORE INTO bought_today(code) VALUES (?)", (code,))

            if "sentiments" in state:
                conn.execute("DELETE FROM sentiments")
                for topic, data in state["sentiments"].items():
                    conn.execute(
                        "INSERT OR REPLACE INTO sentiments(topic, data) VALUES (?, ?)",
                        (topic, json.dumps(data, ensure_ascii=False)),
                    )

            if "prices" in state:
                conn.execute("DELETE FROM prices")
                for code, price in state["prices"].items():
                    conn.execute(
                        "INSERT OR REPLACE INTO prices(code, price) VALUES (?, ?)",
                        (code, float(price)),
                    )

            if "holdings" in state:
                conn.execute("DELETE FROM holdings")
                for code, data in state["holdings"].items():
                    conn.execute(
                        "INSERT OR REPLACE INTO holdings(code, data) VALUES (?, ?)",
                        (code, json.dumps(data, ensure_ascii=False)),
                    )

            if "equity_history" in state:
                conn.execute("DELETE FROM equity_history")
                for entry in state["equity_history"]:
                    conn.execute(
                        "INSERT INTO equity_history(time, total, cash, session) VALUES (?, ?, ?, ?)",
                        (entry.get("time"), entry.get("total"), entry.get("cash"), entry.get("session")),
                    )

            if "trade_log" in state:
                conn.execute("DELETE FROM trade_log")
                for entry in state["trade_log"]:
                    conn.execute(
                        "INSERT INTO trade_log(data) VALUES (?)",
                        (json.dumps(entry, ensure_ascii=False),),
                    )

    def load(self) -> dict:
        conn = self._conn()
        state: dict[str, Any] = {}

        for row in conn.execute("SELECT key, value FROM kv"):
            state[row[0]] = json.loads(row[1])

        state["bought_today"] = [r[0] for r in conn.execute("SELECT code FROM bought_today")]

        state["sentiments"] = {
            r[0]: json.loads(r[1])
            for r in conn.execute("SELECT topic, data FROM sentiments")
        }

        state["prices"] = {
            r[0]: float(r[1])
            for r in conn.execute("SELECT code, price FROM prices")
        }

        state["holdings"] = {
            r[0]: json.loads(r[1])
            for r in conn.execute("SELECT code, data FROM holdings")
        }

        state["equity_history"] = [
            {"time": r[0], "total": r[1], "cash": r[2], "session": r[3]}
            for r in conn.execute(
                "SELECT time, total, cash, session FROM equity_history ORDER BY id"
            )
        ]

        state["trade_log"] = [
            json.loads(r[0])
            for r in conn.execute("SELECT data FROM trade_log ORDER BY id")
        ]

        return state

    # ── equity_history 실시간 append ──────────────────
    def append_equity(self, time: str, total: int, cash: Optional[int], session: str) -> None:
        conn = self._conn()
        with conn:
            # 같은 타임스탬프 중복 방지
            existing = conn.execute(
                "SELECT 1 FROM equity_history WHERE time = ? ORDER BY id DESC LIMIT 1", (time,)
            ).fetchone()
            if existing:
                return
            conn.execute(
                "INSERT INTO equity_history(time, total, cash, session) VALUES (?, ?, ?, ?)",
                (time, total, cash, session),
            )
            # 최대 2000개 유지
            conn.execute(
                "DELETE FROM equity_history WHERE id NOT IN "
                "(SELECT id FROM equity_history ORDER BY id DESC LIMIT 2000)"
            )

    # ── bought_today CRUD ─────────────────────────────
    def add_bought_today(self, code: str) -> None:
        conn = self._conn()
        with conn:
            conn.execute("INSERT OR IGNORE INTO bought_today(code) VALUES (?)", (code,))

    def remove_bought_today(self, code: str) -> None:
        conn = self._conn()
        with conn:
            conn.execute("DELETE FROM bought_today WHERE code = ?", (code,))

    def clear_bought_today(self) -> None:
        conn = self._conn()
        with conn:
            conn.execute("DELETE FROM bought_today")

    def is_bought_today(self, code: str) -> bool:
        conn = self._conn()
        row = conn.execute(
            "SELECT 1 FROM bought_today WHERE code = ?", (code,)
        ).fetchone()
        return row is not None
