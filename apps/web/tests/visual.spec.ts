import { test, expect } from "@playwright/test";
import os from "node:os";

const routes = [
  ["overview", "/"],
  ["market", "/market"],
  ["portfolio", "/paper"],
  ["decisions", "/strategy"],
  ["replay", "/backtest"],
  ["performance", "/analytics"],
  ["audit", "/journal"],
  ["settings", "/settings"],
];

for (const width of [1440, 1024, 390]) {
  for (const [name, route] of routes) {
    test(`@visual ${name} ${width}`, async ({ page, request, browser }) => {
      const send = async (action: string, fields = {}) => {
        const result = await request.post("/api/commands", {
          data: { key: crypto.randomUUID(), action, ...fields },
        });
        expect(result.ok()).toBeTruthy();
      };
      await send("control", { running: false, killed: true });
      expect((await request.post("/api/sessions")).ok()).toBeTruthy();
      for (let i = 0; i < 30; i++) await send("advance");
      const state = await (await request.get("/api/workspace")).json();
      await page.setViewportSize({ width, height: 1000 });
      await page.goto(route);
      await expect(page.locator(".ax-session-bar")).toBeVisible();
      await expect(page.getByText("Bar 30 / 374")).toHaveCount(1);
      // Normalize only nondeterministic identities, never money, quotes or risk.
      await page.locator(".ax-event-seq").evaluateAll((nodes) =>
        nodes.forEach((node) => {
          node.textContent = "#SESSION";
        }),
      );
      await page.locator(".ax-event div > span").evaluateAll((nodes) =>
        nodes.forEach((node) => {
          node.textContent =
            node.textContent?.replace(/[0-9a-f]{16}…/g, "0000000000000000…") ||
            "";
        }),
      );
      const identity = page.getByText(`${state.account.id.slice(0, 18)}…`, {
        exact: true,
      });
      if (await identity.count())
        await identity.evaluate((node) => {
          node.textContent = "00000000-0000-0000…";
        });
      const profile = `chromium-${browser.version().split(".")[0]}-${os.platform()}`;
      await expect(page).toHaveScreenshot([profile, `${name}-${width}.png`], {
        fullPage: true,
        animations: "disabled",
        caret: "hide",
        maxDiffPixels: 0,
      });
    });
  }
}

test("@visual order dialog keyboard state", async ({
  page,
  request,
  browser,
}) => {
  await request.post("/api/commands", {
    data: {
      key: crypto.randomUUID(),
      action: "control",
      running: false,
      killed: true,
    },
  });
  await request.post("/api/sessions");
  await page.goto("/market");
  await page.getByRole("button", { name: "Buy paper" }).first().click();
  await expect(
    page.getByRole("button", { name: "Close order ticket" }),
  ).toBeFocused();
  await expect(page.getByRole("dialog")).toHaveScreenshot(
    [
      `chromium-${browser.version().split(".")[0]}-${os.platform()}`,
      "order-dialog.png",
    ],
    { animations: "disabled", maxDiffPixels: 0 },
  );
});
