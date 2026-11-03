import { test, expect } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";
import type { AuditEvent, Workspace } from "../src/features/workspace/types";

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
  await page.goto("/app/overview");
  await expect(page).toHaveTitle(/AlgoOptionX/);
  await expect(page.getByText("Your research, in perspective.")).toBeVisible();
  await page.getByRole("link", { name: /Trade.*Market terminal/ }).click();
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
      "/app/overview",
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
    await page.goto("/app/overview");
    await expect(page.getByRole("img", { name: /NIFTY price/ })).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath(`overview-${width}-candidate.png`),
      fullPage: true,
    });
    if (width === 390) {
      await page.getByRole("button", { name: "Toggle navigation" }).click();
      await page.getByRole("link", { name: /Trade.*Market terminal/ }).click();
      await expect(
        page.getByRole("heading", { name: "The market, in focus." }),
      ).toBeVisible();
    }
  }
});

// These display-only events are synthetic accessibility fixtures, not trades or
// authenticated audit records. The existing beforeEach resets the isolated test
// database; the new test actions below never submit commands or orders.
test.describe("journal filter accessibility", () => {
  function syntheticEvents(
    kinds = ["BUY", "SELL", "REJECTED", "DECISION", "CONTROL"],
  ): AuditEvent[] {
    return Array.from({ length: 161 }, (_, index) => ({
      seq: 161 - index,
      tick: 0,
      kind: kinds[index % kinds.length],
      hash: (index + 1).toString(16).padStart(64, "0"),
      previous_hash: "0".repeat(64),
      payload: { message: `Synthetic journal display event ${161 - index}` },
    }));
  }

  async function prepareJournal(
    page: Page,
    request: APIRequestContext,
    events: AuditEvent[],
  ) {
    const response = await request.get("/api/workspace");
    expect(response.ok()).toBeTruthy();
    const before: Workspace = await response.json();
    const mutatingRequests: string[] = [];
    const pageErrors: string[] = [];
    page.on("request", (request) => {
      if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
        mutatingRequests.push(`${request.method()} ${request.url()}`);
      }
    });
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await page.route("**/api/**", async (route) => {
      if (!["GET", "HEAD", "OPTIONS"].includes(route.request().method())) {
        await route.abort();
      } else if (new URL(route.request().url()).pathname === "/api/workspace") {
        await route.fulfill({ json: { ...before, events } });
      } else {
        await route.continue();
      }
    });
    await page.goto("/journal");
    const group = page.getByRole("group", {
      name: "Activity filters",
      exact: true,
    });
    await expect(group).toBeVisible();
    return {
      group,
      rows: page.locator(".ax-activity .ax-event"),
      async expectReadOnly() {
        const response = await request.get("/api/workspace");
        expect(response.ok()).toBeTruthy();
        const after: Workspace = await response.json();
        expect(after.account).toEqual(before.account);
        expect(after.positions).toEqual(before.positions);
        expect(after.events).toEqual(before.events);
        expect(mutatingRequests).toEqual([]);
        expect(pageErrors).toEqual([]);
      },
    };
  }

  test("named filter buttons expose pressed state and support keyboard selection", async ({
    page,
    request,
  }) => {
    const events = syntheticEvents();
    const journal = await prepareJournal(page, request, events);
    const buttons = journal.group.getByRole("button");
    await expect(buttons).toHaveCount(6);
    await expect(buttons).toHaveText([
      "All events", "buy", "sell", "rejected", "decision", "control",
    ]);
    await expect(journal.group.locator('button[type="button"]')).toHaveCount(6);
    const all = journal.group.getByRole("button", { name: "All events", exact: true });
    await expect(all).toHaveAttribute("aria-pressed", "true");
    await expect(journal.group.getByRole("button", { pressed: true })).toHaveCount(1);
    await expect(journal.group.locator('button[aria-pressed="false"]')).toHaveCount(5);
    await expect(journal.rows).toHaveCount(150);
    await expect(journal.rows.locator(".ax-event-seq")).toHaveText(
      events.slice(0, 150).map((event) => `#${String(event.seq).padStart(3, "0")}`),
    );

    const buy = journal.group.getByRole("button", { name: "buy", exact: true });
    await buy.focus();
    await page.keyboard.press("Enter");
    await expect(buy).toBeFocused();
    await expect(buy).toHaveAttribute("aria-pressed", "true");
    await expect(all).toHaveAttribute("aria-pressed", "false");
    await expect(journal.group.getByRole("button", { pressed: true })).toHaveCount(1);
    await expect(journal.group.locator('button[aria-pressed="false"]')).toHaveCount(5);
    const buys = events.filter((event) => event.kind === "BUY");
    await expect(journal.rows.locator("strong")).toHaveText(
      buys.map((event) => event.payload.message!),
    );
    await expect(journal.rows.locator(".ax-event-seq")).toHaveText(
      buys.map((event) => `#${String(event.seq).padStart(3, "0")}`),
    );

    const sell = journal.group.getByRole("button", { name: "sell", exact: true });
    await page.keyboard.press("Tab");
    await expect(sell).toBeFocused();
    await page.keyboard.press("Space");
    await expect(sell).toHaveAttribute("aria-pressed", "true");
    await expect(buy).toHaveAttribute("aria-pressed", "false");
    await expect(journal.group.getByRole("button", { pressed: true })).toHaveCount(1);
    await expect(journal.group.locator('button[aria-pressed="false"]')).toHaveCount(5);
    await expect(journal.rows.locator("strong")).toHaveText(
      events.filter((event) => event.kind === "SELL").map((event) => event.payload.message!),
    );
    await page.keyboard.press("Space");
    await expect(sell).toHaveAttribute("aria-pressed", "true");
    await expect(journal.group.getByRole("button", { pressed: true })).toHaveCount(1);
    await expect(journal.group.locator('button[aria-pressed="false"]')).toHaveCount(5);
    await journal.expectReadOnly();
  });

  test("filtering preserves row order, limits, empty state and read-only data", async ({
    page,
    request,
  }) => {
    const events = syntheticEvents(["CONTROL"]);
    const journal = await prepareJournal(page, request, events);
    const control = journal.group.getByRole("button", { name: "control", exact: true });
    await control.click();
    await expect(control).toHaveAttribute("aria-pressed", "true");
    await expect(journal.rows).toHaveCount(150);
    await expect(journal.rows.locator("strong")).toHaveText(
      events.slice(0, 150).map((event) => event.payload.message!),
    );
    await expect(journal.rows.locator(".ax-event-seq")).toHaveText(
      events.slice(0, 150).map((event) => `#${String(event.seq).padStart(3, "0")}`),
    );
    const buy = journal.group.getByRole("button", { name: "buy", exact: true });
    await buy.click();
    await expect(buy).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText("No matching events", { exact: true })).toBeVisible();
    await expect(journal.rows).toHaveCount(0);
    await journal.group.getByRole("button", { name: "All events", exact: true }).click();
    await expect(journal.rows).toHaveCount(150);
    await expect(journal.rows.locator("strong")).toHaveText(
      events.slice(0, 150).map((event) => event.payload.message!),
    );
    await expect(page.getByText("No matching events", { exact: true })).toHaveCount(0);
    await expect(journal.group.getByRole("button", { pressed: true })).toHaveCount(1);
    await expect(journal.group.locator('button[aria-pressed="false"]')).toHaveCount(5);
    await journal.expectReadOnly();
  });

  test("journal filter semantics preserve export, compact overview and mobile layout", async ({
    page,
    request,
  }) => {
    const events = syntheticEvents();
    const journal = await prepareJournal(page, request, events);
    const exported = page.getByRole("link", { name: "Export JSON ↓", exact: true });
    await expect(exported).toHaveAttribute("href", "/api/audit/export");
    await expect(exported).toHaveAttribute("download", "");
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(journal.group).toBeVisible();
    await expect(journal.group.getByRole("button")).toHaveCount(6);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await page.goto("/app/overview");
    await expect(page.getByRole("group", { name: "Activity filters" })).toHaveCount(0);
    const recent = page.locator(".ax-activity .ax-event");
    await expect(recent).toHaveCount(5);
    await expect(recent.locator("strong")).toHaveText(
      events.slice(0, 5).map((event) => event.payload.message!),
    );
    await journal.expectReadOnly();
  });
});
