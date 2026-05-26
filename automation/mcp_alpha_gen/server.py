from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .client import api_get, format_json

PROJECT_ROOT = Path(__file__).resolve().parents[2]

mcp = FastMCP(
    "alpha-gen",
    instructions=(
        "Alpha-Gen trading ops MCP. Read-only API probes and local diagnostics. "
        "Does not place broker orders."
    ),
)


@mcp.tool()
def health_check() -> str:
    """Check /api/health and /api/ready on the local FastAPI server."""
    health = api_get("/api/health")
    try:
        ready = api_get("/api/ready")
    except RuntimeError as exc:
        ready = {"status": "unreachable", "error": str(exc)}
    return format_json({"health": health, "ready": ready})


@mcp.tool()
def get_safety_policy() -> str:
    """Fetch current safety policy and recent audit snippet from /api/safety."""
    return format_json(api_get("/api/safety"))


@mcp.tool()
def list_audit_events(limit: int = 50) -> str:
    """List recent audit events from /api/audit."""
    limit = max(1, min(int(limit), 200))
    return format_json(api_get("/api/audit", params={"limit": limit}))


@mcp.tool()
def get_worker_status() -> str:
    """Fetch agent worker status from /api/agent/worker."""
    return format_json(api_get("/api/agent/worker"))


@mcp.tool()
def run_setup_check() -> str:
    """Run scripts/setup_check.py and return JSON diagnostics report."""
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "setup_check.py")],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip() or "setup_check failed")
    return proc.stdout


@mcp.tool()
def run_backend_tests() -> str:
    """Run pytest tests/test_backend_*.py and return combined stdout/stderr."""
    proc = subprocess.run(
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
    output = (proc.stdout or "") + (proc.stderr or "")
    if not output.strip():
        output = f"pytest exited with code {proc.returncode}"
    header = f"exit_code={proc.returncode}\n"
    return header + output


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
