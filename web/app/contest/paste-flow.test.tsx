// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getContest } from "@/lib/api";
import type { ContestPage, ContestRules, ImportPreview, ImportRow, ImportTeam } from "@/lib/contest";

import { confirmImport, previewImport } from "./actions";
import { ContestLoading } from "./loading";
import Contest from "./page";
import { PasteFlow } from "./paste-flow";

// The paste flow's states (TASK-072): the hero, the parsed preview with the raw text and the
// inline team picker (AC-1, AC-2), C2a and C2b (AC-3), the RepasteDiff (AC-4) and a failed call.
// The Server Actions are mocked; e2e/contest.spec.ts runs the same flow against the API.

vi.mock("./actions", () => ({ previewImport: vi.fn(), confirmImport: vi.fn() }));
const preview = vi.mocked(previewImport);
const confirm = vi.mocked(confirmImport);

// The page itself (a server component, awaited and rendered): its one call is mocked, and the
// shell's links and router are plain stand-ins (as app-shell.test.tsx does).
vi.mock("@/lib/api", () => ({ getContest: vi.fn() }));
vi.mock("next/server", () => ({ connection: async () => {} }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));
const contestCall = vi.mocked(getContest);

afterEach(cleanup);
beforeEach(() => {
  preview.mockReset();
  confirm.mockReset();
});

const RULES: ContestRules = {
  sports: ["cfb", "nfl"],
  picks_per_period: 4,
  picks_exact: true,
  scoring: "point_per_win",
  push: "zero",
  lock: "per_game_kickoff",
};

function team(id: number, sport: string, school: string, abbreviation: string, mascot: string | null = null): ImportTeam {
  return { id, sport_id: sport, school, mascot, abbreviation, color: "#000000" };
}
const TEX = team(1, "cfb", "Texas", "TEX");
const OU = team(2, "cfb", "Oklahoma", "OU");
const HOU = team(31, "nfl", "Houston", "HOU", "Texans");
const JAX = team(32, "nfl", "Jacksonville", "JAX", "Jaguars");

function row(index: number, over: Partial<ImportRow> = {}): ImportRow {
  return {
    index,
    first_line: 1 + index * 3,
    last_line: 3 + index * 3,
    away_name: "Texas",
    home_name: "Oklahoma",
    status: "matched",
    problem: null,
    matched_by: "alias",
    swapped: false,
    game_id: 100 + index,
    sport_id: "cfb",
    away_team: TEX,
    home_team: OU,
    spread_home: 7,
    game_date: "2026-10-10",
    kickoff_at: "2026-10-10T23:30:00Z",
    page_status: "Preview",
    unmatched: [],
    ...over,
  };
}

const UNMATCHED = row(9, {
  away_name: "Hou Texans",
  home_name: "Jax",
  status: "unmatched",
  matched_by: null,
  game_id: null,
  sport_id: null,
  away_team: null,
  home_team: null,
  spread_home: 1,
  game_date: "2026-10-11",
  kickoff_at: "2026-10-11T17:00:00Z",
  unmatched: [
    { name: "Hou Texans", candidates: [HOU, JAX] },
    { name: "Jax", candidates: [JAX, HOU] },
  ],
});

function week6(over: Partial<ImportPreview> = {}): ImportPreview {
  const rows = [...Array.from({ length: 9 }, (_, i) => row(i)), UNMATCHED];
  return {
    contest_id: 7,
    period: 6,
    lock_at: "2026-10-12T00:20:00Z",
    rows,
    counts: { rows: 10, matched: 9, unmatched: 1, problem: 0 },
    changes: [],
    ...over,
  };
}

const TEXT = Array.from({ length: 30 }, (_, i) => (i === 27 ? "Hou Texans" : i === 28 ? "Jax" : `line ${i + 1}`)).join(
  "\n",
);

function hero() {
  render(<PasteFlow contestId={7} period={6} rules={RULES} hero />);
  return screen.getByRole("textbox", { name: "The contest page's text" });
}

function paste(box: HTMLElement, text: string) {
  fireEvent.paste(box, { clipboardData: { getData: () => text } });
}

describe("AC-1: pasting shows the raw text beside the parsed rows", () => {
  it("reads the paste for the hero's week and highlights the unmatched row", async () => {
    preview.mockResolvedValue({ kind: "preview", preview: week6() });
    const box = hero();
    expect(screen.getByRole("heading", { name: "Paste from Splash" })).toBeTruthy();
    expect(screen.getByText(/No Week 6 slate yet/)).toBeTruthy();

    paste(box, TEXT);

    expect(preview).toHaveBeenCalledWith(7, 6, TEXT);
    const summary = await screen.findByText((_, el) => el?.getAttribute("data-slot") === "match-summary");
    expect(summary.textContent).toBe("9 rows match · 1 unmatched");

    const raw = screen.getByRole("region", { name: "Your paste" });
    expect(raw.querySelector(".font-mono")).toBeTruthy();
    expect(within(raw).getAllByText("Hou Texans")[0].className).toContain("text-neg");

    const rows = document.querySelectorAll('[data-slot="parsed-row"]');
    expect(rows).toHaveLength(10);
    expect(rows[9].getAttribute("data-state")).toBe("needs");
    expect(within(rows[9] as HTMLElement).getByText("Needs team")).toBeTruthy();
    expect((await screen.findByRole("button", { name: /Confirm 10 games/ })).hasAttribute("disabled")).toBe(true);
  });
});

