import { formatLineNumber, formatSpread } from "@/lib/format";

import { Sparkline } from "./sparkline";

// LineMovementCell (design/README.md › Components; Market Extras.dc.html › Line-movement cell):
// the opening line and a sparkline, muted, before the current line, so the Market column still
// reads market → model → edge. Lines are `spread_home` (negative when home is favoured). The
// opener and the sparkline are drawn from the current favourite's side.

type MarketCellProps = {
  /** The opening line; null when none was recorded. */
  opener: number | null;
  /** Line snapshots in time order (`line_snapshots`); fewer than two joins opener to current. */
  snapshots: number[];
  /** The current line; null when the game has none. */
  current: number | null;
  home: string;
  away: string;
};

export function MarketCell({ opener, snapshots, current, home, away }: MarketCellProps) {
  if (current === null) {
    return <span className="text-caption text-muted-foreground italic">No line</span>;
  }

  const side = current > 0 ? "away" : "home";
  const fromSide = (line: number) => (side === "home" ? line : -line);
  const history = snapshots.length >= 2 ? snapshots : opener === null ? [] : [opener, current];

  return (
    <span className="inline-flex items-center justify-end gap-1.5 whitespace-nowrap">
      {opener !== null && (
        <span
          data-slot="line-history"
          title={`Opened ${formatSpread(opener, home, away)}`}
          className="inline-flex items-center gap-1 text-muted-foreground"
        >
          <span className="text-caption">{formatLineNumber(opener, side)}</span>
          {history.length >= 2 && <Sparkline values={history.map(fromSide)} />}
        </span>
      )}
      <span className="text-label font-medium">{formatSpread(current, home, away)}</span>
    </span>
  );
}
