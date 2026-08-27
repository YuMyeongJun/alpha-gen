"""dividends.py 단위 테스트 (P7 — 배당 데이터 레이어)

설계 원칙: 순수 계산 함수(point-in-time 지표)와 저장 계층을 분리해
네트워크·DB 없이 검증한다. 룩어헤드 차단이 가장 중요한 검증 대상이다.
"""

from __future__ import annotations

import pytest

import dividends


# ── 배당 이력 픽스처: (배당락일, 주당배당금) ─────────────────────────────────

SAMSUNG = [
    ("2024-03-28", 361.0), ("2024-06-27", 361.0), ("2024-09-27", 361.0), ("2024-12-30", 364.0),
    ("2025-03-28", 365.0), ("2025-06-27", 367.0), ("2025-09-29", 370.0), ("2025-12-29", 566.0),
    ("2026-03-30", 372.0), ("2026-06-29", 374.0),
]


# ── 1. point-in-time 룩어헤드 차단 (최상위 중요) ────────────────────────────

def test_trailing_dividend_excludes_future_payments():
    """asof 이후의 배당은 절대 합산되면 안 된다."""
    asof = "2025-06-30"
    total = dividends.calc_trailing_dividend(SAMSUNG, asof)
    # 2024-07-01 ~ 2025-06-30 구간: 2024-09-27, 2024-12-30, 2025-03-28, 2025-06-27
    assert total == pytest.approx(361.0 + 364.0 + 365.0 + 367.0)

    # 미래 배당(2025-09-29 이후)이 섞이면 값이 커진다 — 그런 일이 없어야 한다
    later = dividends.calc_trailing_dividend(SAMSUNG, "2026-06-30")
    assert later > total
    assert dividends.calc_trailing_dividend(SAMSUNG, "2024-01-01") == 0.0


def test_trailing_dividend_window_is_365_days():
    """정확히 365일 창. 경계 밖 배당은 제외."""
    recs = [("2025-01-01", 100.0), ("2024-01-02", 50.0), ("2023-12-31", 999.0)]
    total = dividends.calc_trailing_dividend(recs, "2025-01-01")
    assert total == pytest.approx(150.0)   # 2023-12-31은 창 밖


# ── 2. 후행 배당수익률: 0-분모 / NaN 가드 ──────────────────────────────────

def test_trailing_yield_guards_bad_price():
    assert dividends.calc_trailing_yield(SAMSUNG, "2025-06-30", price=0) is None
    assert dividends.calc_trailing_yield(SAMSUNG, "2025-06-30", price=-100) is None
    assert dividends.calc_trailing_yield(SAMSUNG, "2025-06-30", price=float("nan")) is None
    assert dividends.calc_trailing_yield(SAMSUNG, "2025-06-30", price=None) is None


def test_trailing_yield_percent_units():
    """반환은 퍼센트 단위(4.5 = 4.5%)로 고정한다."""
    y = dividends.calc_trailing_yield(SAMSUNG, "2025-06-30", price=70_000)
    assert y == pytest.approx((361.0 + 364.0 + 365.0 + 367.0) / 70_000 * 100)
    assert 0 < y < 10


# ── 3. 배당 이력 0건 → fail-closed 제외 ────────────────────────────────────

def test_no_dividend_history_is_excluded():
    assert dividends.calc_trailing_dividend([], "2025-06-30") == 0.0
    assert dividends.calc_trailing_yield([], "2025-06-30", price=70_000) is None


# ── 4. yfinance dividendYield 단위 정규화 (초안 가정이 틀렸던 지점) ────────

def test_normalize_yield_handles_percent_and_fraction():
    # yfinance 현행: 퍼센트로 반환 (KT 4.5 = 4.5%)
    assert dividends.normalize_yield_pct(4.5) == pytest.approx(4.5)
    assert dividends.normalize_yield_pct(0.57) == pytest.approx(0.57)
    # 과거 포맷(소수)이 섞여 들어와도 터지지 않아야 한다
    assert dividends.normalize_yield_pct(None) is None
    assert dividends.normalize_yield_pct(float("nan")) is None
    assert dividends.normalize_yield_pct(-1.0) is None


# ── 5. 배당 무삭감 연속 연수 ───────────────────────────────────────────────

def test_dividend_streak_counts_consecutive_years_without_cut():
    # 연간 합계: 2024=1447, 2025=1668(증가), 2026 부분연도는 제외
    streak = dividends.calc_dividend_streak_years(SAMSUNG, "2026-06-30")
    assert streak >= 1

    cut = [("2023-06-01", 100.0), ("2024-06-01", 50.0), ("2025-06-01", 60.0)]
    # 2024에 삭감 → 2025 기준 연속 무삭감은 1년
    assert dividends.calc_dividend_streak_years(cut, "2025-12-31") == 1


