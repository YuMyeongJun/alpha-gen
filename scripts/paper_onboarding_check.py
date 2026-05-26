#!/usr/bin/env python3
"""KIS paper onboarding gate: env, smoke tests, setup_check summary."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE = PROJECT_ROOT / "env.example"


def run_script(relative: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / relative)],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output.strip()


def main() -> int:
    quick = "--quick" in sys.argv
    steps: list[dict[str, str]] = []

    if not ENV_FILE.exists():
        steps.append(
            {
                "step": "create-env",
                "status": "fail",
                "detail": f".env missing. Run: copy env.example .env  (or scripts/init_env.ps1)",
            }
        )
    else:
        steps.append({"step": "create-env", "status": "pass", "detail": str(ENV_FILE)})

    kis_code, kis_out = run_script("scripts/kis_smoke_test.py")
    if "[SKIP]" in kis_out:
        steps.append(
            {
                "step": "kis-smoke",
                "status": "skip",
                "detail": "Set real KIS keys in .env and MOCK_MODE=false",
            }
        )
    elif kis_code == 0:
        steps.append({"step": "kis-smoke", "status": "pass", "detail": "KIS mock E2E OK"})
    else:
        steps.append({"step": "kis-smoke", "status": "fail", "detail": kis_out[-500:]})

    claude_code, claude_out = run_script("scripts/claude_smoke_test.py")
    if "[SKIP]" in claude_out:
        steps.append(
            {
                "step": "claude-smoke",
                "status": "skip",
                "detail": "Set ANTHROPIC_API_KEY and MOCK_MODE=false in .env",
            }
        )
    elif claude_code == 0:
        steps.append({"step": "claude-smoke", "status": "pass", "detail": "Claude sentiment OK"})
    else:
        steps.append({"step": "claude-smoke", "status": "fail", "detail": claude_out[-500:]})

    setup_code, setup_out = run_script("scripts/setup_check.py")
    setup_ok = False
    stage = "-"
    missing: list[str] = []
    if setup_out.strip():
        try:
            report = json.loads(setup_out)
            setup_ok = bool(report.get("ok"))
            stage = report.get("environment", {}).get("operating_stage", "-")
            missing = report.get("integrations", {}).get("missing_config") or []
        except json.JSONDecodeError:
            pass

    if setup_code == 0 and setup_ok:
        steps.append({"step": "readiness", "status": "pass", "detail": f"setup_check ready, stage={stage}"})
    else:
        steps.append(
            {
                "step": "readiness",
                "status": "fail" if setup_code != 0 else "warn",
                "detail": f"stage={stage}, missing={', '.join(missing) or 'none'}",
            }
        )

    if quick:
        steps.append({"step": "pytest", "status": "skip", "detail": "skipped (--quick)"})
    else:
        pytest_proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        pytest_out = (pytest_proc.stdout or "") + (pytest_proc.stderr or "")
        if pytest_proc.returncode == 0:
            steps.append({"step": "pytest", "status": "pass", "detail": pytest_out.splitlines()[-1] if pytest_out else "ok"})
        else:
            steps.append({"step": "pytest", "status": "fail", "detail": pytest_out[-500:]})

    dist_index = PROJECT_ROOT / "frontend" / "dist" / "index.html"
    if dist_index.exists():
        steps.append({"step": "run-console", "status": "pass", "detail": "frontend/dist built"})
    else:
        steps.append(
            {
                "step": "run-console",
                "status": "warn",
                "detail": "Run: cd frontend && npm run build",
            }
        )

    steps.append(
        {
            "step": "observe-paper",
            "status": "manual",
            "detail": "Run worker 2-3 days on paper; then promote-stage to shadow",
        }
    )

    print(json.dumps({"steps": steps, "env_example": str(ENV_EXAMPLE)}, ensure_ascii=False, indent=2))

    blocking = [s for s in steps if s["status"] == "fail"]
    if blocking:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
