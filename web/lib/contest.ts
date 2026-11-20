// The Contest screen's pure helpers (S-02, TASK-072): which week the page pastes into, and the
// paste flow's summary, rows, raw lines, refusal copy and re-paste diff. Every number goes through
// format.ts; the API's rows are the truth (D-172), so nothing here re-matches a name.

import type { components } from "./api-types";
import {
  formatBet,
  formatCoverPct,
  formatKickoff,
  formatLineNumber,
  formatOrdinal,
  formatPoints,
  formatRecord,
  formatSpread,
  formatWinRate,
  signed,
} from "./format";

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

// The ranked slate (TASK-073). The API ranks (D-095, D-171) and these helpers only arrange and
// word what it sent: rows in the response's order, the cutoff, the ≠ chip, the tray.

export type Side = "home" | "away";
export type ContestEntry = Schemas["ContestEntryOut"];
export type ContestResults = Schemas["ContestResultsOut"];
export type ContestRecord = Schemas["ContestRecordOut"];
export type ContestStanding = Schemas["ContestStandingOut"];
export type StandingIn = Schemas["StandingIn"];
type Tally = Schemas["ContestTallyOut"];

const abbr = (team: ContestGame["home"]): string => team.abbreviation ?? team.school;

/** A side's line as the bet from that side at the game's contest line: `OU +7`. */
export function sideLabel(game: ContestGame, side: Side): string {
  return formatBet(game.contest_spread_home, side, abbr(game.home), abbr(game.away));
}

/** The side the row is ranked on: the model's (CFB), else the one the contest line favors over the market (NFL). */
export function rankedSide(game: ContestGame): Side | null {
  return game.model?.side ?? game.market_gap?.side ?? null;
}

/** The cover % the row ranks on: the model's, or `~54%` market-implied (no model). */
export function coverText(game: ContestGame): string | null {
  if (game.model) return formatCoverPct(game.model.cover_prob);
  return game.market_gap ? formatCoverPct(game.market_gap.implied_prob, { marketImplied: true }) : null;
}

export type SlateLayout = {
  /** Open games, in rank order */
  open: ContestGame[];
  /** Games that have kicked off, as the response lists them (after the open ones) */
  locked: ContestGame[];
  /** The last open game that is one of the model's top N; the cutoff is drawn under it */
  cutoffAfter: ContestGame | null;
  /** The first open game below the top N */
  nextBest: ContestGame | null;
  /** Every game has kicked off (C2d) */
  allLocked: boolean;
  /** Some game has kicked off, so `top_n` is the best of the open games (D-174) */
  anyKicked: boolean;
};

export function slateLayout(games: readonly ContestGame[]): SlateLayout {
  const open = games.filter((g) => !g.locked);
  const locked = games.filter((g) => g.locked);
  return {
    open,
    locked,
    cutoffAfter: open.findLast((g) => g.top_n) ?? null,
    nextBest: open.find((g) => g.next_best) ?? null,
    allLocked: games.length > 0 && open.length === 0,
    anyKicked: locked.length > 0,
  };
}

/** The cutoff row's label; once a game has kicked off it is the best of the open games, not the graded set (D-174). */
export function cutoffLabel(layout: SlateLayout, picks: number): string {
  return `Model's top ${picks}${layout.anyKicked ? " · open games" : ""}`;
}

/** `Next best #5 ND −17.5 · 55%`, in parts. */
export function nextBestText(game: ContestGame): { rank: number; line: string; cover: string } {
  const side = rankedSide(game);
  const line = side
    ? sideLabel(game, side)
    : formatSpread(game.contest_spread_home, abbr(game.home), abbr(game.away));
  return { rank: game.rank, line, cover: coverText(game) ?? "—" };
}

function pts(points: number): string {
  return `${formatPoints(points)} ${points === 1 ? "pt" : "pts"}`;
}

