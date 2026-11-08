import type { ResultState } from "@/components/result-marker";
import type { Tier } from "@/components/tier-badge";

import type { components } from "./api-types";
import {
  formatBet,
  formatClockTime,
  formatCoverPct,
  formatLineNumber,
  formatModelLine,
  formatRecord,
  formatThreshold,
  formatUnits,
  formatWinPct,
  signed,
  zoneLabel,
} from "./format";

// This Week (S-01, TASK-056): what the page derives from the `/slate` response before drawing it.
// Pure and clock-free: kickoffs are fixed instants and the zone is passed in, so tests need
// neither a clock nor a DOM. Thresholds come from the response's `rules` (D-055), never a
// constant here.

export type Slate = components["schemas"]["SlateOut"];
export type SlateGame = components["schemas"]["SlateGameOut"];
export type SlateRules = components["schemas"]["SlateRulesOut"];
export type SlateWeek = components["schemas"]["SlateWeekOut"];

/** Every time on the page is Eastern until Settings' time zone lands (M8.8), as the shell's. */
export const SLATE_ZONE = "America/New_York";

// ---------------------------------------------------------------------------------------------
// Windows

export type SlateWindow = {
  key: string;
  /** `FRI NIGHT`. */
  label: string;
  /** `Fri 10/9 · 8:00 PM ET` on a day's first window, then `3:30 PM ET` or `7:00 – 10:30 PM ET`. */
  time: string;
  games: SlateGame[];
};

const BANDS = ["MORNING", "NOON", "AFTERNOON", "NIGHT"] as const;

/** Morning before 11:00 AM, noon 11:00 AM–1:59 PM, afternoon 2:00–5:59 PM, night from 6:00 PM. */
function bandOf(hour: number): number {
  if (hour < 11) return 0;
  if (hour < 14) return 1;
  if (hour < 18) return 2;
  return 3;
}

type LocalParts = { date: string; weekday: string; shortDate: string; hour: number };

function localParts(iso: string, zone: string): LocalParts {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: zone,
    year: "numeric",
    month: "numeric",
    day: "numeric",
    weekday: "short",
    hour: "numeric",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const month = get("month");
  const day = get("day");
  return {
    date: `${get("year")}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`,
    weekday: get("weekday"),
    shortDate: `${month}/${day}`,
    hour: Number(get("hour")),
  };
}

type Bucket = { sort: string; label: string; date: string; shortDate: string; games: SlateGame[]; tba: boolean };

/** `7:00 – 10:30 PM ET`: one time, or a range that prints the day period once when it is shared. */
function timeRange(first: string, last: string, zone: string, at: string): string {
  const label = zoneLabel(new Date(at), zone);
  if (first === last) return `${first} ${label}`;
  const [firstTime, firstPeriod] = first.split(" ");
  const lastPeriod = last.split(" ")[1];
  const start = firstPeriod === lastPeriod ? firstTime : first;
  return `${start} – ${last} ${label}`;
}

/**
 * The slate's rows grouped by the design's day/time windows, in kickoff order. A TBA kickoff
 * has no time to band, so it joins a last window for its `game_date`.
 */
export function slateWindows(games: SlateGame[], zone: string = SLATE_ZONE): SlateWindow[] {
  const buckets = new Map<string, Bucket>();
  for (const game of games) {
    let key: string;
    let bucket: Bucket;
    if (game.kickoff_at === null) {
      key = `tba-${game.game_date}`;
      const [year, month, day] = game.game_date.split("-").map(Number);
      const noon = new Date(Date.UTC(year, month - 1, day, 12)).toISOString();
      const parts = localParts(noon, "UTC");
      bucket = buckets.get(key) ?? {
        sort: `${game.game_date}-9`,
        label: `${parts.weekday.toUpperCase()} TBA`,
        date: game.game_date,
        shortDate: parts.shortDate,
        games: [],
        tba: true,
      };
    } else {
      const parts = localParts(game.kickoff_at, zone);
      const band = bandOf(parts.hour);
      key = `${parts.date}-${band}`;
      bucket = buckets.get(key) ?? {
        sort: key,
        label: `${parts.weekday.toUpperCase()} ${BANDS[band]}`,
        date: parts.date,
        shortDate: parts.shortDate,
        games: [],
        tba: false,
      };
    }
    bucket.games.push(game);
    buckets.set(key, bucket);
  }

  const seenDays = new Set<string>();
  return [...buckets.entries()]
    .sort(([, a], [, b]) => (a.sort < b.sort ? -1 : a.sort > b.sort ? 1 : 0))
    .map(([key, bucket]) => {
      const dayFirst = !seenDays.has(bucket.date);
      seenDays.add(bucket.date);
      const times = bucket.games
        .map((g) => g.kickoff_at)
        .filter((at): at is string => at !== null)
        .sort();
      const text =
        times.length === 0
          ? "Time TBA"
          : timeRange(
              formatClockTime(times[0], zone),
              formatClockTime(times[times.length - 1], zone),
              zone,
              times[0],
            );
      const weekday = bucket.label.split(" ")[0];
      const day = `${weekday[0]}${weekday.slice(1).toLowerCase()} ${bucket.shortDate}`;
      return {
        key,
        label: bucket.label,
        time: dayFirst ? `${day} · ${text}` : text,
        games: bucket.games,
      };
    });
}

