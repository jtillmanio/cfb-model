// The Contest screen's pure helpers (S-02, TASK-072): which week the page pastes into, and the
// paste flow's summary, rows, raw lines, refusal copy and re-paste diff. Every number goes through
// format.ts; the API's rows are the truth (D-172), so nothing here re-matches a name.

import type { components } from "./api-types";
import { formatKickoff, formatLineNumber, formatSpread } from "./format";

type Schemas = components["schemas"];
export type ContestPage = Schemas["ContestPageOut"];
export type ContestGame = Schemas["ContestGameOut"];
export type ContestRules = Schemas["ContestRulesOut"];
export type ImportIn = Schemas["ImportIn"];
export type ImportPreview = Schemas["ImportPreviewOut"];
export type ImportRow = Schemas["ImportRowOut"];
export type ImportTeam = Schemas["ImportTeamOut"];
export type ImportRefusal = Schemas["ImportRefusalOut"];
export type ImportConfirm = Schemas["ImportConfirmOut"];
export type AliasesIn = Schemas["AliasesIn"];
export type AliasesOut = Schemas["AliasesOut"];
export type LineChange = Schemas["LineChangeOut"];

/** The zone kickoffs and capture times print in, until `user_settings` (M8.7): This Week's
 *  `SLATE_ZONE`, written out so the paste flow's client bundle doesn't carry `lib/slate.ts`. */
export const CONTEST_ZONE = "America/New_York";

/** Names picked in the inline team picker: the name as the page writes it → a team id. */
export type Picks = Readonly<Record<string, number>>;

// The week

/**
 * The week the page is about (D-175). The coming regular-season week of the contest's season,
 * when it has no lines yet, is the one to paste (the hero); otherwise the newest week with lines,
 * which TASK-073 ranks, and which a re-paste updates. Splash numbers its own weeks (D-172), so a
 * contest with no lines out of season starts at week 1.
 */
export function contestWeek(page: Pick<ContestPage, "contest" | "period" | "shell">): {
  paste: boolean;
  period: number;
} {
  const { shell } = page;
  const coming =
    shell.season === page.contest.season && shell.season_type === "regular" ? shell.week : null;
  if (coming !== null && (page.period === null || coming > page.period)) return { paste: true, period: coming };
  if (page.period === null) return { paste: true, period: 1 };
  return { paste: false, period: page.period };
}

const SPORT_LABEL: Record<string, string> = { cfb: "CFB", nfl: "NFL" };
const SPORT_NAME: Record<string, string> = { cfb: "college football", nfl: "NFL" };

/** `CFB + NFL` */
export function sportsLabel(sports: readonly string[]): string {
  return sports.map((s) => SPORT_LABEL[s] ?? s.toUpperCase()).join(" + ");
}

/** The header's rules line: `Week 6 · Pick 4 · CFB + NFL · each game locks at its kickoff · …`. */
export function rulesLine(rules: ContestRules, period: number): string {
  const lock = rules.lock === "per_game_kickoff" ? "each game locks at its kickoff" : "picks lock at a set time";
  const scoring = rules.scoring === "point_per_win" ? "1 pt per correct pick" : "confidence points";
  const push = { zero: "push = 0", half: "push = ½", void: "a push is void" }[rules.push];
  return [`Week ${period}`, `Pick ${rules.picks_per_period}`, sportsLabel(rules.sports), lock, scoring, push].join(
    " · ",
  );
}

/** The confirmed week's toolbar: `From Splash paste · Thu 10:00 PM · 10 games`. */
export function weekSource(games: readonly ContestGame[]): string {
  const newest = games.map((g) => g.contest_captured_at).sort().at(-1);
  const at = newest ? ` · ${formatKickoff(newest, newest.slice(0, 10), { zone: CONTEST_ZONE, inTable: true })}` : "";
  return `From Splash paste${at} · ${plural(games.length, "game")}`;
}

// Teams and rows

/** An NFL team by city and nickname (`Houston Texans`), a CFB team by school. */
export function teamName(team: ImportTeam): string {
  const { school, mascot } = team;
  if (team.sport_id !== "nfl" || !mascot || school.endsWith(mascot)) return school; // "NY Jets" has it
  return `${school} ${mascot}`;
}

export function teamAbbr(team: ImportTeam): string {
  return team.abbreviation ?? team.school;
}

/** What a row needs from the picker: the names it couldn't match, while unmatched. */
export function namesToPick(row: ImportRow): string[] {
  return row.status === "unmatched" ? row.unmatched.map((n) => n.name) : [];
}

/**
 * - `matched`: the API matched it.
 * - `fixed`: unmatched, and every name it couldn't match is picked (saved at Confirm).
 * - `needs`: unmatched, with a name still to pick.
 * - `blocked`: no game that day, more than one, listed twice, or a problem: the picker can't fix it.
 */
export type RowState = "matched" | "fixed" | "needs" | "blocked";

export function rowState(row: ImportRow, picks: Picks): RowState {
  if (row.status === "matched") return "matched";
  if (row.status !== "unmatched" || row.unmatched.length === 0) return "blocked";
  return namesToPick(row).every((name) => name in picks) ? "fixed" : "needs";
}

