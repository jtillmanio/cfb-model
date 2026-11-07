// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { Slate, SlateGame, SlateRules } from "@/lib/slate";

import { SlateView } from "./slate";

// This Week's rendering (TASK-056 AC-2): the legend and the edge pill follow the response's
// pick rules, so a version with other thresholds changes both with no code change (D-055).

afterEach(cleanup);

const GAME: SlateGame = {
  id: 2,
  kickoff_at: "2026-10-10T16:00:00Z",
  game_date: "2026-10-10",
  status: "scheduled",
  neutral_site: false,
  venue: null,
  away: { id: 1, school: "Purdue", abbreviation: "PUR", color: "#CEB888", logo_url: null, division: "fbs", rank: null },
  home: { id: 2, school: "Ohio State", abbreviation: "OSU", color: "#BB0000", logo_url: null, division: "fbs", rank: 1 },
  away_points: null,
  home_points: null,
  cover: null,
  market: { opening_spread_home: -28, current_spread_home: -27.5, closing_spread_home: null, snapshots: [] },
  model: { pred_margin: 31.2, home_win_prob: 0.99, edge: 3.7, side: "home", cover_prob: 0.6057 },
  pick: null,
};

function slate(rules: SlateRules): Slate {
  return {
    season: 2026,
    season_type: "regular",
    week: 6,
    offseason: false,
    rules,
    counts: { games: 1, picks: 0 },
    games: [GAME],
    shell: null,
  } as unknown as Slate;
}

const pill = (container: HTMLElement) => container.querySelector("[data-variant=edge], [data-variant=quiet]");

describe("This Week follows the response's pick rules (AC-2)", () => {
  it("at 2.5 the +3.7 edge is a filled pill and the legend prints 2.5, 5.0, 3.5 and 2.5", () => {
    const { container } = render(
      <SlateView slate={slate({ min_edge_pts: 2.5, min_prob: 0.55, tiers: { A: 5, B: 3.5, C: 2.5 } })} />,
    );
    expect(pill(container)?.getAttribute("data-variant")).toBe("edge");
    expect(pill(container)?.textContent).toBe("+3.7 OSU");
    expect(screen.getByText(/Edge pill = clears 2\.5 pts · Tier A ≥ 5\.0 · B ≥ 3\.5 · C ≥ 2\.5/)).toBeTruthy();
  });

  it("at 4.0 the same edge is plain text and the legend prints the other thresholds", () => {
    const { container } = render(
      <SlateView slate={slate({ min_edge_pts: 4, min_prob: 0.55, tiers: { A: 6, B: 5, C: 4 } })} />,
    );
    expect(pill(container)?.getAttribute("data-variant")).toBe("quiet");
    expect(pill(container)?.textContent).toBe("+3.7 OSU");
    expect(screen.getByText(/Edge pill = clears 4\.0 pts · Tier A ≥ 6\.0 · B ≥ 5\.0 · C ≥ 4\.0/)).toBeTruthy();
    expect(screen.queryByText(/clears 2\.5/)).toBeNull();
  });

  it("with no rules the legend prints no threshold and nothing is filled", () => {
    const { container } = render(<SlateView slate={{ ...slate({ min_edge_pts: 2.5, min_prob: 0.55, tiers: { A: 5, B: 3.5, C: 2.5 } }), rules: null }} />);
    expect(pill(container)?.getAttribute("data-variant")).toBe("quiet");
    expect(screen.getByText("Market = opening line, its moves, then now")).toBeTruthy();
    expect(screen.queryByText(/clears/)).toBeNull();
  });

  it("each game is one link to its Game Detail page, under its window's heading", () => {
    render(<SlateView slate={slate({ min_edge_pts: 2.5, min_prob: 0.55, tiers: { A: 5, B: 3.5, C: 2.5 } })} />);
    expect(screen.getByRole("heading", { level: 2 }).textContent).toContain("SAT NOON");
    const link = document.querySelector("a[data-slot=game-row]")!;
    expect(link.getAttribute("href")).toBe("/games/2");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("This Week");
    expect(screen.getByText("2026 · Week 6 · 1 game · 0 picks")).toBeTruthy();
  });
});

// TASK-057: the empty states, and the strip and chips.

const RULES: SlateRules = { min_edge_pts: 2.5, min_prob: 0.55, tiers: { A: 5, B: 3.5, C: 2.5 } };

function response(over: Record<string, unknown>): Slate {
  return {
    season: 2026,
    season_type: "regular",
    week: 6,
    offseason: false,
    rules: RULES,
    counts: { games: 1, picks: 0 },
    games: [GAME],
    shell: null,
    ...over,
  } as unknown as Slate;
}

const NO_LINE: SlateGame = {
  ...GAME,
  market: { opening_spread_home: null, current_spread_home: null, closing_spread_home: null, snapshots: [] },
  model: { pred_margin: 31.2, home_win_prob: 0.99, edge: null, side: null, cover_prob: null },
} as unknown as SlateGame;

