#!/usr/bin/env python3
"""Print a compact readiness summary from setup_check JSON."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def main() -> int:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "setup_check.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        print(proc.stderr or "setup_check failed", file=sys.stderr)
        return proc.returncode or 1

    report = json.loads(proc.stdout)
    env = report.get("environment", {})
    integrations = report.get("integrations", {})
    policy = report.get("policy", {})
    stop = policy.get("emergency_stop", {})

    lines = [
        f"setup_check: {'OK' if report.get('ok') else 'DEGRADED'} ({report.get('summary', '-')})",
        f"stage: {env.get('operating_stage', policy.get('stage', '-'))}",
        f"emergency_stop: {'ON' if stop.get('enabled') else 'off'}",
        f"kis: {'yes' if integrations.get('kis_configured') else 'no'}",
        f"claude: {'yes' if integrations.get('claude_configured') else 'no'}",
        f"missing: {', '.join(integrations.get('missing_config') or []) or 'none'}",
    ]
    print("\n".join(lines))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
