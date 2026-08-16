# handoff_notes.md — 다음 루프 AI에게

> 세션 시작 시 이 파일 → `current_status.json` → `project_blueprint.md` 순으로 읽고 이어받으세요.
> 이 파일은 **직전 작업 요약 + 경고 + 다음 액션**만 담습니다. 장기 구조는 blueprint에 있습니다.

---

## 🚨 먼저 읽을 것 — 안전 사고 (2026-08-12)
운영 백엔드(`data/alpha_gen.sqlite3` + `.env`)가 **실거래 무장 상태**(`promotion_stage=live_limited`, `.env ALLOW_LIVE_TRADING=true`, `emergency_stop off`)임이 확인됨. 상세·복구절차: [SAFETY_INCIDENT_2026-08-12.md](SAFETY_INCIDENT_2026-08-12.md). 사용자 확인 결과 **의도되지 않음** → 사람이 안전화 예정.
- **UI 작업은 운영 백엔드(:8000)를 켜지 말 것.** 대신 격리 모크 샌드박스(`<scratchpad>/ui_sandbox_server.py`, 포트 **8010**, mock·워커 OFF·임시 DB) 사용.
- `python -m backend.app`는 기동 시 워커 자동재개 → 실주문 위험. 안전화 완료 전까지 금지.

## 최신 핸드오프 (2026-08-12 · Phase 0 다크모드 구현 완료)

### 직전 작업 요약
- 프로젝트 싱크 완료: 실제 스택 **Vite+React+SCSS**(Next/Tailwind 아님), `project_blueprint.md`·`current_status.json` 생성.
- 디자인 토큰 **감사 완료** → `design_tokens/tokens.json` + `README.md`.
- **다크모드 구현 완료 + 온-스크린 검증(Browser MCP)**:
  - `styles.scss`: `@mixin theme-dark` + `:root[data-theme="dark"]` + `@media(prefers-color-scheme:dark)`. `:root`에 `color-scheme` 추가.
  - `styles/console.css`: 하드코딩 `#fff`/`#ffffff` 서피스 7곳 → `var(--bg)`, `.btn`→`var(--bg-input)`, `.btn--primary`·brand mark·toast의 `color:#fff`→`var(--bg)`(다크에서 반전 대응). **라이트 렌더링은 값 동일 → 무변화.**
  - `react-loading-skeleton` 다크 base/highlight 토큰 오버라이드.
  - `common/ThemeToggle.tsx`(신규, 해 아이콘/달 아이콘) + `Icon.tsx`에 `sun`/`moon` 추가 + topbar 마운트 + `index.html` FOUC 방지 인라인 스크립트 + localStorage 영속.
  - i18n `theme.*` 키(ko/en) + 누락됐던 `nav.stocks`(종목/Stocks) 보완.
- 빌드 green(`yarn build`, tsc+vite 통과), 다크 셸 스크린샷 검증 완료.

### ⚠️ 경고 / 미해결
- **풀 베이스라인(8메뉴 light+dark, 실데이터)은 backend 필요.** 검증 시 `/api`가 500(백엔드 미기동)이라 사이드바·콘텐츠는 스켈레톤만 렌더됨. 실데이터 베이스라인은 backend(`python -m backend.app` / uvicorn :8000, **권한 필요·트레이딩 앱**) 기동 후 캡처 — 사용자 승인/실행 필요.
- **Playwright `e2e/`는 아직 미도입**(결정: 둘 다 → Browser MCP 먼저, Playwright는 별도 핸드오프). e2e/ 스캐폴딩은 향후 작업.
- 다크 semantic 색(`tokens.json` dark_note)은 셸 기준으로만 검증됨 — 각 메뉴 차트(echarts)·badge·손익색은 메뉴 페이즈에서 실데이터로 재검증.
- `.claude/config.json`은 만들지 않음 — Claude Code는 `settings.json` 사용(죽은 파일 방지).

### 다크모드 실앱 검증 완료 (2026-08-12, 샌드박스 :8010)
- 대시보드 실데이터(총자산 10,000,000원, 워커 중지됨, equity 차트, 시그널 43건)에서 라이트→다크 전환 정상. 사이드바·토바·메트릭·배지·nav(종목 포함) 모두 일관. JS 에러 0.
- 남은 다크 확인 대상: **echarts 차트(EquityChart/SignalBars)의 팔레트가 토큰을 안 따를 수 있음** → Phase 1에서 처리.

### 진행 현황 — 8개 메뉴 1차 uplift 완료 ✅ (Phase 1, :8010 mock에서 클릭 없이 검증)
- ✅ 대시보드 — 차트(EquityChart/SignalBars) 토큰화 (hand-rolled SVG, echarts 아님)
- ✅ 시그널 — ScoreMeter(양극 점수 미터) + 전일대비 화살표
- ✅ 주문 — 요약 4카드(총 주문/체결/거부/오늘), 거부 강조
- ✅ 포트폴리오 — 잠복 다크 버그 6곳 수정(미정의 var 폴백 → 토큰)
- ✅ 백테스트 — grid-4 요약 지표(샌드박스 runs 0, 실데이터 검증 필요)
- ✅ 감사 — 심각도 필터(전체/정보/경고/위험 + 카운트)
- ✅ 종목 — 필수표시 var(--red) → var(--red-500)
- ✅ 시스템 — 이미 깔끔(안전 패널, 동작 무변경) · 다크만 확인

커밋: feature/dashboard-uplift = 5f313c2 / 397d662 / 860e752 / ab9d63d (4커밋). .claudedata·dist 미커밋.

### 다음 액션 (우선순위)
1. **[사용자] 안전화** (SAFETY_INCIDENT 문서 절차) — 운영 백엔드 live 무장 해제.
2. Playwright `e2e/` 스캐폴딩 → 정식 스냅샷 베이스라인(8메뉴 light+dark).
3. 실데이터 회귀(안전화 후) + 백테스트 요약행 실데이터 검증.
4. 2차 폴리시: 반응형/모바일, i18n 누락키 스윕, 접근성 대비 확정(design_tokens/README 기준).

### 샌드박스 재기동
프로젝트 루트에서: `python "<scratchpad>/ui_sandbox_server.py"` → http://127.0.0.1:8010/ (mock, 안전).

### 절대 금지 (매 세션 유지)
- 매매/안전 게이트 우회, 리스크·live 한도 완화, `.env`/DB/토큰 노출 — `CLAUDE.md` §4 최우선.
- 안전 상태(stage/긴급정지) UI에서 확인 없이 자동 토글.
