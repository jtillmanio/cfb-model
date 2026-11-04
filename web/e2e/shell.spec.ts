import type { APIRequestContext, Page } from "@playwright/test";

import { expect, test } from "./fixtures";
import { COLD_PREVIEW_URL, SWITCH_API_URL, SWITCH_WEB_URL } from "./test-env";

// S-16 app shell and global states (TASK-054), on the seeded fixture at the slate's time (Sat
// 2:15 PM ET, playwright.config.ts): the shell block says 2026 week 6, v1.0's live 32-24-1, the
// Sat 9:00 AM ET pull (not stale) and 9 picks (TASK-053, D-156).

// Waits for the data, so nothing is measured on loading.tsx's shell, which the loaded one then
// replaces (its elements detach mid-test).
async function openTeams(page: Page, url = "/teams") {
  await page.goto(url);
  await expect(page.getByRole("row").filter({ hasText: "Ohio State" })).toBeVisible();
}

async function noSideScroll(page: Page) {
  const widths = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.client);
}

test.describe("desktop shell (AC-1)", () => {
  test.skip(({ viewport }) => (viewport?.width ?? 0) < 1280, "the sidebar is drawn at 1280+");

  test("the sidebar, track-record card and top bar show the fixture's shell", async ({ page }) => {
    await openTeams(page);

    const sidebar = page.getByRole("complementary", { name: "Sidebar" });
    await expect(sidebar).toBeVisible();
    expect((await sidebar.boundingBox())?.width).toBe(224);

    const nav = sidebar.getByRole("navigation", { name: "Main" });
    await expect(nav.getByRole("link")).toHaveText([
      "This Week",
      /^Picks\s*9$/,
      "Contest",
      "Rankings",
      "Teams",
      "Performance",
      "Lab",
    ]);
    // Each item has its 16px lucide icon.
    await expect(nav.locator("a svg")).toHaveCount(7);
    await expect(nav.getByRole("link", { name: "Teams" })).toHaveAttribute("aria-current", "page");
    await expect(nav.locator('[aria-current="page"]')).toHaveCount(1);

    const card = sidebar.getByRole("link", { name: /Track record/ });
    await expect(card).toHaveAttribute("href", "/performance");
    await expect(card).toContainText("Model · 2026 live");
    await expect(card).toContainText("32-24-1");
    await expect(card).toContainText(/\d+\.\d%/);
    await expect(card).toContainText(/[+−]\d+\.\du/);
    await expect(card).toContainText(/CLV [+−]?\d+\.\d/);

    const topBar = page.getByRole("banner");
    await expect(topBar).toContainText("2026 · Week 6");
    await expect(topBar).toContainText("Updated Sat 9:00 AM ET");

    // The fixture's lines are fresh: no stale banner (AC-5).
    await expect(page.getByText(/Lines last updated/)).toHaveCount(0);
    await noSideScroll(page);
  });

  test("at 768 the top-bar nav replaces the sidebar (AC-2)", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await openTeams(page);

    await expect(page.getByRole("complementary", { name: "Sidebar" })).toBeHidden();
    await expect(page.getByRole("navigation", { name: "Tabs" })).toBeHidden();
    const sections = page.getByRole("navigation", { name: "Sections" });
    await expect(sections.getByRole("link")).toHaveText([
      "This Week",
      /^Picks/,
      "Contest",
      "Rankings",
    ]);
    // Teams lives under More, so More is the lit item.
    const more = sections.getByRole("button", { name: "More" });
    await expect(more).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("banner")).toContainText("Updated Sat 9:00 AM ET");
    await noSideScroll(page);
  });
});

