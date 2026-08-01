"""order_registry.py 단위 테스트 — 이중 체결 방지(멱등 주문 키) 로직 검증.

CLAUDE.md가 "실수로라도 건드리면 실제 손실로 직결된다"고 명시한 로직인데 지금까지
테스트가 전혀 없었다 (종합 점검 2026-08-01, P3). 현재 이 모듈은 어디서도 배선되지
않은 상태(dead code)지만, 향후 배선되기 전에 동작을 테스트로 고정해둔다."""

import threading

import order_registry


def _use_tmp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(order_registry, "_DB_PATH", tmp_path / "test_orders.db")
    order_registry._local = threading.local()


def test_make_order_key_format_without_reason():
    key = order_registry.make_order_key("005930", side="BUY")
    parts = key.split("_")
    assert parts[0] == "005930"
    assert parts[1] == "BUY"
    assert len(parts[2]) == 10  # YYYY-MM-DD


def test_make_order_key_format_with_reason():
    key = order_registry.make_order_key("005930", side="SELL", reason="eod")
    assert key.endswith("_EOD")
    assert "SELL" in key


def test_idempotent_buy_blocks_second_call_after_filled(tmp_path, monkeypatch):
    _use_tmp_db(monkeypatch, tmp_path)
    import order_engine

    calls = []

    def fake_execute_buy(ticker, qty, price, session="KR"):
        calls.append((ticker, qty, price, session))
        return True, "체결됨"

    monkeypatch.setattr(order_engine, "execute_buy", fake_execute_buy)

    ok1, msg1 = order_registry.idempotent_buy("005930", qty=1, price=70000, session="KR")
    ok2, msg2 = order_registry.idempotent_buy("005930", qty=1, price=70000, session="KR")

    assert ok1 is True
    assert ok2 is False
    assert "이미 체결" in msg2
    assert len(calls) == 1  # 두 번째 호출은 브로커까지 가지 않아야 함


def test_idempotent_buy_blocks_while_pending(tmp_path, monkeypatch):
    _use_tmp_db(monkeypatch, tmp_path)
    import order_engine

    def fail_if_called(*_a, **_k):
        raise AssertionError("PENDING 상태면 브로커를 다시 호출하면 안 됩니다")

    monkeypatch.setattr(order_engine, "execute_buy", fail_if_called)

    order_key = order_registry.make_order_key("005930", side="BUY")
    order_registry._record(order_key, "005930", "BUY", "", "KR", 1, 70000, "PENDING")

    ok, msg = order_registry.idempotent_buy("005930", qty=1, price=70000, session="KR")

    assert ok is False
    assert "PENDING" in msg


def test_idempotent_sell_realizes_pnl_and_blocks_duplicate(tmp_path, monkeypatch):
    _use_tmp_db(monkeypatch, tmp_path)
    import order_engine

    calls = []

    def fake_execute_sell(ticker, qty, price, session="KR"):
        calls.append((ticker, qty, price, session))
        return True, 5000, "체결됨"

    monkeypatch.setattr(order_engine, "execute_sell", fake_execute_sell)

    ok1, pnl1, msg1 = order_registry.idempotent_sell("005930", qty=1, price=75000, session="KR", reason="EOD")
    ok2, pnl2, msg2 = order_registry.idempotent_sell("005930", qty=1, price=75000, session="KR", reason="EOD")

    assert ok1 is True
    assert pnl1 == 5000
    assert ok2 is False
    assert pnl2 == 0
    assert len(calls) == 1


def test_idempotent_buy_records_failed_status_on_broker_failure(tmp_path, monkeypatch):
    _use_tmp_db(monkeypatch, tmp_path)
    import order_engine

    monkeypatch.setattr(order_engine, "execute_buy", lambda *a, **k: (False, "브로커 거부"))

    ok, msg = order_registry.idempotent_buy("005930", qty=1, price=70000, session="KR")
    assert ok is False

    order_key = order_registry.make_order_key("005930", side="BUY")
    dup, status = order_registry.is_duplicate(order_key)
    assert dup is True
    assert status == "FAILED"

    # FAILED 상태는 FILLED/PENDING이 아니므로 재시도가 다시 브로커를 호출해야 한다(중복 아님)
    retried = []

    def fake_retry_execute_buy(ticker, qty, price, session="KR"):
        retried.append((ticker, qty, price, session))
        return True, "성공"

    monkeypatch.setattr(order_engine, "execute_buy", fake_retry_execute_buy)
    ok2, msg2 = order_registry.idempotent_buy("005930", qty=1, price=70000, session="KR")
    assert ok2 is True
    assert len(retried) == 1
