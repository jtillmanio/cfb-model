import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";

import type { Locator, Page } from "@playwright/test";

import { expect, test } from "./fixtures";
import { CONTEST_WEB_URL } from "./test-env";

// Contest (S-02, TASK-072): journey 3 (docs/02 › End-to-end journeys) at Thu 2026-10-08 10:00 PM ET,
// on the contest servers (playwright.config.ts). Each test starts from the seeded state: `engine
// seed paste-journey` gives this Playwright project a fresh contest with no lines, whose platform
// has every fixture `splash` alias but "Hou Texans" and "Jax" (D-175), so a second run, a retry, or
// the other project running at the same time never finds the week confirmed or the names mapped.

test.use({ baseURL: CONTEST_WEB_URL });

const WEEK6 = readFileSync(path.join(__dirname, "../../python/engine/tests/fixtures/splash_week6.txt"), "utf8");

// Texas vs Oklahoma moved half a point: TEX −7 → TEX −6.5.
const MOVED = WEEK6.replace("Texas\n5-0\n-7\n", "Texas\n5-0\n-6.5\n").replace("Oklahoma\n4-1\n+7\n", "Oklahoma\n4-1\n+6.5\n");

// C2b: three games in Splash's layout between teams the contest's sports don't have.
function block(away: string, home: string, time: string, awayLine: string, homeLine: string): string {
  return [away, home, "Preview", time, "", away, "3-2", awayLine, "", home, "4-1", homeLine, "", "Over 220.5", "", "Under 220.5"].join(
    "\n",
  );
}
const NBA = [
  "Pick against the spread",
  "Picks lock:",
  "Sat, Oct 10, 2026, 10:30 PM",
  "Saturday, Oct 10",
  block("Celtics", "Knicks", "Sat 7:30pm", "-4.5", "+4.5"),
  block("Lakers", "Warriors", "Sat 10:00pm", "+2", "-2"),
  block("Nuggets", "Suns", "Sat 10:30pm", "-6", "+6"),
].join("\n");

function freshContest(project: string): number {
  const out = execFileSync(
    "uv",
    ["--directory", "../python", "run", "engine", "seed", "paste-journey", "--project", project],
    { encoding: "utf8" },
  );
  const last = out.trim().split("\n").at(-1) ?? "";
  return (JSON.parse(last) as { contest_id: number }).contest_id;
}

let contestId: number;

test.beforeEach(({}, testInfo) => {
  contestId = freshContest(testInfo.project.name);
});

async function openContest(page: Page) {
  await page.goto(`/contest?contest=${contestId}`);
  await expect(page.getByRole("heading", { level: 1, name: "Contest" })).toBeVisible();
}

const pasteBox = (page: Page) => page.getByRole("textbox", { name: "The contest page's text" });

/** A real paste: the textarea's paste event with the text on its clipboard data. */
async function paste(page: Page, text: string) {
  await pasteBox(page).evaluate((box, value) => {
    const data = new DataTransfer();
    data.setData("text/plain", value);
    box.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true, cancelable: true }));
  }, text);
}

const summary = (page: Page) => page.locator("[data-slot=match-summary]");
const confirmButton = (page: Page) => page.getByRole("button", { name: /^Confirm \d+ games?$/ });

async function pick(page: Page, name: string, team: string) {
  await page.getByRole("list", { name: `Teams “${name}” may mean` }).getByRole("button", { name: new RegExp(team) }).click();
}

async function noSideScroll(page: Page) {
  const widths = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.client);
}

/** Every visible control in the page's content is at least 44px tall (the shell has its own checks). */
async function tapTargets(page: Page) {
  const targets: Locator = page.locator("main").locator("button, a, input, textarea, summary").filter({ visible: true });
  const count = await targets.count();
  expect(count).toBeGreaterThan(0);
  for (let i = 0; i < count; i++) {
    const target = targets.nth(i);
    const box = await target.boundingBox();
    expect(box, await target.evaluate((el) => el.outerHTML.slice(0, 120))).not.toBeNull();
    expect(box!.height, await target.evaluate((el) => el.outerHTML.slice(0, 120))).toBeGreaterThanOrEqual(44);
  }
}

