import { defineConfig } from "@playwright/test";
import path from "node:path";

const python =
  process.env.LMS_PYTHON ??
  path.resolve(
    "../../.venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
export default defineConfig({
  testDir: "./tests/e2e",
  workers: 1,
  retries: 0,
  timeout: 60000,
  use: {
    baseURL: "http://127.0.0.1:5174",
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: `"${python}" -m scripts.run_demo`,
      cwd: "../backend",
      url: "http://127.0.0.1:8013/healthz",
      timeout: 120000,
      reuseExistingServer: false,
      env: { LMS_DEMO_DATABASE: "lms_demo_e2e", LMS_DEMO_PORT: "8013" },
    },
    {
      command: "npm run dev -- --port 5174",
      url: "http://127.0.0.1:5174",
      reuseExistingServer: false,
      env: { LMS_API_TARGET: "http://127.0.0.1:8013" },
    },
  ],
});
