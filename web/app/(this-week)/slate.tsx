import { Check, ChevronRight, Clock, History } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { EdgePill } from "@/components/edge-pill";
import { MarketCell } from "@/components/market-cell";
import { ResultMarker } from "@/components/result-marker";
import { TeamChip } from "@/components/team-chip";
import { TierBadge } from "@/components/tier-badge";
import {
  type RowNote,
  type RowView,
  type Slate,
  type SlateWindow,
  noPicksNote,
  offseasonSeason,
  recordStrip,
  rowView,
  slateCaption,
  slateLegend,
  slateWindows,
  type TeamLine,
  type Tone,
} from "@/lib/slate";
import { cn } from "@/lib/utils";

import { NoPicksStrip } from "./record-strip";
import { ShowingCount, SlateChips, SlateFilterRoot, SlateStrip } from "./slate-filters";
import { SlateEmpty } from "./slate-empty";

// This Week (S-01, TASK-056): the slate as one list of games grouped by kickoff window. Each game
// is ONE tree of elements that CSS lays out per width, so the document stays small:
//   below 768   a card: status line, teams, a Market / Model / Edge box, Cover and Win, the note
//   768 to 1439 the tablet board's grid (Win % and Pick · result drop; they're on Game Detail)
//   1440 up     the desktop board's grid, rows 44px, the number band behind Market · Model · Edge
// The 1440 break is the owner's (plan gate): the desktop columns need ~976px and the content
// column is ~992px at 1280. It is the `wide` breakpoint (globals.css `@theme`): an arbitrary
// `min-[1440px]:` sorts before `md:` in the generated CSS, so md rules would win. Grids are from the
// boards (This Week Desktop / Tablet / Mobile).

const TABLET_COLS = "md:grid-cols-[24px_64px_minmax(0,1fr)_108px_84px_92px_48px_24px_14px]";
const DESKTOP_COLS =
  "wide:grid-cols-[24px_100px_minmax(0,1fr)_388px_92px_32px_76px_160px_16px]";
const BAND_COLS = "wide:grid-cols-[36px_152px_92px_minmax(0,1fr)]";
const GRID = cn("md:grid md:items-center md:gap-x-2 md:px-3", TABLET_COLS, DESKTOP_COLS);

const TONE: Record<Tone, string> = {
  ink: "text-foreground",
  muted: "text-muted-foreground",
  pos: "text-pos",
  neg: "text-neg",
};

/** The page: title, caption, then the content. Loading and the loaded page share it. */
export function SlatePage({ caption, children }: { caption: ReactNode; children: ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-304 px-4 py-6 md:px-6">
      <header className="mb-3 flex flex-col gap-1 md:flex-row md:items-baseline md:gap-4">
        <h1 className="text-section font-semibold tracking-[-0.005em] md:text-title">This Week</h1>
        <p className="text-caption text-muted-foreground md:text-body">{caption}</p>
      </header>
      {children}
    </main>
  );
}

/** The column headers, real while loading too (md and up; phones label each card instead). */
export function SlateColumnHeader() {
  const cell = "flex items-center";
  const right = cn(cell, "justify-end");
  return (
    <div
      data-slot="slate-header"
      className={cn(
        "hidden h-9 border-b text-caption font-medium text-muted-foreground wide:h-8",
        GRID,
      )}
    >
      <span />
      <span className={cell}>Kickoff ET</span>
      <span className={cell}>Matchup</span>
      <div
        className={cn(
          "md:contents wide:grid wide:h-full wide:border-x wide:bg-muted wide:text-foreground",
          BAND_COLS,
        )}
      >
        <span className="hidden wide:block" />
        <span
          title="Opening line and its movement, then the current consensus line"
          className={cn(right, "gap-1.5 wide:px-2.5")}
        >
          <span className="hidden font-normal text-muted-foreground wide:inline">open →</span>
          Market
        </span>
        <span className={cn(right, "wide:px-2.5")}>Model</span>
        <span className={cn(right, "wide:px-2")}>Edge</span>
      </div>
      <span className={right}>
        Cover<span className="hidden wide:inline">&nbsp;%</span>
      </span>
      <span className={cn(cell, "justify-center")}>Tier</span>
      <span className={cn(right, "hidden wide:flex")}>Win %</span>
      <span className={cn(cell, "hidden pl-2 wide:flex")}>Pick · result</span>
      <span />
    </div>
  );
}

