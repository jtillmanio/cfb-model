// Every number the app shows goes through here (design/README.md § Number formats).
// Pure and clock-free: callers pass "now" and the kickoff zone, so tests need neither.
// Text only: choosing a colour for a number is the component's job.

/** True minus sign (U+2212). A hyphen-minus is never used for a negative number. */
export const MINUS = "−";
/** Figure space + punctuation space: pads a whole-number spread to the width of a ".5" one. */
export const ALIGN_PAD = "  ";

/** Round half away from zero. Math.round and toFixed both round unevenly on floats. */
function roundTo(value: number, decimals: number): number {
  const scale = 10 ** decimals;
  return Math.round(Math.abs(value) * scale + 1e-9) / scale;
}

/**
 * Signed number with a fixed decimal count. `+` for positive, U+2212 for negative,
 * and no sign at all for a value that rounds to zero, so there is no negative zero.
 */
export function signed(value: number, decimals: number): string {
  const magnitude = roundTo(value, decimals);
  if (magnitude === 0) return (0).toFixed(decimals);
  return `${value < 0 ? MINUS : "+"}${magnitude.toFixed(decimals)}`;
}

/** Magnitude with one decimal, or none when it is a whole number (`10`, `9.5`). */
function wholeOrOneDecimal(magnitude: number): string {
  return Number.isInteger(magnitude) ? String(magnitude) : magnitude.toFixed(1);
}

/**
 * Market spread from `spread_home` (negative when home is favored). Names the favorite.
 * `align` pads a whole number so its units digit lines up with `BSU −9.5` in a column.
 */
export function formatSpread(
  spreadHome: number | null,
  home: string,
  away: string,
  opts: { align?: boolean } = {},
): string {
  if (spreadHome === null) return "No line";
  const magnitude = roundTo(spreadHome, 1);
  if (magnitude === 0) return "PK";
  const favorite = spreadHome < 0 ? home : away;
  const text = `${favorite} ${MINUS}${wholeOrOneDecimal(magnitude)}`;
  return opts.align && Number.isInteger(magnitude) ? text + ALIGN_PAD : text;
}

/**
 * A line's number without the team, for the opener beside the current line (`−28`, `PK`).
 * With no `side`, it is the favorite's number. With a `side` (the current favorite), it is that
 * team's line, so an opener that had them as the underdog reads `+1` rather than a bare `−1`.
 */
export function formatLineNumber(spreadHome: number, side?: "home" | "away"): string {
  const magnitude = roundTo(spreadHome, 1);
  if (magnitude === 0) return "PK";
  const favored = side === undefined || (side === "home" ? spreadHome < 0 : spreadHome > 0);
  return `${favored ? MINUS : "+"}${wholeOrOneDecimal(magnitude)}`;
}

/**
 * Model line from `pred_margin` (home − away, positive when home is favored).
 * Always one decimal, so a model line never looks like a market line.
 */
export function formatModelLine(predMargin: number, home: string, away: string): string {
  const magnitude = roundTo(predMargin, 1);
  if (magnitude === 0) return "PK";
  const favorite = predMargin > 0 ? home : away;
  return `${favorite} ${MINUS}${magnitude.toFixed(1)}`;
}

/** American price, always signed: `−110`, `+150`. */
export function formatPrice(american: number): string {
  return signed(american, 0);
}

/** Edge in points (`edge_pts`, positive likes home): always `+`, one decimal, side after. */
export function formatEdge(edgePts: number | null, home: string, away: string): string {
  if (edgePts === null) return "—";
  const magnitude = roundTo(edgePts, 1);
  if (magnitude === 0) return "0.0";
  return `+${magnitude.toFixed(1)} ${edgePts > 0 ? home : away}`;
}

/** Cover probability as an integer percent; `~` marks a market-implied value (no model). */
export function formatCoverPct(prob: number, opts: { marketImplied?: boolean } = {}): string {
  return `${opts.marketImplied ? "~" : ""}${Math.round(prob * 100)}%`;
}

/** Model's favorite and its integer win percent: `TEX 54%`. */
export function formatWinPct(homeWinProb: number, home: string, away: string): string {
  return homeWinProb >= 0.5
    ? `${home} ${Math.round(homeWinProb * 100)}%`
    : `${away} ${Math.round((1 - homeWinProb) * 100)}%`;
}

