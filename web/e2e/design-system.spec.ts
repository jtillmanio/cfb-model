import { expect, test } from "./fixtures";

// The design-system specimen page (D-152): every drawn state of the badges and chips, in a dark
// and a light panel, at phone and desktop width. Runs in both projects (390 and 1440).

for (const theme of ["Dark", "Light"]) {
  test(`${theme} panel shows every badge and chip state`, async ({ page }) => {
    await page.goto("/design-system");
    const panel = page.getByRole("region", { name: theme });

    // Edge pill: pick (filled), below threshold (plain), exactly the threshold, locked.
    await expect(panel.getByText("+3.7 OSU", { exact: true })).toBeVisible();
    await expect(panel.getByText("+0.6 UTAH", { exact: true })).toBeVisible();
    await expect(panel.getByText("+2.5 OSU", { exact: true })).toBeVisible();
    await expect(panel.getByText("+0.9 UNLV", { exact: true })).toBeVisible();
    // No line draws a dash in the edge pill and the tier badge.
    await expect(panel.getByText("—", { exact: true })).toHaveCount(2);

    // Tier badge: letters, and the labelled variant.
    for (const letter of ["A", "B", "C"]) {
      await expect(panel.getByText(letter, { exact: true }).first()).toBeVisible();
    }
    await expect(panel.getByText("Tier A", { exact: true })).toBeVisible();

    // Result marker: glyphs shown, labels for screen readers present.
    for (const glyph of ["✓", "✗"]) {
      await expect(panel.getByText(glyph, { exact: true }).first()).toBeVisible();
    }
    for (const label of ["Covered", "Not covered", "Push", "Pending"]) {
      await expect(panel.getByText(label, { exact: true }).first()).toBeAttached();
    }

    // Filter chips: one selected; a click selects another, a second click clears it.
    const chips = panel.getByRole("group", { name: `${theme.toLowerCase()} filters` });
    await expect(chips.getByRole("button", { name: "Picks only" })).toHaveAttribute("aria-pressed", "true");
    const ranked = chips.getByRole("button", { name: "Ranked" });
    await expect(ranked).toHaveAttribute("aria-pressed", "false");
    await ranked.click();
    await expect(ranked).toHaveAttribute("aria-pressed", "true");
    await ranked.click();
    await expect(ranked).toHaveAttribute("aria-pressed", "false");
  });
}

// TASK-051: the team chip, market cell and data table (AC-5), in each panel at each width.
for (const theme of ["Dark", "Light"]) {
  test(`${theme} panel shows every team chip, market cell and table state`, async ({ page }) => {
    await page.goto("/design-system");
    const panel = page.getByRole("region", { name: theme });
    const group = (title: string) =>
      panel.locator("section", { has: page.getByRole("heading", { level: 3, name: title, exact: true }) });

    // Team chip: a logo from the app's own origin, at most 20px; a colour dot; rank, FCS, N, locked.
    const chips = group("Team chip");
    const logo = chips.locator("img");
    await expect(logo).toHaveCount(1);
    await expect(logo).toBeVisible();
    expect(await logo.getAttribute("src")).toMatch(/^\/_next\/image\?/);
    const box = (await logo.boundingBox())!;
    expect(box.width).toBeLessThanOrEqual(20);
    expect(box.height).toBeLessThanOrEqual(20);
    await expect(chips.locator("[data-slot=team-dot]").first()).toBeVisible();
    await expect(chips.getByText("Ohio State", { exact: true })).toBeVisible();
    await expect(chips.getByText("FCS", { exact: true })).toBeVisible();
    await expect(chips.getByText("N", { exact: true })).toBeVisible();
    await expect(chips.getByText("UNLV", { exact: true })).toBeVisible();

    // Market cell: opener + sparkline before the current line; flat when unchanged; No line.
    const market = group("Market cell");
    await expect(market.getByText("−28", { exact: true })).toBeVisible();
    await expect(market.getByText("OSU −27.5", { exact: true })).toBeVisible();
    const moved = market.locator("figure").filter({ hasText: "OSU −27.5" }).locator("polyline");
    expect((await moved.getAttribute("points"))!.trim().split(/\s+/)).toHaveLength(2);
    const flat = market.locator("figure").filter({ hasText: "MICH −9" }).locator("polyline");
    const ys = (await flat.getAttribute("points"))!.trim().split(/\s+/).map((p) => p.split(",")[1]);
    expect(new Set(ys).size).toBe(1);
    const noLine = market.locator("figure").last();
    await expect(noLine.locator("span", { hasText: "No line" })).toBeVisible();
    await expect(noLine.locator("svg")).toHaveCount(0);

    // Data table: comfortable 40/48, compact 32/36, measured in the browser.
    const heights = async (name: string) => {
      const table = panel.getByRole("table", { name });
      const header = (await table.getByRole("columnheader").first().boundingBox())!.height;
      const row = (await table.getByRole("row").nth(1).boundingBox())!.height;
      return { header: Math.round(header), row: Math.round(row) };
    };
    expect(await heights(`${theme.toLowerCase()} comfortable table`)).toEqual({ header: 40, row: 48 });
    expect(await heights(`${theme.toLowerCase()} compact table`)).toEqual({ header: 32, row: 36 });
    // The header sticks under the 56px app bar.
    const thead = panel.getByRole("table", { name: `${theme.toLowerCase()} comfortable table` }).locator("thead");
    await expect(thead).toHaveCSS("position", "sticky");
    await expect(thead).toHaveCSS("top", "56px");

    // Sorting: a click, then the keyboard, flips aria-sort and the row order.
    const table = panel.getByRole("table", { name: `${theme.toLowerCase()} compact table` });
    const rating = table.getByRole("columnheader", { name: /Rating/ });
    await expect(rating).toHaveAttribute("aria-sort", "none");
    await rating.getByRole("button").click();
    await expect(rating).toHaveAttribute("aria-sort", "ascending");
    await expect(table.getByRole("row").nth(1)).toContainText("OU");
    await rating.getByRole("button").press("Enter");
    await expect(rating).toHaveAttribute("aria-sort", "descending");
    await expect(table.getByRole("row").nth(1)).toContainText("OSU");
    await rating.getByRole("button").press(" ");
    await expect(rating).toHaveAttribute("aria-sort", "ascending");
  });
}

test("the page requests nothing from a host other than the app's own", async ({ page, baseURL }) => {
  const elsewhere: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (/^https?:$/.test(url.protocol) && url.origin !== new URL(baseURL!).origin) elsewhere.push(url.href);
  });
  await page.goto("/design-system");
  // The Ohio State logo loads through /_next/image, which fetches CFBD's CDN on the server.
  await expect(page.getByRole("region", { name: "Dark" }).locator("img")).toBeVisible();
  await page.waitForLoadState("networkidle");
  expect(elsewhere).toEqual([]);
});

test("the page does not scroll sideways", async ({ page }) => {
  await page.goto("/design-system");
  await expect(page.getByRole("heading", { level: 1, name: "Design system" })).toBeVisible();
  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
});