export type Tone = "muted" | "pos" | "neg";

/** The row's status cell. */
export function rowStatus(row: ImportRow, picks: Picks): { text: string; tone: Tone } {
  switch (rowState(row, picks)) {
    case "matched":
      return row.spread_home === null ? { text: "No line", tone: "neg" } : { text: "Matched", tone: "muted" };
    case "fixed":
      return { text: "Fixed", tone: "pos" };
    case "needs":
      return { text: "Needs team", tone: "neg" };
    case "blocked":
      return { text: BLOCKED[row.problem ?? row.status] ?? "Can't match", tone: "neg" };
  }
}

const BLOCKED: Record<string, string> = {
  no_game: "No game that day",
  ambiguous: "More than one game",
  duplicate: "Listed twice",
  "no line": "No line",
  "lines disagree": "Lines disagree",
  "unreadable block": "Couldn't read",
};

/** The row's contest line: `OSU −27`; for a row with no teams yet, each side's (`−1 / +1`). */
export function rowLine(row: ImportRow): string {
  if (row.spread_home === null) return "No line";
  if (row.status === "matched" && row.home_team && row.away_team) {
    return formatSpread(row.spread_home, teamAbbr(row.home_team), teamAbbr(row.away_team));
  }
  return `${formatLineNumber(row.spread_home, "away")} / ${formatLineNumber(row.spread_home, "home")}`;
}

/** A side's line as the page wrote it: `−1` for the away side of HOU −1 @ JAX. */
export function sideLine(row: ImportRow, side: "away" | "home"): string {
  return row.spread_home === null ? "No line" : formatLineNumber(row.spread_home, side);
}

/** `Sun 1:00 PM` (the table's header says ET), else `—` for a block with no date. */
export function rowKickoff(row: ImportRow): string {
  if (!row.game_date) return "—";
  return formatKickoff(row.kickoff_at, row.game_date, { zone: CONTEST_ZONE, inTable: true });
}

/** `L9–20`: the block's lines in the paste. */
export function rowSource(row: ImportRow): string {
  return row.first_line === row.last_line ? `L${row.first_line}` : `L${row.first_line}–${row.last_line}`;
}

/** The row's sport: its game's, else its teams', else the picker's best guess (Splash prints no sport). */
export function rowSport(row: ImportRow): string | null {
  return (
    row.sport_id ??
    row.away_team?.sport_id ??
    row.home_team?.sport_id ??
    row.unmatched.find((n) => n.candidates.length > 0)?.candidates[0].sport_id ??
    null
  );
}

// The summary and Confirm

export type ImportSummary = {
  /** `Found 10 games` */
  found: string;
  /** `Fri Oct 9 – Sun Oct 11`, or null with no dates */
  dates: string | null;
  /** `6 CFB · 4 NFL` */
  sports: string;
  /** `9 rows match`: matched, or fixed in the picker */
  matched: string;
  /** `1 unmatched`, or null when every row matches */
  unmatched: string | null;
  /** The number of games Confirm saves */
  games: number;
};

export function importSummary(preview: ImportPreview, picks: Picks): ImportSummary {
  const { rows } = preview;
  const states = rows.map((r) => rowState(r, picks));
  const good = states.filter((s) => s === "matched" || s === "fixed").length;
  const bad = rows.length - good;
  const counts = new Map<string, number>();
  for (const row of rows) {
    const sport = rowSport(row);
    if (sport) counts.set(sport, (counts.get(sport) ?? 0) + 1);
  }
  const dates = rows.flatMap((r) => (r.game_date ? [r.game_date.slice(0, 10)] : [])).sort();
  const first = dates[0];
  const last = dates.at(-1);
  return {
    found: `Found ${plural(rows.length, "game")}`,
    dates: first && last ? (first === last ? dayLabel(first) : `${dayLabel(first)} – ${dayLabel(last)}`) : null,
    sports: [...counts].map(([s, n]) => `${n} ${SPORT_LABEL[s] ?? s.toUpperCase()}`).join(" · "),
    matched: good === 1 ? "1 row matches" : `${good} rows match`,
    unmatched: bad === 0 ? null : `${bad} unmatched`,
    games: rows.length,
  };
}

/** Confirm saves every row or none (D-172): each row matched, or fixed, with a line. */
export function canConfirm(preview: ImportPreview | null, picks: Picks): boolean {
  if (!preview || preview.rows.length === 0) return false;
  return preview.rows.every((row) => {
    const state = rowState(row, picks);
    return (state === "matched" || state === "fixed") && row.spread_home !== null;
  });
}

/** The picks Confirm saves as aliases first: one per name, for the names unmatched rows need. */
export function aliasMappings(preview: ImportPreview, picks: Picks): AliasesIn["mappings"] {
  const names = new Set(preview.rows.flatMap(namesToPick));
  return [...names].filter((name) => name in picks).map((name) => ({ alias: name, team_id: picks[name] }));
}

