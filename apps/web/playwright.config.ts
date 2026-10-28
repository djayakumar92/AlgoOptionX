import { defineConfig } from "@playwright/test";
import path from "node:path";

if (
  process.argv.some((arg) => arg.startsWith("--update-snapshots")) &&
  (process.env.CI || process.env.ALGOOPTIONX_CAPTURE_CANDIDATES !== "1")
) {
  throw new Error(
    "Use npm run visual:candidates outside CI. Candidates still need human design approval.",
  );
}

export default defineConfig({
  testDir: "./tests",
  snapshotPathTemplate: "{testDir}/visual-baselines/{arg}{ext}",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    ["html", { open: "never" }],
    [
      "json",
      {
        outputFile: path.join(
          process.env.ALGOOPTIONX_EVIDENCE_DIR || "test-results",
          "playwright.json",
        ),
      },
    ],
  ],
  use: {
    baseURL: "http://127.0.0.1:8011",
    browserName: "chromium",
    locale: "en-IN",
    timezoneId: "Asia/Kolkata",
    reducedMotion: "reduce",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {},
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: `ALGOOPTIONX_DB=/tmp/algooptionx-e2e-${process.pid}.db ../../.venv/bin/python -m uvicorn algooptionx.api.app:app --app-dir ../../src --host 127.0.0.1 --port 8011`,
    url: "http://127.0.0.1:8011/api/health",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
