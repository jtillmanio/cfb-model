import { describe, expect, it } from "vitest";

import {
  isPastWeek,
  isShownWeek,
  liveCover,
  noPicksNote,
  offseasonNote,
  parseWeekParams,
  recordStrip,
  showingText,
  slateCaption,
  slateLegend,
  slateWindows,
  rowView,
  weekHref,
  weekLabel,
  weekNeighbours,
  type SlateWeek,
  type Slate,
  type SlateGame,
  type SlateRules,
} from "./slate";

// This Week's pure view logic (TASK-056): kickoff windows, one row's view from the /slate
// response, and the caption and legend. No clock and no DOM; kickoffs are fixed instants and the
// zone is Eastern, as the shell's is until M8.8.

const ET = "America/New_York";

const RULES: SlateRules = { min_edge_pts: 2.5, min_prob: 0.55, tiers: { A: 5, B: 3.5, C: 2.5 } };

function team(abbreviation: string, over: Partial<SlateGame["home"]> = {}): SlateGame["home"] {
  return {
    id: 1,
    school: abbreviation,
    abbreviation,
    color: "#112233",
    logo_url: null,
    division: "fbs",
    rank: null,
    ...over,
  };
}

function game(over: Partial<SlateGame> = {}): SlateGame {
  return {
    id: 7,
    kickoff_at: "2026-10-10T19:30:00Z", // Sat 3:30 PM ET
    game_date: "2026-10-10",
    status: "scheduled",
    neutral_site: false,
    venue: null,
    away: team("AWAY"),
    home: team("HOME"),
    away_points: null,
    home_points: null,
    cover: null,
    market: {
      opening_spread_home: -3,
      current_spread_home: -3.5,
      closing_spread_home: null,
      snapshots: [],
    },
    model: { pred_margin: 7, home_win_prob: 0.7, edge: 3.5, side: "home", cover_prob: 0.58 },
    pick: null,
    ...over,
  };
}

function pick(over: Partial<NonNullable<SlateGame["pick"]>> = {}): NonNullable<SlateGame["pick"]> {
  return {
    side: "home",
    line: -3.5,
    price: -110,
    edge: 3.5,
    cover_prob: 0.58,
    tier: "B",
    picked_at: "2026-10-08T12:00:00Z",
    result: "pending",
    units: null,
    clv: null,
    clv_so_far: 0,
    ...over,
  };
}

describe("slateWindows (the design's day/time windows, in Eastern)", () => {
  const at = (iso: string, id: number) => game({ id, kickoff_at: iso, game_date: iso.slice(0, 10) });

  it("groups by weekday and band: morning < 11, noon 11–1:59, afternoon 2–5:59, night 6+", () => {
    const windows = slateWindows(
      [
        at("2026-10-10T14:59:00Z", 1), // Sat 10:59 AM
        at("2026-10-10T15:00:00Z", 2), // Sat 11:00 AM
        at("2026-10-10T17:59:00Z", 3), // Sat 1:59 PM
        at("2026-10-10T18:00:00Z", 4), // Sat 2:00 PM
        at("2026-10-10T21:59:00Z", 5), // Sat 5:59 PM
        at("2026-10-10T22:00:00Z", 6), // Sat 6:00 PM
      ],
      ET,
    );
    expect(windows.map((w) => [w.label, w.games.map((g) => g.id)])).toEqual([
      ["SAT MORNING", [1]],
      ["SAT NOON", [2, 3]],
      ["SAT AFTERNOON", [4, 5]],
      ["SAT NIGHT", [6]],
    ]);
  });

  it("writes the heading time as the board does: the date on a day's first window, then times", () => {
    const windows = slateWindows(
      [
        at("2026-10-10T00:00:00Z", 1), // Fri 8:00 PM
        at("2026-10-10T16:00:00Z", 2), // Sat 12:00 PM
        at("2026-10-10T19:30:00Z", 3), // Sat 3:30 PM
        at("2026-10-10T23:00:00Z", 4), // Sat 7:00 PM
        at("2026-10-11T02:30:00Z", 5), // Sat 10:30 PM (still Saturday in Eastern)
      ],
      ET,
    );
    expect(windows.map((w) => [w.label, w.time])).toEqual([
      ["FRI NIGHT", "Fri 10/9 · 8:00 PM ET"],
      ["SAT NOON", "Sat 10/10 · 12:00 PM ET"],
      ["SAT AFTERNOON", "3:30 PM ET"],
      ["SAT NIGHT", "7:00 – 10:30 PM ET"],
    ]);
  });

  it("keeps both day periods when a window spans them", () => {
    const [noon] = slateWindows(
      [at("2026-10-10T15:30:00Z", 1), at("2026-10-10T17:00:00Z", 2)], // 11:30 AM, 1:00 PM
      ET,
    );
    expect(noon.time).toBe("Sat 10/10 · 11:30 AM – 1:00 PM ET");
  });

  it("orders windows by kickoff, whatever order the games arrive in", () => {
    const windows = slateWindows(
      [at("2026-10-10T23:00:00Z", 1), at("2026-10-10T16:00:00Z", 2)],
      ET,
    );
    expect(windows.map((w) => w.label)).toEqual(["SAT NOON", "SAT NIGHT"]);
  });

  it("puts a TBA kickoff in a last window for its date", () => {
    const tba = game({ id: 9, kickoff_at: null, game_date: "2026-10-10" });
    const windows = slateWindows([tba, at("2026-10-10T16:00:00Z", 2)], ET);
    expect(windows.map((w) => [w.label, w.time, w.games.map((g) => g.id)])).toEqual([
      ["SAT NOON", "Sat 10/10 · 12:00 PM ET", [2]],
      ["SAT TBA", "Time TBA", [9]],
    ]);
  });

  it("has no windows without games", () => {
    expect(slateWindows([], ET)).toEqual([]);
  });
});

