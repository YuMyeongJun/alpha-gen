# Storybook 컴포넌트 쇼케이스 — 설계 문서

- **날짜:** 2026-08-15
- **상태:** 승인됨 (브레인스토밍 완료, 구현 계획 대기)
- **목적:** alpha-gen 운영 콘솔의 공용 컴포넌트를 Storybook으로 문서화하고, GitHub Pages로 공개 배포해 포트폴리오/쇼케이스 용도로 사용한다.

## 배경

`feature/dashboard-uplift` 브랜치에서 대시보드 UI를 토스 스타일로 폴리시하는 작업(타이포/스페이싱/모션 토큰, `Metric`/`MetricGrid` 컴포넌트 신규)을 완료했다. 이를 바탕으로 사용자가 "고도화 전략"을 요청 — 공통 컴포넌트를 정식 디자인 시스템처럼 문서화하고, 개발자·비개발자 모두가 한눈에 볼 수 있는 쇼케이스를 만들고 싶어함. 목적은 팀 협업이 아니라 **포트폴리오/자랑거리용**(브레인스토밍에서 확인됨) — 이 점이 도구 선택과 배포 방식을 결정한다.

## 접근 방식

두 가지를 검토했다:

- **A. Storybook + GitHub Pages 배포 (채택)** — GitHub Actions로 정적 빌드해 `<owner>.github.io/<repo>/storybook`에 호스팅. 서드파티 계정 불필요, 완전 무료, 리포지토리가 private이어도 Pages 산출물은 공개 URL로 뜬다.
- **B. Storybook + Chromatic 호스팅** — 즉시 호스팅 URL + 기존 Playwright e2e 시각 회귀 스냅샷과 시너지가 있는 자동 시각 회귀 테스트. 다만 서드파티 계정/토큰 연동이 필요하고 무료 티어 스냅샷 수 제한이 있음. **채택하지 않음** — 지금 필요 이상의 의존성이라 YAGNI. 나중에 시각 회귀 자동화가 필요해지면 추가 검토.

## 아키텍처

```
frontend/
  .storybook/
    main.ts          — 프레임워크(@storybook/react-vite), 스토리 경로, addon 목록
    preview.tsx       — 전역 decorator(테마 toggle, i18n provider 등), 기본 파라미터
  src/components/common/
    Badge.stories.tsx
    Card.stories.tsx
    ConfirmDialog.stories.tsx
    DetailModal.stories.tsx
    Icon.stories.tsx
    Metric.stories.tsx        (size="hero" variant 포함)
    MetricGrid.stories.tsx
    PageHeader.stories.tsx
    StagePills.stories.tsx
    LanguageToggle.stories.tsx
    ThemeToggle.stories.tsx
  src/stories/
    Foundations.mdx    — 색상/타이포/스페이싱/모션 토큰 시각화 (tokens.json 기준)

.github/workflows/
  storybook-deploy.yml — main/feature 브랜치 push 시 build-storybook → gh-pages 배포
```

- **빌더:** `@storybook/react-vite` — 기존 `vite.config.ts`의 alias(`@/`)와 SCSS 처리 설정을 그대로 재사용하므로 별도 웹팩 설정 불필요.
- **Docs addon:** TS 컴포넌트의 `interface I*Props` JSDoc 주석에서 props 테이블을 자동 생성 (`Metric.tsx`의 `size` prop처럼 이미 주석이 붙어 있는 것들이 그대로 문서가 됨).
- **테마:** 별도 addon 의존성 추가 없이, `preview.tsx`에 직접 구현한 `globalTypes` + decorator로 토글. decorator는 스토리 루트 엘리먼트에 기존과 동일한 `data-theme="light"|"dark"` 속성을 설정해 `styles.scss`의 기존 다크모드 CSS를 그대로 재사용한다(새 다크모드 로직을 만들지 않음).

## 컴포넌트 범위 (10개 + Foundations)

`components/common/` 전체: Badge, Card, ConfirmDialog, DetailModal, Icon, Metric(+hero variant), MetricGrid, PageHeader, StagePills, LanguageToggle, ThemeToggle.

각 스토리는 다음을 포함:
- 기본(default) 렌더
- 주요 prop 조합별 변형(예: `Badge`의 tone별, `Metric`의 `size="hero"` vs 기본)
- 실사용 맥락과 유사한 예시(예: `MetricGrid`는 4개 `Metric` 자식을 넣은 상태로 스태거 애니메이션 확인 가능)

Foundations MDX 페이지는 코드 아님 — `.claudedata/design_tokens/tokens.json`을 읽어와 표/스와치로 렌더링(정적 값 하드코딩이 아니라 토큰 파일을 import해서 보여줌 → 토큰이 바뀌면 자동 반영).

## 데이터 / 보안

모든 스토리는 **목/픽스처 props만** 사용한다. 실제 API 호출(`react-query`), KIS 인증, 실거래 관련 데이터, `.env` 값은 스토리 코드에 절대 포함하지 않는다 — 배포되면 공개 URL이 되므로 이 경계는 협상 불가.

## 에러 처리 / 엣지 케이스

- `ConfirmDialog`/`DetailModal` 같은 모달류는 Storybook의 `autodocs`가 자동으로 열어서 렌더하면 레이아웃이 깨질 수 있음 — `parameters.docs.story: { inline: false }`로 개별 iframe 렌더 처리.
- 다크모드 decorator가 없는 상태에서 컴포넌트가 라이트 전용 하드코딩 색을 쓰면 Foundations 감사(design_tokens/README.md)에서 이미 다크 대응이 끝난 상태이므로 리스크 낮음.

## 테스트 / 검증 계획

1. `yarn storybook` 로컬 기동 → 11개 스토리(10 컴포넌트 + Foundations) 전부 에러 없이 렌더되는지 확인.
2. `yarn build-storybook` 정적 빌드 성공 확인 (배포 파이프라인과 동일 커맨드).
3. 기존 `yarn build`(프로덕션 앱 빌드)가 Storybook 추가로 인해 영향받지 않는지 확인 — devDependency만 추가되므로 회귀 없어야 함.
4. GitHub Actions 워크플로우 1회 수동 트리거(또는 push) 후 Pages 배포 URL 접속 확인.

## 범위 밖 (지금 안 함)

- Chromatic/시각 회귀 자동화 (YAGNI, 필요해지면 별도 스펙)
- `pages/`(OpsConsole 실제 화면) 자체의 스토리화 — 이번엔 `components/common/`만
- 컴포넌트 단위 테스트(Vitest/RTL) 추가 — Storybook 문서화와는 별개 관심사, 별도 요청 시 진행
