import { describe, expect, it } from "vitest";

import {
  aliasMappings,
  canConfirm,
  contestWeek,
  type ContestPage,
  type ContestRules,
  importSummary,
  type ImportPreview,
  type ImportRow,
  type ImportTeam,
  lockNote,
  movedRows,
  movedTitle,
  rawLines,
  refusalCopy,
  rowLine,
  rowStatus,
  rowState,
  rulesLine,
  teamName,
  weekSource,
  type ContestGame,
  applyTap,
  copyText,
  cutoffLabel,
  differsCount,
  fillFromModel,
  filterGames,
  impliedText,
  lineChip,
  nextBestText,
  nflGapText,
  rankedSide,
  rulesRows,
  rulesSentence,
  seasonCards,
  sharedCount,
  sideLabel,
  slateLayout,
  standingText,
  tapOutcome,
  trayCard,
  weekRows,
  weekSummary,
} from "./contest";
import { RULES as FIXTURE_RULES, weekGames, weekPage } from "./contest-fixture";

// The fixture's Week 6 paste (TASK-070, D-172): nine rows match, and "Hou Texans" @ "Jax" doesn't.

function team(id: number, sport: string, school: string, abbreviation: string, mascot: string | null = null): ImportTeam {
  return { id, sport_id: sport, school, mascot, abbreviation, color: "#000000" };
}

const HOU = team(31, "nfl", "Houston", "HOU", "Texans");
const JAX = team(32, "nfl", "Jacksonville", "JAX", "Jaguars");
const TEX = team(1, "cfb", "Texas", "TEX");
const OU = team(2, "cfb", "Oklahoma", "OU");

function row(index: number, over: Partial<ImportRow> = {}): ImportRow {
  return {
    index,
    first_line: 9 + index * 10,
    last_line: 18 + index * 10,
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
    { name: "Hou Texans", candidates: [HOU] },
    { name: "Jax", candidates: [JAX, HOU] },
  ],
});

function preview(rows: ImportRow[], over: Partial<ImportPreview> = {}): ImportPreview {
  return {
    contest_id: 7,
    period: 6,
    lock_at: "2026-10-12T00:20:00Z",
    rows,
    counts: { rows: rows.length, matched: 0, unmatched: 0, problem: 0 },
    changes: [],
    ...over,
  };
}

const WEEK6 = preview([
  row(0, { game_date: "2026-10-09" }),
  ...Array.from({ length: 4 }, (_, i) => row(i + 1)),
  row(5),
  ...Array.from({ length: 3 }, (_, i) => row(i + 6, { sport_id: "nfl", game_date: "2026-10-11" })),
  UNMATCHED,
]);

const RULES: ContestRules = {
  sports: ["cfb", "nfl"],
  picks_per_period: 4,
  picks_exact: true,
  scoring: "point_per_win",
  push: "zero",
  lock: "per_game_kickoff",
};

