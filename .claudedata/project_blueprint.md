# alpha-gen — 대시보드 고도화 마스터 블루프린트

> `.claudedata/`는 하네스(Claude Code) 지식베이스입니다. 세션이 바뀌어도 프로젝트 싱크를 유지하기 위한 "박제" 문서이며, 코드가 아닌 **의사결정·구조·툴 맵**을 담습니다.
> 생성: 2026-08-12 · 근거: 실제 코드 스캔(`frontend/`, `.cursor/`, `.claude/`, `automation/`).
> **이 문서는 표현 계층(UI) 마스터플랜입니다. 매매·안전·리스크 로직은 `CLAUDE.md`가 최우선이며 그 가드레일을 절대 우회하지 않습니다.**

---

## 1. 프로젝트 실체 (요청 가정 vs 실제)

요청에서 "React, Vite, Next.js, Tailwind"를 언급했으나 실제 스택은 아래와 같습니다. **Next.js·Tailwind는 사용하지 않습니다.**

| 영역 | 실제 |
|---|---|
| 빌드/런타임 | **Vite 7 + React 18 + TypeScript 5.9** (`type: module`) |
| 라우팅 | `react-router-dom` v7 — `OpsConsoleLayout` 아래 8개 라우트 |
| 데이터 페칭 | `@tanstack/react-query` v5 + `axios`. dev는 `/api` → `http://127.0.0.1:8000` 프록시(`vite.config.ts`) |
| 전역 상태 | `zustand` v5 (`src/store/syncStore.ts`) |
| 차트 | `echarts` v6 + `echarts-for-react` (`charts/EquityChart`, `charts/SignalBars`) |
| 애니메이션 | `framer-motion` v12 |
| 폼 | `react-hook-form` + `yup` + `@hookform/resolvers` |
| i18n | `i18next` (한국어 `ko.json` / 영어 `en.json`) |
| 스타일 | **SCSS + CSS 커스텀 프로퍼티 디자인 토큰** (`styles.scss`, `styles/console.css`). Tailwind 없음 |
| 기타 UI | `react-toastify`, `react-loading-skeleton`, `react-modal`, `dayjs`, `classnames`, `react-colorful` |
| 배포 | `yarn build` → `frontend/dist/`. FastAPI(`backend/app/main.py`)가 `/`에서 `dist/index.html` 서빙 |

### 1.1 디자인 시스템 현황

- 토큰은 `src/styles.scss`의 `:root`에 정의 — surface(`--bg`, `--bg-tertiary`…), ink 4단계(`--ink-1..4`), semantic(green/red/blue/amber/gray), accent(`--accent` 테라코타 `#c96f3d`), 반경(`--r-sm..xl`), 그림자(`--shadow-1/2/pop`). 출처 주석: "cluade-design".
- **라이트 테마 전용.** 다크 모드 토큰/`prefers-color-scheme`/`data-theme` 분기 없음 → 고도화 시 1순위 후보.
- `console.css`는 앱 셸(사이드바 그리드, hairline 0.5px, `.nav__item` 등) 담당.

### 1.2 프런트 디렉터리 지도

```
frontend/src/
├─ App.tsx / main.tsx / routers/index.tsx      # 셸·라우팅
├─ pages/                                        # 라우트 진입 (Dashboard/Portfolio/Signals/Orders/Backtests/Audit/Stocks/System)
├─ components/
│  ├─ common/                                    # Badge Card ConfirmDialog DetailModal Icon Metric PageHeader StagePills LanguageToggle
│  └─ pages/OpsConsole/
│     ├─ OpsConsoleLayout / Nav / Rail / Sidebar # 셸 구성
│     ├─ charts/  EquityChart · SignalBars
│     └─ panels/  Audit Backtests Orders Portfolio Signals Stocks System
├─ hooks/client/{dashboard,safety,system}        # react-query 훅 + mutations
├─ hooks/providers/QueryProvider.tsx
├─ models/interface/{req,res}                     # API 타입 계약
├─ modules/apiClient.ts                           # axios 인스턴스
├─ store/syncStore.ts                             # zustand
├─ styles.scss · styles/console.css               # 토큰·셸
├─ translations/ {ko,en}.json · i18n.ts
└─ utils/ {domainLabels,equity,format,orders}.ts
```

### 1.3 백엔드 API 계약 (UI가 소비하는 것)

