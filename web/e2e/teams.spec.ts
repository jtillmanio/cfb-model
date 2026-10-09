import { expect, test } from "./fixtures";

// Walking-skeleton smoke test: the real path from the seeded test DB through FastAPI to the page,
// signed in with the minted test session. Health, which needs no session, is in auth.spec.ts.

test("Teams lists the seeded fixture teams", async ({ page }) => {
  await page.goto("/teams");

  await expect(page.getByRole("heading", { level: 1, name: "Teams" })).toBeVisible();
  const ohioState = page.getByRole("row").filter({ hasText: "Ohio State" });
  await expect(ohioState).toBeVisible();
  await expect(ohioState).toContainText("Big Ten");
});

test("the root URL opens Teams", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/teams$/);
});
