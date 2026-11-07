import type { Locator, Page } from "@playwright/test";

import { expect, test } from "./fixtures";
import { COLD_PREVIEW_URL, SWITCH_API_URL, SWITCH_WEB_URL } from "./test-env";

// This Week (S-01, TASK-056) on the seeded fixture at the slate's time (Sat 2026-10-10 2:15 PM ET,
// playwright.config.ts): 54 games and 9 picks in Week 6. The page lays each game out by width, so
// elements a width hides stay in the document: every check below reads visible elements only.

const ROW = "a[data-slot=game-row]";

async function openSlate(page: Page, url = "/") {
  await page.goto(url);
  await expect(page.getByRole("heading", { level: 1, name: "This Week" })).toBeVisible();
  await expect(page.locator(ROW).first()).toBeVisible();
}

/** The one game between two schools (exact names: "Texas" is also in "Texas A&M"). */
function game(page: Page, away: string, home: string): Locator {
  const team = (name: string) => page.getByText(name, { exact: true });
  return page.locator(ROW).filter({ has: team(away) }).filter({ has: team(home) });
}

const visible = (locator: Locator) => locator.filter({ visible: true });

// A width hides the other layouts' elements with display: none, which textContent still reads.
const INNER = { useInnerText: true } as const;

async function noSideScroll(page: Page) {
  const widths = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.client);
}

async function xOf(locator: Locator): Promise<number> {
  const box = await locator.boundingBox();
  expect(box, "the element has a box").not.toBeNull();
  return box!.x;
}

test("AC-1: the header, the window headings in order, and a link to each game", async ({ page }) => {
  await openSlate(page);

  await expect(page.getByText("2026 · Week 6 · 54 games · 9 picks")).toBeVisible();

  // The design's four windows, in order; the fixture week also has Thursday's Tulane @ Memphis.
  const headings = page.getByRole("heading", { level: 2 });
  await expect(headings).toContainText([
    "THU NIGHT",
    "FRI NIGHT",
    "SAT NOON",
    "SAT AFTERNOON",
    "SAT NIGHT",
  ]);
  await expect(headings.nth(1)).toContainText("Fri 10/9 · 8:00 PM ET");
  await expect(headings.nth(2)).toContainText("Sat 10/10 · 12:00 PM ET");
  await expect(headings.nth(3)).toContainText("3:30");
  await expect(headings.nth(4)).toContainText("7:00 – 10:30 PM ET");

  const rows = page.locator(ROW);
  await expect(rows).toHaveCount(54);
  const hrefs = await rows.evaluateAll((links) => links.map((a) => a.getAttribute("href")));
  expect(hrefs.every((href) => /^\/games\/\d+$/.test(href ?? ""))).toBe(true);
  expect(new Set(hrefs).size).toBe(54);
  // Each row links to its own game (the fixture's ids: UNLV @ Boise State is 1, Purdue @ Ohio State 2).
  await expect(game(page, "UNLV", "Boise State")).toHaveAttribute("href", "/games/1");
  await expect(game(page, "Purdue", "Ohio State")).toHaveAttribute("href", "/games/2");
  // The window headings sit between the rows they group: Purdue @ Ohio State is under SAT NOON.
  const noon = page.locator("section").filter({ has: page.getByRole("heading", { name: /SAT NOON/ }) });
  await expect(noon.locator(ROW).filter({ hasText: "Purdue" })).toHaveCount(1);
  await expect(page.getByText("Showing 54 of 54 games")).toBeVisible();
});

