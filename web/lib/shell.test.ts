import { describe, expect, it } from "vitest";

import { activeTab, MOBILE_TABS, MORE_ITEMS, NAV, type Shell, shellView } from "./shell";

// The fixture's shell at the slate's time (TASK-053's AC-1, D-156): week 6 of 2026, v1.0's
// record through week 6, the Sat 9:00 AM ET pull, 9 picks.
const FIXTURE: Shell = {
  season: 2026,
  season_type: "regular",
  week: 6,
  model: { name: "v1", version: "1.0" },
  record: { wins: 32, losses: 24, pushes: 1, win_pct: 57.14, units: 4.62, avg_clv: 0.94 },
  record_label: "live",
  lines_updated_at: "2026-10-10T13:00:00+00:00",
  stale: false,
  picks: 9,
  next_season: null,
  next_week: null,
};

const EMPTY: Shell = {
  season: null,
  season_type: null,
  week: null,
  model: null,
  record: null,
  record_label: null,
  lines_updated_at: null,
  stale: false,
  picks: null,
  next_season: null,
  next_week: null,
};

describe("nav", () => {
  it("lists the seven sidebar items in the design's order", () => {
    expect(NAV.map((item) => item.label)).toEqual([
      "This Week",
      "Picks",
      "Contest",
      "Rankings",
      "Teams",
      "Performance",
      "Lab",
    ]);
    expect(NAV.find((item) => item.id === "teams")?.href).toBe("/teams");
    expect(NAV.find((item) => item.id === "performance")?.href).toBe("/performance");
  });

  it("puts four tabs and More on phones, and the rest under More", () => {
    expect(MOBILE_TABS.map((item) => item.label)).toEqual([
      "This Week",
      "Picks",
      "Contest",
      "Rankings",
    ]);
    expect(MORE_ITEMS.map((item) => item.label)).toEqual([
      "Teams",
      "Performance",
      "Lab",
      "Settings",
    ]);
  });

  it("marks More active for a screen that lives under it", () => {
    expect(activeTab("teams")).toBe("more");
    expect(activeTab("performance")).toBe("more");
    expect(activeTab("picks")).toBe("picks");
    expect(activeTab("this-week")).toBe("this-week");
  });
});

describe("shellView", () => {
  it("formats the fixture's shell for the top bar and the track-record card", () => {
    const view = shellView(FIXTURE);
    expect(view.week).toBe("2026 · Week 6");
    expect(view.updated).toBe("Updated Sat 9:00 AM ET");
    expect(view.stale).toBeNull();
    expect(view.picks).toBe("9");
    expect(view.card).toEqual({
      label: "Model · 2026 live",
      record: "32-24-1",
      winRate: "57.1%",
      units: "+4.6u",
      unitsTone: "pos",
      clv: "CLV +0.9",
    });
  });

  it("says when the lines are stale, in Eastern time", () => {
    expect(shellView({ ...FIXTURE, stale: true }).stale).toBe(
      "Lines last updated Sat 9:00 AM ET",
    );
  });

  it("labels a finished season's record final and a losing one negative", () => {
    const view = shellView({
      ...FIXTURE,
      week: null,
      season_type: null,
      record_label: "final",
      record: { wins: 20, losses: 30, pushes: 0, win_pct: 40, units: -11.5, avg_clv: -0.04 },
      picks: null,
    });
    expect(view.week).toBe("2026");
    expect(view.picks).toBeNull();
    // The off-season top bar names the coming season and week; the card keeps the last record.
    const next = shellView({
      ...FIXTURE, week: null, season_type: null, record_label: "final", picks: null,
      next_season: 2027, next_week: 1,
    });
    expect(next.week).toBe("2027 · Week 1");
    expect(next.card?.label).toBe("Model · 2026 final");
    expect(view.card).toMatchObject({
      label: "Model · 2026 final",
      record: "20-30",
      winRate: "40.0%",
      units: "−11.5u",
      unitsTone: "neg",
      clv: "CLV 0.0",
    });
  });

  it("names the postseason instead of a week number", () => {
    expect(shellView({ ...FIXTURE, season_type: "postseason", week: 1 }).week).toBe(
      "2026 · Postseason",
    );
  });

  it("shows dashes for a record with no graded picks and no CLV", () => {
    const view = shellView({
      ...FIXTURE,
      record: { wins: 0, losses: 0, pushes: 0, win_pct: null, units: 0, avg_clv: null },
      picks: 0,
    });
    expect(view.card).toMatchObject({
      record: "0-0",
      winRate: "—",
      units: "0.0u",
      unitsTone: "zero",
      clv: "CLV —",
    });
    expect(view.picks).toBeNull();
  });

  it("draws nothing it doesn't have: no season, no model, no pull", () => {
    const view = shellView(EMPTY);
    expect(view).toEqual({ week: null, updated: null, stale: null, picks: null, card: null });
  });

  it("has no data at all while loading or after an error", () => {
    expect(shellView(null)).toEqual({
      week: null,
      updated: null,
      stale: null,
      picks: null,
      card: null,
    });
  });
});
