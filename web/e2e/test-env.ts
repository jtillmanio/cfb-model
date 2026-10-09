// Values `next start` runs with in e2e (playwright.config.ts) and the session fixture signs with.
// Test-only and not secret: production and previews each have their own AUTH_SECRET (02 › Auth).
export const TEST_AUTH_SECRET = "e2e-only-auth-secret-never-used-outside-playwright-0001";
export const TEST_GITHUB_ID = "4242";
