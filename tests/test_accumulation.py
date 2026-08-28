"""AccumulationService 테스트 (P15 — 정기 적립 실행)

가장 중요한 검증: 워커를 켰을 때 P9에서 폐기된 모멘텀 전략
(auto_buy_from_signals)이 실행되지 않아야 한다.
"""

from __future__ import annotations

import pytest

import config
from backend.app.services import build_service_bundle


def make_bundle(tmp_path):
    return build_service_bundle(
        db_path=str(tmp_path / "a.sqlite3"), bootstrap_legacy=False, auto_resume_worker=False
    )


# ── 1. 워커 기본 모드가 적립이어야 한다 (안전 핵심) ────────────────────────

def test_worker_defaults_to_accumulation_not_signals(tmp_path):
    """워커를 그냥 켜면 폐기된 모멘텀 전략이 돌면 안 된다."""
    b = make_bundle(tmp_path)
    import inspect
    sig = inspect.signature(b.worker.start)
    assert "mode" in sig.parameters, "워커에 모드 구분이 있어야 한다"
    assert sig.parameters["mode"].default == "accumulation"


def test_signal_mode_must_be_explicit(tmp_path):
    """폐기 전략은 명시적으로 지정해야만 실행된다."""
    b = make_bundle(tmp_path)
    with pytest.raises(ValueError, match="deprecated|폐기"):
        b.worker.start(interval_sec=60, session="KR", place_orders=True, mode="signal")


# ── 2. 목표 비중 배분 ──────────────────────────────────────────────────────

def test_plan_weights_reserve_manual_sleeve():
    total = sum(v["weight"] for v in config.ACCUMULATION_PLAN.values())
    assert total == pytest.approx(1.0 - config.ACCUMULATION_MANUAL_RESERVE_PCT)


def test_accumulation_buys_toward_target_weights(tmp_path):
    b = make_bundle(tmp_path)
    result = b.accumulation_service.run()
    assert result["executed"], "적립 주문이 생성되어야 한다"
    codes = {o["stock_code"] for o in result["executed"]}
    assert codes == set(config.ACCUMULATION_PLAN)


def test_accumulation_never_sells(tmp_path):
    b = make_bundle(tmp_path)
    r1 = b.accumulation_service.run()
    r2 = b.accumulation_service.run(period="2099-01")   # 다른 기간 → 멱등 키 다름
    for o in r1["executed"] + r2["executed"]:
        assert o.get("side", "buy") == "buy", "적립 경로는 매도하지 않는다"


# ── 3. 멱등성 (같은 기간 재실행) ───────────────────────────────────────────

def test_rerun_does_not_overbuy(tmp_path):
    """목표 비중을 이미 채웠으면 재실행해도 추가 매수하지 않는다 (1차 방어)."""
    b = make_bundle(tmp_path)
    r1 = b.accumulation_service.run(period="2026-08")
    r2 = b.accumulation_service.run(period="2026-08")
    assert r1["executed"], "1회차는 주문이 나가야 한다"
    assert not r2["executed"], "목표 달성 후에는 추가 매수가 없어야 한다"
    assert r2["skipped"], "건너뛴 사유가 기록되어야 한다"


def test_idempotency_key_is_deterministic_per_period(tmp_path):
    """같은 기간·종목은 같은 client_order_id를 쓴다 (2차 방어: DB UNIQUE)."""
    b = make_bundle(tmp_path)
    r1 = b.accumulation_service.run(period="2026-08")
    keys = {o["client_order_id"] for o in r1["executed"]}
    assert keys == {"accum:2026-08:KR:069500:buy", "accum:2026-08:KR:161510:buy"}

    # 포지션을 지워 '목표 미달' 상태로 되돌려도, 같은 기간이면 기존 주문을 재사용한다
    before = len(b.store.list_recent_orders(limit=500))
    for code in config.ACCUMULATION_PLAN:
        b.store.remove_position("KR", code)
    b.accumulation_service.run(period="2026-08")
    after = len(b.store.list_recent_orders(limit=500))
    assert after == before, "같은 멱등 키로 신규 주문이 생기면 이중 체결 위험이다"


# ── 4. 안전게이트 준수 ─────────────────────────────────────────────────────

def test_emergency_stop_blocks_accumulation(tmp_path):
    b = make_bundle(tmp_path)
    b.safety_service.set_emergency_stop(enabled=True, reason="테스트")
    result = b.accumulation_service.run()
    assert not result["executed"]
    assert result["blocked"], "차단 사유가 기록되어야 한다"


def test_sleep_mode_blocks_accumulation(tmp_path):
    b = make_bundle(tmp_path)
    b.store.set_state("sleep_mode", True)
    b.store.set_state("sleep_reason", "테스트 휴면")
    result = b.accumulation_service.run()
    assert not result["executed"]
    assert result["blocked"]


# ── 5. 경계 조건 ───────────────────────────────────────────────────────────

def test_insufficient_cash_does_not_crash(tmp_path):
    b = make_bundle(tmp_path)
    b.store.set_paper_cash(100.0)      # 최소 주문금액 미만
    result = b.accumulation_service.run()
    assert isinstance(result["executed"], list)
    assert not result["executed"], "예산 부족 시 주문을 만들지 않는다"


def test_disabled_flag_blocks_everything(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ACCUMULATION_ENABLED", False)
    b = make_bundle(tmp_path)
    result = b.accumulation_service.run()
    assert not result["executed"]
    assert result["blocked"]