describe("rowView: status and teams", () => {
  it("a game still to play shows its kickoff time and no scores", () => {
    const row = rowView(game(), RULES, ET);
    expect(row.status).toBe("scheduled");
    expect(row.statusLabel).toBe("3:30 PM");
    expect(row.href).toBe("/games/7");
    expect(row.away.points).toBeNull();
    expect(row.home.points).toBeNull();
  });

  it("a TBA kickoff reads TBA", () => {
    expect(rowView(game({ kickoff_at: null }), RULES, ET).statusLabel).toBe("TBA");
  });

  it("a live game says Live, with each team's score, and neither side is bold or muted", () => {
    const row = rowView(
      game({ status: "in_progress", away_points: 3, home_points: 24 }),
      RULES,
      ET,
    );
    expect(row.status).toBe("live");
    expect(row.statusLabel).toBe("Live");
    expect([row.away.points, row.home.points]).toEqual([3, 24]);
    expect([row.away.tone, row.home.tone]).toEqual(["normal", "normal"]);
  });

  it("a final game: Final, the winner emphasised and the loser muted", () => {
    const row = rowView(game({ status: "final", away_points: 24, home_points: 31 }), RULES, ET);
    expect(row.statusLabel).toBe("Final");
    expect([row.away.tone, row.home.tone]).toEqual(["loser", "winner"]);
  });

  it("postponed and canceled keep their words", () => {
    expect(rowView(game({ status: "postponed" }), RULES, ET).statusLabel).toBe("Postponed");
    expect(rowView(game({ status: "canceled" }), RULES, ET).statusLabel).toBe("Canceled");
  });

  it("carries rank, FCS and the abbreviation, falling back to the school", () => {
    const row = rowView(
      game({
        away: team("FUR", { school: "Furman", division: "fcs" }),
        home: team("CLEM", { school: "Clemson", rank: 12 }),
      }),
      RULES,
      ET,
    );
    expect(row.away.fcs).toBe(true);
    expect(row.away.rank).toBeNull();
    expect(row.home.fcs).toBe(false);
    expect(row.home.rank).toBe(12);
    const bare = rowView(game({ home: team("X", { abbreviation: null, school: "Xavier" }) }), RULES, ET);
    expect(bare.home.abbr).toBe("Xavier");
  });

  it("a team with no division is not called FCS", () => {
    const row = rowView(game({ away: team("AWAY", { division: null }) }), RULES, ET);
    expect(row.away.fcs).toBe(false);
  });

  it("a neutral-site game carries its city", () => {
    const row = rowView(
      game({ neutral_site: true, venue: { name: "Cotton Bowl", city: "Dallas", state: "TX" } }),
      RULES,
      ET,
    );
    expect(row.neutral).toEqual({ city: "Dallas" });
    expect(rowView(game({ neutral_site: true }), RULES, ET).neutral).toEqual({ city: null });
    expect(rowView(game(), RULES, ET).neutral).toBeNull();
  });
});