`/api/system/status`, `/api/safety`, `/api/audit`, `/api/agent/worker/*`, `/api/orders`, `/api/orders/{id}/transitions`, `/api/health`, `/api/ready`.
→ UI 리뉴얼이 **필드 의미**를 바꿔야 하면 `backend/app/services.py` 제어면 경유 + 사람 승인(§CLAUDE.md 4.3). 순수 표현 변경은 자유.

---

## 2. 8개 메뉴 (고도화 대상)

`routers/index.tsx` 기준. `/dashboard`는 `/`로 리다이렉트.

| # | 라우트 | 페이지 | 패널 | 라벨 | 핵심 요소 |
|---|---|---|---|---|---|
| 1 | `/` | DashboardPage | (직접) | 대시보드 | EquityChart, 요약 메트릭, worker/safety 배지 |
| 2 | `/signals` | SignalsPage | SignalsPanel | 시그널 | SignalBars, 필터, 신선도 |
| 3 | `/orders` | OrdersPage | OrdersPanel | 주문 | 주문 목록, 상태 전이, mode(paper/live) |
| 4 | `/portfolio` | PortfolioPage | PortfolioPanel | 포트폴리오 | 보유·손익·비중 |
| 5 | `/backtests` | BacktestsPage | BacktestsPanel | 백테스트 | BacktestService 결과 |
| 6 | `/stocks` | StocksPage | StocksPanel | 종목 | 유니버스 관리(KR/US/EU) |
| 7 | `/audit` | AuditPage | AuditPanel | 감사 | audit 이벤트 카드 |
| 8 | `/system` | SystemPage | SystemPanel | 시스템 | stage/긴급정지/한도 — **안전 UX 최우선** |

**안전 UX 규칙(불변, `.cursor/rules/frontend-ops-console.mdc`):** `live_*` 스테이지·긴급정지는 눈에 띄는 badge/색으로, shadow는 warning 스타일로, 위험 액션(긴급정지·stage 변경)은 확인 없이 자동 실행 금지.

---

## 3. 가동 가능한 AI 도구 맵 (스킬 · MCP)

### 3.1 alpha-gen MCP (`.cursor/mcp.json` → `automation/mcp_alpha_gen/server.py`)

`py -m automation.mcp_alpha_gen.server`, base `http://127.0.0.1:8000`. 노출 tool:

| tool | 용도 |
|---|---|
| `health_check` | `/api/health` + `/api/ready` 요약 |
| `get_safety_policy` | stage / 긴급정지 / live 활성 / 한도 |
| `get_worker_status` | 워커 실행·사이클 상태 |
| `list_audit_events(limit=50)` | 최근 감사 이벤트 |
| `run_setup_check` | `scripts/setup_check.py` |
| `run_backend_tests` | backend pytest |

> UI 리뉴얼 검증 시 **실제 데이터 상태를 MCP로 조회**해 목업이 아닌 실 상태 기반으로 패널을 맞춘다(빈 상태·에러 상태 포함).

### 3.2 Cursor 자산 (`.cursor/`)

- **rules** — `alpha-gen-trading-safety`(alwaysApply), `backend-trading-control-plane`(backend glob), `frontend-ops-console`(frontend glob, ← UI 작업 시 항상 준수).
- **skills** — `alpha-gen-ops-console`(브라우저 회귀 체크리스트, **UI 작업의 필수 검증 스킬**), `alpha-gen-readiness`, `alpha-gen-live-gate`, `alpha-gen-incident`, `alpha-gen-ops-loop`.
- **commands** — `commit`, `doc`, `fix-it`, `review`, `incident-triage`, `ops-check`, `promote-stage`.

### 3.3 Claude Code 하네스 도구 (이 환경)

- **In-app Browser MCP (`mcp__Claude_Browser__*`)** — dev 서버 기동(`preview_start`), 네비게이션, `read_page`(접근성 트리), 스크린샷/`computer`, 콘솔·네트워크 로그. → **시각 회귀·스크린샷 베이스라인의 실제 수단**(요청의 "Playwright" 자리를 이 브라우저 MCP가 대체).
- **에이전트** — `Explore`(광역 코드 탐색), `Plan`(구현 설계). *사용자가 명시할 때만 스폰.*
- **스킬** — `dataviz`(차트/대시보드 설계 전 필독), `artifact-design`/`artifact-capabilities`(공유용 시안), `simplify`, `security-review`, `run`, `update-config` 등.
- **하네스 가드(`.claude/settings.json`)** — `.env`·토큰·DB read/edit deny, `config/__init__.py`·`services.py`·`store.py` edit는 ask, live 관련 위험 Bash deny, `PostToolUse` 훅(`post_edit_check.sh`)이 편집 후 자동 점검.

