# Storybook Component Showcase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Storybook to `frontend/`, document the 10 components in `frontend/src/components/common/` plus a Foundations design-token page, and deploy the static build to GitHub Pages via GitHub Actions.

**Architecture:** Storybook 9 with the `@storybook/react-vite` builder reuses the existing `vite.config.ts` (React plugin, `@` alias). One `.stories.tsx` file per component, colocated next to the component it documents. A dedicated `Foundations` story renders design tokens by reading them live from computed CSS custom properties (not by importing `.claudedata/design_tokens/tokens.json`, which lives outside the Vite project root and would require crossing `server.fs.allow` boundaries — reading the already-loaded `styles.scss` custom properties at runtime is simpler, has zero drift risk, and matches the project's own stated convention that `styles.scss` is the runtime source of truth). A GitHub Actions workflow builds and publishes to GitHub Pages on push to `feature/dashboard-uplift` and `main`.

**Tech Stack:** Storybook 9 (`storybook`, `@storybook/react-vite`, `@storybook/addon-docs`), existing Vite 7 / React 18 / TypeScript 5.9 / SCSS stack, GitHub Actions + `actions/deploy-pages`.

**Spec:** [docs/superpowers/specs/2026-08-15-storybook-component-showcase-design.md](../specs/2026-08-15-storybook-component-showcase-design.md)

## Global Constraints

- All stories use mock/fixture props only — no real API calls, no KIS/Claude credentials, no data from `.env` or either SQLite DB. This is non-negotiable because the built Storybook is published to a public URL (CLAUDE.md §4, safety_incident context).
- Do not modify `frontend/src/components/common/*.tsx` component logic — this plan only adds `*.stories.tsx` files alongside them. If a component needs a prop tweak to be documentable, stop and flag it instead of changing behavior silently.
- `yarn build` (the production app build) must stay green throughout — Storybook is additive (devDependencies + new files only).
- Theme decorator must reuse the existing `data-theme` attribute mechanism from `styles.scss` — do not invent a second dark-mode system.
- No new addon dependency without a concrete reason tied to a task below (YAGNI — this repo doesn't need visual regression/interaction testing addons for this plan; that's out of scope per the spec).

---

## Task 1: Install Storybook and wire it to the existing Vite/React/TS setup

**Files:**
- Modify: `frontend/package.json` (new devDependencies + `storybook`/`build-storybook` scripts, added automatically by the init command)
- Create: `frontend/.storybook/main.ts`
- Create: `frontend/.storybook/preview.tsx`

**Interfaces:**
- Produces: `.storybook/main.ts` exporting a `StorybookConfig` that later tasks' `*.stories.tsx` files are picked up by (via the `stories` glob).
- Produces: `.storybook/preview.tsx` exporting `decorators`/`globalTypes` that every story in Tasks 2-6 relies on for theme switching and i18n/CSS being loaded.

- [ ] **Step 1: Run the official Storybook init command**

```bash
cd frontend
npx storybook@latest init --yes --type react --builder vite
```

This detects the existing Vite + React + TS project, adds `storybook` and `@storybook/react-vite` (plus their transitive deps) to `devDependencies`, adds `"storybook": "storybook dev -p 6006"` and `"build-storybook": "storybook build"` to `package.json` scripts, and scaffolds `.storybook/main.ts` + `.storybook/preview.ts` + example stories under `src/stories/`.

- [ ] **Step 2: Delete the example stories the init command scaffolds**

```bash
rm -rf frontend/src/stories
```

We don't want the generated `Button`/`Header`/`Page` example components — our own stories replace them starting in Task 2.

- [ ] **Step 3: Replace `.storybook/main.ts` with the project-specific config**

```ts
import type { StorybookConfig } from "@storybook/react-vite";
import path from "node:path";

const config: StorybookConfig = {
  stories: ["../src/components/common/**/*.stories.tsx", "../src/foundations/**/*.stories.tsx"],
  addons: ["@storybook/addon-docs"],
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  viteFinal: async (viteConfig) => {
    viteConfig.resolve = viteConfig.resolve || {};
    viteConfig.resolve.alias = {
      ...(viteConfig.resolve.alias || {}),
      "@": path.resolve(__dirname, "../src"),
    };
    return viteConfig;
  },
};

export default config;
```

This mirrors the `@` alias from `frontend/vite.config.ts:9` so `*.stories.tsx` files can `import { Badge } from "@/components/common"` exactly like app code does.

- [ ] **Step 4: Replace `.storybook/preview.tsx` with the project-specific preview**

```tsx
import type { Preview } from "@storybook/react-vite";
import { useEffect } from "react";
import "@/translations/i18n";
import "@/styles.scss";

const withTheme = (Story: React.ComponentType, context: { globals: { theme?: string } }) => {
  const theme = context.globals.theme === "dark" ? "dark" : "light";
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);
  return <Story />;
};

const preview: Preview = {
  parameters: {
    backgrounds: { disable: true },
    layout: "padded",
  },
  globalTypes: {
    theme: {
      description: "Light/dark theme",
      toolbar: {
        title: "Theme",
        icon: "circlehollow",
        items: [
          { value: "light", title: "Light" },
          { value: "dark", title: "Dark" },
        ],
        dynamicTitle: true,
      },
    },
  },
  initialGlobals: {
    theme: "light",
  },
  decorators: [withTheme],
};

export default preview;
```

`import "@/translations/i18n"` runs the same `i18n.init(...)` side effect as `App.tsx:6`, so every story's `useTranslation()` calls (Badge's tone labels aren't translated, but `ConfirmDialog`, `DetailModal`, `StagePills`, `LanguageToggle`, `ThemeToggle` all call it) work without a provider wrapper. `import "@/styles.scss"` loads every CSS custom property (light values on `:root`, dark values behind `[data-theme="dark"]`) so the theme toolbar toggle in the decorator actually changes rendering.

- [ ] **Step 5: Verify the dev server boots**

Run: `cd frontend && yarn storybook`
Expected: Storybook dev server starts on `http://localhost:6006` with an empty sidebar (no stories yet — Tasks 2-6 add them) and no console errors in the terminal output. Stop the server (Ctrl+C) once confirmed.

- [ ] **Step 6: Commit**

```bash
cd frontend
git add package.json yarn.lock .storybook/
git commit -m "chore: install Storybook (react-vite builder)"
```

---

## Task 2: Foundations design-token page

**Files:**
- Create: `frontend/src/foundations/Foundations.tsx`
- Create: `frontend/src/foundations/Foundations.stories.tsx`

**Interfaces:**
- Consumes: CSS custom properties already defined in `frontend/src/styles.scss:5-73` (light) and `:79-132` (dark, via `[data-theme="dark"]`) — read at runtime via `getComputedStyle`, not imported.
- Produces: nothing consumed by other tasks (this is a leaf/documentation-only page).

- [ ] **Step 1: Write `Foundations.tsx`**

```tsx
import { useEffect, useState } from "react";

interface ITokenRow {
  name: string;
  value: string;
}

interface ITokenGroup {
  title: string;
  tokens: string[];
  swatch?: boolean;
}

const GROUPS: ITokenGroup[] = [
  { title: "Surface", tokens: ["--bg", "--bg-tertiary", "--bg-subtle", "--bg-hover", "--bg-input"], swatch: true },
  { title: "Border", tokens: ["--border", "--border-strong", "--border-focus"], swatch: true },
  { title: "Ink", tokens: ["--ink-1", "--ink-2", "--ink-3", "--ink-4"], swatch: true },
  {
    title: "Semantic",
    tokens: [
      "--green-500", "--green-600", "--red-500", "--red-600",
      "--blue-500", "--blue-600", "--amber-500", "--gray-500",
    ],
    swatch: true,
  },
  { title: "Accent", tokens: ["--accent", "--accent-600", "--accent-50"], swatch: true },
  { title: "Typography scale", tokens: ["--fs-hero", "--fs-lg", "--fs-base", "--fs-sm"] },
  { title: "Spacing scale", tokens: ["--space-1", "--space-2", "--space-3", "--space-4", "--space-5", "--space-6", "--space-7", "--space-8"] },
  { title: "Motion", tokens: ["--motion-fast", "--motion-base", "--motion-slow", "--ease-out"] },
  { title: "Radii", tokens: ["--r-sm", "--r-md", "--r-lg", "--r-xl"] },
];

function readTokens(names: string[]): ITokenRow[] {
  const styles = getComputedStyle(document.documentElement);
  return names.map((name) => ({ name, value: styles.getPropertyValue(name).trim() }));
}

export const Foundations = () => {
  const [groups, setGroups] = useState<{ title: string; swatch?: boolean; rows: ITokenRow[] }[]>([]);

  useEffect(() => {
    setGroups(GROUPS.map((g) => ({ title: g.title, swatch: g.swatch, rows: readTokens(g.tokens) })));
  }, []);

  return (
    <div style={{ fontFamily: "var(--font)", color: "var(--ink-1)" }}>
      <p style={{ color: "var(--ink-3)", marginBottom: 24 }}>
        Live values read from the current theme&apos;s computed CSS custom properties (toggle the
        Theme control in the toolbar above to see dark-mode values).
      </p>
      {groups.map((group) => (
        <section key={group.title} style={{ marginBottom: 32 }}>
          <h3 style={{ marginBottom: 12 }}>{group.title}</h3>
          <table style={{ borderCollapse: "collapse", width: "100%" }}>
            <tbody>
              {group.rows.map((row) => (
                <tr key={row.name} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "8px 12px", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                    {row.name}
                  </td>
                  <td style={{ padding: "8px 12px", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                    {row.value}
                  </td>
                  {group.swatch && (
                    <td style={{ padding: "8px 12px" }}>
                      <div
                        style={{
                          width: 24,
                          height: 24,
                          borderRadius: 4,
                          border: "1px solid var(--border-strong)",
                          background: row.value,
                        }}
                      />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  );
};
```

- [ ] **Step 2: Write `Foundations.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";
import { Foundations } from "./Foundations";

const meta: Meta<typeof Foundations> = {
  title: "Foundations/Design Tokens",
  component: Foundations,
  tags: ["autodocs"],
  parameters: { layout: "padded" },
};
export default meta;

type Story = StoryObj<typeof Foundations>;

export const AllTokens: Story = {};
```

- [ ] **Step 3: Verify it renders**

Run: `cd frontend && yarn storybook`
Expected: sidebar shows "Foundations / Design Tokens", opening it renders 9 grouped tables with real hex/px/ms values (not empty strings) and small color swatches for the color groups. Toggling the Theme toolbar control changes the swatch colors and the printed hex values (dark ink/bg values from `styles.scss:83-98`).

- [ ] **Step 4: Commit**

```bash
cd frontend
git add src/foundations/
git commit -m "feat(storybook): add Foundations design-token page"
```

---

## Task 3: Stories for Badge, Icon, PageHeader (stateless, no callbacks)

**Files:**
- Create: `frontend/src/components/common/Badge.stories.tsx`
- Create: `frontend/src/components/common/Icon.stories.tsx`
- Create: `frontend/src/components/common/PageHeader.stories.tsx`

**Interfaces:**
- Consumes: `IBadgeProps` (`frontend/src/components/common/Badge.tsx:13-20`), `IIconProps`/`IconName` (`Icon.tsx:3-26`), `IPageHeaderProps` (`PageHeader.tsx:3-8`).

- [ ] **Step 1: `Badge.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";
import { Badge } from "./Badge";

const meta: Meta<typeof Badge> = {
  title: "Common/Badge",
  component: Badge,
  tags: ["autodocs"],
  argTypes: {
    tone: {
      control: "select",
      options: ["green", "red", "blue", "gray", "amber", "success", "warning", "danger", "live"],
    },
  },
};
export default meta;

type Story = StoryObj<typeof Badge>;

export const Default: Story = { args: { children: "관망", tone: "gray" } };
export const Buy: Story = { args: { children: "매수", tone: "green", dot: true } };
export const Sell: Story = { args: { children: "매도", tone: "red", dot: true } };
export const Solid: Story = { args: { children: "거부", tone: "red", solid: true } };
export const AllTones: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {(["green", "red", "blue", "gray", "amber"] as const).map((tone) => (
        <Badge key={tone} tone={tone} dot>
          {tone}
        </Badge>
      ))}
    </div>
  ),
};
```

- [ ] **Step 2: `Icon.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";
import { Icon, type IconName } from "./Icon";

const ALL_NAMES: IconName[] = [
  "dashboard", "portfolio", "signal", "orders", "backtest", "audit", "system",
  "stocks", "play", "pause", "refresh", "bolt", "stop", "warn", "sun", "moon", "menu",
];

const meta: Meta<typeof Icon> = {
  title: "Common/Icon",
  component: Icon,
  tags: ["autodocs"],
  argTypes: {
    name: { control: "select", options: ALL_NAMES },
  },
};
export default meta;

type Story = StoryObj<typeof Icon>;

export const Default: Story = { args: { name: "dashboard", size: 24 } };

export const AllIcons: Story = {
  render: () => (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 16 }}>
      {ALL_NAMES.map((name) => (
        <div key={name} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
          <Icon name={name} size={22} />
          <span style={{ fontSize: 11, color: "var(--ink-3)" }}>{name}</span>
        </div>
      ))}
    </div>
  ),
};
```

- [ ] **Step 3: `PageHeader.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";
import { PageHeader } from "./PageHeader";
import { Badge } from "./Badge";

const meta: Meta<typeof PageHeader> = {
  title: "Common/PageHeader",
  component: PageHeader,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof PageHeader>;

export const Default: Story = {
  args: { title: "포트폴리오", subtitle: "보유 종목과 평가손익을 확인하세요." },
};

export const WithEyebrowAndRight: Story = {
  args: {
    eyebrow: "ALPHA-GEN · 운영 콘솔",
    title: "백테스트",
    subtitle: "전략을 실데이터로 검증합니다.",
    right: <Badge tone="green">모의</Badge>,
  },
};
```

- [ ] **Step 4: Verify**

Run: `cd frontend && yarn storybook`
Expected: "Common/Badge", "Common/Icon", "Common/PageHeader" all appear in the sidebar; `Icon`'s `AllIcons` story renders all 17 icons in a 6-column grid with visible strokes (not blank squares — confirms `currentColor`/`stroke` resolve correctly outside the app shell).

- [ ] **Step 5: Commit**

```bash
cd frontend
git add src/components/common/Badge.stories.tsx src/components/common/Icon.stories.tsx src/components/common/PageHeader.stories.tsx
git commit -m "feat(storybook): add Badge, Icon, PageHeader stories"
```

---

## Task 4: Stories for StagePills, LanguageToggle, ThemeToggle (interactive, self-contained state)

**Files:**
- Create: `frontend/src/components/common/StagePills.stories.tsx`
- Create: `frontend/src/components/common/LanguageToggle.stories.tsx`
- Create: `frontend/src/components/common/ThemeToggle.stories.tsx`

**Interfaces:**
- Consumes: `IStagePillsProps` (`StagePills.tsx:18-22`) — note `value`/`onChange` are controlled, so the story needs local state via `render`, not static `args`, to be interactive in Canvas.

- [ ] **Step 1: `StagePills.stories.tsx`**

```tsx
import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";
import { StagePills, type StagePillId } from "./StagePills";

const meta: Meta<typeof StagePills> = {
  title: "Common/StagePills",
  component: StagePills,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof StagePills>;

export const Interactive: Story = {
  render: () => {
    const [value, setValue] = useState<StagePillId>("paper");
    return <StagePills value={value} onChange={setValue} />;
  },
};

export const Disabled: Story = {
  args: { value: "live", disabled: true },
};
```

(`Disabled` uses static `args` since there's no interaction to preserve; `Interactive` needs `render` with local `useState` because `StagePills` is a controlled component — passing a static `value` with no working `onChange` would make clicking do nothing, which misrepresents the component.)

- [ ] **Step 2: `LanguageToggle.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";
import { LanguageToggle } from "./LanguageToggle";

const meta: Meta<typeof LanguageToggle> = {
  title: "Common/LanguageToggle",
  component: LanguageToggle,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof LanguageToggle>;

export const Default: Story = {};
```

- [ ] **Step 3: `ThemeToggle.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";
import { ThemeToggle } from "./ThemeToggle";

const meta: Meta<typeof ThemeToggle> = {
  title: "Common/ThemeToggle",
  component: ThemeToggle,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof ThemeToggle>;

export const Default: Story = {};
```

Note: `ThemeToggle` reads/writes `document.documentElement`'s `data-theme` attribute directly (`ThemeToggle.tsx:29`), which is the same attribute the `.storybook/preview.tsx` decorator (Task 1) sets from the toolbar. Clicking it in Canvas will flip the attribute; the toolbar control won't visually re-sync to match (it only pushes, doesn't read back) — that's an accepted quirk, not a bug to fix, since the two controls (toolbar vs. in-component button) are just two independent writers to the same attribute.

- [ ] **Step 4: Verify**

Run: `cd frontend && yarn storybook`
Expected: `StagePills` `Interactive` story — clicking "모의"/"실거래" pills actually switches the active pill (confirms local state wiring works). `LanguageToggle` — clicking EN switches its own button to primary style. `ThemeToggle` — clicking flips the sun/moon icon.

- [ ] **Step 5: Commit**

```bash
cd frontend
git add src/components/common/StagePills.stories.tsx src/components/common/LanguageToggle.stories.tsx src/components/common/ThemeToggle.stories.tsx
git commit -m "feat(storybook): add StagePills, LanguageToggle, ThemeToggle stories"
```

---

## Task 5: Stories for Card, Metric, MetricGrid (this session's Toss-polish components)

**Files:**
- Create: `frontend/src/components/common/Card.stories.tsx`
- Create: `frontend/src/components/common/Metric.stories.tsx`
- Create: `frontend/src/components/common/MetricGrid.stories.tsx`

**Interfaces:**
- Consumes: `ICardProps` (`Card.tsx:4-11`), `IMetricProps` incl. `size?: "hero"` (`Metric.tsx:4-13`), `IMetricGridProps` (`MetricGrid.tsx:5-9`).

- [ ] **Step 1: `Card.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";
import { Card } from "./Card";

const meta: Meta<typeof Card> = {
  title: "Common/Card",
  component: Card,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof Card>;

export const Default: Story = {
  args: { title: "최근 사이클", children: <p style={{ margin: 0 }}>본문 내용이 여기 들어갑니다.</p> },
};

export const WithEyebrowAndRight: Story = {
  args: {
    eyebrow: "TOTAL ASSET",
    title: "자산 추이",
    right: <span style={{ fontSize: 12, color: "var(--ink-3)" }}>1개월</span>,
    children: <p style={{ margin: 0 }}>차트나 표가 들어가는 영역.</p>,
  },
};
```

- [ ] **Step 2: `Metric.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";
import { Metric } from "./Metric";
import { Badge } from "./Badge";

const meta: Meta<typeof Metric> = {
  title: "Common/Metric",
  component: Metric,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof Metric>;

export const Default: Story = {
  args: { label: "현금", value: "10,000,000", unit: "원", sub: "가용 비중 100.0%" },
};

export const Hero: Story = {
  args: {
    size: "hero",
    label: "총자산",
    value: "10,201,931",
    unit: "원",
    sub: <span style={{ color: "var(--green-600)" }}>+2.02% · 기준선 대비</span>,
  },
};

export const Danger: Story = {
  args: { label: "리스크 상태", value: "-16.00", unit: "%", tone: "danger", sub: "드로우다운 한계 초과" },
};

export const WithBadge: Story = {
  args: {
    label: "워커 상태",
    value: "실행 중",
    right: (
      <Badge tone="green" dot>
        실행중
      </Badge>
    ),
  },
};
```

- [ ] **Step 3: `MetricGrid.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";
import { MetricGrid } from "./MetricGrid";
import { Metric } from "./Metric";

const meta: Meta<typeof MetricGrid> = {
  title: "Common/MetricGrid",
  component: MetricGrid,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof MetricGrid>;

export const FourColumnWithHero: Story = {
  render: () => (
    <MetricGrid columns={4}>
      <Metric size="hero" label="총자산" value="10,201,931" unit="원" sub="+2.02% · 기준선 대비" />
      <Metric label="현금" value="10,000,000" unit="원" sub="가용 비중 100.0%" />
      <Metric label="워커 상태" value="중지됨" />
      <Metric label="리스크 상태" value="0.00" unit="%" />
    </MetricGrid>
  ),
};

export const TwoColumn: Story = {
  render: () => (
    <MetricGrid columns={2}>
      <Metric label="매수 후보" value="3" unit="건" />
      <Metric label="매도 후보" value="1" unit="건" />
    </MetricGrid>
  ),
};
```

- [ ] **Step 4: Verify**

Run: `cd frontend && yarn storybook`
Expected: `MetricGrid`'s `FourColumnWithHero` story shows the first card visibly larger (34px hero number) than the other three, matching what was verified on the real dashboard earlier this session; reloading the story replays the stagger fade-in (confirms `MetricGrid.tsx`'s framer-motion variants still fire outside the app shell).

- [ ] **Step 5: Commit**

```bash
cd frontend
git add src/components/common/Card.stories.tsx src/components/common/Metric.stories.tsx src/components/common/MetricGrid.stories.tsx
git commit -m "feat(storybook): add Card, Metric, MetricGrid stories"
```

---

## Task 6: Stories for ConfirmDialog, DetailModal (modal components)

**Files:**
- Create: `frontend/src/components/common/ConfirmDialog.stories.tsx`
- Create: `frontend/src/components/common/DetailModal.stories.tsx`

**Interfaces:**
- Consumes: `IConfirmDialogProps` (`ConfirmDialog.tsx:3-12`), `IDetailModalProps` (`DetailModal.tsx:4-9`). Both render `null` when `open={false}` (`ConfirmDialog.tsx:25`, `DetailModal.tsx:13`), so stories must default `open: true` to be visible at all.

- [ ] **Step 1: `ConfirmDialog.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";
import { ConfirmDialog } from "./ConfirmDialog";

const meta: Meta<typeof ConfirmDialog> = {
  title: "Common/ConfirmDialog",
  component: ConfirmDialog,
  tags: ["autodocs"],
  parameters: { docs: { story: { inline: false, iframeHeight: 260 } } },
  args: {
    open: true,
    onCancel: () => {},
    onConfirm: () => {},
  },
};
export default meta;

type Story = StoryObj<typeof ConfirmDialog>;

export const Default: Story = {
  args: { title: "매도 주문 실행", body: "삼성전자 10주를 시장가로 매도합니다." },
};

export const Danger: Story = {
  args: {
    title: "긴급 정지 해제",
    body: "긴급 정지를 해제하면 즉시 자동 주문이 재개될 수 있습니다.",
    danger: true,
    confirmText: "해제",
  },
};
```

- [ ] **Step 2: `DetailModal.stories.tsx`**

```tsx
import type { Meta, StoryObj } from "@storybook/react-vite";
import { DetailModal } from "./DetailModal";

const meta: Meta<typeof DetailModal> = {
  title: "Common/DetailModal",
  component: DetailModal,
  tags: ["autodocs"],
  parameters: { docs: { story: { inline: false, iframeHeight: 320 } } },
  args: {
    open: true,
    onClose: () => {},
  },
};
export default meta;

type Story = StoryObj<typeof DetailModal>;

export const Default: Story = {
  args: {
    title: "주문 상세",
    children: (
      <dl className="kv">
        <dt>종목</dt>
        <dd>삼성전자 (005930)</dd>
        <dt>수량</dt>
        <dd>10주</dd>
        <dt>체결가</dt>
        <dd>75,000원</dd>
      </dl>
    ),
  },
};
```

`parameters.docs.story.inline: false` renders each story in its own iframe on the Docs tab instead of inline in the page flow — without this, the `.scrim`/`.dialog` fixed-position overlay from `console.css` would visually cover every other story stacked below it on the same Docs page.

- [ ] **Step 3: Verify**

Run: `cd frontend && yarn storybook`
Expected: both stories render their dialog centered with the dark scrim behind it, `Danger` story's confirm button is red (`btn--danger`, confirms the `danger` prop path).

- [ ] **Step 4: Commit**

```bash
cd frontend
git add src/components/common/ConfirmDialog.stories.tsx src/components/common/DetailModal.stories.tsx
git commit -m "feat(storybook): add ConfirmDialog, DetailModal stories"
```

---

## Task 7: `build-storybook` sanity check + production build regression check

**Files:** none created — verification only.

- [ ] **Step 1: Static build**

Run: `cd frontend && yarn build-storybook`
Expected: exits 0, produces `frontend/storybook-static/` with an `index.html`. No TypeScript errors (the build step type-checks story files too).

- [ ] **Step 2: Confirm production app build is unaffected**

Run: `cd frontend && yarn build`
Expected: exits 0, identical behavior to before this plan (Storybook only added devDependencies + new files under `src/components/common/*.stories.tsx`, `src/foundations/`, `.storybook/` — none of which are imported by `src/main.tsx`/`App.tsx`, so the production bundle is untouched).

- [ ] **Step 3: Add `storybook-static/` to `.gitignore`**

Check `frontend/.gitignore` for a `dist` entry; add `storybook-static/` alongside it (it's a build artifact, same category as `dist/`, and Task 8's CI job rebuilds it from source anyway).

```bash
cd frontend
grep -q "storybook-static" .gitignore || echo "storybook-static/" >> .gitignore
git add .gitignore
git commit -m "chore: ignore storybook-static build output"
```

---

## Task 8: GitHub Actions workflow — build and deploy to GitHub Pages

**Files:**
- Create: `.github/workflows/storybook-deploy.yml`

**Interfaces:**
- Consumes: `frontend/package.json`'s `build-storybook` script (added by Task 1's init command).
- Produces: a GitHub Pages deployment at `https://<owner>.github.io/<repo>/` (or `/<repo>/storybook/` if Pages is already serving something else at the repo root — confirm with the user before merging if the repo already has a Pages site).

- [ ] **Step 1: Write the workflow**

```yaml
name: Deploy Storybook to GitHub Pages

on:
  push:
    branches: [main, feature/dashboard-uplift]
    paths:
      - "frontend/**"
      - ".github/workflows/storybook-deploy.yml"
  workflow_dispatch: {}

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "yarn"
          cache-dependency-path: frontend/yarn.lock
      - name: Install dependencies
        working-directory: frontend
        run: yarn install --frozen-lockfile
      - name: Build Storybook
        working-directory: frontend
        run: yarn build-storybook
      - uses: actions/upload-pages-artifact@v3
        with:
          path: frontend/storybook-static

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/storybook-deploy.yml
git commit -m "ci: deploy Storybook to GitHub Pages on push"
```

- [ ] **Step 3: Enable GitHub Pages (manual, one-time, needs repo admin)**

This step cannot be scripted — it requires the user to click through GitHub's UI once:
1. GitHub repo → Settings → Pages
2. Under "Build and deployment" → Source: select "GitHub Actions"
3. Push (or re-run) the workflow from Step 1; the Pages URL appears in the Actions run summary and under Settings → Pages once the first deploy succeeds.

Flag this step to the user explicitly when executing this task — it's the one piece of this plan that needs a human with repo admin access, not something an agent can do from the CLI.

---

## Self-Review Notes

- **Spec coverage:** Architecture (Task 1), 10 components + Foundations (Tasks 2-6), data/security constraint (Global Constraints + every story uses literal mock strings, no API/store imports), deployment (Task 8), testing plan (`yarn storybook`/`yarn build-storybook`/`yarn build` — Tasks 1, 2, 7) — all covered.
- **Deviation from spec flagged inline:** spec said "Foundations MDX page reading tokens.json"; this plan implements it as a `.tsx` component reading live computed CSS custom properties instead (Task 2 rationale) because `tokens.json` lives outside the Vite project root. Flagging this again here since it's a implementation-level judgment call made after the spec was already approved — worth a quick nod from the user during execution, not a blocker.
- **Type/signature consistency:** `Metric`'s `size="hero"` (Task 5) matches the prop added to `frontend/src/components/common/Metric.tsx` earlier this session; `MetricGrid`'s `columns={4}` (Task 5) matches `IMetricGridProps` in `MetricGrid.tsx:5-9`.
