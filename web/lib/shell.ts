import type { components } from "./api-types";
import {
  formatKickoff,
  formatRecord,
  formatUnits,
  formatWinRate,
  MINUS,
  signed,
} from "./format";

// S-16 app shell (TASK-054): the nav, and what the sidebar, top bar and banners show from a
// screen response's `shell` block (TASK-053, D-156). Pure, so server pages, the client error
// boundary and tests share it.

/** Every screen endpoint's `shell` block (generated from `api/shell.py`'s `ShellOut`). */
export type Shell = components["schemas"]["ShellOut"];

export type NavId =
  | "this-week"
  | "picks"
  | "contest"
  | "rankings"
  | "teams"
  | "performance"
  | "lab"
  | "settings";

export type NavItem = { id: NavId; label: string; href: string };

// design/README.md › Navigation, in the sidebar's order. Screens not built yet link to their
// paths and 404 until their milestones (This Week is `/`, TASK-056).
export const NAV: readonly NavItem[] = [
  { id: "this-week", label: "This Week", href: "/" },
  { id: "picks", label: "Picks", href: "/picks" },
  { id: "contest", label: "Contest", href: "/contest" },
  { id: "rankings", label: "Rankings", href: "/rankings" },
  { id: "teams", label: "Teams", href: "/teams" },
  { id: "performance", label: "Performance", href: "/performance" },
  { id: "lab", label: "Lab", href: "/lab" },
];

export const SETTINGS: NavItem = { id: "settings", label: "Settings", href: "/settings" };

const byId = (id: NavId) => NAV.find((item) => item.id === id)!;

/** Phones and the 768 nav row: four tabs, then More. */
export const MOBILE_TABS: readonly NavItem[] = (
  ["this-week", "picks", "contest", "rankings"] as const
).map(byId);

/** What More opens (B8a), each with its sub-line. */
export const MORE_ITEMS: readonly (NavItem & { sub: string; desktopOnly?: boolean })[] = [
  { ...byId("teams"), sub: "Every FBS team" },
  { ...byId("performance"), sub: "Track record" },
  { ...byId("lab"), sub: "Weights, versions, compare", desktopOnly: true },
  { ...SETTINGS, sub: "General, contests, alerts, account" },
];

/** The phone tab that lights up for a screen: More for anything that lives under it. */
export function activeTab(active: NavId): NavId | "more" {
  return MOBILE_TABS.some((tab) => tab.id === active) ? active : "more";
}

export const SHELL_COPY = {
  wordmark: "CFB Model",
  sport: "College football",
  sportShort: "CFB",
  later: "Later",
  search: "Search teams",
  more: "More",
  trackRecord: "Track record",
  down: "Can't reach the server",
  cardDown: "Unavailable until the server answers",
  refresh: "Refresh",
  // D-097: no number, so the copy stays true if Neon's wake time changes.
  waking: "Waking up the database…",
} as const;

// Every time in the shell is Eastern until Settings' time zone lands (M8.8).
const ZONE = "America/New_York";

export type ShellCard = {
  label: string;
  record: string;
  winRate: string;
  units: string;
  unitsTone: "pos" | "neg" | "zero";
  clv: string;
};

export type ShellView = {
  /** Top bar: "2026 · Week 6". */
  week: string | null;
  /** Top bar: "Updated Sat 9:00 AM ET", the newest line pull. */
  updated: string | null;
  /** Banner text when the lines are more than 24 h old (D-096), else null. */
  stale: string | null;
  /** The Picks nav badge; none when there are no picks. */
  picks: string | null;
  /** The sidebar's track-record card; null with no model. */
  card: ShellCard | null;
};

function weekLabel(shell: Shell): string | null {
  if (shell.season === null) return null;
  if (shell.season_type === "postseason") return `${shell.season} · Postseason`;
  if (shell.week === null) return String(shell.season);
  return `${shell.season} · Week ${shell.week}`;
}

function pullTime(at: string): string {
  return formatKickoff(at, at.slice(0, 10), { zone: ZONE });
}

function card(shell: Shell): ShellCard | null {
  const { record } = shell;
  if (shell.model === null || record === null) return null;
  const season = [shell.season, shell.record_label].filter((part) => part !== null).join(" ");
  const units = formatUnits(record.units);
  return {
    label: season ? `Model · ${season}` : "Model",
    record: formatRecord(record.wins, record.losses, record.pushes),
    // win_pct is 0–100 (D-156); the formatter takes a rate.
    winRate: record.win_pct === null ? "—" : formatWinRate(record.win_pct / 100),
    units,
    // From the text, so the colour always agrees with the rounded sign shown.
    unitsTone: units.startsWith("+") ? "pos" : units.startsWith(MINUS) ? "neg" : "zero",
    clv: `CLV ${record.avg_clv === null ? "—" : signed(record.avg_clv, 1)}`,
  };
}

/** What the shell draws from a response's `shell` block; null while loading or after an error. */
export function shellView(shell: Shell | null): ShellView {
  if (shell === null) return { week: null, updated: null, stale: null, picks: null, card: null };
  const at = shell.lines_updated_at;
  return {
    week: weekLabel(shell),
    updated: at === null ? null : `Updated ${pullTime(at)}`,
    stale: shell.stale && at !== null ? `Lines last updated ${pullTime(at)}` : null,
    picks: shell.picks ? String(shell.picks) : null,
    card: card(shell),
  };
}
