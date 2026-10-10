import { defineConfig, devices } from "@playwright/test";

import { COLD_PREVIEW_URL, TEST_AUTH_SECRET, TEST_GITHUB_ID } from "./e2e/test-env";

// E2E runs `next start` + uvicorn against the seeded test DB (APP_ENV=test routes the API
// through the test-DB guard). Run `pnpm db:migrate:test` and `pnpm db:seed` first.
// CI runs `pnpm build` as its own step (with API_URL set in ci.yml, since next.config bakes the
// /api/py rewrite at build time); locally this builds first so a stale .next can't pass.
const WEB_PORT = 3100;
const API_PORT = 8001;
const API_URL = `http://127.0.0.1:${API_PORT}`;
const COLD_API_PORT = 8002;
const COLD_PREVIEW_PORT = Number(new URL(COLD_PREVIEW_URL).port);
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
      url: `http://127.0.0.1:${WEB_PORT}/login`,
      // Sign-in: the session fixture (e2e/fixtures.ts) signs with the same test secret. A GitHub
      // client ID and secret that GitHub would refuse, so /login draws its button as in dev and
      // production; no test presses it. AUTH_TRUST_HOST because `next start` is
      // NODE_ENV=production off Vercel.
      env: {
        API_URL,
        AUTH_SECRET: TEST_AUTH_SECRET,
        AUTH_ALLOWED_GITHUB_ID: TEST_GITHUB_ID,
        AUTH_GITHUB_ID: "e2e-github-client-id",
        AUTH_GITHUB_SECRET: "e2e-github-client-secret",
        AUTH_TRUST_HOST: "true",
      },
      reuseExistingServer: !isCI,
      timeout: 180_000,
    },
    // The cold preview (TASK-002): the same build, started after the one above, with no GitHub
    // client (D-102; empty, so the repo's .env.local can't fill it in) and an API that answers
    // 3 s late (e2e/cold-api.mjs).
    {
      command: "node e2e/cold-api.mjs",
      url: `http://127.0.0.1:${COLD_API_PORT}/api/py/health`,
      env: { COLD_API_PORT: String(COLD_API_PORT), COLD_API_TARGET: API_URL, COLD_API_DELAY_MS: "3000" },
      reuseExistingServer: !isCI,
      timeout: 60_000,
    },
    {
      command: `pnpm start --port ${COLD_PREVIEW_PORT}`,
      url: `${COLD_PREVIEW_URL}/login`,
      env: {
        API_URL: `http://127.0.0.1:${COLD_API_PORT}`,
        AUTH_SECRET: TEST_AUTH_SECRET,
        AUTH_ALLOWED_GITHUB_ID: TEST_GITHUB_ID,
        AUTH_GITHUB_ID: "",
        AUTH_GITHUB_SECRET: "",
        AUTH_TRUST_HOST: "true",
      },
      reuseExistingServer: !isCI,
      timeout: 60_000,
    },
  ],
});