/** A window's heading bar: `SAT NOON  Sat 10/10 · 12:00 PM ET`. */
export function WindowHeading({ id, label, time }: { id?: string; label: string; time: string }) {
  return (
    <h2
      id={id}
      className="flex h-8 items-center gap-2 px-1 text-caption md:h-7 md:gap-2.5 md:border-b md:bg-background md:px-3 md:pl-11"
    >
      <span className="font-semibold tracking-wide uppercase">{label}</span>
      <span className="font-normal text-muted-foreground">{time}</span>
    </h2>
  );
}

/** The table frame: a bordered card from 768, bare cards on a phone. */
export function SlateFrame({ children }: { children: ReactNode }) {
  return <div className="md:overflow-hidden md:rounded-lg md:border md:bg-card">{children}</div>;
}

function NoteIcon({ icon }: { icon: NonNullable<RowNote["icon"]> }) {
  const Icon = icon === "check" ? Check : icon === "clock" ? Clock : History;
  return <Icon aria-hidden className="size-3.5 shrink-0" />;
}

function Note({ note }: { note: RowNote }) {
  return (
    <span
      className={cn(
        "flex min-w-0 items-center gap-1.5 text-label md:text-caption",
        TONE[note.tone],
      )}
    >
      {note.result ? <ResultMarker result={note.result} /> : note.icon ? <NoteIcon icon={note.icon} /> : null}
      <span title={note.text} className="min-w-0 wide:truncate">
        {note.text}
      </span>
    </span>
  );
}

function NeutralTag({ city }: { city: string | null }) {
  return (
    <span
      title="Neutral site"
      className="hidden h-4.5 shrink-0 items-center rounded-sm border px-1.25 text-caption whitespace-nowrap text-muted-foreground md:inline-flex"
    >
      N{city ? <span className="hidden wide:inline">&nbsp;·&nbsp;{city}</span> : null}
    </span>
  );
}

function Score({ team }: { team: TeamLine }) {
  if (team.points === null) return null;
  return (
    <span
      data-cell="score"
      className={cn(
        "shrink-0 font-mono text-panel tabular-nums md:text-label",
        team.tone === "loser" ? "font-medium text-muted-foreground" : "font-semibold",
      )}
    >
      {team.points}
    </span>
  );
}

function TeamRow({
  side,
  team,
  neutral,
}: {
  side: "away" | "home";
  team: TeamLine;
  neutral?: { city: string | null } | null;
}) {
  return (
    <div data-team={side} className="flex h-6.5 min-w-0 items-center gap-1.5 md:h-5">
      <TeamChip
        full
        abbreviation={team.abbr}
        school={team.school}
        logoUrl={team.logoUrl}
        color={team.color}
        rank={team.rank}
        fcs={team.fcs}
        className={cn("h-5 px-0", team.tone === "loser" && "text-muted-foreground")}
      />
      {neutral ? <NeutralTag city={neutral.city} /> : null}
      <span className="flex-1" />
      <Score team={team} />
    </div>
  );
}

function Status({ row }: { row: RowView }) {
  return (
    <div
      data-cell="status"
      className="flex h-6 items-center gap-2 text-caption text-muted-foreground md:h-auto md:flex-col md:items-start md:gap-px"
    >
      {row.status === "live" ? (
        <span className="flex items-center gap-1.5 font-semibold text-live">
          <span data-slot="live-dot" aria-hidden className="size-1.5 rounded-full bg-current" />
          Live
        </span>
      ) : row.status === "scheduled" ? (
        <span className="font-medium text-foreground md:text-label">{row.statusLabel}</span>
      ) : (
        <span className="font-semibold md:text-label md:font-medium">{row.statusLabel}</span>
      )}
      {row.neutral ? (
        <span className="md:hidden">Neutral{row.neutral.city ? ` · ${row.neutral.city}` : ""}</span>
      ) : null}
    </div>
  );
}

