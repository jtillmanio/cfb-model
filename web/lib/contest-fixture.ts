// Test data for the Contest screen's helpers and components (TASK-073): the fixture week from
// design/handoff/designs/contest-data.js (Splash work league, 2026 Week 6), shaped as the API's
// `ContestPageOut`. Not imported by app code.

import type { ContestGame, ContestPage, ContestRules } from "./contest";

type Team = ContestGame["home"];

let nextTeam = 1;
function team(school: string, abbreviation: string, rank: number | null = null): Team {
  return { id: nextTeam++, school, abbreviation, color: "#336699", logo_url: null, rank, division: null };
}

const T = {
  UNLV: team("UNLV", "UNLV"),
  BSU: team("Boise State", "BSU"),
  PUR: team("Purdue", "PUR"),
  OSU: team("Ohio State", "OSU", 1),
  MISS: team("Ole Miss", "MISS", 6),
  LSU: team("LSU", "LSU", 9),
  ND: team("Notre Dame", "ND", 7),
  STAN: team("Stanford", "STAN"),
  TEX: team("Texas", "TEX", 2),
  OU: team("Oklahoma", "OU", 4),
  COLO: team("Colorado", "COLO"),
  BYU: team("BYU", "BYU", 20),
  BUF: team("Buffalo", "BUF"),
  NYJ: team("NY Jets", "NYJ"),
  HOU: team("Houston", "HOU"),
  JAX: team("Jacksonville", "JAX"),
  KC: team("Kansas City", "KC"),
  BAL: team("Baltimore", "BAL"),
  NYG: team("NY Giants", "NYG"),
  PHI: team("Philadelphia", "PHI"),
};

/** Minutes from Thu 2026-10-08 00:00 ET, the design's clock, as an ISO instant. */
export function at(minutes: number): string {
  return new Date(Date.UTC(2026, 9, 8, 4, 0) + minutes * 60_000).toISOString();
}

export const NOW = { thu: 1320, fri: 2652, sat: 3735, sun: 5560, after: 6000 } as const;
export type Now = keyof typeof NOW;

// cA / mA: the contest / market spread for the AWAY team (the design's convention). `side` is the
// model's side (CFB) or the side the contest line favors (NFL).
type Def = {
  id: number;
  away: Team;
  home: Team;
  kick: number;
  cA: number;
  mA: number;
  side: "away" | "home" | null;
  cover: number;
  /** The edge in points on the model's side; the API sends it signed (> 0 likes home). */
  edge?: number;
  margin?: number; // pred_margin: home − away
  neutral?: boolean;
  implied?: number;
};

const DEFS: Def[] = [
  { id: 1, away: T.UNLV, home: T.BSU, kick: 2640, cA: 10, mA: 10, side: "away", cover: 52, edge: 0.9, margin: 9.1 },
  { id: 2, away: T.PUR, home: T.OSU, kick: 3600, cA: 27, mA: 27.5, side: "home", cover: 60, edge: 4.2, margin: 31.2 },
  { id: 3, away: T.MISS, home: T.LSU, kick: 3810, cA: 3, mA: 3.5, side: "away", cover: 61, edge: 4.4, margin: -1.4 },
  { id: 4, away: T.ND, home: T.STAN, kick: 3810, cA: -17.5, mA: -17, side: "away", cover: 55, edge: 2.4, margin: -19.9 },
  { id: 5, away: T.TEX, home: T.OU, kick: 4050, cA: -7, mA: -6.5, side: "home", cover: 64, edge: 5.7, margin: -1.3, neutral: true },
  { id: 6, away: T.COLO, home: T.BYU, kick: 4230, cA: 5.5, mA: 6, side: "home", cover: 59, edge: 3.6, margin: 9.1 },
  { id: 7, away: T.BUF, home: T.NYJ, kick: 5100, cA: -3, mA: -4.5, side: "away", cover: 54 },
  { id: 8, away: T.HOU, home: T.JAX, kick: 5100, cA: -1, mA: -1.5, side: "away", cover: 51 },
  { id: 9, away: T.KC, home: T.BAL, kick: 5305, cA: 2.5, mA: 2.5, side: null, cover: 50 },
  { id: 10, away: T.NYG, home: T.PHI, kick: 5540, cA: 6, mA: 7, side: "home", cover: 53 },
];

const NFL_IDS = new Set([7, 8, 9, 10]);

/** The week's ten games as the API serves them at `now`: the open games in rank order, then the
 *  locked ones, with each game's `top_n` and `next_best` as the API sets them (D-095). */
