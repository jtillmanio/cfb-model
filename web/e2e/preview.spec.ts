import { expect, test } from "@playwright/test";

import { COLD_PREVIEW_URL } from "./test-env";

// A Vercel preview trusts Vercel Authentication (TASK-059): with no session cookie at all, the
// gate lets the request through as AUTH_ALLOWED_GITHUB_ID, and the API accepts the JWT it signs.
// The cold preview runs with VERCEL_ENV=preview (playwright.config.ts); its API answers 3 s late.

test("signed out, a preview's /teams isn't redirected and shows the data (AC-1)", async ({
  page,
  request,
}) => {
  const direct = await request.get(`${COLD_PREVIEW_URL}/teams`, { maxRedirects: 0 });
  expect(direct.status()).toBeLessThan(300);
  expect(direct.headers()["location"]).toBeUndefined();

  await page.goto(`${COLD_PREVIEW_URL}/teams`);

  await expect(page).toHaveURL(`${COLD_PREVIEW_URL}/teams`);
  await expect(page.getByRole("heading", { level: 1, name: "Teams" })).toBeVisible({
    timeout: 15_000,
  });
  const ohioState = page.getByRole("row").filter({ hasText: "Ohio State" });
  await expect(ohioState).toBeVisible({ timeout: 15_000 });
  await expect(ohioState).toContainText("Big Ten");
});
