// Values `next start` runs with in e2e (playwright.config.ts) and the session fixture signs with.
// Test-only and not secret: production and previews each have their own AUTH_SECRET (02 › Auth).
export const TEST_AUTH_SECRET = "e2e-only-auth-secret-never-used-outside-playwright-0001";
export const TEST_GITHUB_ID = "4242";
// Signs the API's JWT (TASK-003) in the web servers; the API verifies it (TASK-004). CI's job env
// in .github/workflows/ci.yml sets the same value for pytest: change both together.
export const TEST_API_JWT_SECRET = "e2e-only-api-jwt-secret-never-used-outside-tests-0001";

// A second `next start` set up like a Vercel preview (VERCEL_ENV=preview and no GitHub client,
// D-153) whose API answers only after a delay, as a database waking from idle does (cold-api.mjs;
// TASK-002).
export const COLD_PREVIEW_URL = "http://127.0.0.1:3101";

// A third `next start`, set up like the first, whose API sits behind a switch (switch-api.mjs;
// TASK-054): a journey stops and restarts the API and counts the page's server-side API calls.
export const SWITCH_WEB_URL = "http://127.0.0.1:3102";
export const SWITCH_API_URL = "http://127.0.0.1:8003";

// A fourth `next start`, set up like the first, whose API's clock is the Contest screen's fixture
// time, Thu 2026-10-08 10:00 PM ET (docs/02 › Test-only sign-in and clock; TASK-072).
export const CONTEST_WEB_URL = "http://127.0.0.1:3103";
export const CONTEST_API_URL = "http://127.0.0.1:8004";

// A fifth `next start` and its API, set up like the fourth with the clock at Fri 2026-10-09 8:12 PM
// ET, after UNLV @ Boise State's kickoff and before the rest (TASK-073, journey 4).
export const FRIDAY_WEB_URL = "http://127.0.0.1:3104";
export const FRIDAY_API_URL = "http://127.0.0.1:8005";