---

## 4. 로드맵 — "모든 메뉴 디자인 개선" 대장정

핸드오프 단위는 **PR(=대화 세션) 1개 = 메뉴 1개 또는 기반작업 1묶음**. 각 단위는 아래 4-스텝 사이클을 따른다.

> **핸드오프 사이클(공통):**
> 1. **베이스라인** — Browser MCP로 해당 메뉴 스크린샷 + `read_page`로 현재 구조 캡처, MCP로 실 데이터 상태 조회.
> 2. **스펙** — 개선안(레이아웃·상태·빈/에러/로딩·반응형·다크) 문서화 → 사용자 승인.
> 3. **구현** — `frontend/src/**`만 수정. 토큰·공용 컴포넌트 재사용, `dataviz` 스킬 준수.
> 4. **검증·핸드오프** — `yarn build` → `alpha-gen-ops-console` 스킬 회귀 체크리스트 → 스크린샷 before/after → `current_status.json` 갱신 + 커밋.

### PHASE 0 — 기반 (선행 필수, 1핸드오프)
표현 계층 전체가 딛고 설 토대. 이걸 먼저 하지 않으면 메뉴별 작업이 서로 어긋난다.
- 디자인 토큰 감사 + **다크 모드 토큰/`data-theme` 분기 도입**.
- 공용 컴포넌트 정리·문서화: `Card` `Badge` `Metric` `PageHeader` `StagePills` `ConfirmDialog` `DetailModal` — 리뉴얼의 재사용 팔레트.
- 잔여 정리: nav 한글 라벨 `stocks(종목)` 누락 보완, `eslint.config` 부재 보완(선택).
- Browser MCP로 **8개 메뉴 전부 스크린샷 베이스라인** 확보(회귀 기준선).

### PHASE 1~N — 메뉴별 (각 1핸드오프, 아래 순서 권장)
가치·가시성·안전 민감도 순:

1. **대시보드(`/`)** — 첫 화면·최고 가시성. EquityChart + 요약 메트릭 + worker/safety 배지. `dataviz` 스킬 적용의 대표 사례.
2. **시그널(`/signals`)** — SignalBars, 필터, 신선도(staleness) 시각화.
3. **주문(`/orders`)** — 목록·상태 전이·mode 구분. paper/live 시각적 구분 명확화.
4. **포트폴리오(`/portfolio`)** — 보유·손익·비중.
5. **백테스트(`/backtests`)** — BacktestService 결과 표현.
6. **종목(`/stocks`)** — KR/US/EU 유니버스 관리 폼 UX.
7. **감사(`/audit`)** — 이벤트 카드 타임라인.
8. **시스템(`/system`)** — **마지막.** stage/긴급정지/한도 = 안전 UX. 위험 액션 확인 플로우가 핵심이라 토큰·컴포넌트가 안정된 뒤 착수.

### PHASE FINAL — 통합
- 8개 메뉴 반응형·다크 일관성 크로스체크, i18n(ko/en) 누락 키 스윕, 최종 시각 회귀.

### 핸드오프 원칙
- **한 번에 한 메뉴.** 세션 시작 시 `current_status.json`을 읽어 `current_phase`/`next_action`으로 이어받는다.
- 순수 UI만 다룬다. 백엔드 필드·안전 게이트가 필요하면 멈추고 사용자 확인.
- 각 핸드오프 종료 시 `current_status.json`의 `completed_subtasks`·`current_phase`·`next_action`을 반드시 갱신(다음 세션의 싱크 지점).

---

## 5. 절대 금지 (UI 작업 중에도)
- `SafetyService.ensure_order_allowed()` 등 매매 관문 우회/약화, 리스크 상수·live 한도 완화 (`CLAUDE.md` §4).
- `.env`·`kis_token_cache.json`·`data/*.db` 노출/편집.
- 안전 상태(stage·긴급정지)를 UI에서 확인 없이 자동 토글.
- 서비스 계층 우회 신규 주문 경로 생성.
