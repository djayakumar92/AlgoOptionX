import { test, expect } from "@playwright/test";
test("public entry is read-only and guided start preserves the existing account", async ({ page, request }) => {
  const before = await (await request.get('/api/workspace')).json();
  const calls: string[] = [];
  page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/')) calls.push(request.method() + ' ' + new URL(request.url()).pathname); });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Research clearly/ })).toBeVisible();
  await page.getByRole('link', { name: 'See how it works' }).click();
  await expect(page.getByRole('heading', { name: 'Know what the demo represents.' })).toBeVisible();
  await page.getByRole('link', { name: 'Explore the demo', exact: true }).last().click();
  await expect(page.getByRole('radio', { name: /Guided overview/ })).toBeChecked();
  expect(calls).toEqual([]);
  await page.getByRole('button', { name: 'Open demo workspace' }).click();
  await expect(page).toHaveURL(/\/app\/overview$/);
  await expect(page).toHaveTitle('Overview | AlgoOptionX');
  await expect(page.locator('.ax-session-bar')).toBeVisible();
  const after = await (await request.get('/api/workspace')).json();
  expect(after.account.id).toBe(before.account.id);
  expect(after.account.cash).toBe(before.account.cash);
  expect(after.positions).toEqual(before.positions);
  expect(calls.every(call => call.startsWith('GET '))).toBeTruthy();
});
test("experienced start persists and legacy routes resolve without nested prefixes", async ({ page }) => {
  await page.goto('/app/start');
  await page.getByRole('radio', { name: /Straight to the market/ }).check();
  await page.getByRole('button', { name: 'Open demo workspace' }).click();
  await expect(page).toHaveURL(/\/app\/market$/);
  await page.goto('/app/start');
  await expect(page.getByRole('radio', { name: /Straight to the market/ })).toBeChecked();
  await page.goto('/market?context=test#chain');
  await expect(page).toHaveURL(/\/app\/market\?context=test#chain$/);
  await expect(page.locator('.ax-session-bar')).toBeVisible();
});
test("mobile entry and navigation support keyboard and blocked storage", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('Blocked'); } }); });
  for (const route of ['/', '/walkthrough', '/app/start']) {
    await page.goto(route);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  }
  await page.getByRole('button', { name: 'Open demo workspace' }).click();
  const toggle = page.getByRole('button', { name: 'Toggle navigation' });
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Escape');
  await expect(toggle).toBeFocused();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await toggle.click();
  await page.getByRole('link', { name: /Trade.*Market terminal/ }).click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByRole('heading', { name: 'The market, in focus.' })).toBeVisible();
});

test("limitations anchors scroll and malformed hashes do not crash", async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByRole('link', { name: 'Understand the simulation' }).click();
  await expect(page.locator('#limitations')).toBeInViewport();
  await page.goto('/walkthrough#%');
  await expect(page.getByRole('heading', { name: 'Know what the demo represents.' })).toBeVisible();
  expect(errors).toEqual([]);
});