function CoverBar({ prob, clears }: { prob: number; clears: boolean }) {
  return (
    <span
      aria-hidden
      className="relative hidden h-1 w-9 shrink-0 overflow-hidden rounded-full bg-secondary wide:block"
    >
      <span
        className={cn("absolute inset-y-0 left-0", clears ? "bg-edge" : "bg-muted-foreground")}
        style={{ width: `${Math.round(prob * 100)}%` }}
      />
    </span>
  );
}

/** One game. The whole row is the link; each cell is labelled by its column or its card line. */
export function GameRow({ row, threshold }: { row: RowView; threshold: number }) {
  const home = row.home.abbr;
  const away = row.away.abbr;
  const { current, opener, snapshots } = row.market;
  const clears = row.edge.clears;
  return (
    <Link
      href={row.href}
      prefetch={false}
      data-slot="game-row"
      data-game={row.id}
      data-pick={row.hasPick ? "" : undefined}
      className={cn(
        "flex flex-col gap-2.5 rounded-lg border bg-card px-3.5 pt-2.5 pb-3 active:bg-accent",
        "md:min-h-14 md:gap-0 md:rounded-none md:border-0 md:border-b md:bg-transparent md:py-1.5 md:hover:bg-accent",
        "wide:h-11 wide:min-h-0 wide:py-0",
        GRID,
      )}
    >
      <span aria-hidden className="hidden md:block" />
      <Status row={row} />
      <div className="flex min-w-0 flex-col gap-0.5">
        <TeamRow side="away" team={row.away} />
        <TeamRow side="home" team={row.home} neutral={row.neutral} />
      </div>

      <div
        className={cn(
          "overflow-hidden rounded-md border bg-muted md:contents",
          "wide:flex wide:flex-col wide:justify-center wide:self-stretch",
          "wide:overflow-visible wide:rounded-none wide:border-x wide:border-y-0",
        )}
      >
        <div className="grid h-5.5 grid-cols-[34px_1fr_1fr_1.4fr] items-center text-caption font-semibold tracking-wider text-muted-foreground md:hidden">
          <span />
          <span className="px-1.5">MARKET</span>
          <span className="px-1.5">MODEL</span>
          <span className="px-1.5">EDGE</span>
        </div>
        <div
          className={cn(
            "grid h-10 grid-cols-[34px_1fr_1fr_1.4fr] items-center border-t md:contents",
            "wide:grid wide:h-auto wide:border-t-0",
            BAND_COLS,
          )}
        >
          <span className="pl-2 text-caption font-semibold tracking-wider text-muted-foreground md:hidden wide:block wide:pl-2.5">
            ATS
          </span>
          <div data-cell="market" className="px-1.5 md:flex md:justify-end md:px-0 wide:px-2.5">
            <span className="wide:hidden">
              <MarketCell stacked opener={opener} snapshots={snapshots} current={current} home={home} away={away} />
            </span>
            <span className="hidden wide:block">
              <MarketCell opener={opener} snapshots={snapshots} current={current} home={home} away={away} />
            </span>
          </div>
          <span
            data-cell="model"
            className="px-1.5 text-label font-medium whitespace-nowrap md:px-0 md:text-right md:text-body wide:px-2.5 wide:text-label"
          >
            {row.modelLine ?? "—"}
          </span>
          <span
            data-cell="edge"
            // The pill is 22px / 12px on a card, 24px / 13px at 768 and 20px / 12px at 1440, as the
            // boards draw it: the shared pill is the tablet size, and a card has no room for it
            // beside the tier badge.
            className={cn(
              "flex items-center gap-1.5 px-1.5 md:justify-end md:px-0 wide:px-2",
              "[&_[data-variant]]:h-5.5 [&_[data-variant]]:text-caption",
              "md:[&_[data-variant]]:h-6 md:[&_[data-variant]]:text-label",
              "wide:[&_[data-variant]]:h-5 wide:[&_[data-variant]]:text-caption",
            )}
          >
            <EdgePill edgePts={row.edge.pts} home={home} away={away} threshold={threshold} />
            {row.tier ? (
              <span className="md:hidden">
                <TierBadge tier={row.tier} />
              </span>
            ) : null}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2 text-caption text-muted-foreground md:contents">
        <span
          data-cell="cover"
          className={cn(
            "flex items-center gap-1.5 md:justify-end md:text-body wide:text-caption",
            clears && "font-semibold text-foreground",
          )}
        >
          <span className="md:hidden">Cover&nbsp;</span>
          <span>{row.cover ?? "—"}</span>
          {row.coverProb !== null ? <CoverBar prob={row.coverProb} clears={clears} /> : null}
        </span>
        <span className="hidden justify-center md:flex">
          {row.tier ? (
            <TierBadge tier={row.tier} />
          ) : (
            // A lined row with no tier stays blank at 1440; a row with no line prints "—" there too.
            <span className={cn(row.hasLine && "wide:hidden")}>
              <TierBadge tier={null} />
            </span>
          )}
        </span>
        <span className="max-md:ml-auto md:hidden wide:block wide:text-right">
          <span className="wide:hidden">Win&nbsp;</span>
          <span data-cell="win">{row.win ?? "—"}</span>
        </span>
      </div>

      <div
        data-cell="notes"
        className="flex min-w-0 flex-col gap-0.5 border-t pt-2 max-md:empty:hidden md:hidden wide:flex wide:border-t-0 wide:pt-0 wide:pl-2"
      >
        {row.notes.map((note) => (
          <Note key={note.text} note={note} />
        ))}
      </div>
      <ChevronRight aria-hidden className="hidden size-3.5 text-muted-foreground md:block" />
    </Link>
  );
}

