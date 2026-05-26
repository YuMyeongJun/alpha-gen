from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.conftest import isolated_subprocess_env

ROOT = Path(__file__).resolve().parents[1]


def test_env_example_exists() -> None:
    assert (ROOT / "env.example").exists()


def test_paper_onboarding_check_runs() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "paper_onboarding_check.py"), "--quick"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=isolated_subprocess_env(),
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    steps = {item["step"]: item for item in payload["steps"]}
    assert steps["create-env"]["status"] == "pass"
    assert steps["pytest"]["status"] == "skip"


def test_kis_smoke_script_exits_zero_when_skipped() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "kis_smoke_test.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=isolated_subprocess_env(),
    )
    assert proc.returncode == 0
    assert "[SKIP]" in proc.stdout or "SKIP" in proc.stdout
