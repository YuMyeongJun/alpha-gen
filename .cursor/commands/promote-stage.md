# Alpha-Gen Promote Stage

운영 단계 승격 전 체크리스트를 출력하고, 승격 가능 여부를 판단합니다.

## 입력

사용자가 목표 stage를 지정하지 않으면, 현재 stage의 **다음 단계**를 목표로 가정합니다.

유효 stage: `mock`, `paper`, `shadow`, `live_limited`, `live_full`

## 실행

1. `.cursor/skills/alpha-gen-live-gate/SKILL.md` skill을 읽고 따릅니다.
2. 현재 정책 수집: `GET /api/safety` 또는 MCP `get_safety_policy`.
3. 현재 `policy.stage`와 목표 stage를 비교:
   - 목표가 현재보다 정확히 **한 단계 위**인지 확인 (건너뛰기 불가)
   - 하향(demotion)이면 별도 경고와 롤백 절차 안내
4. 목표 stage별 **추가 게이트** 체크리스트를 표로 출력 (pass/fail/unknown).
5. `alpha-gen-readiness` 미실행 시 ops-check 수행을 권장합니다.

## 출력 형식

```
## Stage Promotion Plan
- Current: <stage>
- Target: <stage>
- Allowed: yes/no (reason)

## Pre-flight checklist
| Item | Status | Notes |
...

## Recommendation
- PROCEED / BLOCK — <reason>

## Post-promotion (if PROCEED)
1. POST /api/safety/stage { "stage": "..." }
2. Re-fetch policy + audit
3. UI badge verification (alpha-gen-ops-console)
```

**주의**: 이 command는 승격 API를 자동 호출하지 않습니다. 운영자 확인 후에만 `POST /api/safety/stage`를 실행하세요.