/** Splash's single lock time, read as the last kickoff, beside the contest's own lock rule. */
export function lockNote(preview: ImportPreview, rules: ContestRules): string | null {
  if (!preview.lock_at || rules.lock !== "per_game_kickoff") return null;
  const at = formatKickoff(preview.lock_at, preview.lock_at.slice(0, 10), { zone: CONTEST_ZONE, inTable: true });
  return `Splash's “Picks lock: ${at}” is read as the last kickoff; your rules lock each game at its own kickoff.`;
}

// The raw paste

export type RawLine = {
  /** From 1 */
  n: number;
  text: string;
  /** Inside a block the parser read */
  read: boolean;
  /** A name the row still needs picked */
  bad: boolean;
  /** The row the line belongs to (its index), or null */
  row: number | null;
};

export function rawLines(text: string, rows: readonly ImportRow[], picks: Picks): RawLine[] {
  const owner = new Map<number, ImportRow>();
  for (const row of rows) for (let n = row.first_line; n <= row.last_line; n++) owner.set(n, row);
  return splitLines(text).map((line, i) => {
    const n = i + 1;
    const row = owner.get(n) ?? null;
    const missing = row ? namesToPick(row).filter((name) => !(name in picks)) : [];
    return { n, text: line, read: row !== null, bad: missing.includes(line.trim()), row: row?.index ?? null };
  });
}

function splitLines(text: string): string[] {
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  if (lines.length > 1 && lines.at(-1) === "") lines.pop();
  return lines;
}

// A paste the API refused (C2a, C2b)

export type RefusalCopy = { title: string; body: string; meta: string };

/** C2a (nothing parseable) and C2b (no team matched), from the refusal; null for another code. */
export function refusalCopy(refusal: ImportRefusal, text: string, sports: readonly string[]): RefusalCopy | null {
  if (refusal.code === "unparseable") {
    const lines = splitLines(text).filter((l) => l.trim() !== "").length;
    return {
      title: "Couldn't find any games in that paste",
      body:
        `We read ${plural(lines, "line")} but none looked like a matchup with a spread. This is usually ` +
        "Splash's My Entries or Standings page. Open the league's Pick against the spread page, select all " +
        "and copy again.",
      meta: `${plural(lines, "line")} read · 0 games · nothing saved`,
    };
  }
  if (refusal.code === "no_match") {
    const games = refusal.rows.filter((r) => r.away_name !== null);
    const names = [...new Set(games.flatMap((r) => [r.away_name, r.home_name]).filter((n) => n !== null))];
    const kinds = sports.map((s) => SPORT_NAME[s] ?? s.toUpperCase()).join(" or ");
    const verb = names.length === 1 ? "isn't a" : "aren't";
    const noun = names.length === 1 ? "team" : "teams";
    return {
      title: `Found ${plural(games.length, "game")}, but no team matched`,
      body:
        `${listOf(names)} ${verb} ${kinds} ${noun}. This contest is ${sportsLabel(sports)}; check you copied ` +
        "the right league.",
      meta: `${plural(games.length, "game")} read · 0 of ${plural(names.length, "team")} matched · nothing saved`,
    };
  }
  return null;
}

// A re-paste (C2e, RepasteDiff)

export type MovedRow = {
  index: number;
  away: ImportTeam;
  home: ImportTeam;
  /** `TEX −7` */
  was: string;
  /** `TEX −6.5` */
  now: string;
};

/** Each matched row whose line differs from the contest's current one, in page order. */
export function movedRows(preview: ImportPreview): MovedRow[] {
  const rows = new Map(preview.rows.map((r) => [r.index, r]));
  return preview.changes.flatMap((change) => {
    const row = rows.get(change.index);
    if (!row?.away_team || !row.home_team) return [];
    const home = teamAbbr(row.home_team);
    const away = teamAbbr(row.away_team);
    return [
      {
        index: change.index,
        away: row.away_team,
        home: row.home_team,
        was: formatSpread(change.old_spread_home, home, away),
        now: formatSpread(change.new_spread_home, home, away),
      },
    ];
  });
}

/** The RepasteDiff's heading: `2 contest lines moved since Thu 10:00 PM`. */
export function movedTitle(changes: readonly LineChange[]): string {
  const since = changes.map((c) => c.old_captured_at).sort().at(-1);
  const at = since ? ` since ${formatKickoff(since, since.slice(0, 10), { zone: CONTEST_ZONE, inTable: true })}` : "";
  return `${plural(changes.length, "contest line")} moved${at}`;
}

// Words

function plural(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

/** `a, b and c`; past six names, `a, …, f and 3 more`. */
function listOf(names: readonly string[]): string {
  if (names.length <= 1) return names.join("");
  if (names.length > 6) return `${names.slice(0, 6).join(", ")} and ${names.length - 6} more`;
  return `${names.slice(0, -1).join(", ")} and ${names.at(-1)}`;
}

/** `Fri Oct 9` from `2026-10-09` (a calendar date, so read in UTC). */
function dayLabel(date: string): string {
  const [y, m, d] = date.split("-").map(Number);
  return new Intl.DateTimeFormat("en-US", { timeZone: "UTC", weekday: "short", month: "short", day: "numeric" })
    .format(new Date(Date.UTC(y, m - 1, d)))
    .replace(",", "");
}
