import { formatLineNumber, formatSpread } from "@/lib/format";

import { Sparkline } from "./sparkline";

const PAST_TITLE = "Past season: opening and closing line only";

type Dots = { w: number; h: number; x1: number; x2: number; top: number; bottom: number; r: number };
const INLINE_DOTS: Dots = { w: 22, h: 10, x1: 2, x2: 20, top: 3, bottom: 7, r: 2 };
const STACKED_DOTS: Dots = { w: 16, h: 8, x1: 2, x2: 14, top: 2, bottom: 6, r: 1.75 };

// A past season's trend (Market Extras.dc.html › Past season): the open and the close as two
// dots joined by a dashed line, no in-between. The more favoured line sits at the top, as the
// sparkline's does; an unmoved line sits at mid-height. The open is hollow, the close filled.
function OpenClose({ open, close, size, className }: { open: number; close: number; size: Dots; className?: string }) {
  const mid = (size.top + size.bottom) / 2;
  const at = (v: number, other: number) => (v === other ? mid : v < other ? size.top : size.bottom);
  const y1 = at(open, close);
  const y2 = at(close, open);
  return (
    <svg
      aria-hidden="true"
      width={size.w}
      height={size.h}
      viewBox={`0 0 ${size.w} ${size.h}`}
      className={`shrink-0 overflow-visible ${className ?? ""}`}
    >
      <line
        x1={size.x1}
        y1={y1}
        x2={size.x2}
        y2={y2}
        className="stroke-muted-foreground [stroke-dasharray:2_2]"
        strokeWidth={1}
      />
      <circle cx={size.x1} cy={y1} r={size.r} className="fill-muted stroke-muted-foreground" strokeWidth={1.25} />
      <circle cx={size.x2} cy={y2} r={size.r} className="fill-muted-foreground" />
    </svg>
  );
}

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
  /**
   * A past season (TASK-061): `current` is the close, and only the open and the close are drawn,
   * as two dots joined by a dashed line; the snapshots are ignored.
   */
  past?: boolean;
};

export function MarketCell({ opener, snapshots, current, home, away, stacked, past }: MarketCellProps) {
  if (current === null) {
    return <span className="text-caption text-muted-foreground italic">No line</span>;
  }

  const side = current > 0 ? "away" : "home";
  const fromSide = (line: number) => (side === "home" ? line : -line);
  const dots = (size: Dots, className?: string) =>
    opener === null ? null : (
      <OpenClose open={fromSide(opener)} close={fromSide(current)} size={size} className={className} />
    );
  const history = snapshots.length >= 2 ? snapshots : opener === null ? [] : [opener, current];

  if (stacked) {
    const moved = opener !== current || (!past && snapshots.some((v) => v !== current));
    return (
      <span className="inline-flex flex-col items-start gap-px whitespace-nowrap md:items-end">
        <span className="text-label font-medium md:text-body">{formatSpread(current, home, away)}</span>
        {opener !== null && (
          <span
            data-slot="line-history"
            title={past ? PAST_TITLE : `Opened ${formatSpread(opener, home, away)}`}
            className="inline-flex items-center gap-1 text-caption text-muted-foreground"
          >
            {past ? dots(STACKED_DOTS) : history.length >= 2 && <Sparkline className="md:hidden" values={history.map(fromSide)} />}
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
          title={past ? PAST_TITLE : `Opened ${formatSpread(opener, home, away)}`}
          className="inline-flex items-center gap-1 text-muted-foreground"
        >
          <span className="text-caption">{formatLineNumber(opener, side)}</span>
          {past ? dots(INLINE_DOTS) : history.length >= 2 && <Sparkline values={history.map(fromSide)} />}
        </span>
      )}
      <span className="text-label font-medium">{formatSpread(current, home, away)}</span>
    </span>
  );
}