describe("a week with no lines (AC-4)", () => {
  it("every row shows No line, the model line, dashes for edge, cover and tier, and the note", () => {
    const { container } = render(<SlateView slate={response({ games: [NO_LINE] })} />);
    const row = container.querySelector("a[data-slot=game-row]")!;
    expect(row.querySelector("[data-cell=market]")?.textContent).toContain("No line");
    expect(row.querySelector("[data-cell=model]")?.textContent).toBe("OSU −31.2");
    expect(row.querySelector("[data-cell=edge]")?.textContent).toContain("—");
    expect(row.querySelector("[data-cell=cover]")?.textContent).toContain("—");
    // The tier dash is not hidden at 1440 on a row with no line.
    const tier = row.querySelector("[title='No pick']")!;
    expect(tier.parentElement?.className).not.toContain("wide:hidden");
    expect(screen.getByText("No line posted yet")).toBeTruthy();
  });

  it("the strip is the dashed note, not a button, and the title follows the rule", () => {
    render(<SlateView slate={response({ games: [NO_LINE] })} />);
    expect(screen.getByText("No picks yet")).toBeTruthy();
    expect(document.querySelector("[data-slot=record-strip]")).toBeNull();
    cleanup();
    render(<SlateView slate={response({})} />);
    expect(screen.getByText("No picks this week")).toBeTruthy();
    expect(screen.getByText(/No game clears 2\.5 pts/)).toBeTruthy();
  });

  it("a lined row with no tier keeps its tier blank at 1440", () => {
    const { container } = render(<SlateView slate={response({})} />);
    const tier = container.querySelector("a[data-slot=game-row] [title='No pick']")!;
    expect(tier.parentElement?.className).toContain("wide:hidden");
  });
});

describe("the off-season (AC-5)", () => {
  const off = (extra: Record<string, unknown> = {}) =>
    response({ offseason: true, week: null, season_type: null, counts: { games: 0, picks: 0 }, games: [], ...extra });

  it("shows '· off-season' and the dashed frame with no table, chips or strip", () => {
    const { container } = render(<SlateView slate={off()} />);
    expect(screen.getByText("2026 · off-season")).toBeTruthy();
    expect(screen.getByText("No games this week")).toBeTruthy();
    expect(container.querySelector("[data-slot=slate-header]")).toBeNull();
    expect(container.querySelector("a[data-slot=game-row]")).toBeNull();
    expect(container.querySelector("[data-slot=record-strip]")).toBeNull();
    expect(screen.queryByRole("group", { name: "Filter games" })).toBeNull();
    expect(screen.queryByText(/Week 0 kicks off/)).toBeNull();
  });

  it("prints the Week 0 kickoff only when the response gives it", () => {
    render(<SlateView slate={off({ next_kickoff_at: "2027-08-28T19:00:00Z" })} />);
    expect(screen.getByText("Week 0 kicks off Sat Aug 28, 2027")).toBeTruthy();
  });
});

describe("Picks only (AC-3)", () => {
  const picked: SlateGame = {
    ...GAME,
    id: 3,
    pick: {
      side: "home", line: -27.5, price: -110, edge: 3.7, cover_prob: 0.6, tier: "B",
      picked_at: "2026-10-08T12:00:00Z", result: "pending", units: null, clv: null, clv_so_far: 0,
    },
  } as unknown as SlateGame;
  const slateWithPick = () => response({ games: [GAME, picked], counts: { games: 2, picks: 1 } });

  it("the strip and the chip each toggle the filter, the footer and aria-pressed", () => {
    const { container } = render(<SlateView slate={slateWithPick()} />);
    const root = container.querySelector("[data-filter]")!;
    const chip = screen.getByRole("button", { name: /^Picks/ });
    expect(chip.getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByText("Showing 2 of 2 games")).toBeTruthy();

    fireEvent.click(chip);
    expect(root.getAttribute("data-filter")).toBe("picks");
    expect(chip.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("1 game with a pick · of 2")).toBeTruthy();

    fireEvent.click(chip);
    expect(root.getAttribute("data-filter")).toBe("all");
    expect(chip.getAttribute("aria-pressed")).toBe("false");

    const strip = container.querySelector("[data-slot=record-strip]")!;
    fireEvent.click(strip);
    expect(root.getAttribute("data-filter")).toBe("picks");
    expect(strip.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "All" }));
    expect(root.getAttribute("data-filter")).toBe("all");
  });

  it("marks only the pick's row, and its window, for the filter's CSS", () => {
    const { container } = render(<SlateView slate={slateWithPick()} />);
    const rows = [...container.querySelectorAll("a[data-slot=game-row]")];
    expect(rows.map((r) => r.hasAttribute("data-pick"))).toEqual([false, true]);
    expect(container.querySelector("section")?.getAttribute("data-picks")).toBe("1");
  });
});
