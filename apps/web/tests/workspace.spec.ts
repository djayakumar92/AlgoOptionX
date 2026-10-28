import { test, expect } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

async function command(
  request: APIRequestContext,
  action: string,
  fields = {},
) {
  const response = await request.post("/api/commands", {
    data: { key: crypto.randomUUID(), action, ...fields },
  });
  expect(response.ok()).toBeTruthy();
}

test.beforeEach(async ({ request }) => {
  await command(request, "control", { running: false, killed: true });
  const response = await request.post("/api/sessions");
  expect(response.ok()).toBeTruthy();
});

test("buy, mark, close and export a virtual trade", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page).toHaveTitle(/AlgoOptionX/);
  await expect(page.getByText("Your market. Your edge.")).toBeVisible();
  await page.getByRole("link", { name: "Market terminal" }).click();
  await page.getByRole("button", { name: "Buy paper" }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("button", { name: "Close order ticket" })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(page.getByRole("button", { name: "Cancel", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Buy paper" }).first().click();
  await page.getByRole("button", { name: "Confirm virtual buy" }).click();
  await expect(page.getByRole("status")).toContainText("Virtual buy filled");
  await page.getByRole("link", { name: /Paper portfolio/ }).click();
  await expect(
    page.getByRole("button", { name: "Close position" }),
  ).toHaveCount(1);
  await page.getByRole("button", { name: "Close position" }).click();
  await expect(page.getByText("A clean slate. A clear plan.")).toBeVisible();
  const state = await (await request.get("/api/workspace")).json();
  expect(state.account.cash).toBe(state.account.equity);
  expect(state.account.fees).toBe(4000);
  await page.getByRole("link", { name: "Activity & audit" }).click();
  await expect(
    page.getByText("Virtual exit · MANUAL", { exact: false }),
  ).toBeVisible();
  const exported = await request.get("/api/audit/export");
  expect(
    (await exported.json()).events.filter(
      (e: { kind: string }) => e.kind === "SELL",
    ),
  ).toHaveLength(1);
  expect(errors).toEqual([]);
});

test("playback, autonomous decisions and emergency exit", async ({
  page,
  request,
}) => {
  await page.goto("/strategy");
  await page
    .getByRole("button", { name: "Enable autonomous paper entries" })
    .click();
  for (let i = 0; i < 6; i++) await command(request, "advance");
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/workspace")).json()).positions.length,
    )
    .toBeGreaterThan(0);
  await page.getByRole("button", { name: "Start playback" }).click();
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/workspace")).json()).market.tick,
    )
    .toBeGreaterThan(6);
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Activate kill switch" }).click();
  await expect(
    page.getByRole("button", { name: "Release kill switch" }),
  ).toBeVisible();
  const state = await (await request.get("/api/workspace")).json();
  expect(state.positions).toEqual([]);
  expect(state.account.killed).toBe(1);
  const response = await request.post("/api/commands", {
    data: {
      key: "kill-bypass",
      action: "buy",
      instrument: state.market.contracts[0].id,
    },
  });
  expect(response.status()).toBe(409);
});

test("isolated replay produces results without changing portfolio", async ({
  page,
  request,
}) => {
  await page.goto("/backtest");
  const before = await (await request.get("/api/workspace")).json();
  await page.getByLabel("Session length").selectOption("60");
  await page.getByRole("button", { name: "Run experiment" }).click();
  await expect(page.getByText("COMPLETED · 60 BARS")).toBeVisible();
  await expect(page.getByRole("img", { name: /Replay equity/ })).toBeVisible();
  const after = await (await request.get("/api/workspace")).json();
  expect(after.account).toEqual(before.account);
});

test("responsive routes and candidate screenshots", async ({
  page,
  request,
}, testInfo) => {
  for (let i = 0; i < 30; i++) await command(request, "advance");
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const route of [
      "/",
      "/market",
      "/paper",
      "/strategy",
      "/backtest",
      "/analytics",
      "/journal",
      "/settings",
    ]) {
      await page.goto(route);
      await expect(page.locator(".ax-session-bar")).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBeTruthy();
    }
    await page.goto("/");
    await expect(page.getByRole("img", { name: /NIFTY price/ })).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath(`overview-${width}-candidate.png`),
      fullPage: true,
    });
    if (width === 390) {
      await page.getByRole("button", { name: "Toggle navigation" }).click();
      await page.getByRole("link", { name: "Market terminal" }).click();
      await expect(
        page.getByRole("heading", { name: "The market, in focus." }),
      ).toBeVisible();
    }
  }
});
