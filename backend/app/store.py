from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import config


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class SQLiteStore:
    def __init__(self, db_path: str | Path | None = None, bootstrap_legacy: bool = True) -> None:
        self.db_path = Path(db_path or config.DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()
        if bootstrap_legacy:
            self.bootstrap_from_legacy_state()
        else:
            self.set_state("legacy_bootstrap_done", True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sentiment_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    keywords_json TEXT NOT NULL,
                    headlines_json TEXT NOT NULL,
                    cached INTEGER NOT NULL DEFAULT 0,
                    analyzed_at TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS signal_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT NOT NULL,
                    session TEXT NOT NULL,
                    sentiment_score INTEGER NOT NULL,
                    sentiment_label TEXT NOT NULL,
                    technical_signal INTEGER NOT NULL,
                    buy_signal INTEGER NOT NULL,
                    current_price REAL NOT NULL,
                    technical_reason TEXT NOT NULL,
                    detail_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS paper_positions (
                    position_key TEXT PRIMARY KEY,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT NOT NULL,
                    session TEXT NOT NULL,
                    qty INTEGER NOT NULL,
                    avg_price REAL NOT NULL,
                    last_price REAL NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS order_events (
                    id TEXT PRIMARY KEY,
                    client_order_id TEXT UNIQUE,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT NOT NULL,
                    session TEXT NOT NULL,
                    side TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    qty INTEGER NOT NULL,
                    requested_price REAL NOT NULL,
                    executed_price REAL,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    realized_pnl REAL,
                    message TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS fills (
                    id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    stock_code TEXT NOT NULL,
                    qty INTEGER NOT NULL,
                    price REAL NOT NULL,
                    realized_pnl REAL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS equity_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_asset REAL NOT NULL,
                    cash REAL NOT NULL,
                    session TEXT NOT NULL,
                    note TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS backtest_runs (
                    id TEXT PRIMARY KEY,
                    parameters_json TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

        if self.get_state("paper_cash") is None:
            self.set_state("paper_cash", config.MOCK_INITIAL_CASH)
        if self.get_state("initial_capital") is None:
            self.set_state("initial_capital", config.TOTAL_CAPITAL)
        if self.get_state("daily_trade_guard") is None:
            self.set_json_state(
                "daily_trade_guard",
                {"date": datetime.now(UTC).date().isoformat(), "codes": []},
            )
        if self.get_state("sleep_mode") is None:
            self.set_state("sleep_mode", False)
        if self.get_state("sleep_reason") is None:
            self.set_state("sleep_reason", "")

    def bootstrap_from_legacy_state(self, legacy_path: str | Path | None = None) -> None:
        legacy_file = Path(legacy_path) if legacy_path else config.PROJECT_ROOT / "mock_state.json"
        if self.get_state("legacy_bootstrap_done"):
            return
        if not legacy_file.exists():
            self.set_state("legacy_bootstrap_done", True)
            return

        try:
            with legacy_file.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            self.set_state("legacy_bootstrap_done", True)
            return

        cash = int(payload.get("cash", config.MOCK_INITIAL_CASH))
        holdings = payload.get("holdings", {}) or {}
        trade_log = payload.get("trade_log", []) or []
        equity_history = payload.get("equity_history", []) or []
        sentiments = payload.get("sentiments", {}) or payload.get("_shared_sentiments", {}) or {}
        bought_today = payload.get("bought_today", []) or []
        bought_date = payload.get("bought_today_date", datetime.now(UTC).date().isoformat())

        self.set_state("paper_cash", cash)
        self.set_json_state("daily_trade_guard", {"date": bought_date, "codes": bought_today})
        self.set_state("sleep_mode", bool(payload.get("sleep_mode", False)))
        self.set_state("sleep_reason", payload.get("sleep_reason", ""))
        self.set_state("initial_capital", int(payload.get("initial_capital", config.TOTAL_CAPITAL)))

        with self._connect() as conn:
            for code, position in holdings.items():
                session = "US" if code in config.US_STOCKS else "KR"
                conn.execute(
                    """
                    INSERT OR REPLACE INTO paper_positions (
                        position_key, stock_code, stock_name, session, qty, avg_price, last_price, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.position_key(session, code),
                        code,
                        position.get("name", code),
                        session,
                        int(position.get("qty", 0)),
                        float(position.get("avg_price", 0)),
                        float(position.get("eval_price", position.get("avg_price", 0))),
                        utc_now(),
                    ),
                )

            for trade in trade_log:
                order_id = str(uuid.uuid4())
                qty = int(trade.get("qty", 0))
                price = float(trade.get("price", 0))
                side = "buy" if trade.get("action") == "매수" else "sell"
                code = trade.get("code", "")
                session = "US" if code in config.US_STOCKS else "KR"
                created_at = trade.get("time", utc_now())
                conn.execute(
                    """
                    INSERT OR IGNORE INTO order_events (
                        id, client_order_id, stock_code, stock_name, session, side, mode, qty,
                        requested_price, executed_price, status, attempt_count, realized_pnl,
                        message, metadata_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        None,
                        code,
                        trade.get("name", code),
                        session,
                        side,
                        "legacy",
                        qty,
                        price,
                        price,
                        "filled",
                        1,
                        trade.get("pnl"),
                        "Imported from legacy mock_state.json",
                        json.dumps({"source": "legacy"}),
                        created_at,
                        created_at,
                    ),
                )

            for snapshot in equity_history:
                total = float(snapshot.get("total", 0))
                cash_val = float(snapshot.get("cash", cash))
                session = snapshot.get("session", "KR")
                created_at = snapshot.get("time", utc_now())
                conn.execute(
                    """
                    INSERT INTO equity_snapshots (total_asset, cash, session, note, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (total, cash_val, session, "Imported from legacy state", created_at),
                )

            for topic, data in sentiments.items():
                conn.execute(
                    """
                    INSERT INTO sentiment_snapshots (
                        topic, score, label, reason, keywords_json, headlines_json, cached, analyzed_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic,
                        int(data.get("score", 0)),
                        data.get("label", "중립"),
                        data.get("reason", ""),
                        json.dumps(data.get("keywords", []), ensure_ascii=False),
                        json.dumps(data.get("headlines", []), ensure_ascii=False),
                        1 if data.get("cached") else 0,
                        data.get("analyzed_at"),
                        utc_now(),
                    ),
                )
            conn.commit()

        self.set_state("legacy_bootstrap_done", True)

    @staticmethod
    def position_key(session: str, stock_code: str) -> str:
        return f"{session}:{stock_code}"

    def get_state(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM agent_state WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return default
        value = row["value"]
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    def set_state(self, key: str, value: Any) -> None:
        serialized = json.dumps(value, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, serialized, utc_now()),
            )
            conn.commit()

    def set_json_state(self, key: str, value: dict[str, Any] | list[Any]) -> None:
        self.set_state(key, value)

    def get_daily_trade_guard(self) -> dict[str, Any]:
        guard = self.get_state("daily_trade_guard", {"date": "", "codes": []})
        today = datetime.now(UTC).date().isoformat()
        if guard.get("date") != today:
            guard = {"date": today, "codes": []}
            self.set_json_state("daily_trade_guard", guard)
        return guard

    def has_bought_today(self, stock_code: str) -> bool:
        return stock_code in self.get_daily_trade_guard().get("codes", [])

    def mark_bought_today(self, stock_code: str) -> None:
        guard = self.get_daily_trade_guard()
        codes = set(guard.get("codes", []))
        codes.add(stock_code)
        guard["codes"] = sorted(codes)
        self.set_json_state("daily_trade_guard", guard)

    def list_positions(self, session: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM paper_positions"
        params: tuple[Any, ...] = ()
        if session:
            query += " WHERE session = ?"
            params = (session,)
        query += " ORDER BY session, stock_code"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_position(self, session: str, stock_code: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM paper_positions WHERE position_key = ?",
                (self.position_key(session, stock_code),),
            ).fetchone()
        return dict(row) if row else None

    def upsert_position(
        self,
        session: str,
        stock_code: str,
        stock_name: str,
        qty: int,
        avg_price: float,
        last_price: float,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO paper_positions (
                    position_key, stock_code, stock_name, session, qty, avg_price, last_price, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.position_key(session, stock_code),
                    stock_code,
                    stock_name,
                    session,
                    qty,
                    avg_price,
                    last_price,
                    utc_now(),
                ),
            )
            conn.commit()

    def remove_position(self, session: str, stock_code: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM paper_positions WHERE position_key = ?",
                (self.position_key(session, stock_code),),
            )
            conn.commit()

    def update_position_price(self, session: str, stock_code: str, last_price: float) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE paper_positions
                SET last_price = ?, updated_at = ?
                WHERE position_key = ?
                """,
                (last_price, utc_now(), self.position_key(session, stock_code)),
            )
            conn.commit()

    def get_paper_cash(self) -> float:
        return float(self.get_state("paper_cash", config.MOCK_INITIAL_CASH))

    def set_paper_cash(self, cash: float) -> None:
        self.set_state("paper_cash", float(cash))

    def save_sentiments(self, results: dict[str, dict[str, Any]]) -> None:
        created_at = utc_now()
        with self._connect() as conn:
            for topic, data in results.items():
                conn.execute(
                    """
                    INSERT INTO sentiment_snapshots (
                        topic, score, label, reason, keywords_json, headlines_json, cached, analyzed_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic,
                        int(data.get("score", 0)),
                        data.get("label", "중립"),
                        data.get("reason", ""),
                        json.dumps(data.get("keywords", []), ensure_ascii=False),
                        json.dumps(data.get("headlines", []), ensure_ascii=False),
                        1 if data.get("cached") else 0,
                        data.get("analyzed_at"),
                        created_at,
                    ),
                )
            conn.commit()

    def latest_sentiments(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s1.*
                FROM sentiment_snapshots s1
                JOIN (
                    SELECT topic, MAX(id) AS max_id
                    FROM sentiment_snapshots
                    GROUP BY topic
                ) latest ON latest.max_id = s1.id
                ORDER BY topic
                """
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["keywords"] = json.loads(item.pop("keywords_json"))
            item["headlines"] = json.loads(item.pop("headlines_json"))
            results.append(item)
        return results

    def save_signals(self, signals: list[dict[str, Any]]) -> None:
        created_at = utc_now()
        with self._connect() as conn:
            for signal in signals:
                conn.execute(
                    """
                    INSERT INTO signal_snapshots (
                        stock_code, stock_name, session, sentiment_score, sentiment_label,
                        technical_signal, buy_signal, current_price, technical_reason, detail_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        signal["stock_code"],
                        signal["stock_name"],
                        signal["session"],
                        signal["sentiment_score"],
                        signal["sentiment_label"],
                        1 if signal["technical_signal"] else 0,
                        1 if signal["buy_signal"] else 0,
                        float(signal["current_price"]),
                        signal["technical_reason"],
                        json.dumps(signal, ensure_ascii=False),
                        created_at,
                    ),
                )
            conn.commit()

    def list_recent_signals(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT detail_json FROM signal_snapshots ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(row["detail_json"]) for row in rows]

    def create_order(
        self,
        *,
        stock_code: str,
        stock_name: str,
        session: str,
        side: str,
        mode: str,
        qty: int,
        requested_price: float,
        client_order_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        order_id = str(uuid.uuid4())
        now = utc_now()
        order = {
            "id": order_id,
            "client_order_id": client_order_id,
            "stock_code": stock_code,
            "stock_name": stock_name,
            "session": session,
            "side": side,
            "mode": mode,
            "qty": qty,
            "requested_price": requested_price,
            "executed_price": None,
            "status": "pending",
            "attempt_count": 0,
            "realized_pnl": None,
            "message": "Order accepted",
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO order_events (
                    id, client_order_id, stock_code, stock_name, session, side, mode, qty,
                    requested_price, executed_price, status, attempt_count, realized_pnl,
                    message, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order["id"],
                    order["client_order_id"],
                    stock_code,
                    stock_name,
                    session,
                    side,
                    mode,
                    qty,
                    requested_price,
                    None,
                    "pending",
                    0,
                    None,
                    order["message"],
                    json.dumps(order["metadata"], ensure_ascii=False),
                    now,
                    now,
                ),
            )
            conn.commit()
        return order

    def update_order(
        self,
        order_id: str,
        *,
        status: str,
        message: str,
        attempt_count: int,
        executed_price: float | None = None,
        realized_pnl: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE order_events
                SET status = ?, message = ?, attempt_count = ?, executed_price = ?,
                    realized_pnl = ?, metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    message,
                    attempt_count,
                    executed_price,
                    realized_pnl,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                    order_id,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM order_events WHERE id = ?",
                (order_id,),
            ).fetchone()
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json"))
        return item

    def add_fill(self, order_id: str, stock_code: str, qty: int, price: float, realized_pnl: float | None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO fills (id, order_id, stock_code, qty, price, realized_pnl, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    order_id,
                    stock_code,
                    qty,
                    price,
                    realized_pnl,
                    utc_now(),
                ),
            )
            conn.commit()

    def list_recent_orders(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM order_events ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            items.append(item)
        return items

    def record_equity(self, total_asset: float, cash: float, session: str, note: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO equity_snapshots (total_asset, cash, session, note, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (total_asset, cash, session, note, utc_now()),
            )
            conn.commit()

    def list_equity(self, limit: int = 120) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT total_asset, cash, session, note, created_at
                FROM equity_snapshots
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        items = [dict(row) for row in rows]
        items.reverse()
        return items

    def save_backtest_run(self, parameters: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        created_at = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO backtest_runs (id, parameters_json, summary_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    run_id,
                    json.dumps(parameters, ensure_ascii=False),
                    json.dumps(summary, ensure_ascii=False),
                    created_at,
                ),
            )
            conn.commit()
        return {"id": run_id, "created_at": created_at, "parameters": parameters, "summary": summary}

    def list_backtest_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM backtest_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["parameters"] = json.loads(item.pop("parameters_json"))
            item["summary"] = json.loads(item.pop("summary_json"))
            items.append(item)
        return items
