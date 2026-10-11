import os from "node:os";
import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

// Dedicated ports and a throwaway database keep e2e runs away from the developer's app and data.
// reuseExistingServer is off so a port conflict fails loudly instead of testing the wrong server.
const FRONTEND_PORT = 3100;
const BACKEND_PORT = 8100;

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `uv run uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT}`,
      cwd: "../backend",
      url: `http://127.0.0.1:${BACKEND_PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        DB_PATH: path.join(os.tmpdir(), "pm-e2e.db"),
        // An empty key makes the backend answer "not configured" instead of calling OpenRouter.
        OPENROUTER_API_KEY: "",
      },
    },
    {
      command: `npm run dev -- --hostname 127.0.0.1 --port ${FRONTEND_PORT}`,
      url: `http://127.0.0.1:${FRONTEND_PORT}`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { BACKEND_API_URL: `http://127.0.0.1:${BACKEND_PORT}` },
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
