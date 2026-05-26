#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services import DiagnosticsService
from backend.app.store import SQLiteStore


def main() -> None:
    store = SQLiteStore()
    diagnostics = DiagnosticsService(store)
    report = diagnostics.run()
    report["timestamp"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
