import { test, expect } from "@playwright/test";

/**
 * 운영 콘솔 8개 메뉴 시각 회귀 스냅샷.
 * 라이트/다크(프로젝트별)로 각 메뉴 전체 페이지를 캡처한다.
 * 최초 실행 시 baseline이 없으면 생성되고, 이후 diff로 회귀를 감지한다.
 */
const ROUTES: { path: string; name: string }[] = [
  { path: "/", name: "dashboard" },
  { path: "/portfolio", name: "portfolio" },
  { path: "/signals", name: "signals" },
  { path: "/orders", name: "orders" },
  { path: "/backtests", name: "backtests" },
  { path: "/audit", name: "audit" },
  { path: "/stocks", name: "stocks" },
  { path: "/system", name: "system" },
];

for (const route of ROUTES) {
  test(`ops-console · ${route.name}`, async ({ page }) => {
    await page.goto(route.path, { waitUntil: "networkidle" });
    // 스켈레톤/데이터 정착 대기
    await page.waitForTimeout(700);

    await expect(page).toHaveScreenshot(`${route.name}.png`, {
      fullPage: true,
      // 상단 동기화 시각 등 미세 변동 허용
      maxDiffPixelRatio: 0.02,
      animations: "disabled",
      // 실시간 타임스탬프(동기화 시각)는 마스킹해 재실행 안정화
      mask: [page.locator(".topbar__sync")],
    });
  });
}
