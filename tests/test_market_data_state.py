"""market_data.get_live_sleep_state() 단위 테스트 — alpha_gen.sqlite3를 대시보드 휴면 표시의
source of truth로 사용하는지 검증 (agent_state.db와의 상태 이중화 문제 P1 수정, spec.md 참고)."""

import os

import config
import market_data
from backend.app.store import SQLiteStore


def test_get_live_sleep_state_returns_false_when_not_sleeping(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_MODE", False)
    db_path = str(tmp_path / "alpha_gen.sqlite3")
    SQLiteStore(db_path=db_path, bootstrap_legacy=False)

    is_sleep, reason = market_data.get_live_sleep_state(db_path=db_path)

    assert is_sleep is False
    assert reason == ""


def test_get_live_sleep_state_returns_true_with_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_MODE", False)
    db_path = str(tmp_path / "alpha_gen.sqlite3")
    store = SQLiteStore(db_path=db_path, bootstrap_legacy=False)
    store.set_state("sleep_mode", True)
    store.set_state("sleep_reason", "드로우다운 -15%")

    is_sleep, reason = market_data.get_live_sleep_state(db_path=db_path)

    assert is_sleep is True
    assert reason == "드로우다운 -15%"


def test_get_live_sleep_state_forces_false_in_mock_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_MODE", True)
    db_path = str(tmp_path / "alpha_gen.sqlite3")
    store = SQLiteStore(db_path=db_path, bootstrap_legacy=False)
    store.set_state("sleep_mode", True)
    store.set_state("sleep_reason", "테스트 잔재")

    is_sleep, reason = market_data.get_live_sleep_state(db_path=db_path)

    assert is_sleep is False
    assert reason == ""


def test_get_live_sleep_state_handles_empty_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_MODE", False)
    db_path = str(tmp_path / "does_not_exist_yet.sqlite3")

    is_sleep, reason = market_data.get_live_sleep_state(db_path=db_path)

    assert is_sleep is False
    assert reason == ""
    # 진짜 읽기 전용이어야 한다 — 존재하지 않는 DB를 조회했다고 파일을 만들면 안 됨
    # (독립 리뷰에서 지적된, SQLiteStore를 그대로 썼을 때의 부작용을 재발 방지)
    assert not os.path.exists(db_path)


def test_get_live_sleep_state_does_not_write_to_existing_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MOCK_MODE", False)
    db_path = str(tmp_path / "alpha_gen.sqlite3")
    store = SQLiteStore(db_path=db_path, bootstrap_legacy=False)
    store.set_state("sleep_mode", False)

    def _row_count() -> int:
        conn = store._connect()
        try:
            return conn.execute("SELECT COUNT(*) FROM agent_state").fetchone()[0]
        finally:
            conn.close()

    before = _row_count()
    market_data.get_live_sleep_state(db_path=db_path)
    market_data.get_live_sleep_state(db_path=db_path)
    after = _row_count()

    assert after == before
