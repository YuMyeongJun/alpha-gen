#!/usr/bin/env python3
"""
scripts/ui_sandbox_server.py — 격리된 UI 검증용 샌드박스 서버.

`yarn dev`는 /api를 127.0.0.1:8000으로 프록시하는데, 그 포트는 비어있거나(빈 화면)
운영 백엔드(실거래 무장 가능성 있음, .claudedata/SAFETY_INCIDENT_2026-08-12.md 참고)일 수
있어 UI 확인 용도로 쓰기 위험하다. 이 스크립트는 그 대신:
  - 운영 DB(data/alpha_gen.sqlite3)를 절대 건드리지 않는 temp DB 사용
  - MOCK_MODE 강제, 워커 자동재개 비활성화, ALLOW_LIVE_TRADING=false
  - frontend/dist를 서버가 직접 서빙 (프록시 불필요, 같은 오리진)
로 :8010에서 뜬다.

사전 준비: frontend에서 `yarn build` 한 번 실행해 dist/가 있어야 함.
실행: python scripts/ui_sandbox_server.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

tmp_dir = tempfile.mkdtemp(prefix="alpha_gen_ui_sandbox_")
tmp_db = os.path.join(tmp_dir, "opsui_sandbox.sqlite3")

# 반드시 backend.app.main import 이전에 설정: 그 모듈은 import되는 순간 모듈 레벨에서
# `app = create_app()`(db_path=None → 운영 DB, auto_resume_worker=True)를 실행한다.
# ALPHA_GEN_DB_PATH를 먼저 temp 경로로 돌려놓지 않으면 이 부수효과가 운영 DB를 향한다.
os.environ["ALPHA_GEN_DB_PATH"] = tmp_db
os.environ["MOCK_MODE"] = "true"
os.environ["AUTO_MOCK_ON_MISSING_KIS"] = "true"
os.environ["ALLOW_LIVE_TRADING"] = "false"
os.environ["ALPHA_GEN_STAGE"] = "mock"
os.environ["EMERGENCY_STOP"] = "true"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from backend.app.main import create_app

dist_dir = PROJECT_ROOT / "frontend" / "dist"
if not (dist_dir / "index.html").exists():
    print(f"[sandbox] 경고: {dist_dir}/index.html 없음 — 먼저 `cd frontend && yarn build` 실행하세요.")

app = create_app(db_path=tmp_db, bootstrap_legacy=False, auto_resume_worker=False)

if __name__ == "__main__":
    print(f"[sandbox] temp db: {tmp_db}")
    print("[sandbox] http://127.0.0.1:8010  (mock / temp db / worker off — 운영 DB 무관)")
    uvicorn.run(app, host="127.0.0.1", port=8010, log_level="info")
