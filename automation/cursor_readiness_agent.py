#!/usr/bin/env python3
"""One-shot readiness agent using cursor-sdk when API key is present."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

READINESS_PROMPT = """\
alpha-gen readiness 점검을 수행하세요.

1. scripts/setup_check.py 결과 요약
2. pytest tests/test_backend_*.py -q 결과
3. /api/health, /api/ready (서버 실행 중이면)
4. safety policy stage, emergency_stop

한국어로 READY/NOT READY 판정과 차단 사유를 표로 보고하세요.
"""


def run_local_fallback() -> dict:
    setup = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "setup_check.py")],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    tests = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_backend_api.py",
            "tests/test_backend_store.py",
            "-q",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    setup_ok = False
    setup_summary = setup.stderr.strip() or setup.stdout.strip()
    if setup.stdout.strip():
        try:
            report = json.loads(setup.stdout)
            setup_ok = bool(report.get("ok"))
            setup_summary = report.get("summary", setup_summary)
        except json.JSONDecodeError:
            pass

    return {
        "mode": "local_fallback",
        "reason": "CURSOR_API_KEY not set; cursor-sdk skipped",
        "setup_check_ok": setup_ok,
        "setup_summary": setup_summary,
        "pytest_exit_code": tests.returncode,
        "pytest_output": (tests.stdout or "") + (tests.stderr or ""),
    }


def run_sdk_agent() -> dict:
    from cursor_sdk import Agent, AgentOptions, LocalAgentOptions

    result = Agent.prompt(
        READINESS_PROMPT,
        AgentOptions(
            api_key=os.environ["CURSOR_API_KEY"],
            model=os.environ.get("CURSOR_AGENT_MODEL", "composer-2.5"),
            local=LocalAgentOptions(cwd=str(PROJECT_ROOT)),
        ),
    )
    return {
        "mode": "cursor_sdk",
        "status": result.status,
        "result": result.result,
    }


def main() -> int:
    api_key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not api_key:
        payload = run_local_fallback()
    else:
        try:
            payload = run_sdk_agent()
        except ImportError:
            payload = run_local_fallback()
            payload["reason"] = "cursor-sdk not installed; local fallback only"
        except Exception as exc:  # pragma: no cover - SDK runtime errors
            payload = {
                "mode": "cursor_sdk_error",
                "error": str(exc),
                **run_local_fallback(),
            }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload.get("mode") == "local_fallback":
        return 0 if payload.get("pytest_exit_code") == 0 else 1
    return 0 if payload.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