describe("rowView: market, model and edge", () => {
  it("the market keeps the opener, each snapshot in order, and the current line", () => {
    const row = rowView(
      game({
        market: {
          opening_spread_home: 7,
          current_spread_home: 6.5,
          closing_spread_home: null,
          snapshots: [
            { captured_at: "2026-10-05T12:00:00Z", spread_home: 7 },
            { captured_at: "2026-10-06T12:00:00Z", spread_home: 6.5 },
            { captured_at: "2026-10-08T12:00:00Z", spread_home: 6 },
          ],
        },
      }),
      RULES,
      ET,
    );
    expect(row.market).toEqual({ opener: 7, snapshots: [7, 6.5, 6], current: 6.5, past: false });
  });

  it("writes the model line, the edge, the cover % and the favourite's win %", () => {
    const row = rowView(
      game({
        model: { pred_margin: 31.2, home_win_prob: 0.99, edge: 3.7, side: "home", cover_prob: 0.6057 },
      }),
      RULES,
      ET,
    );
    expect(row.modelLine).toBe("HOME −31.2");
    expect(row.edge).toEqual({ pts: 3.7, clears: true });
    expect(row.cover).toBe("61%");
    expect(row.coverProb).toBe(0.6057);
    expect(row.win).toBe("HOME 99%");
  });

  it("an edge below the threshold does not clear it, and the threshold is the response's", () => {
    const model = { pred_margin: 4.6, home_win_prob: 0.63, edge: 0.6, side: "home" as const, cover_prob: 0.51 };
    expect(rowView(game({ model }), RULES, ET).edge.clears).toBe(false);
    const wide = { ...model, edge: 3.0 };
    expect(rowView(game({ model: wide }), RULES, ET).edge.clears).toBe(true);
    expect(rowView(game({ model: wide }), { ...RULES, min_edge_pts: 4 }, ET).edge.clears).toBe(false);
  });

  it("an away edge is negative and clears on its magnitude", () => {
    const model = { pred_margin: -1.4, home_win_prob: 0.46, edge: -4.9, side: "away" as const, cover_prob: 0.64 };
    const row = rowView(game({ model }), RULES, ET);
    expect(row.edge).toEqual({ pts: -4.9, clears: true });
    expect(row.win).toBe("AWAY 54%");
  });

  it("no rules means nothing clears", () => {
    expect(rowView(game(), null, ET).edge.clears).toBe(false);
  });

  it("a game with no line still shows the model line and no edge, cover or tier", () => {
    const row = rowView(
      game({
        market: { opening_spread_home: null, current_spread_home: null, closing_spread_home: null, snapshots: [] },
        model: { pred_margin: 34, home_win_prob: 0.99, edge: null, side: null, cover_prob: null },
      }),
      RULES,
      ET,
    );
    expect(row.market).toEqual({ opener: null, snapshots: [], current: null, past: false });
    expect(row.modelLine).toBe("HOME −34.0");
    expect(row.edge).toEqual({ pts: null, clears: false });
    expect(row.cover).toBeNull();
    expect(row.tier).toBeNull();
  });

  it("a game the run did not predict has no model figures", () => {
    const row = rowView(game({ model: null }), RULES, ET);
    expect([row.modelLine, row.cover, row.win]).toEqual([null, null, null]);
    expect(row.edge).toEqual({ pts: null, clears: false });
  });

  it("the tier is the current pick's", () => {
    expect(rowView(game({ pick: pick({ tier: "A" }) }), RULES, ET).tier).toBe("A");
    expect(rowView(game({ pick: pick({ tier: null }) }), RULES, ET).tier).toBeNull();
    expect(rowView(game(), RULES, ET).tier).toBeNull();
  });
});

