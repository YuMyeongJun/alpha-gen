# Alpha-Gen Incident Triage

장애·이상 징후 발생 시 상태를 수집하고 원인·다음 액션을 정리합니다.

## 실행

1. `.cursor/skills/alpha-gen-incident/SKILL.md` skill을 읽고 따릅니다.
2. 상태 수집 (서버 실행 중):
   - MCP: `get_worker_status`, `get_safety_policy`, `list_audit_events`, `health_check`
   - 또는 API: `/api/agent/worker`, `/api/safety`, `/api/audit`, `/api/orders`, `/api/system/status`
3. 최근 audit 이벤트에서 critical/warning 우선 분석.
4. worker `last_result`, `current_status`, rejected orders 패턴 확인.
5. skill의 **Incident Summary** 템플릿으로 한국어 보고.

## 긴급정지

의도하지 않은 live 주문·연속 critical audit·게이트 우회 의심 시:
- 긴급정지 **권고** 및 `POST /api/safety/emergency-stop` 절차 안내
- 자동 호출은 운영자 명시 요청이 있을 때만

## 후속

- 코드 수정 필요 시 Linear 이슈 생성(optional, `plugin-linear-linear` MCP)
- fix 후 `ops-check` 재실행 권장