test.describe("desktop table (AC-2, AC-3, AC-4, AC-5)", () => {
  test.skip(({ viewport }) => (viewport?.width ?? 0) < 1440, "the full grid starts at 1440");

  test("AC-2: Purdue @ Ohio State reads market, model, edge, cover, tier, win % left to right", async ({
    page,
  }) => {
    await openSlate(page);
    const row = game(page, "Purdue", "Ohio State");
    const market = visible(row.locator("[data-cell=market]"));
    const model = row.locator("[data-cell=model]");
    const edge = row.locator("[data-cell=edge]");
    const cover = row.locator("[data-cell=cover]");
    const tier = row.getByText("B", { exact: true }).filter({ visible: true });
    const win = row.locator("[data-cell=win]");

    await expect(market).toContainText("OSU −27.5", INNER);
    await expect(model).toHaveText("OSU −31.2", INNER);
    await expect(edge.locator("[data-variant=edge]")).toHaveText("+3.7 OSU");
    await expect(cover).toContainText("61%", INNER);
    await expect(tier).toHaveCount(1);
    await expect(win).toHaveText("OSU 99%", INNER);

    const xs = [market, model, edge, cover, tier, win];
    const positions = [];
    for (const cell of xs) positions.push(await xOf(cell));
    expect(positions).toEqual([...positions].sort((a, b) => a - b));

    // Kansas State @ Utah: the edge is plain muted text, and there is no tier.
    const utah = game(page, "Kansas State", "Utah");
    const quiet = utah.locator("[data-cell=edge] [data-variant]");
    await expect(quiet).toHaveText("+0.6 UTAH");
    await expect(quiet).toHaveAttribute("data-variant", "quiet");
    await expect(utah.getByText(/^[ABC]$/)).toHaveCount(0);

    // The legend prints the response's thresholds.
    await expect(page.locator("[data-slot=slate-legend]")).toHaveText(
      "Edge pill = clears 2.5 pts · Tier A ≥ 5.0 · B ≥ 3.5 · C ≥ 2.5 · Market = opening line, its moves, then now",
    );
  });

  test("AC-3: final, live, no-line, neutral and moved-pick rows", async ({ page }) => {
    await openSlate(page);

    const unlv = game(page, "UNLV", "Boise State");
    await expect(unlv.locator("[data-cell=status]")).toHaveText("Final");
    await expect(unlv.locator("[data-team=away] [data-cell=score]")).toHaveText("24");
    await expect(unlv.locator("[data-team=home] [data-cell=score]")).toHaveText("31");
    await expect(unlv.locator("[data-cell=notes]")).toHaveText("No pick · UNLV covered", INNER);

    const purdue = game(page, "Purdue", "Ohio State");
    await expect(purdue.locator("[data-cell=status]")).toHaveText("Live");
    await expect(purdue.locator("[data-slot=live-dot]")).toBeVisible();
    await expect(purdue.locator("[data-team=away] [data-cell=score]")).toHaveText("3");
    await expect(purdue.locator("[data-team=home] [data-cell=score]")).toHaveText("24");
    await expect(purdue.locator("[data-cell=notes]")).toHaveText("OSU −27.5 · not yet, needs 28+", INNER);

    const furman = game(page, "Furman", "Clemson");
    await expect(visible(furman.locator("[data-cell=market]"))).toHaveText("No line", INNER);
    await expect(furman.locator("[data-cell=notes]")).toHaveText("FCS · no lines yet", INNER);
    await expect(furman.getByText("FCS", { exact: true })).toBeVisible();

    const neutral = game(page, "Texas", "Oklahoma");
    await expect(neutral.getByText("N · Dallas")).toBeVisible();

    const miss = game(page, "Ole Miss", "LSU");
    await expect(miss.locator("[data-cell=notes] > span")).toHaveText([
      "Picked at −2.5 → now −3.5",
      "CLV −1.0",
    ]);
  });

  test("AC-4: the opener and sparkline come muted before the current line", async ({ page }) => {
    await openSlate(page);

    const purdue = visible(game(page, "Purdue", "Ohio State").locator("[data-cell=market]"));
    const opener = visible(purdue.locator("[data-slot=line-history]"));
    await expect(opener).toHaveText("−28", INNER);
    await expect(opener).toHaveClass(/text-muted-foreground/);
    expect(await xOf(opener)).toBeLessThan(await xOf(visible(purdue.getByText("OSU −27.5"))));

    const points = async (cell: Locator) =>
      // A flat line is a zero-height polyline, which Playwright calls invisible: find its svg.
      (await visible(cell.locator("svg")).locator("polyline").getAttribute("points"))!.trim().split(/\s+/);
    // Texas vs Oklahoma's line was pulled five times: one point per snapshot.
    const texas = visible(game(page, "Texas", "Oklahoma").locator("[data-cell=market]"));
    expect(await points(texas)).toHaveLength(5);
    // Michigan @ Northwestern never moved: a flat line, every point at one height.
    const michigan = visible(game(page, "Michigan", "Northwestern").locator("[data-cell=market]"));
    const heights = (await points(michigan)).map((p) => p.split(",")[1]);
    expect(heights.length).toBeGreaterThanOrEqual(2);
    expect(new Set(heights).size).toBe(1);
    // Furman @ Clemson has no line, so no opener.
    await expect(visible(game(page, "Furman", "Clemson").locator("[data-slot=line-history]"))).toHaveCount(0);
  });

  test("AC-5: a compact table: header 32px, rows 44px", async ({ page }) => {
    await openSlate(page);
    const header = (await page.locator("[data-slot=slate-header]").boundingBox())!;
    expect(header.height).toBe(32);
    for (const row of await page.locator(ROW).all()) {
      expect((await row.boundingBox())!.height).toBe(44);
    }
    await noSideScroll(page);
  });
});

