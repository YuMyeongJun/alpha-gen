---
name: alpha-gen-readiness
description: >-
  alpha-gen 배포·운영 전 readiness 점검. setup_check, backend pytest,
  KIS/Claude smoke(키 없으면 skip), /api/health·/api/ready 요약. ops-check
  command 또는 승격 전에 사용.
---

# Alpha-Gen Readiness

운영 단계 승격, PR 머지, 장애 복구 후 재기동 전에 실행합니다.

## 점검 순서

1. **로컬 API 가용성** (서버 실행 중일 때)
   - `GET /api/health` → `status: ok`
   - `GET /api/ready` → `status: ready` 또는 degraded 원인 파악
   - MCP `alpha-gen` 서버가 연결되어 있으면 `health_check` tool 우선 사용

2. **setup_check**
   ```bash
   py scripts/setup_check.py
   ```
   또는 MCP `run_setup_check`. JSON에서 확인:
   - `ok`, `summary`, `environment.operating_stage`
   - `integrations.kis_configured`, `integrations.claude_configured`
   - `packages` 실패 모듈

3. **backend pytest**
   ```bash
   py -m pytest tests/test_backend_*.py -q
   ```
   또는 MCP `run_backend_tests`. 목표: 전체 통과, skip은 키 미설정 smoke만 허용.

4. **선택 smoke** (자격증명 있을 때만)
   - `py scripts/kis_smoke_test.py` — KIS 미설정 시 skip 정상
   - `py scripts/claude_smoke_test.py` — Anthropic 키 없으면 skip 정상

5. **안전 정책 스냅샷**
   - `GET /api/safety` 또는 MCP `get_safety_policy`
   - `emergency_stop.enabled`, `stage`, `live_orders_enabled` 기록

## 출력 형식

한국어로 아래 표를 채워 보고합니다.

| 영역 | 상태 | 비고 |
|------|------|------|
| API health | pass/fail/skip | |
| API ready | pass/fail | degraded 이유 |
| setup_check | pass/fail | |
| backend tests | pass/fail | N passed, M skipped |
| KIS smoke | pass/fail/skip | |
| Claude smoke | pass/fail/skip | |
| Safety policy | info | stage, emergency_stop |

**판정**: API ready + setup_check ok + backend tests pass → `READY`. 그 외 `NOT READY`와 차단 항목 나열.

## 주의

- 실거래 승격 판정은 이 skill만으로 충분하지 않습니다. `alpha-gen-live-gate`를 이어서 실행하세요.
- 서버가 꺼져 있으면 API 항목은 skip하고 로컬 pytest/setup_check만으로 partial 보고합니다.
