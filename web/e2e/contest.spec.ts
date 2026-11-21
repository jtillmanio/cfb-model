import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";

import type { Locator, Page } from "@playwright/test";
import { SignJWT } from "jose";

import { expect as baseExpect, test } from "./fixtures";
import { CONTEST_WEB_URL, FRIDAY_API_URL, FRIDAY_WEB_URL, TEST_API_JWT_SECRET, TEST_GITHUB_ID } from "./test-env";

// Contest (S-02, TASK-072): journey 3 (docs/02 › End-to-end journeys) at Thu 2026-10-08 10:00 PM ET,
// on the contest servers (playwright.config.ts). Each test starts from the seeded state: `engine
// seed paste-journey` gives this Playwright project a fresh contest with no lines, whose platform
// has every fixture `splash` alias but "Hou Texans" and "Jax" (D-175), so a second run, a retry, or
// the other project running at the same time never finds the week confirmed or the names mapped.

test.use({ baseURL: CONTEST_WEB_URL });

// The contest call takes a second or more on the test DB and the API answers one call at a time, so
// when the whole suite runs, a page can wait several seconds for it. Both projects share this API.
const expect = baseExpect.configure({ timeout: 30_000 });
test.describe.configure({ timeout: 90_000 });

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

/** Every visible control in the page's content is at least 44px each way (the shell has its own checks). */
async function tapTargets(page: Page) {
  const targets: Locator = page.locator("main").locator("button, a, input, textarea, summary").filter({ visible: true });
  const count = await targets.count();
  expect(count).toBeGreaterThan(0);
  for (let i = 0; i < count; i++) {
    const target = targets.nth(i);
    const box = await target.boundingBox();
    expect(box, await target.evaluate((el) => el.outerHTML.slice(0, 120))).not.toBeNull();
    expect(box!.height, await target.evaluate((el) => el.outerHTML.slice(0, 120))).toBeGreaterThanOrEqual(44);
    expect(box!.width, await target.evaluate((el) => el.outerHTML.slice(0, 120))).toBeGreaterThanOrEqual(44);
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
  expect(await rawLine.evaluate((el) => getComputedStyle(el).fontFamily)).toMatch(/IBM[ _]Plex[ _]Mono/i);
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

// Journey 4 (docs/02 › End-to-end journeys › 4; TASK-073): the ranked slate, the pick tray and
// the results. At Thu 10:00 PM the picks are written to a fresh contest of this Playwright
// project's own (`engine seed pick-journey`: the work league's rules and Week 6 lines, no
// entries), and the default Splash work league is only read, so it keeps its seeded picks and
// standing. At Fri 8:12 PM (a second server pair) UNLV @ Boise State has kicked off.

function pickContest(project: string): number {
  const out = execFileSync(
    "uv",
    ["--directory", "../python", "run", "engine", "seed", "pick-journey", "--project", project],
    { encoding: "utf8" },
  );
  const last = out.trim().split("\n").at(-1) ?? "";
  return (JSON.parse(last) as { contest_id: number }).contest_id;
}

const slateRow = (page: Page, text: string) => page.locator("[data-slot=contest-game]").filter({ hasText: text });
const side = (page: Page, row: string, name: string) => slateRow(page, row).getByRole("button", { name, exact: true });
const picksHeading = (page: Page, n: number) => page.getByRole("heading", { name: `Your picks ${n} of 4` });
const tray = (page: Page) => page.locator("[data-slot=pick-tray]");
/** The tray marks itself while a pick is being saved: wait for it before reloading, since a save
 *  ends with the page re-rendering. */
const saved = (page: Page) => expect(tray(page)).not.toHaveAttribute("data-saving", "", { timeout: 40_000 });

/** Below 1024 px the tray is a bar that opens to the whole tray; from 1024 it is always open. */
async function openTray(page: Page) {
  const show = page.getByRole("button", { name: "Show your picks" });
  if (await show.isVisible()) await show.click();
}

/** On a phone an open tray covers most of the slate, so close it before tapping the slate again. */
async function closeTray(page: Page) {
  const hide = page.getByRole("button", { name: "Hide your picks" });
  if (await hide.isVisible()) await hide.click();
}

async function tab(page: Page, name: string) {
  await page.getByRole("tab", { name }).click();
}

test.describe("journey 4: the ranked slate, picks and results", () => {
  // One contest per project per run for the tests that don't add picks (a contest's lines can't be
  // deleted, so each seed leaves ten more in the test DB); the test that does gets its own.
  let sharedId: number;

  test.beforeAll(({}, testInfo) => {
    sharedId = pickContest(testInfo.project.name);
  });

  async function openPicks(page: Page, contestId: number = sharedId) {
    await page.goto(`/contest?contest=${contestId}`);
    await expect(page.getByRole("heading", { level: 1, name: "Contest" })).toBeVisible();
    await expect(page.locator("[data-slot=contest-game]")).toHaveCount(10);
  }

  test("AC-1, AC-2: ranked rows, the cutoff under the 4th, NFL rows, and the ≠ filter", async ({ page }) => {
    await openPicks(page);
    const rows = page.locator("[data-slot=contest-game]");
    const cutoff = page.locator("[data-slot=cutoff]");
    await expect(cutoff).toContainText("Model's top 4");
    await expect(cutoff).toContainText(/Next best #5 \S+ [−+]\S+ · \d+%/);
    // The cutoff sits between the 4th and 5th rows.
    const order = await page
      .locator("[data-slot=contest-week] > li")
      .evaluateAll((items) =>
        items.map((li) => (li.getAttribute("data-slot") === "cutoff" ? "cutoff" : li.getAttribute("data-game"))),
      );
    expect(order.indexOf("cutoff")).toBe(4);
    const nfl = rows.filter({ hasText: "No model yet" });
    await expect(nfl).toHaveCount(4);
    await expect(nfl.first()).toContainText(/pts? off mkt → \w+|No gap to market/);
    await expect(nfl.first()).toContainText("mkt-implied");

    const chip = page.getByRole("button", { name: /^Line ≠ market/ });
    await expect(chip).toContainText("8");
    await chip.click();
    await expect(rows).toHaveCount(8);
    await expect(page.locator("[data-slot=contest-game] [data-slot=line-chip]")).toHaveCount(8);
    await chip.click();
    await expect(rows).toHaveCount(10);
  });

  test("AC-3: tap OU +7 and BUF −3 → 2 of 4; tap again to remove; fill from the model's top 4", async ({ page }, testInfo) => {
    test.setTimeout(150_000);
    // Its own contest: a seed replaces the contest of the same name, so not the shared one.
    await openPicks(page, pickContest(`${testInfo.project.name}own`));
    await expect(picksHeading(page, 0)).toBeVisible();
    await side(page, "Oklahoma", "OU +7").click();
    await expect(picksHeading(page, 1)).toBeVisible();
    await side(page, "Buffalo", "BUF −3").click();
    await expect(picksHeading(page, 2)).toBeVisible();
    await expect(side(page, "Oklahoma", "OU +7")).toHaveAttribute("aria-pressed", "true");
    await saved(page);

    // Saved: still there after a reload, with the line it was added at and when.
    await page.reload();
    await expect(picksHeading(page, 2)).toBeVisible();
    await openTray(page);
    await expect(tray(page)).toContainText("Locked in at OU +7 · Thu 10:00 PM");
    await expect(tray(page)).toContainText("Locked in at BUF −3 · Thu 10:00 PM");
    await closeTray(page);

    // A second tap on the same side removes it; a tap on the other side switches it.
    await side(page, "Buffalo", "BUF −3").click();
    await expect(picksHeading(page, 1)).toBeVisible();
    await side(page, "Oklahoma", "TEX −7").click();
    await expect(side(page, "Oklahoma", "TEX −7")).toHaveAttribute("aria-pressed", "true");
    await expect(picksHeading(page, 1)).toBeVisible();

    // The model's top 4 fills the open slots.
    await openTray(page);
    await tray(page).getByRole("button", { name: /^Fill 3 open slots/ }).click();
    await expect(picksHeading(page, 4)).toBeVisible();
    await saved(page);
    await expect(tray(page).getByRole("button", { name: /^Fill|^Use the model/ })).toHaveCount(0);
    await page.reload();
    await expect(picksHeading(page, 4)).toBeVisible();
  });

  test("AC-5: Edit standing saves a new standing that is still there after a reload", async ({ page }) => {
    await openPicks(page);
    await tab(page, "Results & standing");
    const standing = page.locator("[data-slot=standing]");
    await standing.getByRole("button", { name: "Edit standing" }).click();
    await standing.getByLabel("Place").fill("4");
    await standing.getByLabel("Of").fill("12");
    await standing.getByLabel("Pts back").fill("2.5");
    await standing.getByRole("button", { name: "Save" }).click();
    await expect(standing).toContainText("4th of 12");
    await expect(standing).toContainText("2.5 pts behind 1st");
    await page.reload();
    await tab(page, "Results & standing");
    await expect(page.locator("[data-slot=standing]")).toContainText("4th of 12");
  });

  test("AC-6: no sideways scroll and 44px targets on the picks and results tabs", async ({ page }, testInfo) => {
    const widths = testInfo.project.name === "desktop" ? [1440, 768] : [390];
    for (const width of widths) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 1024 });
      await openPicks(page);
      await expect(page.locator("[data-slot=pick-tray]")).toBeVisible();
      await noSideScroll(page);
      await tapTargets(page);
      await openTray(page);
      await noSideScroll(page);
      await tapTargets(page);
      await tab(page, "Results & standing");
      await expect(page.locator("[data-slot=results-standing]")).toBeVisible();
      await noSideScroll(page);
      await tapTargets(page);
    }
  });
});