test.describe("tablet table (AC-5)", () => {
  test.use({ viewport: { width: 768, height: 1024 } });
  test("the priority columns show and Win % and Pick · result drop", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "the viewport is set here; one project is enough");
    await openSlate(page);

    const header = page.locator("[data-slot=slate-header]");
    await expect(header).toBeVisible();
    await expect(header).toHaveText(/^Kickoff ET\s+Matchup\s+Market\s+Model\s+Edge\s+Cover\s+Tier$/, INNER);

    const row = game(page, "Purdue", "Ohio State");
    await expect(row.locator("[data-cell=win]")).toBeHidden();
    await expect(row.locator("[data-cell=notes]")).toBeHidden();
    await expect(visible(row.locator("[data-cell=market]"))).toContainText("opened −28", INNER);
    await expect(row.locator("[data-cell=model]")).toHaveText("OSU −31.2", INNER);
    await expect(row.locator("[data-cell=edge] [data-variant]")).toHaveText("+3.7 OSU");
    await expect(row.locator("[data-cell=cover]")).toContainText("61%", INNER);
    expect((await page.locator("[data-slot=slate-header]").boundingBox())!.height).toBe(36);
    expect((await row.boundingBox())!.height).toBeGreaterThanOrEqual(56);
    await noSideScroll(page);
  });
});

test.describe("tablet layout up to 1439 (AC-5)", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  // 1280 is the md-to-wide boundary the named breakpoint exists for: still the tablet board's
  // columns (header 36px, no Win %), not the 1440 grid.
  test("1280 still has the tablet columns", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "the viewport is set here; one project is enough");
    await openSlate(page);

    await expect(page.locator("[data-slot=slate-header]")).toHaveText(
      /^Kickoff ET\s+Matchup\s+Market\s+Model\s+Edge\s+Cover\s+Tier$/,
      INNER,
    );
    expect((await page.locator("[data-slot=slate-header]").boundingBox())!.height).toBe(36);
    const row = game(page, "Purdue", "Ohio State");
    await expect(row.locator("[data-cell=win]")).toBeHidden();
    expect((await row.boundingBox())!.height).toBeGreaterThanOrEqual(56);
    await noSideScroll(page);
  });
});

test.describe("phone cards (AC-5)", () => {
  test.skip(({ viewport }) => (viewport?.width ?? 0) >= 768, "cards are below 768");

  test("each game is a card with Market, Model and Edge showing, no sideways scroll, 44px targets", async ({
    page,
  }) => {
    await openSlate(page);
    await expect(page.locator("[data-slot=slate-header]")).toBeHidden();

    const card = game(page, "Purdue", "Ohio State");
    await expect(card.getByText("MARKET", { exact: true })).toBeVisible();
    await expect(card.getByText("MODEL", { exact: true })).toBeVisible();
    await expect(card.getByText("EDGE", { exact: true })).toBeVisible();
    await expect(visible(card.locator("[data-cell=market]"))).toContainText("OSU −27.5", INNER);
    await expect(visible(card.locator("[data-cell=market]"))).toContainText("opened −28", INNER);
    await expect(card.locator("[data-cell=model]")).toHaveText("OSU −31.2", INNER);
    await expect(card.locator("[data-cell=edge]")).toContainText("+3.7 OSU", INNER);
    await expect(card.locator("[data-cell=cover]")).toContainText("Cover 61%", INNER);
    await expect(card.locator("[data-cell=win]")).toHaveText("OSU 99%", INNER);
    await expect(card.locator("[data-cell=notes]")).toHaveText("OSU −27.5 · not yet, needs 28+", INNER);
    await expect(game(page, "Texas", "Oklahoma")).toContainText("Neutral · Dallas");

    await noSideScroll(page);
    for (const target of await page.locator("main a:visible, main button:visible").all()) {
      const box = await target.boundingBox();
      expect(box!.height, await target.innerText()).toBeGreaterThanOrEqual(44);
    }
  });
});