describe("AC-1: the paste's summary, and Confirm disabled with a row unmatched", () => {
  it("reads 9 rows match · 1 unmatched across the paste's three days", () => {
    expect(importSummary(WEEK6, {})).toEqual({
      found: "Found 10 games",
      dates: "Fri Oct 9 – Sun Oct 11",
      sports: "6 CFB · 4 NFL",
      matched: "9 rows match",
      unmatched: "1 unmatched",
      games: 10,
    });
    expect(canConfirm(WEEK6, {})).toBe(false);
  });

  it("marks the unmatched row and writes its line from each side", () => {
    expect(rowState(UNMATCHED, {})).toBe("needs");
    expect(rowStatus(UNMATCHED, {})).toEqual({ text: "Needs team", tone: "neg" });
    expect(rowLine(UNMATCHED)).toBe("−1 / +1");
    expect(rowLine(row(0))).toBe("TEX −7");
  });

  it("underlines the names still to pick in the raw paste and greys what wasn't read", () => {
    const text = ["Pick against the spread", ...Array.from({ length: 98 }, () => "x"), "Hou Texans", "Jax", "-1"].join(
      "\n",
    );
    const lines = rawLines(text, [UNMATCHED], {});
    expect(lines).toHaveLength(102);
    expect(lines[0]).toEqual({ n: 1, text: "Pick against the spread", read: false, bad: false, row: null });
    expect(lines[99]).toMatchObject({ n: 100, read: true, bad: true, row: 9 });
    expect(lines[97]).toMatchObject({ n: 98, read: false, bad: false, row: null });
    expect(lines[101]).toMatchObject({ n: 102, read: true, bad: false });
    expect(rawLines(text, [UNMATCHED], { "Hou Texans": 31 })[99].bad).toBe(false);
  });

  it("names Splash's lock time beside the contest's per-game lock", () => {
    expect(lockNote(WEEK6, RULES)).toBe(
      "Splash's “Picks lock: Sun 8:20 PM” is read as the last kickoff; your rules lock each game at its own kickoff.",
    );
    expect(lockNote(WEEK6, { ...RULES, lock: "fixed_time" })).toBeNull();
  });
});

describe("AC-2: picking both names enables Confirm and saves them as aliases", () => {
  it("needs every name the row couldn't match", () => {
    expect(canConfirm(WEEK6, { "Hou Texans": 31 })).toBe(false);
    const picks = { "Hou Texans": 31, Jax: 32 };
    expect(rowState(UNMATCHED, picks)).toBe("fixed");
    expect(rowStatus(UNMATCHED, picks)).toEqual({ text: "Fixed", tone: "pos" });
    expect(importSummary(WEEK6, picks)).toMatchObject({ matched: "10 rows match", unmatched: null });
    expect(canConfirm(WEEK6, picks)).toBe(true);
    expect(aliasMappings(WEEK6, { ...picks, Other: 9 })).toEqual([
      { alias: "Hou Texans", team_id: 31 },
      { alias: "Jax", team_id: 32 },
    ]);
  });

  it("can't confirm a row the picker can't fix, or one with no line", () => {
    for (const blocked of [
      row(0, { status: "no_game", game_id: null }),
      row(0, { status: "duplicate" }),
      row(0, { status: "problem", problem: "no line", spread_home: null }),
    ]) {
      expect(canConfirm(preview([blocked]), {})).toBe(false);
      expect(rowState(blocked, {})).toBe("blocked");
    }
    expect(rowStatus(row(0, { status: "no_game" }), {}).text).toBe("No game that day");
    expect(rowStatus(row(0, { status: "problem", problem: "lines disagree" }), {}).text).toBe("Lines disagree");
    expect(canConfirm(preview([]), {})).toBe(false);
    expect(canConfirm(null, {})).toBe(false);
  });

  it("names NFL teams by city and nickname, CFB teams by school", () => {
    expect(teamName(HOU)).toBe("Houston Texans");
    expect(teamName(TEX)).toBe("Texas");
    expect(teamName(team(33, "nfl", "NY Jets", "NYJ", "Jets"))).toBe("NY Jets");
  });
});