function WindowSection({ window, rules }: { window: SlateWindow; rules: Slate["rules"] }) {
  const id = `window-${window.key}`;
  const picks = window.games.filter((g) => g.pick !== null).length;
  return (
    <section aria-labelledby={id} data-picks={picks}>
      <WindowHeading id={id} label={window.label} time={window.time} />
      <div className="flex flex-col gap-2.5 pb-3 md:block md:pb-0">
        {window.games.map((game) => (
          <GameRow
            key={game.id}
            row={rowView(game, rules)}
            threshold={rules?.min_edge_pts ?? Number.POSITIVE_INFINITY}
          />
        ))}
      </div>
    </section>
  );
}

/** The page's content for a loaded slate: the strip and chips, the windows, then the footer with the printed legend. */
export function SlateView({ slate }: { slate: Slate }) {
  if (slate.offseason) {
    return (
      <SlatePage caption={slateCaption(slate)}>
        <SlateEmpty season={offseasonSeason(slate)} nextKickoffAt={slate.next_kickoff_at} />
      </SlatePage>
    );
  }
  const windows = slateWindows(slate.games);
  const strip = recordStrip(slate.games);
  const picks = slate.games.filter((g) => g.pick !== null).length;
  return (
    <SlatePage caption={slateCaption(slate)}>
      <SlateFilterRoot>
        <div className="mb-3">
          {strip.segments.length > 0 ? <SlateStrip strip={strip} /> : <NoPicksStrip {...noPicksNote(slate)} />}
        </div>
        <div className="mb-3">
          <SlateChips />
        </div>
        <SlateFrame>
          <SlateColumnHeader />
          {windows.map((window) => (
            <WindowSection key={window.key} window={window} rules={slate.rules} />
          ))}
          <div className="flex flex-col gap-1 px-1 pt-1 text-caption text-muted-foreground md:min-h-10 md:flex-row md:items-center md:justify-between md:gap-4 md:px-3 md:py-2 md:pl-11">
            <ShowingCount shown={slate.games.length} total={slate.counts.games} picks={picks} />
            <span data-slot="slate-legend" className="md:text-right">
              {slateLegend(slate.rules)}
            </span>
          </div>
        </SlateFrame>
      </SlateFilterRoot>
    </SlatePage>
  );
}
