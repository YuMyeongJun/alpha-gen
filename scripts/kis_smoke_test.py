#!/usr/bin/env python3
"""
KIS 모의투자 연동 스모크 테스트 (수동 E2E)

사전 조건:
  1. cp config.example.py config.py
  2. config.py 에 MOCK_MODE=False, IS_REAL_TRADING=False
  3. KIS 모의투자 APP_KEY / SECRET / 계좌번호 입력

실행:
  python scripts/kis_smoke_test.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
import market_data


def _configured() -> bool:
    placeholders = ("여기에", "your_", "YOUR_")
    fields = (config.KIS_APP_KEY, config.KIS_APP_SECRET, config.ACCOUNT_NO)
    if config.MOCK_MODE:
        return False
    return all(f and not any(p in str(f) for p in placeholders) for f in fields)


def main() -> int:
    print("=" * 60)
    print("alpha-gen KIS 모의투자 스모크 테스트")
    print(f"  MOCK_MODE={config.MOCK_MODE}  IS_REAL_TRADING={config.IS_REAL_TRADING}")
    print(f"  KIS_URL={config.KIS_URL}")
    print("=" * 60)

    if not _configured():
        print("\n[SKIP] KIS API 키가 설정되지 않았거나 MOCK_MODE=True 입니다.")
        print("  config.py: MOCK_MODE=False, KIS_* 및 ACCOUNT_NO 입력 후 재실행")
        return 0

    code = next(iter(config.KR_STOCKS))
    name = config.KR_STOCKS[code]["name"]

    print("\n[1/4] OAuth 토큰 발급...")
    token = market_data._get_kis_token()
    print(f"  OK (len={len(token)})")

    print(f"\n[2/4] 시세 조회 ({name} {code})...")
    quote = market_data.kis_get_price(code)
    print(f"  현재가: {quote['current_price']:,}원")

    print(f"\n[3/4] 과거 시세 ({code}, 10일)...")
    hist = market_data.kis_get_price_history(code, days=10)
    print(f"  {len(hist)}개 캔들 (최근: {hist[-1]:,.0f}원)" if hist else "  데이터 없음")

    print("\n[4/4] 잔고 조회...")
    cash, holdings = market_data.kis_get_balance()
    print(f"  예수금: {cash:,}원 | 보유 종목: {len(holdings)}개")
    for h in holdings[:5]:
        print(f"    - {h['name']}({h['code']}) {h['qty']}주")

    print("\n✅ KIS 모의투자 E2E 스모크 테스트 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