describe("the week the page is about", () => {
  const shell = { season: 2026, season_type: "regular", week: 6 } as ContestPage["shell"];
  const contest = { season: 2026 } as ContestPage["contest"];

  it("pastes the coming week when it has no lines, else shows the newest week", () => {
    expect(contestWeek({ contest, shell, period: null })).toEqual({ paste: true, period: 6 });
    expect(contestWeek({ contest, shell, period: 5 })).toEqual({ paste: true, period: 6 });
    expect(contestWeek({ contest, shell, period: 6 })).toEqual({ paste: false, period: 6 });
    expect(contestWeek({ contest, shell, period: 7 })).toEqual({ paste: false, period: 7 });
  });

  it("out of the contest's regular season, shows its newest week, or pastes week 1 with none", () => {
    const post = { ...shell, season_type: "postseason" } as ContestPage["shell"];
    expect(contestWeek({ contest, shell: post, period: 12 })).toEqual({ paste: false, period: 12 });
    const next = { ...shell, season: 2027, week: 1 } as ContestPage["shell"];
    expect(contestWeek({ contest, shell: next, period: null })).toEqual({ paste: true, period: 1 });
  });

  it("writes the header's rules line and the confirmed week's source", () => {
    expect(rulesLine(RULES, 6)).toBe(
      "Week 6 · Pick 4 · CFB + NFL · each game locks at its kickoff · 1 pt per correct pick · push = 0",
    );
    const games = [
      { contest_captured_at: "2026-10-09T01:10:00Z" },
      { contest_captured_at: "2026-10-09T02:00:00Z" },
    ] as ContestGame[];
    expect(weekSource(games)).toBe("From Splash paste · Thu 10:00 PM · 2 games");
  });
});

describe("AC-3: a paste the API refused says what was read and that nothing was saved", () => {
  it("C2a: nothing parseable", () => {
    expect(refusalCopy({ code: "unparseable", message: "", rows: [] }, "hello\n\n", RULES.sports)).toEqual({
      title: "Couldn't find any games in that paste",
      body:
        "We read 1 line but none looked like a matchup with a spread. This is usually Splash's My Entries or " +
        "Standings page. Open the league's Pick against the spread page, select all and copy again.",
      meta: "1 line read · 0 games · nothing saved",
    });
  });

  it("C2b: games, but no team matched", () => {
    const nba = [
      row(0, { away_name: "Celtics", home_name: "Knicks", status: "unmatched" }),
      row(1, { away_name: "Lakers", home_name: "Warriors", status: "unmatched" }),
      row(2, { away_name: "Nuggets", home_name: "Suns", status: "unmatched" }),
    ];
    expect(refusalCopy({ code: "no_match", message: "", rows: nba }, "", RULES.sports)).toEqual({
      title: "Found 3 games, but no team matched",
      body:
        "Celtics, Knicks, Lakers, Warriors, Nuggets and Suns aren't college football or NFL teams. This contest " +
        "is CFB + NFL; check you copied the right league.",
      meta: "3 games read · 0 of 6 teams matched · nothing saved",
    });
  });

  it("leaves another refusal to the caller", () => {
    expect(refusalCopy({ code: "unresolved", message: "x", rows: [] }, "", RULES.sports)).toBeNull();
  });
});

describe("AC-4: a re-paste lists each moved line, old then new", () => {
  it("writes each change on the favorite's side, in page order", () => {
    const moved = preview([row(0), row(1, { spread_home: -2.5 })], {
      changes: [
        {
          index: 0,
          game_id: 100,
          contest_line_id: 1,
          old_spread_home: 7,
          old_captured_at: "2026-10-09T02:00:00Z",
          new_spread_home: 6.5,
        },
        {
          index: 1,
          game_id: 101,
          contest_line_id: 2,
          old_spread_home: 1,
          old_captured_at: "2026-10-09T01:10:00Z",
          new_spread_home: -2.5,
        },
      ],
    });
    expect(movedRows(moved).map(({ index, was, now }) => ({ index, was, now }))).toEqual([
      { index: 0, was: "TEX −7", now: "TEX −6.5" },
      { index: 1, was: "TEX −1", now: "OU −2.5" },
    ]);
    expect(movedTitle(moved.changes)).toBe("2 contest lines moved since Thu 10:00 PM");
    expect(movedRows(WEEK6)).toEqual([]);
  });
});

// TASK-073: the ranked slate, the pick tray and the results.

const byId = (games: readonly ContestGame[], id: number) => games.find((g) => g.id === id)!;
const entries = () => weekPage().entries;

