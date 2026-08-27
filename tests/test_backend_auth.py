"""backend/app/main.py 인증 게이트 테스트 (P5)

위협 모델: 이 API는 실계좌 주문(`/api/orders/manual`)과 긴급정지 해제
(`/api/safety/emergency-stop`)를 노출한다. n8n 등 외부에서 호출하려면
루프백 밖으로 열어야 하고, 그 순간 인증 부재가 곧 자산 탈취 경로가 된다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import config
from backend.app.main import create_app, ensure_bind_is_safe

TOKEN = "test-token-abc123"


def make_client(tmp_path):
    return TestClient(create_app(db_path=str(tmp_path / "a.sqlite3"), bootstrap_legacy=False))


# ── 바인딩 안전성 (기동 시점 게이트) ────────────────────────────────────────

def test_non_loopback_bind_without_token_is_refused():
    """0.0.0.0으로 열면서 토큰이 없으면 기동을 거부해야 한다."""
    for host in ("0.0.0.0", "::", "192.168.0.10"):
        with pytest.raises(RuntimeError, match="API_AUTH_TOKEN"):
            ensure_bind_is_safe(host, "")


def test_loopback_bind_without_token_is_allowed():
    """루프백 전용이면 토큰 없이도 기동 가능 (현행 동작 유지)."""
    for host in ("127.0.0.1", "localhost", "::1"):
        ensure_bind_is_safe(host, "")


def test_non_loopback_bind_with_token_is_allowed():
    ensure_bind_is_safe("0.0.0.0", TOKEN)


# ── 토큰 미설정: 기존 동작 유지 (하위호환) ─────────────────────────────────

def test_without_token_configured_requests_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "API_AUTH_TOKEN", "")
    client = make_client(tmp_path)
    assert client.get("/api/portfolio").status_code == 200


# ── 토큰 설정 시 강제 ──────────────────────────────────────────────────────

def test_missing_header_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "API_AUTH_TOKEN", TOKEN)
    client = make_client(tmp_path)
    assert client.get("/api/portfolio").status_code == 401


def test_wrong_token_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "API_AUTH_TOKEN", TOKEN)
    client = make_client(tmp_path)
    r = client.get("/api/portfolio", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_correct_token_is_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "API_AUTH_TOKEN", TOKEN)
    client = make_client(tmp_path)
    r = client.get("/api/portfolio", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200


def test_order_and_safety_routes_are_protected(tmp_path, monkeypatch):
    """가장 위험한 두 경로가 반드시 막혀야 한다."""
    monkeypatch.setattr(config, "API_AUTH_TOKEN", TOKEN)
    client = make_client(tmp_path)
    assert client.post("/api/orders/manual", json={
        "stock_code": "005930", "session": "KR", "side": "buy", "qty": 1}).status_code == 401
    assert client.post("/api/safety/emergency-stop", json={
        "enabled": False, "reason": "x"}).status_code == 401
    assert client.post("/api/safety/stage", json={"stage": "live_full"}).status_code == 401


# ── 헬스체크 면제 ──────────────────────────────────────────────────────────

def test_health_and_ready_are_exempt(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "API_AUTH_TOKEN", TOKEN)
    client = make_client(tmp_path)
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/ready").status_code == 200


# ── CORS 와일드카드 제거 ───────────────────────────────────────────────────

def test_cors_is_not_wildcard(tmp_path):
    """allow_origins=['*'] + allow_credentials=True 조합을 남겨두지 않는다."""
    app = create_app(db_path=str(tmp_path / "b.sqlite3"), bootstrap_legacy=False)
    origins = []
    for mw in app.user_middleware:
        opts = getattr(mw, "kwargs", None) or getattr(mw, "options", {})
        if "allow_origins" in opts:
            origins = opts["allow_origins"]
    assert origins != ["*"], "와일드카드 CORS는 제거되어야 한다"
    assert origins, "허용 출처가 비어 있으면 안 된다"
