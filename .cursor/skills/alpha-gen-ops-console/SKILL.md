---
name: alpha-gen-ops-console
description: >-
  cursor-ide-browser MCP로 alpha-gen 운영 콘솔(http://127.0.0.1:8000/) 회귀
  검증. safety, worker, audit UI 체크리스트. frontend 변경 후 사용.
---

# Alpha-Gen Ops Console (Browser Regression)

vanilla 운영 콘솔은 FastAPI가 `/`에서 `frontend/dist/index.html`(React 빌드)을 서빙합니다. 개발 시 `yarn dev`(5173) + API 프록시.

## 사전 조건

```bash
py -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

기본 URL: `http://127.0.0.1:8000/` (env `WEB_PORT` 다르면 맞춤)

## 브라우저 워크플로

1. `browser_navigate` → 운영 콘솔 URL
2. `browser_snapshot`으로 DOM 확인
3. 필요 시 `browser_console_messages`, `browser_network_requests`로 API 오류 확인

## 체크리스트

### 헤더·요약
- [ ] 동기화 상태 배지 표시 (성공/경고)
- [ ] 운영 단계 badge (`mock`, `paper`, `shadow`, `live_*`)
- [ ] 워커 RUNNING/STOPPED badge
- [ ] 긴급 정지 활성/해제 badge

### Worker monitor (`#worker-monitor`)
- [ ] 현재 상태, 마지막 실행, 다음 실행 예정
- [ ] 사이클 횟수·시그널/주문 건수

### Safety controls (`#safety-status`, `#stage-form`, `#emergency-stop-form`)
- [ ] 운영 단계·자동 주문·실거래 활성 여부
- [ ] 긴급 정지 상태·사유
- [ ] 주문 제한(일일 건수, staleness 초)
- [ ] stage select 옵션 5단계 존재

### 데이터 패널
- [ ] 포트폴리오·시그널·주문·백테스트 섹션 렌더 (빈 상태 메시지 포함)
- [ ] `#audit-list` 감사 카드 또는 "아직 없음" 메시지

### 상호작용 (선택, 테스트 DB에서)
- [ ] 워커 시작/중지 버튼 API 호출 후 UI 갱신
- [ ] 긴급 정지 제출 후 badge가 danger로 변경

## 보고 형식

| 섹션 | 결과 | 이슈 |
|------|------|------|
| Load | pass/fail | |
| Header badges | pass/fail | |
| Worker monitor | pass/fail | |
| Safety controls | pass/fail | |
| Audit panel | pass/fail | |

회귀 실패 시: 콘솔/네트워크 오류, 깨진 selector, API 4xx/5xx를 함께 기록합니다.

## 연관 파일

- `frontend/src/**`, `frontend/dist/**`
- 레거시 참고: `frontend-legacy/`
- API: `/api/system/status`, `/api/safety`, `/api/audit`, `/api/agent/worker`
