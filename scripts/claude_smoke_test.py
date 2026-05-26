#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
import news_analyzer


def _configured() -> bool:
    return config.CLAUDE_CREDENTIALS_CONFIGURED


def main() -> int:
    print("=" * 60)
    print("alpha-gen Claude 뉴스 감성 스모크 테스트")
    print(f"  MOCK_MODE={config.MOCK_MODE}")
    print(f"  MOCK_MODE_REASON={config.MOCK_MODE_REASON}")
    print(f"  MODEL={config.CLAUDE_MODEL}")
    print("=" * 60)

    if not _configured():
        print("\n[SKIP] ANTHROPIC_API_KEY 가 설정되지 않았습니다.")
        print("  .env 에 ANTHROPIC_API_KEY 입력 후 재실행")
        return 0

    if config.MOCK_MODE:
        print("\n[SKIP] 현재는 자동 mock 모드입니다.")
        print("  KIS 자격정보를 입력하거나 MOCK_MODE 설정을 조정한 뒤 재실행하세요.")
        return 0

    topic = config.NEWS_TOPICS[0]
    print(f"\n[1/2] 뉴스 감성 분석 ({topic})...")
    result = news_analyzer.analyze_topic(topic, force_refresh=True)
    print(f"  점수: {result['score']} ({result['label']})")
    print(f"  키워드: {', '.join(result.get('keywords', []))}")
    print(f"  사유: {result.get('reason', '')}")

    print("\n[2/2] 배치 감성 분석...")
    batch = news_analyzer.analyze_all_topics()
    print(f"  토픽 수: {len(batch)}")

    print("\n[OK] Claude 감성 스모크 테스트 완료")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\n[FAIL] Claude smoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