describe("rowView: the Pick · result notes", () => {
  const away = team("UNLV");
  const home = team("BSU");

  it("final with no pick: which side covered, or a push", () => {
    const final = { status: "final" as const, away, home, away_points: 24, home_points: 31 };
    expect(rowView(game({ ...final, cover: "away" }), RULES, ET).notes).toEqual([
      { text: "No pick · UNLV covered", tone: "muted", icon: "check" },
    ]);
    expect(rowView(game({ ...final, cover: "home" }), RULES, ET).notes[0].text).toBe(
      "No pick · BSU covered",
    );
    expect(rowView(game({ ...final, cover: "push" }), RULES, ET).notes[0].text).toBe("No pick · push");
  });

  it("final with a pick: the result marker, the bet, the result and the units", () => {
    const final = { status: "final" as const, away, home, away_points: 27, home_points: 24, cover: "away" as const };
    const won = rowView(game({ ...final, pick: pick({ side: "away", line: -4, result: "won", units: 0.91 }) }), RULES, ET);
    expect(won.notes).toEqual([{ text: "UNLV +4 · covered · +0.9u", tone: "ink", result: "covered" }]);
    const lost = rowView(game({ ...final, pick: pick({ side: "home", line: -4, result: "lost", units: -1 }) }), RULES, ET);
    expect(lost.notes).toEqual([{ text: "BSU −4 · not covered · −1.0u", tone: "ink", result: "not_covered" }]);
    const push = rowView(game({ ...final, pick: pick({ side: "home", line: -3, result: "push", units: 0 }) }), RULES, ET);
    expect(push.notes[0]).toMatchObject({ text: "BSU −3 · push · 0.0u", result: "push" });
  });

  it("final with a pick not yet graded reads as a plain pick", () => {
    const row = rowView(
      game({ status: "final", away, home, pick: pick({ result: "pending", line: -3.5, side: "home" }) }),
      RULES,
      ET,
    );
    expect(row.notes).toEqual([{ text: "Pick BSU −3.5", tone: "ink" }]);
  });

  it("live with a pick on the favourite: covering, or not yet and what it needs", () => {
    const live = { status: "in_progress" as const, away: team("PUR"), home: team("OSU") };
    const behind = rowView(
      game({ ...live, away_points: 3, home_points: 24, pick: pick({ side: "home", line: -27.5 }) }),
      RULES,
      ET,
    );
    expect(behind.notes).toEqual([{ text: "OSU −27.5 · not yet, needs 28+", tone: "neg" }]);
    const whole = rowView(
      game({ ...live, away_points: 3, home_points: 24, pick: pick({ side: "home", line: -28 }) }),
      RULES,
      ET,
    );
    expect(whole.notes[0].text).toBe("OSU −28 · not yet, needs 29+");
    const ahead = rowView(
      game({ ...live, away_points: 3, home_points: 40, pick: pick({ side: "home", line: -27.5 }) }),
      RULES,
      ET,
    );
    expect(ahead.notes).toEqual([{ text: "OSU −27.5 · covering", tone: "pos" }]);
  });

  it("live with a pick on the underdog: covering, or just not yet, and never lost", () => {
    const live = { status: "in_progress" as const, away: team("IOWA"), home: team("WIS") };
    const covering = rowView(
      game({ ...live, away_points: 10, home_points: 7, pick: pick({ side: "away", line: -1.5 }) }),
      RULES,
      ET,
    );
    expect(covering.notes).toEqual([{ text: "IOWA +1.5 · covering", tone: "pos" }]);
    const trailing = rowView(
      game({ ...live, away_points: 0, home_points: 14, pick: pick({ side: "away", line: -1.5 }) }),
      RULES,
      ET,
    );
    expect(trailing.notes).toEqual([{ text: "IOWA +1.5 · not yet", tone: "neg" }]);
    expect(trailing.notes[0].text).not.toMatch(/lost/i);
  });

  it("live without a pick has no note", () => {
    expect(rowView(game({ status: "in_progress", away_points: 1, home_points: 0 }), RULES, ET).notes).toEqual([]);
  });

  it("no line: FCS · no lines yet when a team is FCS, else no line posted yet", () => {
    const noLine = {
      opening_spread_home: null,
      current_spread_home: null,
      closing_spread_home: null,
      snapshots: [],
    };
    const fcs = rowView(
      game({ market: noLine, away: team("FUR", { division: "fcs" }), model: null }),
      RULES,
      ET,
    );
    expect(fcs.notes).toEqual([{ text: "FCS · no lines yet", tone: "muted", icon: "clock" }]);
    const plain = rowView(game({ market: noLine, model: null }), RULES, ET);
    expect(plain.notes).toEqual([{ text: "No line posted yet", tone: "muted", icon: "clock" }]);
  });

  it("an upcoming pick whose line has not moved: Pick <bet>", () => {
    const row = rowView(
      game({
        away: team("ND"),
        home: team("STAN"),
        market: { opening_spread_home: 16.5, current_spread_home: 17, closing_spread_home: null, snapshots: [] },
        pick: pick({ side: "away", line: 17, clv_so_far: 0 }),
      }),
      RULES,
      ET,
    );
    expect(row.notes).toEqual([{ text: "Pick ND −17", tone: "ink" }]);
  });

  it("an upcoming pick whose line moved: Picked at → now over CLV, with D-140's sign", () => {
    const moved = (clv: number | null) =>
      rowView(
        game({
          away: team("MISS"),
          home: team("LSU"),
          market: { opening_spread_home: -2.5, current_spread_home: -3.5, closing_spread_home: null, snapshots: [] },
          pick: pick({ side: "away", line: -2.5, clv_so_far: clv }),
        }),
        RULES,
        ET,
      ).notes;
    expect(moved(-1)).toEqual([
      { text: "Picked at −2.5 → now −3.5", tone: "muted", icon: "history" },
      { text: "CLV −1.0", tone: "neg" },
    ]);
    expect(moved(1)[1]).toEqual({ text: "CLV +1.0 · moved our way", tone: "pos" });
    expect(moved(0)[1]).toEqual({ text: "CLV 0.0", tone: "muted" });
    expect(moved(null)).toHaveLength(1);
  });

  it("an upcoming pick that moved from the favourite's side reads from the current favourite", () => {
    const notes = rowView(
      game({
        away: team("ASU"),
        home: team("BAY"),
        market: { opening_spread_home: -3, current_spread_home: -2.5, closing_spread_home: null, snapshots: [] },
        pick: pick({ side: "away", line: -3, clv_so_far: 0.5 }),
      }),
      RULES,
      ET,
    ).notes;
    expect(notes[0].text).toBe("Picked at −3 → now −2.5");
  });

  it("postponed and canceled games have no note", () => {
    expect(rowView(game({ status: "postponed" }), RULES, ET).notes).toEqual([]);
    expect(rowView(game({ status: "canceled", pick: pick() }), RULES, ET).notes).toEqual([]);
  });
});

