// This creates review candidates, never a human approval.
import { spawnSync } from "node:child_process";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import path from "node:path";

if (process.env.CI)
  throw new Error("CI cannot update visual approval candidates.");
const result = spawnSync(
  process.execPath,
  [
    "node_modules/@playwright/test/cli.js",
    "test",
    "visual.spec.ts",
    "--update-snapshots",
  ],
  {
    stdio: "inherit",
    env: { ...process.env, ALGOOPTIONX_CAPTURE_CANDIDATES: "1" },
  },
);
if (result.status !== 0) process.exit(result.status || 1);
const base = path.resolve("tests/visual-baselines");
const files = readdirSync(base, { recursive: true })
  .filter((name) => String(name).endsWith(".png"))
  .map((name) => ({
    path: String(name),
    sha256: createHash("sha256")
      .update(readFileSync(path.join(base, String(name))))
      .digest("hex"),
  }))
  .sort((a, b) => a.path.localeCompare(b.path));
writeFileSync(
  path.join(base, "manifest.json"),
  JSON.stringify(
    {
      schema_version: 1,
      approval_status: "pending_human_review",
      files,
      masked_fields: [
        "session UUID",
        "global event sequence",
        "event content hash",
      ],
      environment: { platform: process.platform, node: process.version },
      policy:
        "Comparison success is not design approval. External signed UI approval must bind this source and candidate manifest before release.",
    },
    null,
    2,
  ) + "\n",
);
