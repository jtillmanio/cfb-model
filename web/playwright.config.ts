import { defineConfig, devices } from "@playwright/test";

// E2E runs `next start` + uvicorn against the seeded test DB (APP_ENV=test routes the API
// through the test-DB guard). Run `pnpm db:migrate:test` and `pnpm db:seed` first.
// CI runs `pnpm build` as its own step; locally this builds first so a stale .next can't pass.
const WEB_PORT = 3100;
const API_PORT = 8001;
const API_URL = `http://127.0.0.1:${API_PORT}`;
const isCI = !!process.env.CI;

export default defineConfig({
  testDir: "./e2e",
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  reporter: isCI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "phone", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 } } },
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
  ],
  webServer: [
    {
      command: `uv --directory ../python run uvicorn api.main:app --port ${API_PORT}`,
      url: `${API_URL}/api/py/health`,
      env: { APP_ENV: "test", GIT_COMMIT_SHA: process.env.GITHUB_SHA ?? "local" },
      reuseExistingServer: !isCI,
      timeout: 60_000,
    },
    {
      command: isCI
        ? `pnpm start --port ${WEB_PORT}`
        : `pnpm build && pnpm start --port ${WEB_PORT}`,
      url: `http://127.0.0.1:${WEB_PORT}/teams`,
      env: { API_URL },
      reuseExistingServer: !isCI,
      timeout: 180_000,
    },
  ],
});