test("journey 3: paste → 9 rows match · 1 unmatched → map → Confirm, then a re-paste", async ({ page }, testInfo) => {
  await openContest(page);
  await expect(page.getByRole("heading", { name: "Paste from Splash" })).toBeVisible();
  await expect(page.getByText(/No Week 6 slate yet/)).toBeVisible();

  // AC-1: the raw text beside the parsed rows, the unmatched row highlighted, Confirm disabled.
  await paste(page, WEEK6);
  await expect(summary(page)).toHaveText("9 rows match · 1 unmatched");
  const raw = testInfo.project.name === "desktop" ? page.locator("[data-slot=raw-paste]") : page.locator("[data-slot=raw-paste-disclosure]");
  if (testInfo.project.name !== "desktop") await raw.locator("summary").click();
  const rawLine = raw.locator("[data-slot=raw-line]").filter({ hasText: "Hou Texans" }).first();
  await expect(rawLine).toBeVisible();
  expect(await rawLine.evaluate((el) => getComputedStyle(el).fontFamily)).toMatch(/Plex Mono|Plex_Mono|monospace/i);
  const rows = page.locator("[data-slot=parsed-row]");
  await expect(rows).toHaveCount(10);
  const unmatched = rows.filter({ hasText: "“Hou Texans”" });
  await expect(unmatched).toHaveAttribute("data-state", "needs");
  await expect(unmatched).toContainText("Needs team");
  await expect(confirmButton(page)).toBeDisabled();

  // AC-2: map both names, and Confirm saves the slate.
  await pick(page, "Hou Texans", "Houston Texans");
  await expect(confirmButton(page)).toBeDisabled();
  await pick(page, "Jax", "Jacksonville Jaguars");
  await expect(unmatched).toHaveAttribute("data-state", "fixed");
  await expect(summary(page)).toHaveText("10 rows match");
  await expect(confirmButton(page)).toBeEnabled();
  await confirmButton(page).click();

  const week = page.locator("[data-slot=contest-week]");
  await expect(week.locator("[data-slot=contest-game]")).toHaveCount(10);
  await expect(page.locator("[data-slot=week-toolbar]")).toContainText("From Splash paste · Thu 10:00 PM · 10 games");
  await page.reload();
  await expect(week.locator("[data-slot=contest-game]")).toHaveCount(10);

  // The same text again matches all 10 rows, and nothing moved.
  await page.getByRole("button", { name: "Re-paste to update lines" }).click();
  await paste(page, WEEK6);
  await expect(summary(page)).toHaveText("10 rows match");
  await expect(page.locator("[data-slot=repaste-diff]")).toHaveCount(0);
  await expect(confirmButton(page)).toBeEnabled();

  // AC-4: a moved line shows in the RepasteDiff, old then new, before Confirm.
  await page.getByRole("button", { name: "Paste again" }).click();
  await paste(page, MOVED);
  const diff = page.locator("[data-slot=repaste-diff]");
  await expect(diff).toContainText("1 contest line moved since Thu 10:00 PM");
  const moved = diff.locator("[data-slot=moved-row]");
  await expect(moved).toHaveCount(1);
  await expect(moved).toContainText("TEX −7");
  await expect(moved).toContainText("TEX −6.5");
});

test("AC-3: a bad paste shows its state, saves nothing, and the way back works", async ({ page }) => {
  await openContest(page);

  await paste(page, "hello");
  const alert = page.getByRole("alert").filter({ hasText: "Couldn't find any games in that paste" });
  await expect(alert).toBeVisible();
  await expect(alert).toContainText("1 line read · 0 games · nothing saved");
  await expect(pasteBox(page)).toHaveValue("hello");
  await alert.getByRole("button", { name: "Clear and paste again" }).click();
  await expect(pasteBox(page)).toHaveValue("");
  await expect(pasteBox(page)).toBeFocused();

  await paste(page, NBA);
  const noMatch = page.getByRole("alert").filter({ hasText: "Found 3 games, but no team matched" });
  await expect(noMatch).toBeVisible();
  await expect(noMatch).toContainText(
    "Celtics, Knicks, Lakers, Warriors, Nuggets and Suns aren't college football or NFL teams. This contest is CFB + NFL",
  );
  await expect(noMatch).toContainText("3 games read · 0 of 6 teams matched · nothing saved");

  // Nothing was written: the week still has no slate, and the names are still unmatched.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Paste from Splash" })).toBeVisible();
  await paste(page, WEEK6);
  await expect(summary(page)).toHaveText("9 rows match · 1 unmatched");
});

test("AC-5: no sideways scroll and 44px targets, on the hero and the parsed view", async ({ page }, testInfo) => {
  const widths = testInfo.project.name === "desktop" ? [1440, 768] : [390];
  for (const width of widths) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1024 });
    await openContest(page);
    await expect(page.getByRole("heading", { name: "Paste from Splash" })).toBeVisible();
    await noSideScroll(page);
    await tapTargets(page);

    await paste(page, WEEK6);
    await expect(summary(page)).toHaveText("9 rows match · 1 unmatched");
    await noSideScroll(page);
    await tapTargets(page);
  }
});
