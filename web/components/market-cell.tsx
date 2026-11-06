import { formatLineNumber, formatSpread } from "@/lib/format";

import { Sparkline } from "./sparkline";

// LineMovementCell (design/README.md › Components; Market Extras.dc.html › Line-movement cell):
// the opening line and a sparkline, muted, before the current line, so the Market column still
// reads market → model → edge. Lines are `spread_home` (negative when home is favoured). The
// opener and the sparkline are drawn from the current favourite's side.
//
// `stacked` is the 768 and phone layout (This Week Tablet / Mobile boards): the current line over
// "opened −28" or "no move", the sparkline kept on phones and dropped on tablets. The inline
// layout stays the default; a screen that needs both draws each and shows one per width.

type MarketCellProps = {
  /** The opening line; null when none was recorded. */
  opener: number | null;
  /** Line snapshots in time order (`line_snapshots`); fewer than two joins opener to current. */
  snapshots: number[];
  /** The current line; null when the game has none. */
  current: number | null;
  home: string;
  away: string;
  /** The current line over a muted "opened …" line, instead of the opener before it. */
  stacked?: boolean;
};

export function MarketCell({ opener, snapshots, current, home, away, stacked }: MarketCellProps) {
  if (current === null) {
    return <span className="text-caption text-muted-foreground italic">No line</span>;
  }

  const side = current > 0 ? "away" : "home";
  const fromSide = (line: number) => (side === "home" ? line : -line);
  const history = snapshots.length >= 2 ? snapshots : opener === null ? [] : [opener, current];

  if (stacked) {
    const moved = opener !== current || snapshots.some((v) => v !== current);
    return (
      <span className="inline-flex flex-col items-start gap-px whitespace-nowrap md:items-end">
        <span className="text-label font-medium md:text-body">{formatSpread(current, home, away)}</span>
        {opener !== null && (
          <span
            data-slot="line-history"
            title={`Opened ${formatSpread(opener, home, away)}`}
            className="inline-flex items-center gap-1 text-caption text-muted-foreground"
          >
            {history.length >= 2 && <Sparkline className="md:hidden" values={history.map(fromSide)} />}
            <span>{moved ? `opened ${formatLineNumber(opener, side)}` : "no move"}</span>
          </span>
        )}
      </span>
    );
  }

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
