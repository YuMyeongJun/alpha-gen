"""
migrate_to_sqlite.py — mock_state.json → agent_state.db 일회성 마이그레이션

실행: python migrate_to_sqlite.py
  - mock_state.json 존재 시 DB로 이전 후 .bak 백업 보존
  - mock_state.json 없으면 빈 DB 초기화만 수행
"""

import json
import shutil
from pathlib import Path

import config
from state_store import StateStore

MOCK_STATE_FILE = Path("mock_state.json")
DB_PATH = config.DATA_DIR / "agent_state.db"


def migrate() -> None:
    store = StateStore(DB_PATH)
    print(f"[migrate] DB 초기화 완료: {DB_PATH}")

    if not MOCK_STATE_FILE.exists():
        print("[migrate] mock_state.json 없음 — 빈 DB 사용")
        _verify(store)
        return

    bak = MOCK_STATE_FILE.with_suffix(".json.bak")
    shutil.copy2(MOCK_STATE_FILE, bak)
    print(f"[migrate] 백업 생성: {bak}")

    with open(MOCK_STATE_FILE, encoding="utf-8") as f:
        state = json.load(f)

    store.save(state)
    print("[migrate] 데이터 이전 완료")
    _verify(store)


def _verify(store: StateStore) -> None:
    loaded = store.load()
    print(f"[migrate] OK sentiments    : {len(loaded.get('sentiments', {}))}")
    print(f"[migrate] OK prices        : {len(loaded.get('prices', {}))}")
    print(f"[migrate] OK holdings      : {len(loaded.get('holdings', {}))}")
    print(f"[migrate] OK bought_today  : {loaded.get('bought_today', [])}")
    print(f"[migrate] OK equity_history: {len(loaded.get('equity_history', []))}")
    print(f"[migrate] OK trade_log     : {len(loaded.get('trade_log', []))}")
    print("[migrate] migration complete")


if __name__ == "__main__":
    migrate()
