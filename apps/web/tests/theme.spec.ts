import { test, expect } from "@playwright/test";

test("theme preference persists, follows system and works across routes on mobile", async ({ page }, testInfo) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/app/overview");
  const root = page.locator("html");
  const theme = page.getByRole("combobox", { name: "Theme", exact: true });
  await expect(root).toHaveAttribute("data-workspace-theme", "dark");
  await theme.selectOption("light");
  await expect(root).toHaveAttribute("data-workspace-theme", "light");
  await expect(page.locator(".ax-app")).toHaveCSS("background-color", "rgb(246, 248, 252)");
  await expect(page.locator(".ax-app")).toHaveCSS("color", "rgb(23, 32, 51)");
  await page.screenshot({ path: testInfo.outputPath("light-desktop-candidate.png"), fullPage: true });
  await page.reload();
  await expect(theme).toHaveValue("light");
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ["/app/overview", "/market", "/paper", "/strategy", "/backtest", "/analytics", "/journal", "/settings"]) {
    await page.goto(route);
    await expect(page.locator(".ax-session-bar")).toBeVisible();
    await expect(theme).toHaveValue("light");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  }
  await page.screenshot({ path: testInfo.outputPath("light-mobile-candidate.png"), fullPage: true });
  await theme.selectOption("system");
  await expect(root).toHaveAttribute("data-workspace-theme", "light");
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(root).toHaveAttribute("data-workspace-theme", "dark");
  await theme.selectOption("light");
  await page.emulateMedia({ colorScheme: "light" });
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(root).toHaveAttribute("data-workspace-theme", "light");
  await theme.selectOption("dark");
  await page.reload();
  await expect(theme).toHaveValue("dark");
  await expect(page.locator(".ax-app")).toHaveCSS("background-color", "rgb(11, 18, 32)");
  await page.screenshot({ path: testInfo.outputPath("dark-mobile-candidate.png"), fullPage: true });
});

test("theme works when storage is unavailable", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "localStorage", { get() { throw new Error("Storage blocked"); } });
  });
  await page.goto("/app/overview");
  await page.getByRole("combobox", { name: "Theme", exact: true }).selectOption("light");
  await expect(page.locator("html")).toHaveAttribute("data-workspace-theme", "light");
  await expect(page.locator(".ax-session-bar")).toBeVisible();
});