describe("caption and legend", () => {
  const slate = (over: Partial<Slate> = {}): Slate =>
    ({
      season: 2026,
      season_type: "regular",
      week: 6,
      offseason: false,
      rules: RULES,
      counts: { games: 54, picks: 9 },
      games: [],
      ...over,
    }) as Slate;

  it("the caption names the season, week and counts", () => {
    expect(slateCaption(slate())).toBe("2026 · Week 6 · 54 games · 9 picks");
    expect(slateCaption(slate({ counts: { games: 1, picks: 1 } }))).toBe("2026 · Week 6 · 1 game · 1 pick");
  });

  it("the postseason has no week number", () => {
    expect(slateCaption(slate({ season_type: "postseason", week: 1 }))).toBe(
      "2026 · Postseason · 54 games · 9 picks",
    );
  });

  it("names the coming season and week in the off-season, else the season that ended", () => {
    const off = { season: null, season_type: null, week: null, counts: { games: 0, picks: 0 }, offseason: true };
    expect(slateCaption({ ...off, shell: { season: 2026, next_season: 2027, next_week: 1 } })).toBe(
      "2027 · Week 1 · off-season",
    );
    expect(slateCaption({ ...off, shell: { season: 2026, next_season: null, next_week: null } })).toBe(
      "2026 · off-season",
    );
  });

  it("without a week the caption is just the counts", () => {
    expect(slateCaption(slate({ season: null, season_type: null, week: null, counts: { games: 0, picks: 0 } }))).toBe(
      "0 games · 0 picks",
    );
  });

  it("the legend prints the response's thresholds (D-055), not constants", () => {
    expect(slateLegend(RULES)).toBe(
      "Edge pill = clears 2.5 pts · Tier A ≥ 5.0 · B ≥ 3.5 · C ≥ 2.5 · Market = opening line, its moves, then now",
    );
    expect(slateLegend({ min_edge_pts: 4, min_prob: 0.55, tiers: { A: 6, B: 5, C: 4 } })).toBe(
      "Edge pill = clears 4.0 pts · Tier A ≥ 6.0 · B ≥ 5.0 · C ≥ 4.0 · Market = opening line, its moves, then now",
    );
  });

  it("with no rules the legend prints no threshold", () => {
    expect(slateLegend(null)).toBe("Market = opening line, its moves, then now");
  });
});


