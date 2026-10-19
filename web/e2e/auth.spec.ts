import { readdirSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { findSessionCookie, mintSessionCookie } from "./fixtures";

// Sign-in gate (TASK-001, F-42 items 1-2): every page needs the allowlisted session; a missing,
// stale or forged one lands on /login, never a 500.

const DAY = 24 * 60 * 60;

// The newest migration's revision: they're numbered 0001, 0002, … and `pnpm db:check` keeps one
// head, so the test DB e2e runs against is at this one.
const MIGRATION_HEAD = readdirSync(path.join(__dirname, "../../python/db/migrations/versions"))
  .flatMap((file) => /^(\d{4})_\w+\.py$/.exec(file)?.[1] ?? [])
  .sort()
  .at(-1);

// Every response the page sees, redirects included.
function recordStatuses(page: Page): number[] {
  const statuses: number[] = [];
  page.on("response", (response) => statuses.push(response.status()));
  return statuses;
}

async function expectOnLogin(page: Page) {
  await expect(page).toHaveURL(/\/login(\?|$)/);
  await expect(page.getByRole("button", { name: "Sign in with GitHub" })).toBeVisible();
}

test.describe("signed out", () => {
  for (const path of ["/", "/teams"]) {
    test(`${path} redirects to /login`, async ({ page, request, baseURL }) => {
      const direct = await request.get(path, { maxRedirects: 0 });
      expect(direct.status()).toBe(307);
      expect(new URL(direct.headers()["location"], baseURL).pathname).toBe("/login");

      const statuses = recordStatuses(page);
      await page.goto(path);
      await expectOnLogin(page);
      expect(statuses.filter((status) => status >= 500)).toEqual([]);
    });
  }

  test("health stays open: 200 JSON with a reachable database, no redirect", async ({
    request,
  }) => {
    const response = await request.get("/api/py/health", { maxRedirects: 0 });
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("application/json");
    expect(await response.json()).toMatchObject({ db_reachable: true, migration_head: MIGRATION_HEAD });
  });
});

test.describe("a session cookie that doesn't hold", () => {
  const cases: { name: string; cookie: (baseURL: string) => ReturnType<typeof mintSessionCookie> }[] =
    [
      {
        name: "garbage",
        cookie: async (baseURL) => ({
          ...(await mintSessionCookie({ baseURL })),
          value: "not-a-session-token",
        }),
      },
      {
        name: "signed with a different AUTH_SECRET",
        cookie: (baseURL) =>
          mintSessionCookie({ baseURL, secret: "some-other-deployments-auth-secret-0002" }),
      },
      {
        name: "expired",
        cookie: (baseURL) => mintSessionCookie({ baseURL, tokenMaxAge: -60 }),
      },
      {
        name: "valid, but for another GitHub account",
        cookie: (baseURL) => mintSessionCookie({ baseURL, githubId: "9999999" }),
      },
    ];

  for (const { name, cookie } of cases) {
    test(`${name}: /teams ends on /login with no 500`, async ({ page, context, baseURL }) => {
      await context.addCookies([await cookie(baseURL!)]);
      const statuses = recordStatuses(page);

      await page.goto("/teams");

      await expectOnLogin(page);
      expect(statuses.filter((status) => status >= 500)).toEqual([]);
      await expect(page.getByRole("row").filter({ hasText: "Ohio State" })).toHaveCount(0);
    });
  }
});

test.describe("signed in", () => {
  test("a visit renews the session cookie for 90 days", async ({ page, context, baseURL }) => {
    // Mint a cookie good for one hour; Auth.js re-issues it with the configured max age.
    await context.addCookies([
      await mintSessionCookie({ baseURL: baseURL!, tokenMaxAge: 60 * 60 }),
    ]);
    const before = findSessionCookie(await context.cookies())!;
    expect(before.expires - Date.now() / 1000).toBeLessThan(2 * 60 * 60);

    await page.goto("/teams");
    await expect(page.getByRole("heading", { level: 1, name: "Teams" })).toBeVisible();

    const after = findSessionCookie(await context.cookies())!;
    const daysLeft = (after.expires - Date.now() / 1000) / DAY;
    expect(daysLeft).toBeGreaterThan(89);
    expect(daysLeft).toBeLessThanOrEqual(90);
  });
});