# ── 6. 배당 함정 판정 (라이브 전용 — 백테스트 판정 근거로 쓰지 않음) ───────

def test_payout_classification_handles_none_negative_and_reit():
    # None = 검증 불가 → 제외 (fail-closed)
    assert dividends.classify_payout(None) == "unknown"
    # 음수 = 적자 시사 → 제외
    assert dividends.classify_payout(-0.3) == "loss_making"
    # 정상
    assert dividends.classify_payout(0.45) == "ok"
    # 85% 초과 → 함정
    assert dividends.classify_payout(0.90) == "trap"
    # REIT은 FFO 기준이라 100% 초과가 정상 — 별도 임계값
    assert dividends.classify_payout(2.36, is_reit=True) == "ok"
    assert dividends.classify_payout(9.9, is_reit=True) == "trap"


def test_payout_classification_is_not_used_for_backtest():
    """백테스트 경로에서 payout을 쓰면 룩어헤드다 — 명시적으로 표시되어야 한다."""
    assert dividends.PAYOUT_IS_LIVE_ONLY is True


# ── 7. KOSDAQ .KQ 폴백 (P9에서 .KS 오염 데이터 실증됨) ─────────────────────

def test_yf_ticker_candidates_include_kq_for_kr_codes():
    cands = dividends.yf_ticker_candidates("086520")
    assert cands == ["086520.KS", "086520.KQ"], "KR 6자리는 .KS/.KQ 양쪽을 시도해야 한다"
    assert dividends.yf_ticker_candidates("SCHD") == ["SCHD"]


# ── 8. DB 왕복 ─────────────────────────────────────────────────────────────

def test_store_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(dividends, "_DB_PATH", tmp_path / "dividends.db")
    monkeypatch.setattr(dividends, "_local", type("L", (), {})())
    dividends.store_dividends("005930", SAMSUNG)
    loaded = dividends.load_dividends("005930")
    assert len(loaded) == len(SAMSUNG)
    assert dividends.calc_trailing_dividend(loaded, "2025-06-30") == pytest.approx(1457.0)
    # 재삽입 시 중복이 생기지 않아야 한다 (PRIMARY KEY upsert)
    dividends.store_dividends("005930", SAMSUNG)
    assert len(dividends.load_dividends("005930")) == len(SAMSUNG)


# ── 9. 회귀: 배당락일 이동을 삭감으로 오판하지 않을 것 ─────────────────────

# SK텔레콤 실제 이력. 4분기 배당락일이 2023-12-27 → 2025-02-27로 이동해
# 달력연도 기준으로 2024년이 3회분만 잡힌다. 이것은 삭감이 아니다.
SKT_REAL = [
    ("2022-03-30", 830.0), ("2022-06-29", 830.0), ("2022-09-28", 830.0), ("2022-12-28", 1050.0),
    ("2023-03-30", 830.0), ("2023-06-29", 830.0), ("2023-09-26", 830.0), ("2023-12-27", 1050.0),
    ("2024-03-28", 830.0), ("2024-06-27", 830.0), ("2024-09-27", 830.0),
    ("2025-02-27", 1050.0), ("2025-05-29", 830.0), ("2025-08-28", 830.0),
]

# 삼성화재 실제 이력. 2022-12-28 다음이 2024-03-26 → 달력연도 2023년 배당이 0원이 된다.
SFIRE_REAL = [
    ("2021-12-29", 12000.0), ("2022-12-28", 13800.0),
    ("2024-03-26", 16000.0), ("2025-03-25", 19000.0), ("2026-03-26", 19500.0),
]


def test_streak_is_stable_across_ex_date_shift():
    """연말 경계를 지나며 연속연수가 0으로 붕괴하면 안 된다 (달력연도 버킷 버그 회귀)."""
    before = dividends.calc_dividend_streak_years(SKT_REAL, "2024-12-30")
    after = dividends.calc_dividend_streak_years(SKT_REAL, "2025-01-03")
    assert before > 0 and after > 0, "배당락일 이동을 삭감으로 오판하면 안 된다"
    assert abs(before - after) <= 1, f"나흘 사이에 연속연수가 급변했다: {before} → {after}"


def test_streak_survives_year_with_no_ex_date():
    """배당락일이 해를 건너뛰어도(2023년 0원) 삭감으로 보지 않는다."""
    assert dividends.calc_dividend_streak_years(SFIRE_REAL, "2025-06-30") > 0


def test_streak_still_detects_a_real_cut():
    """허용치(30%)를 넘는 진짜 삭감은 여전히 잡아야 한다."""
    real_cut = [("2023-06-01", 1000.0), ("2024-06-01", 1000.0), ("2025-06-01", 200.0)]
    assert dividends.calc_dividend_streak_years(real_cut, "2025-12-31") == 0