describe("AC-2: picking both names enables Confirm, which saves them", () => {
  it("sends the picks with the paste and the week", async () => {
    preview.mockResolvedValue({ kind: "preview", preview: week6() });
    confirm.mockResolvedValue({ kind: "confirmed" });
    paste(hero(), TEXT);
    await screen.findByText("Needs team");

    const away = screen.getByRole("list", { name: "Teams “Hou Texans” may mean" });
    fireEvent.click(within(away).getByText("Houston Texans"));
    expect(screen.getByRole("button", { name: /Confirm 10 games/ }).hasAttribute("disabled")).toBe(true);
    const home = screen.getByRole("list", { name: "Teams “Jax” may mean" });
    fireEvent.click(within(home).getByText("Jacksonville Jaguars"));

    const button = screen.getByRole("button", { name: /Confirm 10 games/ });
    expect(button.hasAttribute("disabled")).toBe(false);
    expect(document.querySelectorAll('[data-slot="parsed-row"]')[9].getAttribute("data-state")).toBe("fixed");
    fireEvent.click(button);
    expect(confirm).toHaveBeenCalledWith(7, 6, TEXT, [
      { alias: "Hou Texans", team_id: 31 },
      { alias: "Jax", team_id: 32 },
    ]);
  });

  it("filters the picker and takes the best match on Enter", async () => {
    preview.mockResolvedValue({ kind: "preview", preview: week6() });
    paste(hero(), TEXT);
    await screen.findByText("Needs team");
    const search = screen.getByRole("searchbox", { name: "Find the team “Jax” means" });
    fireEvent.change(search, { target: { value: "jag" } });
    expect(within(screen.getByRole("list", { name: "Teams “Jax” may mean" })).queryByText("Houston Texans")).toBeNull();
    fireEvent.keyDown(search, { key: "Enter" });
    expect(screen.getByRole("button", { name: "Jacksonville Jaguars for “Jax”. Change" })).toBeTruthy();
  });

  it("shows a refused confirm's message and the rows again", async () => {
    preview.mockResolvedValue({ kind: "preview", preview: week6() });
    confirm.mockResolvedValue({
      kind: "refused",
      refusal: { code: "unresolved", message: "Every row must match one game.", rows: [UNMATCHED] },
    });
    paste(hero(), TEXT);
    await screen.findByText("Needs team");
    fireEvent.click(within(screen.getByRole("list", { name: "Teams “Hou Texans” may mean" })).getByText("Houston Texans"));
    fireEvent.click(within(screen.getByRole("list", { name: "Teams “Jax” may mean" })).getByText("Jacksonville Jaguars"));
    fireEvent.click(screen.getByRole("button", { name: /Confirm 10 games/ }));
    expect(await screen.findByText("Every row must match one game.")).toBeTruthy();
    expect(preview).toHaveBeenCalledTimes(2);
  });
});

