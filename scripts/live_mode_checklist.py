"""
scripts/live_mode_checklist.py — KIS 실전 모드 전환 체크리스트

실행: python scripts/live_mode_checklist.py [--api]

--api 없으면 config 값만 정적 검사 (네트워크 불필요).
--api 추가 시 KIS 토큰 발급 · 잔고 조회까지 실제 호출 검증.

종료코드: 0 = 전체 통과, 1 = 하나 이상 실패
"""

from __future__ import annotations

import sys
import os

# 프로젝트 루트 기준 import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
SKIP = "SKIP"


def _check(label: str, ok: bool | None, detail: str = "", level: str = FAIL) -> dict:
    if ok is None:
        status = SKIP
    elif ok:
        status = PASS
    else:
        status = level
    return {"label": label, "status": status, "detail": detail}


# ── 개별 체크 함수 ─────────────────────────────────────────────────────────

def check_mock_off() -> dict:
    ok = not config.MOCK_MODE
    reason = f"MOCK_MODE={config.MOCK_MODE}"
    if not ok:
        reason += " → config.py: MOCK_MODE = False 로 변경 필요"
    return _check("MOCK_MODE=False", ok, reason)


def check_real_trading_flag() -> dict:
    ok = config.IS_REAL_TRADING
    reason = f"IS_REAL_TRADING={config.IS_REAL_TRADING}"
    if not ok:
        reason += " → IS_REAL_TRADING = True 로 변경 필요"
    return _check("IS_REAL_TRADING=True", ok, reason)


def check_allow_live_trading() -> dict:
    ok = config.ALLOW_LIVE_TRADING
    reason = f"ALLOW_LIVE_TRADING={config.ALLOW_LIVE_TRADING}"
    if not ok:
        reason += " → ALLOW_LIVE_TRADING = True 로 변경 필요"
    return _check("ALLOW_LIVE_TRADING=True", ok, reason)


def check_operating_stage() -> dict:
    live_stages = {"live_limited", "live_full"}
    ok = config.OPERATING_STAGE in live_stages
    reason = f"OPERATING_STAGE={config.OPERATING_STAGE} (허용: {live_stages})"
    return _check("OPERATING_STAGE=live_*", ok, reason)


def check_emergency_stop() -> dict:
    ok = not config.EMERGENCY_STOP
    reason = f"EMERGENCY_STOP={config.EMERGENCY_STOP}"
    if not ok:
        reason += " → 비상정지 해제 후 진행"
    return _check("EMERGENCY_STOP=False", ok, reason)


def check_kis_credentials() -> dict:
    ok = config.KIS_CREDENTIALS_CONFIGURED
    markers = config.PLACEHOLDER_MARKERS
    details = []
    if any(m in config.KIS_APP_KEY for m in markers):
        details.append("KIS_APP_KEY 미설정")
    if any(m in config.KIS_APP_SECRET for m in markers):
        details.append("KIS_APP_SECRET 미설정")
    if any(m in config.ACCOUNT_NO for m in markers):
        details.append("ACCOUNT_NO 미설정")
    detail = ", ".join(details) if details else "KIS credentials OK"
    return _check("KIS 자격증명 완비", ok, detail)


def check_kis_url() -> dict:
    expected = "https://openapi.koreainvestment.com:9443"
    ok = config.KIS_URL == expected
    return _check(
        "KIS_URL=실전 도메인",
        ok,
        f"KIS_URL={config.KIS_URL}",
    )


def check_anthropic_key() -> dict:
    ok = config.CLAUDE_CREDENTIALS_CONFIGURED
    detail = "ANTHROPIC_API_KEY " + ("설정됨" if ok else "미설정 (감성분석 불가)")
    return _check("Claude API 키", ok, detail, level=WARN)


def check_risk_params() -> dict:
    issues = []
    if config.MAX_POSITION_PCT > 0.10:
        issues.append(f"MAX_POSITION_PCT={config.MAX_POSITION_PCT:.0%} > 10% 위험")
    if config.MAX_DRAWDOWN_PCT > 0.20:
        issues.append(f"MAX_DRAWDOWN_PCT={config.MAX_DRAWDOWN_PCT:.0%} > 20% 위험")
    if config.STOP_LOSS_PCT < 0.02:
        issues.append(f"STOP_LOSS_PCT={config.STOP_LOSS_PCT:.0%} < 2% 너무 좁음")
    if config.LIVE_MAX_ORDERS_PER_DAY > 10:
        issues.append(f"LIVE_MAX_ORDERS_PER_DAY={config.LIVE_MAX_ORDERS_PER_DAY} > 10")
    ok = len(issues) == 0
    detail = "; ".join(issues) if issues else (
        f"포지션≤{config.MAX_POSITION_PCT:.0%} | "
        f"손절≥{config.STOP_LOSS_PCT:.0%} | "
        f"DD≤{config.MAX_DRAWDOWN_PCT:.0%}"
    )
    return _check("리스크 파라미터 안전 범위", ok, detail, level=WARN)


