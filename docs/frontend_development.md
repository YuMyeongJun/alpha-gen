# Frontend Development Spec

alpha-gen 웹 운영 콘솔은 **Vite + React + TypeScript** 스택을 사용합니다.

## Getting Started

```bash
cd frontend
yarn
yarn dev
```

프로덕션 빌드:

```bash
yarn build
```

FastAPI는 `frontend/dist/index.html`을 `/`에서 서빙합니다.

## Packages

스펙에 포함된 주요 패키지:

- Router: `react-router`, `react-router-dom`
- Style utils: `classnames`, `sass`
- i18n: `i18next`, `react-i18next`, `i18next-browser-languagedetector`
- Head: `react-helmet-async`
- Store: `zustand`, `encrypt-storage`
- HTTP: `axios`, `@tanstack/react-query`
- UI: `react-modal`, `react-loading-skeleton`, `react-toastify`
- Form: `react-hook-form`, `@hookform/resolvers`, `yup`
- Realtime: `@microsoft/fetch-event-source`
- Utils: `dayjs`
- Charts: `echarts`, `echarts-for-react`
- Motion: `framer-motion`
- Color: `react-colorful`

## Folder Structure

```
frontend/src
├─ assets
├─ components
│  ├─ common
│  └─ pages
│      └─ [PageName]
├─ hooks
│  ├─ client
│  ├─ providers
│  └─ use[name].ts
├─ models
│  ├─ interface
│  │  ├─ req
│  │  ├─ res
│  │  └─ dto
│  └─ type
├─ modules
├─ pages
├─ routers
├─ store
├─ translations
├─ utils
├─ main.tsx
└─ styles.scss
```

## Component Convention

```tsx
import ...

export interface I[ComponentName]Props {
  ...
}

export const ComponentName = ({ ... }: I[ComponentName]Props) => {
  const [value, setValue] = useState<Type>(defaultValue);

  const variable = value;

  const handler = () => {};

  useEffect(() => {}, []);

  return <>...</>;
};
```

## alpha-gen Mapping

| Area | Path |
|------|------|
| Ops layout | `src/components/pages/OpsConsole/OpsConsoleLayout.tsx` |
| Ops sidebar | `src/components/pages/OpsConsole/OpsConsoleSidebar.tsx` |
| Route pages | `src/pages/*Page.tsx` |
| Dashboard data | `src/hooks/client/dashboard/*` |
| Safety mutations | `src/hooks/client/safety/useSafetyMutations.ts` |
| API types | `src/models/interface/res/IDashboardRes.ts` |
| Axios client | `src/modules/apiClient.ts` |

## Routes

운영 콘솔은 사이드바 + `<Outlet />` 레이아웃으로 여러 페이지에 나뉩니다.

| Path | Page | 내용 |
|------|------|------|
| `/` | `DashboardPage` | 요약 지표, equity/signal 차트 |
| `/portfolio` | `PortfolioPage` | 포트폴리오 테이블·개요 |
| `/signals` | `SignalsPage` | 전략 시그널 목록 |
| `/orders` | `OrdersPage` | 주문 내역 |
| `/backtests` | `BacktestsPage` | 백테스트 실행·기록 |
| `/audit` | `AuditPage` | 감사 이벤트 |
| `/system` | `SystemPage` | 시스템 진단 |

`/dashboard`는 `/`로 리다이렉트됩니다. FastAPI는 SPA fallback으로 클라이언트 라우트 새로고침을 지원합니다.

## Dev Proxy

`vite.config.ts`는 `/api`를 `http://127.0.0.1:8000`으로 프록시합니다. 백엔드를 먼저 실행한 뒤 `yarn dev`를 사용하세요.