test.describe("journey 4: the default contest, read only", () => {
  test("AC-3, AC-5: the seeded picks, the season, the standing and the week at 0 pts", async ({ page }) => {
    await page.goto("/contest");
    await expect(page.getByRole("heading", { level: 1, name: "Contest" })).toBeVisible();
    await expect(page.locator("[data-slot=contest-game]")).toHaveCount(10);
    await expect(picksHeading(page, 2)).toBeVisible();
    await openTray(page);
    await expect(tray(page)).toContainText("Locked in at OU +7 · Thu 9:14 PM");
    await expect(tray(page)).toContainText("Locked in at BUF −3 · Thu 9:20 PM");
    await expect(tray(page)).toContainText("1 of 2 match the model");

    await tab(page, "Results & standing");
    const results = page.locator("[data-slot=results-standing]");
    await expect(results.locator("[data-slot=season-card]").nth(0)).toContainText("You · season12-8");
    await expect(results.locator("[data-slot=season-card]").nth(1)).toContainText("Model top 4 · season11-9");
    await expect(results.locator("[data-slot=standing]")).toContainText("3rd of 14");
    await expect(results.locator("[data-slot=week-row]")).toHaveCount(5);
    const sides = results.locator("[data-slot=week-side]");
    await expect(sides.nth(0)).toContainText("0 pts");
    await expect(sides.nth(1)).toContainText("0 pts");
  });

  test("AC-5: the rules panel lists the contest's rules (desktop only)", async ({ page }, testInfo) => {
    await page.goto("/contest");
    const rules = page.getByRole("tab", { name: "Rules" });
    if (testInfo.project.name !== "desktop") {
      await expect(rules).toBeHidden();
      return;
    }
    await rules.click();
    const panel = page.locator("[data-slot=rules-panel]");
    await expect(panel).toContainText("Splash work league");
    await expect(panel).toContainText("CFB + NFL");
    await expect(panel).toContainText("Exactly 4");
    await expect(panel).toContainText("Each game locks at its kickoff");
  });
});

