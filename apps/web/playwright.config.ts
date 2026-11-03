import { defineConfig } from "@playwright/test";
import path from "node:path";
import { readFileSync } from "node:fs";
const governed = process.env.ALGOOPTIONX_UI_CONTEXT ? JSON.parse(readFileSync(process.env.ALGOOPTIONX_UI_CONTEXT, "utf8")) : null;

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
  outputDir: process.env.ALGOOPTIONX_EVIDENCE_DIR ? path.join(process.env.ALGOOPTIONX_EVIDENCE_DIR, "artifacts") : "test-results",
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
    locale: governed?.renderer.locale || "en-IN",
    timezoneId: governed?.renderer.timezone || "Asia/Kolkata",
    reducedMotion: "reduce",
    deviceScaleFactor: governed?.renderer.device_scale_factor || 1,
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