// ---------------------------------------------------------------------------------------------
// The record strip (TASK-057, F-32)

const live = (home: number, away: number, over: Partial<SlateGame> = {}) =>
  game({ status: "in_progress", home_points: home, away_points: away, ...over });

describe("liveCover (AC-2: a live pick is covering, on the number or not yet, never lost)", () => {
  it("a home favourite of 3.5 trailing by 7 is not yet, and needs 4+ to cover", () => {
    const g = live(0, 7, { pick: pick({ side: "home", line: -3.5 }) });
    expect(liveCover(g)).toEqual({ state: "not_yet", needs: 4 });
  });

  it("an away underdog at +1.5 ahead by 3 is covering; the cushion at 0 is on the number", () => {
    const covering = live(7, 10, { pick: pick({ side: "away", line: -1.5 }) });
    // away side line is the home spread flipped: home −1.5 → away +1.5
    expect(liveCover(covering)?.state).toBe("covering");
    const even = live(7, 10, { pick: pick({ side: "home", line: 3 }) });
    expect(liveCover(even)?.state).toBe("push");
  });

  it("is null for a game that isn't live or has no pick", () => {
    expect(liveCover(game({ pick: pick() }))).toBeNull();
    expect(liveCover(live(0, 0))).toBeNull();
  });
});

describe("recordStrip", () => {
  const won = game({ id: 1, status: "final", home_points: 30, away_points: 10, pick: pick({ result: "won", units: 0.91 }) });
  const iowa = live(14, 20, {
    id: 2,
    away: team("IOWA"),
    home: team("WIS"),
    pick: pick({ side: "away", line: -1.5, result: "pending" }),
  });
  const osu = live(0, 7, { id: 3, home: team("OSU"), away: team("PUR"), pick: pick({ side: "home", line: -27.5, result: "pending" }) });
  const upcoming = (id: number) => game({ id, pick: pick({ result: "pending" }) });
  const games = [osu, won, iowa, ...[4, 5, 6, 7, 8, 9].map(upcoming), game({ id: 10 })];

  it("reads 1-0 · 2 live (IOWA covering, OSU not yet) · 6 to play · +0.9u", () => {
    const strip = recordStrip(games);
    expect(strip.record).toBe("1-0");
    expect(strip.live).toBe(2);
    expect(strip.liveNote).toBe("IOWA covering, OSU not yet");
    expect(strip.toPlay).toBe(6);
    expect(strip.units).toBe("+0.9u");
  });

  it("has one segment per pick, graded first, then live (covering first), then to play", () => {
    const states = recordStrip(games).segments.map((s) => s.state);
    expect(states).toEqual(["won", "covering", "not_yet", ...Array(6).fill("to_play")]);
  });

  it("a trailing live pick is never a lost segment", () => {
    expect(recordStrip([osu]).segments[0].state).toBe("not_yet");
    expect(recordStrip([osu]).record).toBe("0-0");
  });

  it("leaves void picks out and counts a loss and a push in the record", () => {
    const lost = game({ id: 20, status: "final", pick: pick({ result: "lost", units: -1.1 }) });
    const push = game({ id: 21, status: "final", pick: pick({ result: "push", units: 0 }) });
    const voided = game({ id: 22, pick: pick({ result: "void" }) });
    const strip = recordStrip([lost, push, voided]);
    expect(strip.record).toBe("0-1-1");
    expect(strip.segments.map((s) => s.state)).toEqual(["lost", "push"]);
    expect(strip.units).toBe("−1.1u");
  });
});

describe("showingText", () => {
  it("prints both footers with their counts", () => {
    expect(showingText("all", { shown: 54, games: 54, picks: 9 })).toBe("Showing 54 of 54 games");
    expect(showingText("picks", { shown: 9, games: 54, picks: 9 })).toBe("9 games with a pick · of 54");
    expect(showingText("picks", { shown: 1, games: 54, picks: 1 })).toBe("1 game with a pick · of 54");
  });
});

