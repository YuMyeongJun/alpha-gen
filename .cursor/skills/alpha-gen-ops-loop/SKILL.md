---
name: alpha-gen-ops-loop
description: >-
  /loop 주기 점검으로 alpha-gen health·safety·worker 감시. Windows
  cursor_ops_watch.ps1, bash cursor_ops_watch.sh sentinel 사용. 중복 loop 금지.
---

# Alpha-Gen Ops Loop

IDE 내 `/loop` 또는 watch script로 운영 상태를 주기적으로 깨웁니다.

## Watch Script

| Shell | Script |
|-------|--------|
| Windows | `scripts/cursor_ops_watch.ps1` |
| bash | `scripts/cursor_ops_watch.sh` |

기본 간격 **5분**. 환경 변수 `ALPHA_GEN_WATCH_INTERVAL_SEC`로 변경.

Sentinel (고정):
```
AGENT_LOOP_TICK_ALPHA_GEN_OPS {"prompt":"alpha-gen ops watch: MCP health_check, get_safety_policy, get_worker_status 요약. 이상 시 alpha-gen-incident skill 적용."}
```

## /loop 사용법

```
/loop 5m alpha-gen ops watch: health, safety policy, worker status 요약. 이상 시 incident triage.
```

또는 watch script를 background shell로 실행하고 `notify_on_output` regex:
`^AGENT_LOOP_TICK_ALPHA_GEN_OPS`

## 각 tick 워크플로

1. MCP `alpha-gen` 연결 시:
   - `health_check`
   - `get_safety_policy`
   - `get_worker_status`
2. MCP 없으면 curl/requests로 동일 API
3. 변경 없으면 한 줄 heartbeat만
4. 이상 시 `alpha-gen-incident` skill로 triage

## 중복 방지

- 동일 sentinel regex의 loop가 이미 돌면 **새 loop 시작 금지**
- 사용자가 stop 요청 시 watch PID/shell 종료

## Cloud Agent

Cloud 환경에서는 로컬 `127.0.0.1:8000` 접근 불가 → loop/watch **로컬 IDE 전용**.

## 관련

- Loop 패턴: Cursor built-in `loop` skill
- Readiness: `alpha-gen-readiness` (loop 대체 아님, 보조 감시)