// ---------------------------------------------------------------------------------------------
// One row

export type Tone = "ink" | "muted" | "pos" | "neg";

export type RowNote = {
  text: string;
  tone: Tone;
  icon?: "check" | "clock" | "history";
  /** A graded pick's marker (✓ ✗ P), drawn before the text. */
  result?: ResultState;
};

export type TeamLine = {
  id: number;
  school: string;
  /** The abbreviation, or the school when there is none: what the market, model and edge print. */
  abbr: string;
  logoUrl: string | null;
  color: string | null;
  rank: number | null;
  fcs: boolean;
  points: number | null;
  /** A final's winner is emphasised and its loser muted; every other state is normal. */
  tone: "normal" | "winner" | "loser";
};

export type RowView = {
  id: number;
  href: string;
  status: "scheduled" | "live" | "final" | "postponed" | "canceled";
  /** `3:30 PM`, `TBA`, `Live`, `Final`, `Postponed`, `Canceled`. */
  statusLabel: string;
  /** A neutral site; `city` is null when the venue has none. */
  neutral: { city: string | null } | null;
  away: TeamLine;
  home: TeamLine;
  /**
   * `past`: a final game in a past week, drawn open → close only (`current` is the close).
   */
  market: { opener: number | null; snapshots: number[]; current: number | null; past: boolean };
  /** `OSU −31.2`; null when the run made no prediction. */
  modelLine: string | null;
  /** `pts` is `edge_pts` (positive likes home); `clears` is the raw edge against the threshold. */
  edge: { pts: number | null; clears: boolean };
  /** `61%`, and the probability behind it for the bar. */
  cover: string | null;
  coverProb: number | null;
  /** The current pick's tier. */
  tier: Tier | null;
  /** The game has a current pick (the Picks only filter keeps it). */
  hasPick: boolean;
  /** A current market line exists; without one the empty cells print "—". */
  hasLine: boolean;
  /** The model's favourite and its win %: `OSU 99%`. */
  win: string | null;
  notes: RowNote[];
};

function teamLine(
  team: SlateGame["home"],
  points: number | null,
  tone: TeamLine["tone"],
): TeamLine {
  const division = team.division;
  const outsideFbs = division !== null && division !== "fbs";
  return {
    id: team.id,
    school: team.school,
    abbr: team.abbreviation ?? team.school,
    logoUrl: team.logo_url,
    color: team.color,
    rank: team.rank,
    fcs: outsideFbs,
    points,
    tone,
  };
}

const STATUS: Record<SlateGame["status"], RowView["status"]> = {
  scheduled: "scheduled",
  in_progress: "live",
  final: "final",
  postponed: "postponed",
  canceled: "canceled",
};

function statusLabel(game: SlateGame, status: RowView["status"], zone: string): string {
  switch (status) {
    case "live":
      return "Live";
    case "final":
      return "Final";
    case "postponed":
      return "Postponed";
    case "canceled":
      return "Canceled";
    case "scheduled":
      return game.kickoff_at === null ? "TBA" : formatClockTime(game.kickoff_at, zone);
  }
}

const RESULT_WORD = { covered: "covered", not_covered: "not covered", push: "push" } as const;
const PICK_RESULT: Partial<Record<NonNullable<SlateGame["pick"]>["result"], keyof typeof RESULT_WORD>> = {
  won: "covered",
  lost: "not_covered",
  push: "push",
};

