// Values `next start` runs with in e2e (playwright.config.ts) and the session fixture signs with.
// Test-only and not secret: production and previews each have their own AUTH_SECRET (02 › Auth).
export const TEST_AUTH_SECRET = "e2e-only-auth-secret-never-used-outside-playwright-0001";
export const TEST_GITHUB_ID = "4242";
// Signs the API's JWT (TASK-003) in the web servers; the API verifies it (TASK-004). CI's job env
// in .github/workflows/ci.yml sets the same value for pytest: change both together.
export const TEST_API_JWT_SECRET = "e2e-only-api-jwt-secret-never-used-outside-tests-0001";

// A second `next start` set up like a Vercel preview (no GitHub client, D-102) whose API answers
// only after a delay, as a database waking from idle does (cold-api.mjs; TASK-002).
export const COLD_PREVIEW_URL = "http://127.0.0.1:3101";
