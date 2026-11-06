import type { ResultState } from "@/components/result-marker";
import type { Tier } from "@/components/tier-badge";

import type { components } from "./api-types";
import {
  formatBet,
  formatClockTime,
  formatCoverPct,
  formatLineNumber,
  formatModelLine,
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
  market: { opener: number | null; snapshots: number[]; current: number | null };
  /** `OSU −31.2`; null when the run made no prediction. */
  modelLine: string | null;
  /** `pts` is `edge_pts` (positive likes home); `clears` is the raw edge against the threshold. */
  edge: { pts: number | null; clears: boolean };
  /** `61%`, and the probability behind it for the bar. */
  cover: string | null;
  coverProb: number | null;
  /** The current pick's tier. */
  tier: Tier | null;
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
    const margin = (game.home_points ?? 0) - (game.away_points ?? 0);
    const pickMargin = pick.side === "home" ? margin : -margin;
    const pickLine = pick.side === "home" ? pick.line : -pick.line;
    const cushion = pickMargin + pickLine;
    if (cushion > 0) return [{ text: `${bet} · covering`, tone: "pos" }];
    if (cushion === 0) return [{ text: `${bet} · on the number`, tone: "muted" }];
    // A favourite must win by more than its line: the smallest whole margin that covers.
    const needs = pickLine < 0 ? `, needs ${Math.floor(-pickLine) + 1}+` : "";
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

/** One game's row, from its `/slate` entry and the shown version's rules. */
export function rowView(game: SlateGame, rules: SlateRules | null, zone: string = SLATE_ZONE): RowView {
  const status = STATUS[game.status];
  const final = status === "final" && game.away_points !== null && game.home_points !== null;
  const awayWon = final && game.away_points! > game.home_points!;
  const homeWon = final && game.home_points! > game.away_points!;
  const away = teamLine(game.away, game.away_points, final ? (awayWon ? "winner" : "loser") : "normal");
  const home = teamLine(game.home, game.home_points, final ? (homeWon ? "winner" : "loser") : "normal");

  const { model, market } = game;
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
      snapshots: market.snapshots.map((s) => s.spread_home),
      current: market.current_spread_home,
    },
    modelLine: model ? formatModelLine(model.pred_margin, home.abbr, away.abbr) : null,
    edge: {
      pts: edgePts,
      clears: edgePts !== null && rules !== null && Math.abs(edgePts) >= rules.min_edge_pts,
    },
    cover: model?.cover_prob == null ? null : formatCoverPct(model.cover_prob),
    coverProb: model?.cover_prob ?? null,
    tier: game.pick?.tier ?? null,
    win: model ? formatWinPct(model.home_win_prob, home.abbr, away.abbr) : null,
    notes: notesFor(game, { home: home.abbr, away: away.abbr }),
  };
}

// ---------------------------------------------------------------------------------------------
// Caption and legend

function count(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

/** `2026 · Week 6 · 54 games · 9 picks` (`2026 · Postseason · …` after the regular season). */
export function slateCaption(slate: Pick<Slate, "season" | "season_type" | "week" | "counts">): string {
  const parts: string[] = [];
  if (slate.season !== null) parts.push(String(slate.season));
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
