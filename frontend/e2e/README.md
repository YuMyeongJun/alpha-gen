# e2e/ — 운영 콘솔 시각 회귀 테스트 (Playwright)

`frontend/`의 Vite/React 운영 콘솔을 라이트/다크로 스냅샷 비교하여 UI 회귀를 감지합니다.
설정: [`../playwright.config.ts`](../playwright.config.ts) · 테스트: [`ops-console.spec.ts`](ops-console.spec.ts).

## 최초 1회 준비
```bash
cd frontend
yarn install                 # @playwright/test 설치 (이미 devDependency에 등록됨)
npx playwright install chromium   # 브라우저 바이너리 (~150MB, 1회)
```

## 앱 서버 먼저 띄우기 (자동 기동 안 함)
> ⚠️ 트레이딩 운영 백엔드(`python -m backend.app`)는 **띄우지 마세요** — 실거래 무장 상태일 수 있고 워커가 자동 재개됩니다(루트 `.claudedata/SAFETY_INCIDENT_2026-08-12.md` 참고).

둘 중 하나:
- **격리 mock 샌드박스(권장, 실데이터·안전)** — `MOCK_MODE=true` 등으로 강제한 임시 인스턴스(:8010).
- **정적 프리뷰(백엔드 없음)** — `cd frontend && yarn build && yarn preview` → :4173. `/api`가 없어 스켈레톤/에러 상태로 렌더됨.

## 실행
```bash
cd frontend
# 기본 대상 http://127.0.0.1:8010 (샌드박스)
yarn test:e2e
# 다른 대상 지정
PLAYWRIGHT_BASE_URL=http://127.0.0.1:4173 yarn test:e2e
# baseline 갱신 (의도된 UI 변경 후)
yarn test:e2e:update
```

## 스냅샷 baseline
- `__snapshots__/`에 프로젝트(light/dark)·플랫폼별로 저장됩니다.
- baseline은 렌더 환경(OS·폰트)에 민감하므로, **팀이 합의한 기준 환경/CI에서 생성**해 커밋하는 것을 권장합니다. 로컬 최초 실행분을 무심코 커밋하지 마세요.
- `test-results/`·`playwright-report/`는 `.gitignore` 처리됨.

## 메모
- 대상 8개 라우트: dashboard·portfolio·signals·orders·backtests·audit·stocks·system.
- 상단 동기화 시각 등 미세 변동은 `maxDiffPixelRatio: 0.02`로 흡수. 흔들림이 크면 해당 요소 `mask` 추가 검토.