export type LiveCover = {
  /** `push` is on the number. A live pick is never lost (F-32). */
  state: "covering" | "push" | "not_yet";
  /** The smallest whole margin that covers, for a favourite that is behind its line. */
  needs: number | null;
};

/** Where a live pick stands against its line right now; null for a game that isn't live or has no pick. */
export function liveCover(game: SlateGame): LiveCover | null {
  const { pick } = game;
  if (pick === null || game.status !== "in_progress") return null;
  const margin = (game.home_points ?? 0) - (game.away_points ?? 0);
  const pickMargin = pick.side === "home" ? margin : -margin;
  const pickLine = pick.side === "home" ? pick.line : -pick.line;
  const cushion = pickMargin + pickLine;
  if (cushion > 0) return { state: "covering", needs: null };
  if (cushion === 0) return { state: "push", needs: null };
  // A favourite must win by more than its line: the smallest whole margin that covers.
  return { state: "not_yet", needs: pickLine < 0 ? Math.floor(-pickLine) + 1 : null };
}

function notesFor(game: SlateGame, abbr: { home: string; away: string }): RowNote[] {
  const { pick, market } = game;
  const current = market.current_spread_home;
  if (game.status === "postponed" || game.status === "canceled") return [];

  if (current === null) {
    const fcs = [game.away, game.home].some((t) => t.division !== null && t.division !== "fbs");
    return [{ text: fcs ? "FCS · no lines yet" : "No line posted yet", tone: "muted", icon: "clock" }];
  }

  if (game.status === "final") {
    if (pick === null) {
      if (game.cover === null) return [];
      if (game.cover === "push") return [{ text: "No pick · push", tone: "muted", icon: "check" }];
      return [{ text: `No pick · ${abbr[game.cover]} covered`, tone: "muted", icon: "check" }];
    }
    const bet = formatBet(pick.line, pick.side, abbr.home, abbr.away);
    const graded = PICK_RESULT[pick.result];
    if (graded === undefined) {
      return [{ text: pick.result === "void" ? `${bet} · void` : `Pick ${bet}`, tone: "ink" }];
    }
    const units = pick.units === null ? "" : ` · ${formatUnits(pick.units)}`;
    return [{ text: `${bet} · ${RESULT_WORD[graded]}${units}`, tone: "ink", result: graded }];
  }

  if (pick === null) return [];
  const bet = formatBet(pick.line, pick.side, abbr.home, abbr.away);

  if (game.status === "in_progress") {
    // Never "lost" while a game is live (F-32): covering, or not yet.
    const cover = liveCover(game);
    if (cover?.state === "covering") return [{ text: `${bet} · covering`, tone: "pos" }];
    if (cover?.state === "push") return [{ text: `${bet} · on the number`, tone: "muted" }];
    const needs = cover?.needs != null ? `, needs ${cover.needs}+` : "";
    return [{ text: `${bet} · not yet${needs}`, tone: "neg" }];
  }

  if (pick.line === current) return [{ text: `Pick ${bet}`, tone: "ink" }];

  // The line moved since the pick: both numbers from the current favourite's side, as the market
  // column reads, with the CLV so far under it (D-140's sign: positive means the pick beat it).
  const favourite = current > 0 ? "away" : "home";
  const moved: RowNote = {
    text: `Picked at ${formatLineNumber(pick.line, favourite)} → now ${formatLineNumber(current, favourite)}`,
    tone: "muted",
    icon: "history",
  };
  if (pick.clv_so_far === null) return [moved];
  const tenths = Math.round(pick.clv_so_far * 10);
  const clv: RowNote = {
    text: `CLV ${signed(pick.clv_so_far, 1)}${tenths > 0 ? " · moved our way" : ""}`,
    tone: tenths > 0 ? "pos" : tenths < 0 ? "neg" : "muted",
  };
  return [moved, clv];
}

/**
 * One game's row, from its `/slate` entry and the shown version's rules. `past`: the week is
 * before the coming week (`isPastWeek`), so a final game's market cell is its open and its close.
 */