/** An NFL row's gap (no model): `1.5 pts off mkt → BUF`, `No gap to market`; null for a game with a model. */
export function nflGapText(game: ContestGame): string | null {
  const gap = game.market_gap;
  if (!gap) return null;
  if (gap.side === null) return "No gap to market";
  return `${pts(gap.points)} off mkt → ${abbr(gap.side === "home" ? game.home : game.away)}`;
}

/** `~54%`, the market-implied cover of an NFL row; null for a game with a model. */
export function impliedText(game: ContestGame): string | null {
  return game.market_gap ? formatCoverPct(game.market_gap.implied_prob, { marketImplied: true }) : null;
}

export type LineChip = { text: string; tone: "better" | "worse" };

/**
 * The ≠ chip on a row whose contest line differs from the market: the side the contest line favors
 * and by how many points. Blue (`better`) when that side is the ranked one, orange (`worse`) when
 * the contest line favors the other side.
 */
export function lineChip(game: ContestGame): LineChip | null {
  if (!game.differs || game.market_spread_home === null) return null;
  const gap = game.contest_spread_home - game.market_spread_home;
  const side: Side = gap > 0 ? "home" : "away";
  // A bigger home spread helps the home side: the "+n" the team would see on its own line.
  const points = formatLineNumber(Math.abs(gap), "home");
  return {
    text: `≠ ${abbr(side === "home" ? game.home : game.away)} ${points}`,
    tone: side === rankedSide(game) ? "better" : "worse",
  };
}

export function differsCount(games: readonly ContestGame[]): number {
  return games.filter((g) => g.differs).length;
}

export type SlateFilter = "all" | "cfb" | "nfl" | "differs";

export function filterGames(games: readonly ContestGame[], filter: SlateFilter): ContestGame[] {
  if (filter === "all") return [...games];
  if (filter === "differs") return games.filter((g) => g.differs);
  return games.filter((g) => g.sport_id === filter);
}

// The pick tray

export type TapOutcome = "add" | "remove" | "switch" | "full" | "locked";

/** What a tap on a side does: add it, remove it (a second tap), switch to it (the other side), or nothing. */
export function tapOutcome(
  entries: readonly ContestEntry[],
  game: ContestGame,
  side: Side,
  picks: number,
): TapOutcome {
  if (game.locked) return "locked";
  const mine = entries.find((e) => e.game_id === game.id);
  if (mine) return mine.side === side ? "remove" : "switch";
  return entries.length >= picks ? "full" : "add";
}

function entryFor(game: ContestGame, side: Side, now: string): ContestEntry {
  // Until the save answers, a stand-in at the game's line: `id` is not the stored row's.
  return {
    id: -game.id,
    game_id: game.id,
    side,
    contest_line_id: game.contest_line_id,
    line: game.contest_spread_home,
    created_at: now,
  };
}

/** The picks after a tap, for the tray to show at once; a refused tap changes nothing. */
export function applyTap(
  entries: readonly ContestEntry[],
  game: ContestGame,
  side: Side,
  outcome: TapOutcome,
  now: string,
): ContestEntry[] {
  switch (outcome) {
    case "add":
      return [...entries, entryFor(game, side, now)];
    case "remove":
      return entries.filter((e) => e.game_id !== game.id);
    case "switch":
      return entries.map((e) => (e.game_id === game.id ? entryFor(game, side, now) : e));
    default:
      return [...entries];
  }
}

/** Your picks, oldest first: the tray's order. */
export function trayOrder(entries: readonly ContestEntry[]): ContestEntry[] {
  return [...entries].sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id - b.id);
}

/** "Use the model's top 4": the open top-N games you haven't picked, on the model's side, up to the open slots. */
export function fillFromModel(
  games: readonly ContestGame[],
  entries: readonly ContestEntry[],
  picks: number,
): { game: ContestGame; side: Side }[] {
  const slots = Math.max(0, picks - entries.length);
  return games
    .filter((g) => g.top_n && !g.locked && g.model !== null && !entries.some((e) => e.game_id === g.id))
    .slice(0, slots)
    .map((game) => ({ game, side: game.model!.side }));
}

function when(iso: string): string {
  return formatKickoff(iso, iso.slice(0, 10), { zone: CONTEST_ZONE, inTable: true });
}

