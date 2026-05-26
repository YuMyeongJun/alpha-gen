---
name: alpha-gen-incident
description: >-
  worker_state, audit events, orders, logs 기반 alpha-gen 장애 triage.
  incident-triage command, 운영 이상 징후, 긴급정지 판단 시 사용.
---

# Alpha-Gen Incident Triage

주문·워커·안전정책 이상 시 **수집 → 분류 → 다음 액션** 순으로 진행합니다.

## 1. 상태 수집

서버 실행 중이면 API/MCP 우선:

| 소스 | 경로 / tool |
|------|-------------|
| Worker | `GET /api/agent/worker` 또는 `get_worker_status` |
| Safety | `GET /api/safety` 또는 `get_safety_policy` |
| Audit | `GET /api/audit?limit=50` 또는 `list_audit_events` |
| Orders | `GET /api/orders?limit=20` |
| Transitions | `GET /api/orders/{id}/transitions` (문제 주문) |
| System | `GET /api/system/status` |
| Health | `GET /api/health`, `/api/ready` |

로컬만 가능할 때: `py scripts/setup_check.py`, SQLite `data/alpha_gen.sqlite3` audit 테이블, `agent_logging` 로그 파일.

## 2. 분류 매트릭스

| 증상 | 가능 원인 | 우선 조치 |
|------|-----------|-----------|
| worker stopped + cycle 실패 audit | API/브로커/감성 오류 | audit payload·last_result 확인, 재시작 |
| emergency_stop ON | 수동 또는 리스크 트리거 | 사유 확인, 해제 전 원인 제거 |
| orders rejected 급증 | staleness, 한도, stage | `policy.limits`, 최근 audit `order_rejected` |
| live_orders_enabled but no fills | KIS 자격·장 시간·mock | config, `MOCK_MODE`, session |
| ready not_ready | 패키지/frontend/db | setup_check `packages`, `storage` |

## 3. 긴급정지 판단

다음 중 하나면 **긴급정지 검토** (`POST /api/safety/emergency-stop`):

- 의도하지 않은 live 주문 시도
- audit에 critical severity 연속 발생
- worker가 오류 상태로 live 주문 경로 반복 시도
- 데이터 신선도 게이트 무력화 의심

긴급정지 후: worker 중지, 원인 기록, Linear 이슈(optional).

## 4. 보고 템플릿

```
## Incident Summary
- 시간:
- stage / emergency_stop:
- worker: running?, last_cycle_at, last_summary

## Timeline (audit 상위 5건)
1. ...

## Affected orders
- ...

## Root cause (hypothesis)
- ...

## Next actions
1. ...
```

## 5. 후속

- 코드 수정 필요 시 `backend/app/services.py` 제어면 경유
- 실거래 관련 fix는 store + API + frontend 동시 업데이트
- 회귀: `tests/test_backend_*.py` + ops-console spot check