describe("AC-3: a paste the API refused keeps the text and saves nothing", () => {
  it("C2a: nothing parseable, with a way back to edit the paste", async () => {
    preview.mockResolvedValue({ kind: "refused", refusal: { code: "unparseable", message: "", rows: [] } });
    const box = hero();
    paste(box, "hello");
    expect(await screen.findByText("Couldn't find any games in that paste")).toBeTruthy();
    expect(screen.getByText("1 line read · 0 games · nothing saved")).toBeTruthy();
    expect((box as HTMLTextAreaElement).value).toBe("hello");
    fireEvent.click(screen.getByRole("button", { name: "Clear and paste again" }));
    expect((box as HTMLTextAreaElement).value).toBe("");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(confirm).not.toHaveBeenCalled();
  });

  it("C2b: games, but no team matched", async () => {
    const nba = [row(0, { away_name: "Celtics", home_name: "Knicks", status: "unmatched" })];
    preview.mockResolvedValue({ kind: "refused", refusal: { code: "no_match", message: "", rows: nba } });
    paste(hero(), "Celtics\nKnicks");
    expect(await screen.findByText("Found 1 game, but no team matched")).toBeTruthy();
    expect(screen.getByText(/Celtics and Knicks aren't college football or NFL teams/)).toBeTruthy();
    expect(screen.getByText("1 game read · 0 of 2 teams matched · nothing saved")).toBeTruthy();
  });

  it("says so when the API can't be reached", async () => {
    preview.mockResolvedValue({ kind: "failed", message: "Couldn't reach the server. Nothing was saved; try again." });
    paste(hero(), TEXT);
    expect(await screen.findByText("Couldn't reach the server. Nothing was saved; try again.")).toBeTruthy();
  });
});

describe("AC-4: a re-paste lists each moved line before Confirm", () => {
  it("opens from the confirmed week and shows the RepasteDiff", async () => {
    preview.mockResolvedValue({
      kind: "preview",
      preview: week6({
        changes: [
          {
            index: 4,
            game_id: 104,
            contest_line_id: 9,
            old_spread_home: 7,
            old_captured_at: "2026-10-09T02:00:00Z",
            new_spread_home: 6.5,
          },
        ],
      }),
    });
    render(
      <PasteFlow contestId={7} period={6} rules={RULES} hero={false} source="From Splash paste · Thu 10:00 PM · 10 games">
        <p>the week</p>
      </PasteFlow>,
    );
    expect(screen.getByText("the week")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Re-paste to update lines" }));
    expect(screen.getByText(/Update Week 6's lines/)).toBeTruthy();
    paste(screen.getByRole("textbox", { name: "The contest page's text" }), TEXT);

    const diff = await screen.findByRole("region", { name: "Contest lines that moved" });
    expect(within(diff).getByText("1 contest line moved since Thu 10:00 PM")).toBeTruthy();
    const moved = diff.querySelectorAll('[data-slot="moved-row"]');
    expect(moved).toHaveLength(1);
    expect(moved[0].textContent).toContain("TEX −7");
    expect(moved[0].textContent).toContain("TEX −6.5");
    expect(within(diff).getByText(/The other 9 games are unchanged/)).toBeTruthy();
  });

  it("has no Re-paste once every game is locked", () => {
    render(<PasteFlow contestId={7} period={6} rules={RULES} hero={false} weekOpen={false} source="x" />);
    expect(screen.queryByRole("button", { name: "Re-paste to update lines" })).toBeNull();
    expect(screen.getByText("Week 6 closed · results after the last game")).toBeTruthy();
  });
});

const PAGE: ContestPage = {
  contest: { id: 414, name: "Paste journey (phone)", platform: "splash-e2e-phone", season: 2026, rules: RULES },
  period: null,
  periods: [],
  games: [],
  entries: [],
  counts: { games: 0, entries: 0, differs: 0 },
  results: null,
  standing: null,
  shell: {
    season: 2026,
    season_type: "regular",
    week: 6,
    model: null,
    record: null,
    record_label: null,
    lines_updated_at: null,
    stale: false,
    picks: null,
    next_season: null,
    next_week: null,
  },
};

async function renderPage(params: Record<string, string> = {}) {
  render(await Contest({ searchParams: Promise.resolve(params) }));
}

describe("AC-5: the page's states", () => {
  beforeEach(() => {
    contestCall.mockReset();
  });

  it("draws API unreachable inside the shell when its one call fails (D-096)", async () => {
    contestCall.mockImplementation(() => Promise.reject(new Error("GET /api/py/contest failed with 503")));
    vi.spyOn(console, "error").mockImplementation(() => {});
    await renderPage();
    expect(screen.getByRole("heading", { level: 1, name: "Contest" })).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("Couldn't reach the server");
    expect(screen.queryByRole("heading", { name: "Paste from Splash" })).toBeNull();
  });

  it("opens the contest the URL names, on the hero when its week has no slate", async () => {
    contestCall.mockResolvedValue(PAGE);
    await renderPage({ contest: "414" });
    expect(contestCall).toHaveBeenCalledWith(414);
    expect(screen.getByText("Paste journey (phone)")).toBeTruthy();
    expect(
      screen.getByText("Week 6 · Pick 4 · CFB + NFL · each game locks at its kickoff · 1 pt per correct pick · push = 0"),
    ).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Paste from Splash" })).toBeTruthy();
  });

  it("asks for the default contest when the URL names none, or a bad id", async () => {
    contestCall.mockResolvedValue(null);
    await renderPage({ contest: "abc" });
    expect(contestCall).toHaveBeenCalledWith(null);
    expect(screen.getByRole("heading", { name: "No contest yet" })).toBeTruthy();
  });
});

describe("AC-5: the loading skeleton", () => {
  it("draws the title, the toolbar and ten slate rows as bars, with the pulse off under reduced motion", () => {
    render(<ContestLoading />);
    expect(screen.getByRole("heading", { level: 1, name: "Contest" })).toBeTruthy();
    const status = screen.getByRole("status", { name: "Loading the contest" });
    const rows = status.querySelectorAll('[data-slot="skeleton-row"]');
    expect(rows).toHaveLength(10);
    // 64px from 768 (the slate's row), a taller card on a phone (Loading States › Contest).
    expect(rows[0].className).toContain("md:h-16");
    const bars = document.querySelectorAll(".animate-pulse");
    expect(bars.length).toBeGreaterThan(10);
    for (const bar of bars) expect(bar.className).toContain("motion-reduce:animate-none");
  });
});
