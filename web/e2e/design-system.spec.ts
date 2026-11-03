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

test("the page does not scroll sideways", async ({ page }) => {
  await page.goto("/design-system");
  await expect(page.getByRole("heading", { level: 1, name: "Design system" })).toBeVisible();
  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
});