describe("AC-1: the slate, the cutoff under row 4 and the next best", () => {
  it("lists the open games in the response's order, the top 4 above the cutoff, then the locked", () => {
    const layout = slateLayout(weekGames("fri"));
    expect(layout.open.map((g) => g.rank)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9]);
    expect(layout.cutoffAfter?.id).toBe(layout.open[3].id);
    expect(layout.locked.map((g) => g.away.abbreviation)).toEqual(["UNLV"]);
    expect(layout.nextBest?.away.abbreviation).toBe("ND");
    expect(layout.allLocked).toBe(false);
  });

  it("puts the cutoff after the last top-N row even when an NFL row ranks above it", () => {
    const games = weekGames("thu");
    const nfl = games.find((g) => g.sport_id === "nfl")!;
    const rest = games.filter((g) => g !== nfl);
    // An NFL row at rank 2 is not one of the model's picks; the cutoff stays under the 4th pick.
    const layout = slateLayout([rest[0], nfl, ...rest.slice(1)]);
    expect(layout.cutoffAfter).toBe(rest[3]);
  });

  it("reads 'Next best #5' from the flagged row: its side's line and cover %", () => {
    const layout = slateLayout(weekGames("thu"));
    expect(nextBestText(layout.nextBest!)).toEqual({ rank: 5, line: "ND −17.5", cover: "55%" });
  });

  it("labels the cutoff for the whole slate until a game kicks off (D-174), then for the open games", () => {
    expect(cutoffLabel(slateLayout(weekGames("thu")), 4)).toBe("Model's top 4");
    expect(cutoffLabel(slateLayout(weekGames("sat")), 4)).toBe("Model's top 4 · open games");
  });

  it("has no cutoff or next best once every game is locked, only the locked list", () => {
    const layout = slateLayout(weekGames("after"));
    expect(layout.allLocked).toBe(true);
    expect(layout.open).toEqual([]);
    expect(layout.cutoffAfter).toBeNull();
    expect(layout.nextBest).toBeNull();
    expect(layout.locked).toHaveLength(10);
  });

  it("reads an NFL row's gap and implied probability from the response", () => {
    const games = weekGames("thu");
    expect(nflGapText(byId(games, 7))).toBe("1.5 pts off mkt → BUF");
    expect(nflGapText(byId(games, 10))).toBe("1 pt off mkt → PHI");
    expect(nflGapText(byId(games, 9))).toBe("No gap to market");
    expect(nflGapText(byId(games, 5))).toBeNull();
    expect(impliedText(byId(games, 7))).toBe("~54%");
    expect(impliedText(byId(games, 5))).toBeNull();
  });

  it("labels each side as the bet from that side", () => {
    const ou = byId(weekGames("thu"), 5);
    expect(sideLabel(ou, "home")).toBe("OU +7");
    expect(sideLabel(ou, "away")).toBe("TEX −7");
    expect(rankedSide(ou)).toBe("home");
    expect(rankedSide(byId(weekGames("thu"), 7))).toBe("away");
    expect(rankedSide(byId(weekGames("thu"), 9))).toBeNull();
  });
});

describe("AC-2: the ≠ chip, its tone and the 'Line ≠ market' filter", () => {
  const games = weekGames("thu");

  it("names the side the contest line favors and the points, blue when it is the ranked side", () => {
    // OU: contest TEX −7, market TEX −6.5, so the contest gives OU half a point; the model likes OU.
    expect(lineChip(byId(games, 5))).toEqual({ text: "≠ OU +0.5", tone: "better" });
    // PHI: contest PHI −6 vs market PHI −7: the contest line gives PHI a point; the ranked side is PHI.
    expect(lineChip(byId(games, 10))).toEqual({ text: "≠ PHI +1", tone: "better" });
  });

  it("is orange when the difference favors the other side than the ranked one", () => {
    // LSU: contest MISS −3 vs market MISS −3.5 gives LSU half a point; the model likes MISS.
    expect(lineChip(byId(games, 3))).toEqual({ text: "≠ LSU +0.5", tone: "worse" });
    expect(lineChip(byId(games, 4))).toEqual({ text: "≠ STAN +0.5", tone: "worse" });
  });

  it("has no chip for a line that matches the market", () => {
    expect(lineChip(byId(games, 1))).toBeNull();
    expect(lineChip(byId(games, 9))).toBeNull();
  });

  it("counts the flagged rows from the flag (8 in the fixture) and filters to exactly them", () => {
    expect(differsCount(games)).toBe(8);
    const flagged = filterGames(games, "differs");
    expect(flagged).toHaveLength(8);
    expect(flagged.every((g) => g.differs)).toBe(true);
    expect(filterGames(games, "all")).toHaveLength(10);
    expect(filterGames(games, "cfb")).toHaveLength(6);
    expect(filterGames(games, "nfl")).toHaveLength(4);
  });
});

