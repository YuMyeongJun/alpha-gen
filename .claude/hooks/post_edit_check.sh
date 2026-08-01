#!/usr/bin/env bash
# .claude/hooks/post_edit_check.sh (v2 — 실제 서비스 계층 기준)
#
# PostToolUse 훅 (Edit|Write 매칭). Claude Code가 표준입력으로
# {"tool_name":..., "tool_input": {"file_path": "..."}, ...} 형태의 JSON을 넘긴다.
#
# 동작:
#   1) 방금 수정된 파일이 .py 면 문법/린트 검사
#   2) config/__init__.py 또는 risk_manager.py 에서 위험 상수 완화 감지
#   3) 루트 config.py 편집 시 "죽은 파일일 수 있다" 경고 (CLAUDE.md §7-1)
#   4) backend/app/services.py 편집 시 SafetyService 핵심 함수 변경 감지
#   5) .env 편집 시 ALLOW_LIVE_TRADING/EMERGENCY_STOP 완화 감지
#   6) 빠른 회귀 테스트(pytest)
#
# exit 0 = 통과, exit 2 = 차단(에이전트에게 stderr가 전달되어야 함)

set -uo pipefail

INPUT_JSON="$(cat)"

FILE_PATH="$(python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get("tool_input", {}).get("file_path", ""))
except Exception:
    print("")
' <<< "$INPUT_JSON")"

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

echo "[post_edit_check] 대상 파일: $FILE_PATH"

# ── 1) .py 파일 문법/린트 검사 ──────────────────────────────────
if [[ "$FILE_PATH" == *.py ]]; then
  if command -v ruff >/dev/null 2>&1; then
    ruff check "$FILE_PATH" || { echo "[post_edit_check] ruff 검사 실패" >&2; exit 2; }
  else
    python3 -m py_compile "$FILE_PATH" || { echo "[post_edit_check] 문법 오류(py_compile)" >&2; exit 2; }
    echo "[post_edit_check] 참고: ruff 미설치 — py_compile로만 검증함. 'pip install ruff' 권장."
  fi
fi

# ── 2) 루트 config.py 편집 경고 (CLAUDE.md §7-1: 죽은 파일 추정) ──
if [[ "$FILE_PATH" == */config.py || "$FILE_PATH" == "config.py" ]]; then
  echo "[post_edit_check] ⚠️  루트 config.py는 config/__init__.py 패키지에 의해" >&2
  echo "[post_edit_check]     가려질 가능성이 높은 죽은 파일입니다 (CLAUDE.md §7-1)." >&2
  echo "[post_edit_check]     실제 설정을 바꾸려던 것이라면 config/__init__.py를 수정하세요." >&2
fi

# ── 3) 리스크 가드레일 완화 감지 (config/__init__.py, risk_manager.py) ──
if [[ "$FILE_PATH" == *config/__init__.py || "$FILE_PATH" == *risk_manager.py ]]; then
  if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    DIFF="$(git diff -- "$FILE_PATH" 2>/dev/null || true)"
    if echo "$DIFF" | grep -Eq '^\+.*(MAX_POSITION_PCT|STOP_LOSS_PCT|MAX_DRAWDOWN_PCT|LIVE_MAX_ORDERS_PER_CYCLE|LIVE_MAX_ORDERS_PER_DAY|MAX_CONSECUTIVE_LOSSES|MAX_DAILY_LOSS_PCT)[[:space:]]*='; then
      echo "[post_edit_check] ⚠️  리스크/게이트 상수 변경 감지 (MAX_POSITION_PCT 등)." >&2
      echo "[post_edit_check]     Plans.md에 'RISK LIMIT CHANGE APPROVED' 승인 서명이 없으면 진행 금지." >&2
      if ! grep -q "RISK LIMIT CHANGE APPROVED" Plans.md 2>/dev/null; then
        exit 2
      fi
    fi
    if echo "$DIFF" | grep -Eq '^\+.*(ALLOW_LIVE_TRADING|EMERGENCY_STOP)[[:space:]]*='; then
      echo "[post_edit_check] 🚨 CRITICAL: ALLOW_LIVE_TRADING/EMERGENCY_STOP 기본값 변경 감지. 사람 승인 없이는 진행 금지." >&2
      exit 2
    fi
  fi
fi

# ── 4) backend/app/services.py — SafetyService 핵심 함수 변경 감지 ──
if [[ "$FILE_PATH" == *backend/app/services.py ]]; then
  if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    DIFF="$(git diff -- "$FILE_PATH" 2>/dev/null || true)"
    if echo "$DIFF" | grep -Eq '^\+.*(def ensure_order_allowed|def set_emergency_stop|def set_stage|def _consecutive_losses|def _daily_realized_loss|def _count_live_orders)'; then
      echo "[post_edit_check] 🚨 CRITICAL: SafetyService의 핵심 게이트 함수(ensure_order_allowed/" >&2
      echo "[post_edit_check]     set_emergency_stop/set_stage/_consecutive_losses 등) 변경 감지." >&2
      echo "[post_edit_check]     CLAUDE.md §4.3에 따라 사람 승인 없이는 진행 금지." >&2
      exit 2
    fi
  fi
fi

# ── 5) .env 편집 시 실거래 관련 값 완화 감지 ─────────────────────
if [[ "$FILE_PATH" == *.env ]]; then
  if grep -Eq '^ALLOW_LIVE_TRADING[[:space:]]*=[[:space:]]*(true|1|yes|on)' "$FILE_PATH" 2>/dev/null; then
    echo "[post_edit_check] 🚨 CRITICAL: .env에서 ALLOW_LIVE_TRADING을 활성화하려는 시도 감지." >&2
    exit 2
  fi
  if grep -Eq '^EMERGENCY_STOP[[:space:]]*=[[:space:]]*(false|0|no|off)' "$FILE_PATH" 2>/dev/null; then
    echo "[post_edit_check] 🚨 CRITICAL: .env에서 EMERGENCY_STOP을 해제하려는 시도 감지." >&2
    exit 2
  fi
fi

# ── 6) 빠른 회귀 테스트 ───────────────────────────────────────
if command -v pytest >/dev/null 2>&1; then
  if find tests -maxdepth 1 -name 'test_*.py' 2>/dev/null | grep -q .; then
    pytest -q --timeout=60 || { echo "[post_edit_check] pytest 실패" >&2; exit 2; }
  fi
fi

echo "[post_edit_check] 통과."
exit 0