function entryLine(game: ContestGame, entry: ContestEntry): string {
  return formatBet(entry.line, entry.side, abbr(game.home), abbr(game.away));
}

/** The text "Copy picks to enter on Splash" puts on the clipboard (the owner's format, TASK-073). */
export function copyText(
  contestName: string,
  period: number,
  entries: readonly ContestEntry[],
  games: readonly ContestGame[],
): string {
  const lines = trayOrder(entries).flatMap((entry) => {
    const game = games.find((g) => g.id === entry.game_id);
    if (!game) return [];
    const sep = game.neutral_site ? "vs" : "@";
    const kickoff = formatKickoff(game.kickoff_at, game.game_date, { zone: CONTEST_ZONE, inTable: true });
    return [`${entryLine(game, entry)} (${game.away.school} ${sep} ${game.home.school}, ${kickoff})`];
  });
  return [`${contestName} · Week ${period}`, ...lines].join("\n");
}

/** The pick agrees with the model: one of its top N, on its side. */
export function matchesModel(game: ContestGame, entry: ContestEntry): boolean {
  return game.top_n && game.model?.side === entry.side;
}

export function sharedCount(entries: readonly ContestEntry[], games: readonly ContestGame[]): number {
  return entries.filter((e) => {
    const game = games.find((g) => g.id === e.game_id);
    return game ? matchesModel(game, e) : false;
  }).length;
}

export type TrayCard = {
  /** `OU +7` */
  line: string;
  side: Side;
  /** `Model #1`, `Against model` or `Your call` */
  badge: string;
  match: boolean;
  against: boolean;
  /** `Texas vs Oklahoma · Sat 7:30 PM` */
  matchup: string;
  /** `Locked in at OU +7 · Thu 9:14 PM` */
  lockedIn: string;
  why: string;
  /** `Switch to TEX −7` */
  switchLabel: string;
  switchTo: Side;
  locked: boolean;
};

export function trayCard(game: ContestGame, entry: ContestEntry, picks: number): TrayCard {
  const match = matchesModel(game, entry);
  const against = game.top_n && game.model !== null && game.model.side !== entry.side;
  const other: Side = entry.side === "home" ? "away" : "home";
  const outside = `Not in model's top ${picks} · `;
  let why: string;
  if (match) {
    why = `Model's #${game.rank} pick · ${formatCoverPct(game.model!.cover_prob)} to cover`;
  } else if (against) {
    why = `Model has the other side (${sideLabel(game, game.model!.side)})`;
  } else if (game.model) {
    why = `${outside}Model ranks it #${game.rank} · ${formatCoverPct(game.model.cover_prob)} to cover`;
  } else {
    const gap = game.market_gap;
    const better =
      !gap || gap.side === null
        ? "same as market"
        : `${pts(gap.points)} ${gap.side === entry.side ? "better" : "worse"} than market`;
    const implied = impliedText(game);
    why = `${outside}No model yet (NFL) · contest ${better}${implied ? ` · ${implied} mkt-implied` : ""}`;
  }
  const kickoff = formatKickoff(game.kickoff_at, game.game_date, { zone: CONTEST_ZONE, inTable: true });
  const sep = game.neutral_site ? "vs" : "@";
  return {
    line: entryLine(game, entry),
    side: entry.side,
    badge: match ? `Model #${game.rank}` : against ? "Against model" : "Your call",
    match,
    against,
    matchup: `${game.away.school} ${sep} ${game.home.school} · ${kickoff}`,
    // A stand-in (negative id) is still being saved: it has no stored line or time yet.
    lockedIn:
      entry.id < 0
        ? `Saving ${entryLine(game, entry)}…`
        : `Locked in at ${entryLine(game, entry)} · ${when(entry.created_at)}`,
    why,
    switchLabel: `Switch to ${sideLabel(game, other)}`,
    switchTo: other,
    locked: game.locked,
  };
}

// Results & standing