const STRIP = "[data-slot=record-strip]";

// TASK-057 on the same fixture: 9 picks = Thursday's win, Iowa covering and Ohio State not yet
// (both live), and 6 to play.
test.describe("record strip and Picks only (TASK-057)", () => {
  test("AC-1, AC-2: the strip reads 1-0 · 2 live · 6 to play · +1.0u, with one segment per pick", async ({
    page,
    viewport,
  }) => {
    await openSlate(page);
    const strip = page.locator(STRIP);
    await expect(strip).toHaveAttribute(
      "aria-label",
      /^This week 1-0, 2 live \(IOWA covering, OSU not yet\), 6 to play, \+1\.0u\./,
    );
    await expect(strip.locator("[data-slot=strip-record]")).toHaveText("1-0");
    await expect(strip).toContainText("2 live", INNER);
    await expect(strip).toContainText("6", INNER);
    await expect(strip).toContainText("+1.0u", INNER);
    // The live note: beside the stats at 1440, under them on a phone, and absent at 768.
    const width = viewport?.width ?? 0;
    if (width >= 1440) await expect(strip).toContainText("(IOWA covering, OSU not yet)", INNER);
    else if (width < 768) await expect(strip).toContainText("IOWA covering, OSU not yet", INNER);
    else await expect(strip).not.toContainText("IOWA covering", INNER);

    const segments = visible(strip.locator("[data-slot=strip-segments] > span"));
    await expect(segments).toHaveCount(9);
    const states = await segments.evaluateAll((els) => els.map((el) => el.getAttribute("data-state")));
    expect(states).toEqual(["won", "covering", "not_yet", ...Array(6).fill("to_play")]);
    // The fixture's OSU pick is live and behind its line: "not yet", never lost.
    await expect(segments.nth(2)).toHaveAttribute("title", /Live · not covering yet · OSU/);
    await noSideScroll(page);
  });

  test("AC-3: the strip and the chip each show only the 9 picks, then all 54", async ({ page }) => {
    await openSlate(page);
    const strip = page.locator(STRIP);
    const chip = page.getByRole("button", { name: /^Picks/ });
    await expect(visible(page.locator(ROW))).toHaveCount(54);
    await expect(page.getByText("Showing 54 of 54 games")).toBeVisible();
    await expect(chip).toHaveAttribute("aria-pressed", "false");

    await strip.click();
    await expect(visible(page.locator(ROW))).toHaveCount(9);
    await expect(page.getByText("9 games with a pick · of 54")).toBeVisible();
    await expect(chip).toHaveAttribute("aria-pressed", "true");
    await expect(strip).toHaveAttribute("aria-pressed", "true");
    // A window with no pick drops its heading too.
    expect(await visible(page.getByRole("heading", { level: 2 })).count()).toBeLessThan(5);

    await strip.click();
    await expect(visible(page.locator(ROW))).toHaveCount(54);
    await expect(page.getByText("Showing 54 of 54 games")).toBeVisible();

    await chip.click();
    await expect(visible(page.locator(ROW))).toHaveCount(9);
    await expect(chip).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "All", exact: true }).click();
    await expect(visible(page.locator(ROW))).toHaveCount(54);
    await expect(chip).toHaveAttribute("aria-pressed", "false");
    await noSideScroll(page);
  });
});

