import { expect, test, type Page } from "@playwright/test";

import { mintSessionCookie } from "./fixtures";
import { COLD_PREVIEW_URL } from "./test-env";

// S-15 sign-in card (TASK-002, F-42 items 1 and 3), at phone and desktop (the two projects).
// The cold preview server has no GitHub client and an API that answers 3 s late (cold-api.mjs).

const SIGN_IN = { name: "Sign in with GitHub" } as const;
const FOOTNOTE = "Stays signed in on this device for 90 days.";
const WAKING = "Waking up the database…";
const WAKING_NOTE = "GitHub said yes. The first request after a quiet spell can take a few seconds.";

async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
}

// Next's route announcer is also role="alert".
function deniedAlert(page: Page) {
  return page.getByRole("alert").filter({ hasText: "This GitHub account isn't allowed" });
}

async function expectTouchTarget(page: Page, name: string) {
  const box = await page.getByRole("button", { name }).boundingBox();
  expect(box?.height).toBeGreaterThanOrEqual(44);
}

test("default card: wordmark, copy and exactly one sign-in button (AC-1)", async ({
  page,
}, testInfo) => {
  await page.goto("/login");

  await expect(page.getByText("CFB Model", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
  await expect(page.getByText("Private app · one GitHub account")).toBeVisible();
  await expect(page.getByRole("button", SIGN_IN)).toHaveCount(1);
  await expect(page.getByText(FOOTNOTE)).toBeVisible();
  await expectNoHorizontalScroll(page);
  if (testInfo.project.name === "phone") await expectTouchTarget(page, SIGN_IN.name);
});

test("denied: names the refused GitHub account and offers another (AC-2)", async ({
  page,
}, testInfo) => {
  await page.goto("/login?error=AccessDenied&login=someone-else");

  const alert = deniedAlert(page);
  await expect(alert).toBeVisible();
  await expect(alert).toContainText("You're signed in to GitHub as someone-else.");
  await expect(page.getByRole("button", { name: "Use a different account" })).toBeVisible();
  await expect(page.getByRole("button", SIGN_IN)).toHaveCount(0);
  await expectNoHorizontalScroll(page);
  if (testInfo.project.name === "phone") await expectTouchTarget(page, "Use a different account");
});

test("denied: a login that isn't a GitHub login is not echoed", async ({ page }) => {
  await page.goto("/login?error=AccessDenied&login=%3Cscript%3E");

  const alert = deniedAlert(page);
  await expect(alert).toBeVisible();
  await expect(alert).not.toContainText("signed in to GitHub as");
  await expect(alert).not.toContainText("<script>");
});

test.describe("after sign-in (AC-3)", () => {
  // With cacheComponents, Next has committed a 200 by the time the race settles, so even the
  // fast path redirects in the browser; what matters is that the waking card is never drawn.
  test("database awake: straight to the page asked for, no waking card", async ({
    page,
    context,
    baseURL,
  }) => {
    await context.addCookies([await mintSessionCookie({ baseURL: baseURL! })]);

    const direct = await page.request.get("/login/continue?to=%2Fteams");
    expect(await direct.text()).not.toContain(WAKING);

    await page.goto("/login/continue?to=%2Fteams");
    await expect(page).toHaveURL(/\/teams$/);
    await expect(page.getByRole("heading", { level: 1, name: "Teams" })).toBeVisible();
    await expect(page.getByText(WAKING)).toHaveCount(0);
  });

  test("no target: lands on / (which opens Teams)", async ({ context, baseURL, page }) => {
    await context.addCookies([await mintSessionCookie({ baseURL: baseURL! })]);
    await page.goto("/login/continue");
    await expect(page).toHaveURL(/\/teams$/);
  });

  test("database waking: the card says so, then the page asked for opens", async ({
    page,
    context,
  }) => {
    await context.addCookies([await mintSessionCookie({ baseURL: COLD_PREVIEW_URL })]);

    await page.goto(`${COLD_PREVIEW_URL}/login/continue?to=%2Fteams`, { waitUntil: "commit" });

    const status = page.getByRole("status");
    await expect(status).toContainText(WAKING);
    await expect(status).toContainText(WAKING_NOTE);
    await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();

    await expect(page).toHaveURL(`${COLD_PREVIEW_URL}/teams`, { timeout: 15_000 });
    await expect(page.getByRole("heading", { level: 1, name: "Teams" })).toBeVisible({
      timeout: 15_000,
    });
  });

  // Guard, not AC-3 proof: the gate already covers every new route; this keeps it that way.
  test("guard: /login/continue is behind the gate when signed out", async ({ request, baseURL }) => {
    const direct = await request.get("/login/continue?to=%2Fteams", { maxRedirects: 0 });
    expect(direct.status()).toBe(307);
    expect(new URL(direct.headers()["location"], baseURL).pathname).toBe("/login");
  });
});

test.describe("waking spinner (AC-5)", () => {
  async function spinnerAnimation(page: Page): Promise<string> {
    await page.goto(`${COLD_PREVIEW_URL}/login/continue?to=%2Fteams`, { waitUntil: "commit" });
    const spinner = page.getByRole("status").locator("svg");
    await expect(spinner).toBeVisible();
    return spinner.evaluate((el) => getComputedStyle(el).animationName);
  }

  test.beforeEach(async ({ context }) => {
    await context.addCookies([await mintSessionCookie({ baseURL: COLD_PREVIEW_URL })]);
  });

  test("spins when motion is allowed", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    expect(await spinnerAnimation(page)).not.toBe("none");
  });

  test("stops under prefers-reduced-motion", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(await spinnerAnimation(page)).toBe("none");
  });
});

test("preview: no GitHub client, so no button, and a 200 (AC-4)", async ({ page, request }) => {
  const direct = await request.get(`${COLD_PREVIEW_URL}/login`);
  expect(direct.status()).toBe(200);

  await page.goto(`${COLD_PREVIEW_URL}/login`);
  await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
  await expect(page.getByText("Sign-in isn't available on preview deployments.")).toBeVisible();
  await expect(page.getByRole("button", SIGN_IN)).toHaveCount(0);
  await expect(page.getByText(FOOTNOTE)).toHaveCount(0);
  await expectNoHorizontalScroll(page);
});
