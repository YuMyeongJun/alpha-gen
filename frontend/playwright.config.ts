import { defineConfig, devices } from "@playwright/test";

/**
 * 운영 콘솔 시각 회귀(스냅샷) 설정.
 * - 테스트는 frontend/e2e/ 에 위치 (단일 node 프로젝트라 모듈 해석이 단순함).
 * - 앱 서버는 자동 기동하지 않는다(트레이딩 백엔드 자동 실행 금지). 아래 중 하나를
 *   먼저 띄우고 PLAYWRIGHT_BASE_URL로 지정한다:
 *     · 격리 mock 샌드박스(:8010, 실데이터·안전) — 권장
 *     · frontend 정적 프리뷰: `yarn build && yarn preview` (:4173, /api 없음)
 * - 최초 1회 브라우저 설치 필요: `npx playwright install chromium`
 */
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:8010";

export default defineConfig({
  testDir: "./e2e",
  snapshotDir: "./e2e/__snapshots__",
  outputDir: "./e2e/test-results",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { outputFolder: "./e2e/playwright-report", open: "never" }]],
  use: {
    baseURL: BASE_URL,
    screenshot: "only-on-failure",
  },
  // 라이트/다크 각각 스냅샷 (프로젝트명이 스냅샷 경로에 포함되어 자동 분리됨)
  projects: [
    { name: "light", use: { ...devices["Desktop Chrome"], colorScheme: "light" } },
    { name: "dark", use: { ...devices["Desktop Chrome"], colorScheme: "dark" } },
  ],
});