function winRate(t: Tally): string {
  return t.wins + t.losses === 0 ? "—" : formatWinRate(t.wins / (t.wins + t.losses));
}

function record(t: Tally): string {
  return formatRecord(t.wins, t.losses, t.pushes);
}

function winsBehind(a: Tally, b: Tally | null): string {
  return b === null ? "—" : signed(a.wins - b.wins, 0);
}

export type SeasonCard = { label: string; record: string; rate: string };

/** The season cards: you, the model's top N and you against it. */
export function seasonCards(
  results: ContestResults,
  picks: number,
): { you: SeasonCard; model: SeasonCard | null; diff: string } {
  const { you, model } = results.season;
  return {
    you: { label: "You", record: record(you), rate: winRate(you) },
    model: model ? { label: `Model top ${picks}`, record: record(model), rate: winRate(model) } : null,
    diff: winsBehind(you, model),
  };
}

export type WeekSide = { record: string; points: string; pending: number };

function weekSide(t: Tally): WeekSide {
  return { record: record(t), points: pts(t.points), pending: t.pending };
}

/** This week so far: each side's record, points and pending picks. */
export function weekSummary(week: ContestRecord): { you: WeekSide; model: WeekSide | null } {
  return { you: weekSide(week.you), model: week.model ? weekSide(week.model) : null };
}

export type WeekRow = {
  label: string;
  /** `3-1` */
  youRecord: string;
  modelRecord: string;
  diff: string;
  cumulativeYou: number;
  cumulativeModel: number;
};

/** The past weeks, W1…: each side's record and the running wins. */
export function weekRows(results: ContestResults): WeekRow[] {
  let you = 0;
  let model = 0;
  return results.weeks.map((w) => {
    you += w.you.wins;
    model += w.model?.wins ?? 0;
    return {
      label: `W${w.period}`,
      youRecord: record(w.you),
      modelRecord: w.model ? record(w.model) : "—",
      diff: winsBehind(w.you, w.model),
      cumulativeYou: you,
      cumulativeModel: model,
    };
  });
}

/** `3rd of 14` and `1 pt behind 1st`; null with no standing entered. */
export function standingText(standing: ContestStanding | null): { place: string; behind: string | null } | null {
  if (!standing) return null;
  const behind = standing.points_behind_leader;
  return {
    place: `${formatOrdinal(standing.position)} of ${standing.field_size}`,
    behind: behind === null ? null : behind === 0 ? "Leading" : `${pts(behind)} behind 1st`,
  };
}

// The Rules panel (read-only; the form is M8.8)

const LOCK_ROW = { per_game_kickoff: "Each game locks at its kickoff", fixed_time: "Picks lock at a set time" } as const;
const SCORING_ROW = { point_per_win: "1 point per correct pick", confidence: "Confidence points" } as const;
const PUSH_ROW = { zero: "A push scores 0", half: "A push scores ½", void: "A push is void" } as const;

/** The rules as label and value rows. */
export function rulesRows(rules: ContestRules): [string, string][] {
  return [
    ["Sports", sportsLabel(rules.sports)],
    ["Picks per week", `${rules.picks_exact ? "Exactly" : "Up to"} ${rules.picks_per_period}`],
    ["Lock", LOCK_ROW[rules.lock]],
    ["Scoring", SCORING_ROW[rules.scoring]],
    ["Push", PUSH_ROW[rules.push]],
  ];
}

/** "This week, in plain English": the rules as one short paragraph. */
export function rulesSentence(rules: ContestRules): string {
  const pick = `Pick ${rules.picks_exact ? "exactly" : "up to"} ${rules.picks_per_period} games from ${sportsLabel(rules.sports)}.`;
  const lock =
    rules.lock === "per_game_kickoff"
      ? "Each game locks at its own kickoff, so you can change a pick until then."
      : "Picks lock together at a set time.";
  const score = rules.scoring === "point_per_win" ? "A correct pick scores 1 point" : "Picks score confidence points";
  const push = PUSH_ROW[rules.push].replace(/^A/, "a");
  return `${pick} ${lock} ${score}; ${push}.`;
}
