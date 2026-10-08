import { expect, test } from "@playwright/test";

// Walking-skeleton smoke test: the real path from the seeded test DB through FastAPI to the page.

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

test("health reports a reachable database and the migration head", async ({ request }) => {
  const response = await request.get("/api/py/health");
  expect(response.ok()).toBe(true);
  expect(await response.json()).toMatchObject({ db_reachable: true, migration_head: "0001" });
});