describe("AC-3: tapping a side adds, removes or switches a pick", () => {
  const games = weekGames("thu");
  const mine = entries();
  const lsu = byId(games, 3);
  const NOW_ISO = "2026-10-09T02:00:00.000Z";

  it("adds on a tap of an unpicked game", () => {
    expect(tapOutcome([], lsu, "away", 4)).toBe("add");
    const next = applyTap(mine, lsu, "away", "add", NOW_ISO);
    expect(next.map((e) => [e.game_id, e.side])).toEqual([[5, "home"], [7, "away"], [3, "away"]]);
    expect(next[2]).toMatchObject({ line: lsu.contest_spread_home, created_at: NOW_ISO });
  });

  it("removes on a second tap of the same side, and switches on a tap of the other", () => {
    const ou = byId(games, 5);
    expect(tapOutcome(mine, ou, "home", 4)).toBe("remove");
    expect(applyTap(mine, ou, "home", "remove", NOW_ISO).map((e) => e.game_id)).toEqual([7]);
    expect(tapOutcome(mine, ou, "away", 4)).toBe("switch");
    const switched = applyTap(mine, ou, "away", "switch", NOW_ISO);
    expect(switched.map((e) => [e.game_id, e.side])).toEqual([[5, "away"], [7, "away"]]);
  });

  it("refuses a new pick when the week is full, but still allows a switch or a remove", () => {
    const full = applyTap(applyTap(mine, lsu, "away", "add", NOW_ISO), byId(games, 2), "home", "add", NOW_ISO);
    expect(full).toHaveLength(4);
    expect(tapOutcome(full, byId(games, 6), "home", 4)).toBe("full");
    expect(tapOutcome(full, lsu, "home", 4)).toBe("switch");
    expect(tapOutcome(full, lsu, "away", 4)).toBe("remove");
  });

  it("refuses a locked game", () => {
    expect(tapOutcome([], byId(weekGames("fri"), 1), "away", 4)).toBe("locked");
  });

  it("fills the open slots from the open top 4, on the model's side, skipping what you picked", () => {
    expect(fillFromModel(games, mine, 4).map((f) => [f.game.id, f.side])).toEqual([
      [3, "away"],
      [2, "home"],
    ]);
    expect(fillFromModel(games, [], 4).map((f) => f.game.id)).toEqual([5, 3, 2, 6]);
    expect(fillFromModel(games, mine.slice(0, 1), 2).map((f) => f.game.id)).toEqual([3]);
  });

  it("writes the clipboard text: the contest and week, then a line per pick in tray order", () => {
    expect(copyText("Splash work league", 6, mine, games)).toBe(
      "Splash work league · Week 6\n" +
        "OU +7 (Texas vs Oklahoma, Sat 7:30 PM)\n" +
        "BUF −3 (Buffalo @ NY Jets, Sun 1:00 PM)",
    );
  });

  it("explains each pick in the tray: model match, against the model, or your call", () => {
    const [ou, buf] = mine;
    expect(trayCard(byId(games, 5), ou, 4)).toMatchObject({
      badge: "Model #1",
      match: true,
      lockedIn: "Locked in at OU +7 · Thu 9:14 PM",
      why: "Model's #1 pick · 64% to cover",
    });
    expect(trayCard(byId(games, 7), buf, 4)).toMatchObject({
      badge: "Your call",
      match: false,
      lockedIn: "Locked in at BUF −3 · Thu 9:20 PM",
      why: "Not in model's top 4 · No model yet (NFL) · contest 1.5 pts better than market · ~54% mkt-implied",
    });
    expect(trayCard(byId(games, 5), { ...ou, side: "away" }, 4)).toMatchObject({
      badge: "Against model",
      why: "Model has the other side (OU +7)",
    });
    expect(trayCard(byId(games, 4), { ...ou, game_id: 4, side: "away", line: 17.5 }, 4).why).toBe(
      "Not in model's top 4 · Model ranks it #5 · 55% to cover",
    );
    // A pick still being saved has no stored line or time, so it is not "locked in" yet.
    const stand = applyTap([], byId(games, 3), "away", "add", NOW_ISO)[0];
    expect(trayCard(byId(games, 3), stand, 4).lockedIn).toBe("Saving MISS +3…");
    expect(sharedCount(mine, games)).toBe(1);
  });
});