export function rowView(
  game: SlateGame,
  rules: SlateRules | null,
  zone: string = SLATE_ZONE,
  past: boolean = false,
): RowView {
  const status = STATUS[game.status];
  const final = status === "final" && game.away_points !== null && game.home_points !== null;
  const awayWon = final && game.away_points! > game.home_points!;
  const homeWon = final && game.home_points! > game.away_points!;
  const away = teamLine(game.away, game.away_points, final ? (awayWon ? "winner" : "loser") : "normal");
  const home = teamLine(game.home, game.home_points, final ? (homeWon ? "winner" : "loser") : "normal");

  const { model, market } = game;
  const pastCell = past && status === "final";
  const edgePts = model?.edge ?? null;
  return {
    id: game.id,
    href: `/games/${game.id}`,
    status,
    statusLabel: statusLabel(game, status, zone),
    neutral: game.neutral_site ? { city: game.venue?.city ?? null } : null,
    away,
    home,
    market: {
      opener: market.opening_spread_home,
      snapshots: pastCell ? [] : market.snapshots.map((s) => s.spread_home),
      current: pastCell
        ? (market.closing_spread_home ?? market.current_spread_home)
        : market.current_spread_home,
      past: pastCell,
    },
    modelLine: model ? formatModelLine(model.pred_margin, home.abbr, away.abbr) : null,
    edge: {
      pts: edgePts,
      clears: edgePts !== null && rules !== null && Math.abs(edgePts) >= rules.min_edge_pts,
    },
    cover: model?.cover_prob == null ? null : formatCoverPct(model.cover_prob),
    coverProb: model?.cover_prob ?? null,
    tier: game.pick?.tier ?? null,
    hasPick: game.pick !== null,
    hasLine: market.current_spread_home !== null,
    win: model ? formatWinPct(model.home_win_prob, home.abbr, away.abbr) : null,
    notes: notesFor(game, { home: home.abbr, away: away.abbr }),
  };
}

// ---------------------------------------------------------------------------------------------
// Stepping through weeks (TASK-061)

type Params = Record<string, string | string[] | undefined>;

/**
 * The week a URL names: `?season=2026&week=5`, plus `&type=postseason` for the postseason. Null
 * (the coming week) when a parameter is missing, repeated or not a whole number, or the type is
 * anything else; the API refuses a partial or a week below 1, so a bad URL never reaches it.
 */
export function parseWeekParams(params: Params): SlateWeek | null {
  const one = (key: string): string | null => {
    const value = params[key];
    return typeof value === "string" ? value : null;
  };
  const whole = (text: string | null): number | null =>
    text !== null && /^\d{1,4}$/.test(text) ? Number(text) : null;
  const season = whole(one("season"));
  const week = whole(one("week"));
  if (season === null || week === null || week < 1) return null;
  const type = params.type;
  if (type !== undefined && type !== "postseason") return null;
  return { season, season_type: type === "postseason" ? "postseason" : "regular", week };
}

/** Order: season, regular before postseason, week. */
function weekKey(w: SlateWeek): number {
  return w.season * 1000 + (w.season_type === "postseason" ? 500 : 0) + w.week;
}

export function isShownWeek(a: SlateWeek, b: SlateWeek | null): boolean {
  return b !== null && weekKey(a) === weekKey(b);
}

/** `/` for the coming week, else `/?season=2026&week=5` (`&type=postseason` after the regular season). */
export function weekHref(week: SlateWeek, coming: SlateWeek | null): string {
  if (isShownWeek(week, coming)) return "/";
  const type = week.season_type === "postseason" ? "&type=postseason" : "";
  return `/?season=${week.season}&week=${week.week}${type}`;
}

/** The nearest week with games before and after `current`, across seasons; null at either end. */
export function weekNeighbours(
  weeks: SlateWeek[],
  current: SlateWeek,
): { previous: SlateWeek | null; next: SlateWeek | null } {
  const here = weekKey(current);
  let previous: SlateWeek | null = null;
  let next: SlateWeek | null = null;
  for (const week of weeks) {
    const key = weekKey(week);
    if (key < here && (previous === null || key > weekKey(previous))) previous = week;
    if (key > here && (next === null || key < weekKey(next))) next = week;
  }
  return { previous, next };
}

/** `2026 · Week 5`, `2025 · Postseason`: the same words the shell's label uses. */
export function weekLabel(week: SlateWeek): string {
  return week.season_type === "postseason"
    ? `${week.season} · Postseason`
    : `${week.season} · Week ${week.week}`;
}

