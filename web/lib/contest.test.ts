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
} from "./contest";

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