test.describe("phone shell (AC-2)", () => {
  test.skip(({ viewport }) => (viewport?.width ?? 0) >= 768, "the tab bar is drawn below 768");

  test("the tab bar has five 44px tabs and More opens the rest", async ({ page }) => {
    await openTeams(page);

    const tabs = page.getByRole("navigation", { name: "Tabs" });
    await expect(tabs).toBeVisible();
    await expect(page.getByRole("complementary", { name: "Sidebar" })).toBeHidden();
    const items = tabs.locator("a, button");
    await expect(items).toHaveText(["This Week", /^Picks/, "Contest", "Rankings", "More"]);
    for (const item of await items.all()) {
      const box = await item.boundingBox();
      expect(box, await item.innerText()).not.toBeNull();
      expect(box!.height).toBeGreaterThanOrEqual(44);
    }
    await expect(page.getByRole("banner")).toContainText("2026 · Week 6");

    const sheet = page.getByRole("dialog", { name: "More" });
    await expect(sheet).toBeHidden();
    await tabs.getByRole("button", { name: "More" }).click();
    await expect(sheet).toBeVisible();
    for (const [name, href] of [
      ["Teams", "/teams"],
      ["Performance", "/performance"],
      ["Lab", "/lab"],
      ["Settings", "/settings"],
    ]) {
      await expect(sheet.getByRole("link", { name: new RegExp(`^${name}`) })).toHaveAttribute(
        "href",
        href,
      );
    }
    await expect(sheet).toContainText("Track record · 32-24-1");
    await noSideScroll(page);
  });
});

test.describe("waking database (AC-4)", () => {
  test("the note shows after 1.5 s, then the page loads", async ({ page }) => {
    // The cold preview's API answers 3 s late (cold-api.mjs), as a database waking from idle.
    const started = Date.now();
    await page.goto(`${COLD_PREVIEW_URL}/teams`, { waitUntil: "commit" });

    const note = page.getByRole("status").filter({ hasText: "Waking up the database…" });
    await expect(note).toBeVisible({ timeout: 10_000 });
    expect(Date.now() - started).toBeGreaterThanOrEqual(1500);

    await expect(page.getByRole("row").filter({ hasText: "Ohio State" })).toBeVisible({
      timeout: 15_000,
    });
    await expect(note).toHaveCount(0);
    await expect(page.getByText("Couldn't reach the server")).toHaveCount(0);
  });
});

// One switch server for every test below, so they run one at a time in the desktop project only.
test.describe("API switched off and on (AC-3, AC-6)", () => {
  test.describe.configure({ mode: "serial" });
  test.skip(({ viewport }) => (viewport?.width ?? 0) < 1280, "one switch server: desktop only");

  async function control(request: APIRequestContext, action: "up" | "down") {
    expect((await request.post(`${SWITCH_API_URL}/__e2e/${action}`)).ok()).toBe(true);
  }

  async function apiCalls(request: APIRequestContext): Promise<number> {
    return ((await (await request.get(`${SWITCH_API_URL}/__e2e/count`)).json()) as { count: number })
      .count;
  }

  test.afterEach(async ({ request }) => {
    await control(request, "up");
  });

  test("a page load makes exactly one server-side API call", async ({ page, request }) => {
    const before = await apiCalls(request);
    await page.goto(`${SWITCH_WEB_URL}/teams`);
    await expect(page.getByRole("row").filter({ hasText: "Ohio State" })).toBeVisible();
    await page.waitForLoadState("networkidle");
    expect((await apiCalls(request)) - before).toBe(1);

    const again = await apiCalls(request);
    await page.reload();
    await expect(page.getByRole("row").filter({ hasText: "Ohio State" })).toBeVisible();
    await page.waitForLoadState("networkidle");
    expect((await apiCalls(request)) - again).toBe(1);
  });

  test("with the API stopped Teams shows API unreachable, and Retry loads it", async ({
    page,
    request,
  }) => {
    await control(request, "down");
    await page.goto(`${SWITCH_WEB_URL}/teams`);

    // Next's route announcer is an empty role="alert" too.
    const alert = page.getByRole("alert").filter({ hasText: "Couldn't reach the server" });
    await expect(alert).toBeVisible();
    await expect(alert).toContainText("The API didn't answer");
    // D-096: no saved copies, so no saved-copy sentence.
    await expect(page.getByText(/saved copy/i)).toHaveCount(0);
    await expect(page.getByRole("banner")).toContainText("Can't reach the server");
    const retry = alert.getByRole("button", { name: "Retry" });
    await expect(retry).toBeVisible();

    await control(request, "up");
    await retry.click();
    await expect(page.getByRole("row").filter({ hasText: "Ohio State" })).toBeVisible();
    await expect(alert).toHaveCount(0);
    await expect(page.getByRole("banner")).toContainText("Updated Sat 9:00 AM ET");
  });
});