describe("AC-5: season, weeks and standing, as the response has them", () => {
  const page = weekPage();

  it("writes the season cards and the week's points", () => {
    expect(seasonCards(page.results!, 4)).toEqual({
      you: { label: "You", record: "12-8", rate: "60.0%" },
      model: { label: "Model top 4", record: "11-9", rate: "55.0%" },
      diff: "+1",
    });
    expect(weekSummary(page.results!.this_week)).toMatchObject({
      you: { points: "0 pts", pending: 2 },
      model: { points: "0 pts", pending: 4 },
    });
  });

  it("lists the weeks W1 to W5 with a running total", () => {
    const rows = weekRows(page.results!);
    expect(rows.map((r) => [r.label, r.youRecord, r.modelRecord, r.diff])).toEqual([
      ["W1", "3-1", "2-2", "+1"],
      ["W2", "2-2", "3-1", "−1"],
      ["W3", "3-1", "2-2", "+1"],
      ["W4", "1-3", "2-2", "−1"],
      ["W5", "3-1", "2-2", "+1"],
    ]);
    expect(rows.map((r) => [r.cumulativeYou, r.cumulativeModel])).toEqual([
      [3, 2],
      [5, 5],
      [8, 7],
      [9, 9],
      [12, 11],
    ]);
  });

  it("says where you stand, and how far behind", () => {
    expect(standingText(page.standing)).toEqual({ place: "3rd of 14", behind: "1 pt behind 1st" });
    expect(standingText({ ...page.standing!, position: 1, points_behind_leader: 0 })).toEqual({
      place: "1st of 14",
      behind: "Leading",
    });
    expect(standingText({ ...page.standing!, position: 2, points_behind_leader: 2.5 })?.behind).toBe(
      "2.5 pts behind 1st",
    );
    expect(standingText(null)).toBeNull();
  });

  it("lists the contest's rules as rows and a plain-English paragraph", () => {
    expect(rulesRows(FIXTURE_RULES)).toEqual([
      ["Sports", "CFB + NFL"],
      ["Picks per week", "Exactly 4"],
      ["Lock", "Each game locks at its kickoff"],
      ["Scoring", "1 point per correct pick"],
      ["Push", "A push scores 0"],
    ]);
    expect(rulesSentence(FIXTURE_RULES)).toBe(
      "Pick exactly 4 games from CFB + NFL. Each game locks at its own kickoff, so you can change a pick until then. " +
        "A correct pick scores 1 point; a push scores 0.",
    );
    expect(rulesRows({ ...FIXTURE_RULES, picks_exact: false, lock: "fixed_time", push: "half" })).toContainEqual([
      "Picks per week",
      "Up to 4",
    ]);
  });
});