def check_no_mock_continuous() -> dict:
    # 실전에서 MOCK_CONTINUOUS는 의미 없지만 혼동 방지
    ok = not getattr(config, "MOCK_CONTINUOUS", False)
    reason = f"MOCK_CONTINUOUS={getattr(config, 'MOCK_CONTINUOUS', False)}"
    return _check("MOCK_CONTINUOUS=False", ok, reason, level=WARN)


def check_order_dedup() -> dict:
    try:
        import order_registry  # noqa: F401
        ok = True
        detail = "order_registry.py 존재 — idempotent 주문 사용 가능"
    except ImportError:
        ok = False
        detail = "order_registry.py 없음 — 이중 주문 위험"
    return _check("Idempotent 주문 레지스트리", ok, detail, level=WARN)


# ── API 호출 체크 (--api 플래그 시) ─────────────────────────────────────────

def check_kis_token_api() -> dict:
    try:
        import market_data
        market_data.reset_kis_token_cache()
        token = market_data._get_kis_token()
        ok = bool(token)
        return _check("KIS 토큰 발급 (실전)", ok, "토큰 발급 성공" if ok else "토큰 발급 실패")
    except Exception as e:
        return _check("KIS 토큰 발급 (실전)", False, str(e)[:120])


def check_kis_balance_api() -> dict:
    try:
        import market_data
        cash, holdings = market_data.kis_get_balance()
        detail = f"예수금={cash:,}원 | 보유종목={len(holdings)}개"
        return _check("KIS 잔고 조회 (실전)", True, detail)
    except Exception as e:
        return _check("KIS 잔고 조회 (실전)", False, str(e)[:120])


def check_order_registry_db() -> dict:
    try:
        from order_registry import today_orders
        orders = today_orders()
        return _check("OrderRegistry DB 접근", True, f"오늘 주문 {len(orders)}건")
    except Exception as e:
        return _check("OrderRegistry DB 접근", False, str(e)[:120])


# ── 체크리스트 실행 ────────────────────────────────────────────────────────

def run_checklist(api: bool = False) -> tuple[bool, list[dict]]:
    checks = [
        check_mock_off(),
        check_real_trading_flag(),
        check_allow_live_trading(),
        check_operating_stage(),
        check_emergency_stop(),
        check_kis_credentials(),
        check_kis_url(),
        check_anthropic_key(),
        check_risk_params(),
        check_no_mock_continuous(),
        check_order_dedup(),
    ]
    if api:
        checks += [
            check_kis_token_api(),
            check_kis_balance_api(),
            check_order_registry_db(),
        ]
    overall = all(c["status"] in (PASS, WARN, SKIP) for c in checks)
    return overall, checks


def _fmt(c: dict) -> str:
    icons = {PASS: "[PASS]", FAIL: "[FAIL]", WARN: "[WARN]", SKIP: "[SKIP]"}
    icon = icons.get(c["status"], c["status"])
    line = f"  {icon} {c['label']}"
    if c["detail"]:
        line += f"\n         {c['detail']}"
    return line


def main() -> None:
    api = "--api" in sys.argv
    print("=" * 60)
    print("  KIS 실전 모드 전환 체크리스트")
    print("=" * 60)

    overall, checks = run_checklist(api=api)

    for c in checks:
        print(_fmt(c))

    print("=" * 60)
    passed = sum(1 for c in checks if c["status"] == PASS)
    failed = sum(1 for c in checks if c["status"] == FAIL)
    warned = sum(1 for c in checks if c["status"] == WARN)

    summary = f"  PASS={passed} FAIL={failed} WARN={warned}"
    if overall and failed == 0:
        print(f"  RESULT: GO  {summary}")
    else:
        print(f"  RESULT: NO-GO  {summary}")
        print("  FAIL 항목 해결 후 재실행하세요.")
    print("=" * 60)
    sys.exit(0 if (overall and failed == 0) else 1)


if __name__ == "__main__":
    main()