describe("noPicksNote and offseasonNote", () => {
  const base = { week: 6, rules: RULES } as const;
  it("titles 'No picks yet' when no game has a line, 'No picks this week' when lines exist", () => {
    const noLine = game({ market: { opening_spread_home: null, current_spread_home: null, closing_spread_home: null, snapshots: [] } });
    expect(noPicksNote({ ...base, games: [noLine] }).title).toBe("No picks yet");
    const note = noPicksNote({ ...base, games: [game()] });
    expect(note.title).toBe("No picks this week");
    expect(note.body).toContain("2.5 pts");
  });

  it("the off-season copy names the shell's season and shows the next kickoff only when given", () => {
    expect(offseasonNote(2026, null).body).toContain("2026 season");
    expect(offseasonNote(2026, null).kickoff).toBeNull();
    expect(offseasonNote(2026, "2027-08-28T19:00:00Z", { season: 2027, week: 1 }).kickoff).toBe("Week 1 kicks off Sat Aug 28, 2027");
    expect(offseasonNote(2026, null, { season: 2027, week: 1 }).body).toBe(
      "The 2026 season has ended. The 2027 slate fills in when books post Week 1 lines, usually in early August.",
    );
  });

  it("names the title game's date when the response carries the last game's date (TASK-066)", () => {
    const next = { season: 2027, week: 1 };
    expect(offseasonNote(2026, null, next, undefined, "2026-10-10").body).toBe(
      "The 2026 season ended with the title game on Sat Oct 10. The 2027 slate fills in when books post Week 1 lines, usually in early August.",
    );
    // A date, not a moment: Sunday and the first of a month stay on their own day in any zone.
    expect(offseasonNote(2026, null, next, "Pacific/Auckland", "2027-01-17").body).toContain(
      "title game on Sun Jan 17.",
    );
    expect(offseasonNote(2026, null, next, undefined, null).body).toMatch(/^The 2026 season has ended\./);
    expect(offseasonNote(2026, null, next).body).toMatch(/^The 2026 season has ended\./);
  });
});

// ---------------------------------------------------------------------------------------------
// Stepping through weeks and a past season's market (TASK-061)

const W = (season: number, week: number, season_type: SlateWeek["season_type"] = "regular"): SlateWeek => ({
  season,
  season_type,
  week,
});

describe("parseWeekParams (the URL for a chosen week)", () => {
  it("reads ?season=2026&week=5 as that regular-season week and ?type=postseason as the postseason", () => {
    expect(parseWeekParams({ season: "2026", week: "5" })).toEqual(W(2026, 5));
    expect(parseWeekParams({ season: "2025", week: "1", type: "postseason" })).toEqual(W(2025, 1, "postseason"));
  });

  it("falls back (null) on a partial, non-numeric, out-of-range or repeated parameter", () => {
    expect(parseWeekParams({})).toBeNull();
    expect(parseWeekParams({ season: "2026" })).toBeNull();
    expect(parseWeekParams({ week: "5" })).toBeNull();
    expect(parseWeekParams({ season: "2026", week: "0" })).toBeNull();
    expect(parseWeekParams({ season: "2026", week: "5.5" })).toBeNull();
    expect(parseWeekParams({ season: "twenty", week: "5" })).toBeNull();
    expect(parseWeekParams({ season: "2026", week: "5", type: "bowl" })).toBeNull();
    expect(parseWeekParams({ season: ["2026", "2025"], week: "5" })).toBeNull();
  });
});

describe("weekHref", () => {
  it("sends the coming week to / and any other week to its query", () => {
    expect(weekHref(W(2026, 6), W(2026, 6))).toBe("/");
    expect(weekHref(W(2026, 5), W(2026, 6))).toBe("/?season=2026&week=5");
    expect(weekHref(W(2025, 1, "postseason"), W(2026, 6))).toBe("/?season=2025&week=1&type=postseason");
    expect(weekHref(W(2026, 5), null)).toBe("/?season=2026&week=5");
  });
});