/** A record's win rate to one decimal: `56.4%`. */
export function formatWinRate(rate: number): string {
  return `${roundTo(rate * 100, 1).toFixed(1)}%`;
}

/** Team rating: signed, one decimal (`+27.4`). */
export function formatRating(value: number): string {
  return signed(value, 1);
}

/** Week-over-week rank change: `▲3`, `▼1`, `—` for no change or no previous rank. */
export function formatRankMove(change: number | null): string {
  const rounded = change === null ? 0 : Math.round(change);
  if (rounded === 0) return "—";
  return rounded > 0 ? `▲${rounded}` : `▼${Math.abs(rounded)}`;
}

/** Win-loss record; the push count shows only when non-zero: `31-24-1`, `5-0`. */
export function formatRecord(wins: number, losses: number, pushes = 0): string {
  return pushes ? `${wins}-${losses}-${pushes}` : `${wins}-${losses}`;
}

/** Units won or lost: `+4.6u`, `−1.1u`. */
export function formatUnits(value: number): string {
  return `${signed(value, 1)}u`;
}

/** Closing-line value in points. Positive means the pick beat the close (D-132, D-140). */
export function formatClv(value: number): string {
  return `${signed(value, 1)} pts`;
}

const ZONE_LABELS: Record<string, string> = {
  "America/New_York": "ET",
  "America/Chicago": "CT",
  "America/Denver": "MT",
  "America/Los_Angeles": "PT",
};

function zoneLabel(date: Date, zone: string): string {
  const known = ZONE_LABELS[zone];
  if (known) return known;
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: zone, timeZoneName: "shortGeneric" }).formatToParts(date);
  return parts.find((p) => p.type === "timeZoneName")?.value ?? zone;
}

/**
 * Kickoff as `Sat 3:30 PM ET`; `inTable` drops the zone (the table header says it).
 * A NULL kickoff (TBA) gives the weekday of `gameDate` plus `TBA`.
 */
export function formatKickoff(
  kickoffAt: string | null,
  gameDate: string,
  opts: { zone: string; inTable?: boolean },
): string {
  if (kickoffAt === null) {
    const [year, month, day] = gameDate.slice(0, 10).split("-").map(Number);
    const weekday = new Intl.DateTimeFormat("en-US", { timeZone: "UTC", weekday: "short" }).format(
      new Date(Date.UTC(year, month - 1, day)),
    );
    return `${weekday} TBA`;
  }
  const date = new Date(kickoffAt);
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: opts.zone,
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).formatToParts(date);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const text = `${get("weekday")} ${get("hour")}:${get("minute")} ${get("dayPeriod")}`;
  return opts.inTable ? text : `${text} ${zoneLabel(date, opts.zone)}`;
}

/** Time until the pick lock: the two largest units, floored. `Locked` at or after kickoff. */
export function formatLockCountdown(kickoffAt: string, now: Date): string {
  const remaining = Date.parse(kickoffAt) - now.getTime();
  if (remaining <= 0) return "Locked";
  const totalMinutes = Math.floor(remaining / 60_000);
  if (totalMinutes < 1) return "Locks in <1m";
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return `Locks in ${days}d ${hours}h`;
  if (hours > 0) return `Locks in ${hours}h ${minutes}m`;
  return `Locks in ${minutes}m`;
}

/** Live score, away team first: `PUR 3 · OSU 24`. */
export function formatLiveScore(away: string, awayPts: number, home: string, homePts: number): string {
  return `${away} ${awayPts} · ${home} ${homePts}`;
}

/** Game clock: `Q3 9:12`; period 5 is `OT`, 6 is `2OT`. */
export function formatGameClock(period: number, secondsLeft: number): string {
  const label = period <= 4 ? `Q${period}` : period === 5 ? "OT" : `${period - 4}OT`;
  const minutes = Math.floor(secondsLeft / 60);
  const seconds = String(Math.floor(secondsLeft % 60)).padStart(2, "0");
  return `${label} ${minutes}:${seconds}`;
}

/** Final score, away team first: `Final · UNLV 24, BSU 31`. */
export function formatFinal(away: string, awayPts: number, home: string, homePts: number): string {
  return `Final · ${away} ${awayPts}, ${home} ${homePts}`;
}
