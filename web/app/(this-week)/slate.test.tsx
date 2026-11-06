// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
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