describe("weekNeighbours (previous and next week with games, across seasons)", () => {
  const weeks = [W(2025, 14), W(2025, 15), W(2025, 1, "postseason"), W(2026, 1), W(2026, 2), W(2026, 6)];

  it("steps within a season and skips a week with no games", () => {
    expect(weekNeighbours(weeks, W(2026, 2))).toEqual({ previous: W(2026, 1), next: W(2026, 6) });
  });

  it("steps from one season into the previous season's postseason, and back", () => {
    expect(weekNeighbours(weeks, W(2026, 1))).toEqual({ previous: W(2025, 1, "postseason"), next: W(2026, 2) });
    expect(weekNeighbours(weeks, W(2025, 1, "postseason")).next).toEqual(W(2026, 1));
  });

  it("has no previous at the first week and no next at the last", () => {
    expect(weekNeighbours(weeks, W(2025, 14)).previous).toBeNull();
    expect(weekNeighbours(weeks, W(2026, 6)).next).toBeNull();
  });

  it("places a week that has no games between its neighbours", () => {
    expect(weekNeighbours(weeks, W(2026, 4))).toEqual({ previous: W(2026, 2), next: W(2026, 6) });
  });
});

describe("weekLabel", () => {
  it("names a regular week and the postseason", () => {
    expect(weekLabel(W(2026, 5))).toBe("2026 · Week 5");
    expect(weekLabel(W(2025, 1, "postseason"))).toBe("2025 · Postseason");
  });
});

describe("isPastWeek and isShownWeek", () => {
  const slate = (shown: SlateWeek | null, coming: SlateWeek | null) => ({
    season: shown?.season ?? null,
    season_type: shown?.season_type ?? null,
    week: shown?.week ?? null,
    shell: { season: coming?.season ?? null, season_type: coming?.season_type ?? null, week: coming?.week ?? null },
  });

  it("is past when the shown week is before the shell's coming week", () => {
    expect(isPastWeek(slate(W(2026, 5), W(2026, 6)))).toBe(true);
    expect(isPastWeek(slate(W(2025, 1, "postseason"), W(2026, 1)))).toBe(true);
    expect(isPastWeek(slate(W(2026, 6), W(2026, 6)))).toBe(false);
    expect(isPastWeek(slate(W(2026, 7), W(2026, 6)))).toBe(false);
  });

  it("is past for every week in the off-season, when there is no coming week", () => {
    expect(isPastWeek(slate(W(2026, 15), null))).toBe(true);
  });

  it("is not past when the response carries no shell block", () => {
    expect(isPastWeek({ season: 2026, season_type: "regular", week: 5, shell: null })).toBe(false);
  });

  it("is never past with no shown week", () => {
    expect(isPastWeek(slate(null, null))).toBe(false);
  });

  it("matches a listed week to the shown one", () => {
    expect(isShownWeek(W(2026, 5), W(2026, 5))).toBe(true);
    expect(isShownWeek(W(2026, 5), W(2026, 6))).toBe(false);
    expect(isShownWeek(W(2026, 5), null)).toBe(false);
  });
});

describe("rowView: a past week's market", () => {
  const final = {
    status: "final" as const,
    away_points: 20,
    home_points: 27,
    market: {
      opening_spread_home: -3.5,
      current_spread_home: -2.5,
      closing_spread_home: -2,
      snapshots: [
        { captured_at: "2026-10-01T00:00:00Z", spread_home: -3 },
        { captured_at: "2026-10-05T00:00:00Z", spread_home: -2.5 },
      ],
    },
  };

  it("draws a final game open → close as the past variant, ignoring the snapshots", () => {
    const row = rowView(game(final), RULES, ET, true);
    expect(row.market).toEqual({ opener: -3.5, snapshots: [], current: -2, past: true });
    expect(row.hasLine).toBe(true);
  });

  it("falls back to the current line when a final has no close", () => {
    const row = rowView(
      game({ ...final, market: { ...final.market, closing_spread_home: null } }),
      RULES,
      ET,
      true,
    );
    expect(row.market).toMatchObject({ current: -2.5, past: true });
  });

  it("keeps the usual cell for a game that isn't final, and in the coming week", () => {
    expect(rowView(game({ ...final, status: "postponed" }), RULES, ET, true).market.past).toBe(false);
    const usual = rowView(game(final), RULES, ET, false);
    expect(usual.market).toEqual({ opener: -3.5, snapshots: [-3, -2.5], current: -2.5, past: false });
  });

  it("a final game with no line at all draws no line", () => {
    const bare = game({
      status: "final",
      away_points: 1,
      home_points: 2,
      market: { opening_spread_home: null, current_spread_home: null, closing_spread_home: null, snapshots: [] },
    });
    expect(rowView(bare, RULES, ET, true).market).toEqual({ opener: null, snapshots: [], current: null, past: true });
  });
});
