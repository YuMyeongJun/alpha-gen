---
name: alpha-gen-live-gate
description: >-
  mock→paper→shadow→live_limited→live_full 운영 단계 승격 전후 검증.
  SafetyService 정책, config 게이트, promote-stage command와 함께 사용.
---

# Alpha-Gen Live Gate (Stage Promotion)

승격은 **한 단계씩**만 합니다. `docs/operating_stages.md`와 `config.OPERATING_STAGES`를 기준으로 합니다.

## 단계 순서

`mock` → `paper` → `shadow` → `live_limited` → `live_full`

## 공통 전제 (모든 승격)

1. `alpha-gen-readiness` 통과
2. `GET /api/safety` — `emergency_stop.enabled == false` (테스트 후 원복 가능)
3. 운영 콘솔에서 stage·긴급정지·audit UI 노출 (`alpha-gen-ops-console`)
4. 관련 pytest 통과

## 단계별 추가 게이트

| 목표 stage | 필수 확인 |
|------------|-----------|
| **paper** | 실시세/뉴스 파이프라인, worker cycle, 주문 상태 전이 기록 |
| **shadow** | 브로커 미제출, `shadow_mode` 정책, audit에 의도만 기록 |
| **live_limited** | `ALLOW_LIVE_TRADING=true`, KIS 자격증명, 일일 주문 한도·손실 한도 차단 테스트 |
| **live_full** | broker sync·전이·포지션 정합성 반복 검증, smoke test 완료 |

## 승격 절차

1. 현재 stage 확인: `/api/safety` → `policy.stage`
2. 목표 stage가 **바로 다음 단계**인지 검증 (건너뛰기 금지)
3. 아래 체크리스트 출력 (promote-stage command와 동일)
4. 운영자 승인 후에만 `POST /api/safety/stage` `{ "stage": "<target>" }`
5. 승격 직후:
   - policy 재조회
   - audit 최근 이벤트에 stage 변경 기록 확인
   - UI badge 갱신 확인

## 승격 후 smoke

- **paper/shadow**: worker 1 cycle, 주문/의도 audit 확인
- **live_limited+**: 긴급정지 ON → 신규 live 주문 거절 → OFF 복구

## 금지

- SafetyService·config 게이트 우회 코드
- MCP/에이전트가 브로커에 직접 주문 (API 정책 계층만 사용)
- audit·UI 없이 live 단계 진입

## 참고

- 환경 변수: `OPERATING_STAGE`, `ALLOW_LIVE_TRADING`, `EMERGENCY_STOP`
- 구현: `backend/app/services.py` (`SafetyService`), `config/__init__.py`