/** The slate's own week, null in the off-season. */
export function shownWeek(slate: Pick<Slate, "season" | "season_type" | "week">): SlateWeek | null {
  if (slate.season === null || slate.season_type === null || slate.week === null) return null;
  return { season: slate.season, season_type: slate.season_type, week: slate.week };
}

type ShellWeek = { season: number | null; season_type: SlateWeek["season_type"] | null; week: number | null };

/** The shell's coming week: what the shell block names; null in the off-season. */
export function comingWeek(shell: ShellWeek): SlateWeek | null {
  return shownWeek(shell);
}

/**
 * The shown week is before the coming week, so its games are over and a final's market is its
 * open and close. With no coming week (the off-season) every week is past.
 */
export function isPastWeek(
  slate: Pick<Slate, "season" | "season_type" | "week"> & { shell?: ShellWeek | null },
): boolean {
  const shown = shownWeek(slate);
  // No shell block at all (never in a real response) says nothing about the coming week.
  if (shown === null || !slate.shell) return false;
  const coming = comingWeek(slate.shell);
  return coming === null || weekKey(shown) < weekKey(coming);
}

// ---------------------------------------------------------------------------------------------
// Caption and legend

function count(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

/** The season to name: the slate's own, or in the off-season (where it is null) the shell's. */
export function offseasonSeason(slate: {
  season: number | null;
  shell?: { season: number | null } | null;
}): number | null {
  return slate.season ?? slate.shell?.season ?? null;
}

/**
 * `2026 · Week 6 · 54 games · 9 picks` (`2026 · Postseason · …` after the regular season). In the
 * off-season it names the coming season and its first week when the shell has them (D-164),
 * else the season that ended: `2027 · Week 1 · off-season`, `2026 · off-season`.
 */
export function slateCaption(
  slate: Pick<Slate, "season" | "season_type" | "week" | "counts"> & {
    offseason?: boolean;
    shell?: { season: number | null; next_season?: number | null; next_week?: number | null } | null;
  },
): string {
  const parts: string[] = [];
  if (slate.offseason && slate.shell?.next_season != null) {
    parts.push(String(slate.shell.next_season));
    if (slate.shell.next_week != null) parts.push(`Week ${slate.shell.next_week}`);
    parts.push("off-season");
    return parts.join(" · ");
  }
  const season = offseasonSeason(slate);
  if (season !== null) parts.push(String(season));
  if (slate.offseason) {
    parts.push("off-season");
    return parts.join(" · ");
  }
  if (slate.season_type === "postseason") parts.push("Postseason");
  else if (slate.week !== null) parts.push(`Week ${slate.week}`);
  parts.push(count(slate.counts.games, "game"), count(slate.counts.picks, "pick"));
  return parts.join(" · ");
}

const LEGEND_MARKET = "Market = opening line, its moves, then now";

/** The footer legend, printed from the shown version's rules; with none, no threshold at all. */
export function slateLegend(rules: SlateRules | null): string {
  if (rules === null) return LEGEND_MARKET;
  const { min_edge_pts: edge, tiers } = rules;
  return [
    `Edge pill = clears ${formatThreshold(edge)} pts`,
    `Tier A ≥ ${formatThreshold(tiers.A)}`,
    `B ≥ ${formatThreshold(tiers.B)}`,
    `C ≥ ${formatThreshold(tiers.C)}`,
    LEGEND_MARKET,
  ].join(" · ");
}

// ---------------------------------------------------------------------------------------------
// The record strip, the Picks only filter and the empty states (TASK-057)

export type StripState = "won" | "lost" | "push" | "covering" | "push_live" | "not_yet" | "to_play";

export type StripSegment = { state: StripState; label: string };

export type RecordStrip = {
  /** `1-0`, graded picks only. */
  record: string;
  live: number;
  /** `IOWA covering, OSU not yet`; empty with nothing live. */
  liveNote: string;
  toPlay: number;
  /** `+1.0u`. */
  units: string;
  /** One per pick, graded first, then live (covering first), then to play. Void picks are left out. */
  segments: StripSegment[];
};

const GRADED_LABEL = { won: "Won", lost: "Lost", push: "Push" } as const;

/** F-32's strip, from the week's picks. Pure: a live pick's state comes from `liveCover`. */
export function recordStrip(games: SlateGame[]): RecordStrip {
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let units = 0;
  const graded: StripSegment[] = [];
  const covering: StripSegment[] = [];
  const behind: StripSegment[] = [];
  const toPlay: StripSegment[] = [];
  const notes = { covering: [] as string[], behind: [] as string[], onTheNumber: [] as string[] };

  for (const game of games) {
    const { pick } = game;
    if (pick === null || pick.result === "void") continue;
    const home = game.home.abbreviation ?? game.home.school;
    const away = game.away.abbreviation ?? game.away.school;
    const bet = formatBet(pick.line, pick.side, home, away);
    const team = pick.side === "home" ? home : away;
    if (pick.result === "won" || pick.result === "lost" || pick.result === "push") {
      if (pick.result === "won") wins += 1;
      else if (pick.result === "lost") losses += 1;
      else pushes += 1;
      units += pick.units ?? 0;
      graded.push({ state: pick.result, label: `${GRADED_LABEL[pick.result]} · ${bet}` });
      continue;
    }
    const cover = liveCover(game);
    if (cover === null) {
      toPlay.push({ state: "to_play", label: `To play · ${bet}` });
    } else if (cover.state === "covering") {
      covering.push({ state: "covering", label: `Live · covering · ${bet}` });
      notes.covering.push(team);
    } else if (cover.state === "push") {
      behind.push({ state: "push_live", label: `Live · on the number · ${bet}` });
      notes.onTheNumber.push(team);
    } else {
      behind.push({ state: "not_yet", label: `Live · not covering yet · ${bet}` });
      notes.behind.push(team);
    }
  }

  const liveNote = [
    ...notes.covering.map((t) => `${t} covering`),
    ...notes.onTheNumber.map((t) => `${t} on the number`),
    ...notes.behind.map((t) => `${t} not yet`),
  ].join(", ");

  return {
    record: formatRecord(wins, losses, pushes),
    live: covering.length + behind.length,
    liveNote,
    toPlay: toPlay.length,
    units: formatUnits(units),
    segments: [...graded, ...covering, ...behind, ...toPlay],
  };
}

export type SlateFilter = "all" | "picks";

/** The footer's left half: `Showing 54 of 54 games`, or `9 games with a pick · of 54`. */
export function showingText(
  filter: SlateFilter,
  counts: { shown: number; games: number; picks: number },
): string {
  if (filter === "picks") return `${count(counts.picks, "game")} with a pick · of ${counts.games}`;
  return `Showing ${counts.shown} of ${counts.games} games`;
}

/** The dashed note that replaces the strip when the week has no picks. */
export function noPicksNote(slate: Pick<Slate, "games" | "week" | "rules">): {
  title: string;
  body: string;
} {
  const noLines =
    slate.games.length > 0 && slate.games.every((g) => g.market.current_spread_home === null);
  if (noLines) {
    const week = slate.week === null ? "This week's" : `Week ${slate.week}`;
    return {
      title: "No picks yet",
      body: `${week} lines haven't posted. Model lines are ready; picks appear when books open, usually Sun–Mon.`,
    };
  }
  const why =
    slate.rules === null
      ? "No game qualifies as a pick."
      : `No game clears ${formatThreshold(slate.rules.min_edge_pts)} pts.`;
  return {
    title: "No picks this week",
    body: `${why} The record strip comes back with the first pick.`,
  };
}

/** The off-season frame's copy. The season and week come from the API, never guessed; the kickoff line needs its date. */
export function offseasonNote(
  season: number | null,
  nextKickoffAt: string | null | undefined,
  next: { season: number | null; week: number | null } | null = null,
  zone: string = SLATE_ZONE,
): { title: string; body: string; kickoff: string | null } {
  const nextWeek = next?.week ?? null;
  const week = nextWeek === null ? "The next season" : `Week ${nextWeek}`;
  const ended = season === null ? "The season has ended." : `The ${season} season has ended.`;
  const kickoff = nextKickoffAt
    ? `${week} kicks off ${new Intl.DateTimeFormat("en-US", {
        timeZone: zone,
        weekday: "short",
        month: "short",
        day: "numeric",
        year: "numeric",
      })
        .format(new Date(nextKickoffAt))
        .replace(",", "")}`
    : null;
  return {
    title: "No games this week",
    body: `${ended} The ${next?.season ?? "next"} slate fills in when books post ${nextWeek === null ? "its" : `Week ${nextWeek}`} lines, usually in early August.`,
    kickoff,
  };
}