export function weekGames(now: Now = "thu", picksPerPeriod = 4): ContestGame[] {
  const clock = NOW[now];
  const rows = DEFS.map((d) => {
    const nfl = NFL_IDS.has(d.id);
    const locked = d.kick <= clock;
    const gap = d.cA - d.mA;
    const game: ContestGame = {
      id: d.id,
      sport_id: nfl ? "nfl" : "cfb",
      kickoff_at: at(d.kick),
      game_date: at(d.kick).slice(0, 10),
      locks_at: at(d.kick),
      status: locked ? "in_progress" : "scheduled",
      neutral_site: d.neutral ?? false,
      venue: null,
      away: d.away,
      home: d.home,
      away_points: null,
      home_points: null,
      contest_line_id: 100 + d.id,
      contest_spread_home: -d.cA,
      contest_captured_at: at(NOW.thu - 50),
      market_spread_home: -d.mA,
      differs: gap !== 0,
      locked,
      no_model: nfl,
      model: nfl
        ? null
        : { side: d.side as "home" | "away", cover_prob: d.cover / 100, edge: (d.side === "home" ? 1 : -1) * (d.edge ?? 0), pred_margin: d.margin ?? 0 },
      market_gap: nfl
        ? { points: Math.abs(gap), side: gap === 0 ? null : gap > 0 ? "away" : "home", implied_prob: d.cover / 100 }
        : null,
      rank: 0,
      top_n: false,
      next_best: false,
    };
    return game;
  });
  const order = (a: ContestGame, b: ContestGame) => {
    const pa = a.model?.cover_prob ?? a.market_gap?.implied_prob ?? 0.5;
    const pb = b.model?.cover_prob ?? b.market_gap?.implied_prob ?? 0.5;
    return pb - pa || Math.abs(b.model?.edge ?? 0) - Math.abs(a.model?.edge ?? 0);
  };
  const open = rows.filter((g) => !g.locked).sort(order);
  const locked = rows.filter((g) => g.locked).sort(order);
  const allLocked = open.length === 0;
  const ranking = allLocked ? [...locked] : open;
  const everything = [...rows].sort(order);
  let taken = 0;
  let last = -1;
  ranking.forEach((g, i) => {
    if (taken < picksPerPeriod && g.model) {
      g.top_n = true;
      taken += 1;
      last = i;
    }
  });
  if (!allLocked && taken === picksPerPeriod && last + 1 < ranking.length) ranking[last + 1].next_best = true;
  open.forEach((g, i) => (g.rank = i + 1));
  locked.forEach((g) => (g.rank = allLocked ? ranking.indexOf(g) + 1 : everything.indexOf(g) + 1));
  return [...open, ...locked];
}

export const RULES: ContestRules = {
  sports: ["cfb", "nfl"],
  picks_per_period: 4,
  picks_exact: true,
  scoring: "point_per_win",
  push: "zero",
  lock: "per_game_kickoff",
};

const tally = (wins: number, losses: number, pending = 0) => ({ wins, losses, pushes: 0, voids: 0, pending, points: wins });

/** The fixture's page at `now`: your two picks (OU +7 at Thu 9:14 PM, BUF −3 at 9:20 PM). */
export function weekPage(now: Now = "thu"): ContestPage {
  const games = weekGames(now);
  return {
    contest: { id: 1, name: "Splash work league", platform: "splash", season: 2026, rules: RULES },
    counts: { differs: games.filter((g) => g.differs).length, entries: 2, games: games.length },
    entries: [
      { id: 11, game_id: 5, side: "home", contest_line_id: 105, line: 7, created_at: at(NOW.thu - 46) },
      { id: 12, game_id: 7, side: "away", contest_line_id: 107, line: 3, created_at: at(NOW.thu - 40) },
    ],
    games,
    period: 6,
    periods: [1, 2, 3, 4, 5, 6],
    results: {
      season: { you: tally(12, 8), model: tally(11, 9) },
      this_week: { you: tally(0, 0, 2), model: tally(0, 0, 4) },
      weeks: [
        { period: 1, you: tally(3, 1), model: tally(2, 2) },
        { period: 2, you: tally(2, 2), model: tally(3, 1) },
        { period: 3, you: tally(3, 1), model: tally(2, 2) },
        { period: 4, you: tally(1, 3), model: tally(2, 2) },
        { period: 5, you: tally(3, 1), model: tally(2, 2) },
      ],
    },
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
    standing: {
      id: 1,
      period: 5,
      position: 3,
      field_size: 14,
      points_behind_leader: 1,
      note: null,
      entered_at: at(NOW.thu - 2000),
    },
  };
}