test.describe("loading and error (AC-6)", () => {
  test("the skeleton is drawn at the loaded size and the pulse stops under reduced motion", async ({
    page,
    viewport,
  }) => {
    // The cold preview's API answers 3 s late (cold-api.mjs), so loading.tsx stays on screen.
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(`${COLD_PREVIEW_URL}/`, { waitUntil: "commit" });

    const skeleton = page.getByRole("status", { name: "Loading this week's games" });
    await expect(skeleton).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("heading", { level: 1, name: "This Week" })).toBeVisible();
    const rows = skeleton.locator("[data-slot=skeleton-row]");
    expect(await rows.count()).toBeGreaterThanOrEqual(6);
    if ((viewport?.width ?? 0) >= 1440) {
      await expect(page.locator("[data-slot=slate-header]")).toHaveCSS("height", "32px");
      for (const row of await rows.all()) expect((await row.boundingBox())!.height).toBe(44);
    }
    // Reduced motion: no bar animates.
    const bar = skeleton.locator(".animate-pulse").first();
    await expect(bar).toHaveCSS("animation-name", "none");

    await expect(page.locator(ROW).first()).toBeVisible({ timeout: 15_000 });
    await expect(skeleton).toHaveCount(0);
  });

  test("AC-6: the skeleton's strip is as tall as the loaded strip, and the chips are already there", async ({
    page,
  }) => {
    await page.goto(`${COLD_PREVIEW_URL}/`, { waitUntil: "commit" });
    const bar = page.locator("[data-slot=skeleton-strip]");
    await expect(bar).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("group", { name: "Filter games" })).toBeVisible();
    // The strip's bars stop pulsing under reduced motion, like the rows'.
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect(bar.locator(".animate-pulse").first()).toHaveCSS("animation-name", "none");
    const drawn = (await bar.boundingBox())!.height;
    await expect(page.locator(ROW).first()).toBeVisible({ timeout: 15_000 });
    const loaded = (await page.locator(STRIP).boundingBox())!.height;
    expect(Math.abs(loaded - drawn)).toBeLessThanOrEqual(1);
  });

  test("a loaded phone card is as tall as its skeleton card", async ({ page, viewport }) => {
    test.skip((viewport?.width ?? 0) >= 768, "cards are below 768");
    await page.goto(`${COLD_PREVIEW_URL}/`, { waitUntil: "commit" });
    const skeleton = page.getByRole("status", { name: "Loading this week's games" });
    await expect(skeleton).toBeVisible({ timeout: 10_000 });
    const drawn = (await skeleton.locator("[data-slot=skeleton-row]").first().boundingBox())!.height;
    await expect(page.locator(ROW).first()).toBeVisible({ timeout: 15_000 });
    // A card with no note under it: the common case.
    const loaded = (await game(page, "Michigan", "Northwestern").boundingBox())!.height;
    expect(Math.abs(loaded - drawn)).toBeLessThanOrEqual(12);
  });
});

// One switch server for every test below, so they run one at a time in the desktop project only.
test.describe("API switched off and on (AC-6)", () => {
  test.describe.configure({ mode: "serial" });
  test.skip(({ viewport }) => (viewport?.width ?? 0) < 1280, "one switch server: desktop only");

  async function control(request: import("@playwright/test").APIRequestContext, action: "up" | "down") {
    expect((await request.post(`${SWITCH_API_URL}/__e2e/${action}`)).ok()).toBe(true);
  }

  async function apiCalls(request: import("@playwright/test").APIRequestContext): Promise<number> {
    return ((await (await request.get(`${SWITCH_API_URL}/__e2e/count`)).json()) as { count: number }).count;
  }

  test.afterEach(async ({ request }) => {
    await control(request, "up");
  });

  test("a page load makes exactly one server-side API call", async ({ page, request }) => {
    const before = await apiCalls(request);
    await openSlate(page, `${SWITCH_WEB_URL}/`);
    await page.waitForLoadState("networkidle");
    expect((await apiCalls(request)) - before).toBe(1);
  });

  test("with the API stopped it shows API unreachable and no games, and Retry loads them", async ({
    page,
    request,
  }) => {
    await control(request, "down");
    await page.goto(`${SWITCH_WEB_URL}/`);

    const alert = page.getByRole("alert").filter({ hasText: "Couldn't reach the server" });
    await expect(alert).toBeVisible();
    // D-096: no saved copies, so no games and no saved-copy sentence.
    await expect(page.locator(ROW)).toHaveCount(0);
    await expect(page.getByText(/saved copy/i)).toHaveCount(0);
    await expect(page.getByRole("banner")).toContainText("Can't reach the server");

    await control(request, "up");
    await alert.getByRole("button", { name: "Retry" }).click();
    await expect(page.locator(ROW).first()).toBeVisible();
    await expect(alert).toHaveCount(0);
  });
});