test.describe("journey 4 at Fri 8:12 PM", () => {
  test.use({ baseURL: FRIDAY_WEB_URL });

  // The API's JWT for the test account, as web/lib/api-token.ts mints it (that file is
  // server-only, so a spec can't import it): HS256, issuer cfb-model-web, audience cfb-model-api.
  async function token(): Promise<string> {
    return new SignJWT()
      .setProtectedHeader({ alg: "HS256", typ: "JWT" })
      .setSubject(TEST_GITHUB_ID)
      .setIssuer("cfb-model-web")
      .setAudience("cfb-model-api")
      .setIssuedAt()
      .setExpirationTime("1m")
      .sign(new TextEncoder().encode(TEST_API_JWT_SECRET));
  }

  test("AC-4: UNLV @ Boise State reads Picks closed with its buttons disabled, and the API refuses an entry", async ({
    page,
    request,
  }) => {
    await page.goto("/contest");
    await expect(page.locator("[data-slot=contest-game]")).toHaveCount(10);
    const unlv = slateRow(page, "Boise State");
    await expect(unlv).toContainText("Picks closed");
    await expect(unlv.getByRole("button")).toHaveCount(2);
    for (const button of await unlv.getByRole("button").all()) await expect(button).toBeDisabled();
    await expect(page.locator("[data-slot=locked-header]")).toBeVisible();
    // The open games still take picks.
    await expect(side(page, "Oklahoma", "OU +7")).toBeEnabled();

    // The API refuses a pick on it, and the refusal writes nothing.
    const headers = { Authorization: `Bearer ${await token()}` };
    const read = async () =>
      (await (await request.get(`${FRIDAY_API_URL}/api/py/contest`, { headers })).json()) as {
        contest: { id: number };
        entries: unknown[];
        games: { id: number; away: { school: string }; locked: boolean }[];
      };
    const before = await read();
    const game = before.games.find((g) => g.away.school === "UNLV")!;
    expect(game.locked).toBe(true);
    const refused = await request.post(`${FRIDAY_API_URL}/api/py/contests/${before.contest.id}/entries`, {
      headers,
      data: { game_id: game.id, side: "away" },
    });
    expect(refused.status()).toBe(409);
    expect((await refused.json()).detail.code).toBe("locked");
    expect((await read()).entries).toHaveLength(before.entries.length);
  });
});
