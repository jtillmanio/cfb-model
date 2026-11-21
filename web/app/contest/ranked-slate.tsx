"use client";

import { Check, Lock, MoveUp } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Toggle } from "@/components/ui/toggle";
import { TeamChip } from "@/components/team-chip";
import {
  CONTEST_ZONE,
  type ContestEntry,
  type ContestGame,
  coverText,
  cutoffLabel,
  differsCount,
  filterGames,
  impliedText,
  lineChip,
  nextBestText,
  nflGapText,
  rankedSide,
  type Side,
  sideLabel,
  type SlateFilter,
  slateLayout,
} from "@/lib/contest";
import {
  formatEdge,
  formatKickoff,
  formatLineNumber,
  formatModelLine,
  formatSpread,
} from "@/lib/format";
import { cn } from "@/lib/utils";

// The ranked slate (S-02, TASK-073; Contest Desktop `now`, Contest Mobile). The API ranks the
// week's games against the contest's lines (D-095, D-171); this draws them in its order: the open
// games with the model's top N above the cutoff, then the games that have kicked off. One tap on a
// side adds a pick, a second tap on it removes it, a tap on the other side switches (D-070: users
// "add" picks; nothing here says "lock" for a control). One DOM serves every width: a card on a
// phone, a table row from 768.
//
// Left out, on purpose: the board's "Locks in" countdown (the response carries no clock, so a
// countdown would be wrong under the fixture clock; the kickoff time shows), the tier badge and
// the "under 2.5" caption (the response carries neither the tier nor the pick threshold, D-055).

type Props = {
  games: readonly ContestGame[];
  entries: readonly ContestEntry[];
  /** `rules.picks_per_period` */
  picks: number;
  onTap: (game: ContestGame, side: Side) => void;
};

const FILTERS: { value: SlateFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "cfb", label: "CFB" },
  { value: "nfl", label: "NFL" },
  { value: "differs", label: "Line ≠ market" },
];

// The table's columns from 1440 (below it a row is a card, which also fits beside the tray): #, matchup, contest · market, model, edge, cover, kickoff, pick.
const TABLE =
  "wide:grid-cols-[48px_minmax(0,1.9fr)_minmax(0,1.1fr)_minmax(0,.8fr)_minmax(0,.9fr)_minmax(0,.8fr)_80px_128px]";

const CHIP_TONE = { better: "border-pos text-pos", worse: "border-neg text-neg" } as const;

export function RankedSlate({ games, entries, picks, onTap }: Props) {
  const [filter, setFilter] = useState<SlateFilter>("all");
  const layout = slateLayout(filterGames(games, filter));
  const whole = slateLayout(games);
  const counts: Record<SlateFilter, number> = {
    all: games.length,
    cfb: filterGames(games, "cfb").length,
    nfl: filterGames(games, "nfl").length,
    differs: differsCount(games),
  };
  const full = entries.length >= picks;
  const rowProps = { entries, full, onTap };

  return (
    <section aria-label="Ranked slate" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div role="group" aria-label="Filter games" className="flex flex-wrap gap-1.5">
          {FILTERS.map(({ value, label }) => (
            <Toggle
              key={value}
              variant="chip"
              pressed={filter === value}
              // Pressing the pressed chip again returns to All.
              onPressedChange={() => setFilter(filter === value ? "all" : value)}
              className="h-11 gap-1 px-2.5"
            >
              {filter === value ? <Check aria-hidden className="size-3.5" /> : null}
              {label} <span className="font-normal opacity-80">{counts[value]}</span>
            </Toggle>
          ))}
        </div>
        <p className="text-caption text-muted-foreground wide:ml-auto">Ranked by cover % against the contest line</p>
      </div>

      <div className="rounded-lg border bg-card">
        <div
          aria-hidden
          className={cn("hidden h-10 items-center gap-x-3 border-b px-3 text-label font-medium text-muted-foreground wide:grid", TABLE)}
        >
          <span>#</span>
          <span>Matchup</span>
          <span className="text-right">Contest · market</span>
          <span className="text-center">Model</span>
          <span className="text-right">Edge</span>
          <span>Cover % ↓</span>
          <span>Kickoff</span>
          <span className="text-center">Pick</span>
        </div>

        <ul data-slot="contest-week" aria-label="This week's contest games">
          {layout.open.map((game) => (
            <GameRows key={game.id} game={game} {...rowProps}>
              {layout.cutoffAfter?.id === game.id && layout.nextBest ? (
                <CutoffRow label={cutoffLabel(whole, picks)} next={layout.nextBest} />
              ) : null}
            </GameRows>
          ))}
          {layout.locked.length > 0 ? (
            <li
              data-slot="locked-header"
              className="flex min-h-10 items-center gap-2 border-b bg-background px-3 text-label text-muted-foreground"
            >
              <Lock aria-hidden className="size-3.5" />
              <span className="font-semibold tracking-wider uppercase">Locked</span>
              <span>kicked off · can&apos;t be picked or changed</span>
            </li>
          ) : null}
          {layout.locked.map((game) => (
            <GameRows key={game.id} game={game} {...rowProps} />
          ))}
          {layout.open.length + layout.locked.length === 0 ? (
            <li className="px-3 py-10 text-center text-body text-muted-foreground">No games match this filter.</li>
          ) : null}
        </ul>

        <Legend />
      </div>
    </section>
  );
}

/** The game's row, then (for the last top-N game) the cutoff row as a sibling. */
function GameRows({
  game,
  children,
  ...rest
}: {
  game: ContestGame;
  children?: React.ReactNode;
  entries: readonly ContestEntry[];
  full: boolean;
  onTap: (game: ContestGame, side: Side) => void;
}) {
  return (
    <>
      <GameRow game={game} {...rest} />
      {children}
    </>
  );
}

function CutoffRow({ label, next }: { label: string; next: ContestGame }) {
  const { rank, line, cover } = nextBestText(next);
  return (
    <li
      data-slot="cutoff"
      className="flex min-h-10 flex-wrap items-center gap-x-3 gap-y-0.5 border-b bg-secondary px-3 py-1 text-label"
    >
      <span className="inline-flex items-center gap-1.5 font-semibold tracking-wider text-edge uppercase">
        <MoveUp aria-hidden className="size-3.5" />
        {label}
      </span>
      <span aria-hidden className="hidden h-px flex-1 border-t border-dashed border-edge wide:block" />
      <span className="text-muted-foreground wide:ml-auto">
        Next best <span className="font-semibold text-foreground">{`#${rank} ${line} · ${cover}`}</span>
      </span>
    </li>
  );
}

function GameRow({
  game,
  entries,
  full,
  onTap,
}: {
  game: ContestGame;
  entries: readonly ContestEntry[];
  full: boolean;
  onTap: (game: ContestGame, side: Side) => void;
}) {
  const home = game.home.abbreviation ?? game.home.school;
  const away = game.away.abbreviation ?? game.away.school;
  const mine = entries.find((e) => e.game_id === game.id);
  const side = rankedSide(game);
  const chip = lineChip(game);
  const nfl = game.model === null;
  const kickoff = formatKickoff(game.kickoff_at, game.game_date, { zone: CONTEST_ZONE, inTable: true });
  const cover = coverText(game);
  const pct = game.model ? game.model.cover_prob : (game.market_gap?.implied_prob ?? 0);
  const closed = mine ? `Your pick · ${sideLabel(game, mine.side)}` : "Picks closed";
  const modelPick = game.top_n && !game.locked;

  return (
    <li
      data-slot="contest-game"
      data-game={game.id}
      data-locked={game.locked ? "" : undefined}
      data-picked={mine ? mine.side : undefined}
      className={cn(
        "grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-2 border-b px-3 py-3 wide:items-center wide:gap-y-0 wide:py-2",
        TABLE,
        game.locked && "bg-background text-locked",
        mine && !game.locked && "bg-secondary",
      )}
    >
      <div className="col-span-2 flex items-center gap-2 wide:contents">
        <span className="wide:col-start-1 wide:row-start-1 wide:flex wide:flex-col wide:items-center wide:gap-1">
          <span
            data-slot="rank"
            className={cn(
              "inline-flex size-6 items-center justify-center rounded-full text-label font-semibold",
              modelPick ? "bg-edge text-edge-foreground" : "text-muted-foreground",
            )}
          >
            {game.locked ? <Lock aria-label="Locked" className="size-3.5" /> : game.rank}
          </span>
          <span className="ml-1 rounded-sm bg-secondary px-1 text-caption font-semibold tracking-wider text-muted-foreground wide:ml-0">
            {game.sport_id.toUpperCase()}
          </span>
        </span>
        <span className="text-label text-muted-foreground wide:col-start-7 wide:row-start-1">
          {game.locked ? `Locked · ${kickoff}` : kickoff}
        </span>
      </div>

      <div className="flex min-w-0 flex-col wide:col-start-2 wide:row-start-1">
        <TeamChip
          abbreviation={away}
          school={game.away.school}
          full
          rank={game.away.rank}
          logoUrl={game.away.logo_url}
          color={game.away.color}
          locked={game.locked}
        />
        <TeamChip
          abbreviation={home}
          school={game.home.school}
          full
          rank={game.home.rank}
          logoUrl={game.home.logo_url}
          color={game.home.color}
          neutral={game.neutral_site}
          locked={game.locked}
        />
      </div>

      <div className="flex flex-col gap-1.5 wide:col-start-8 wide:row-start-1 wide:w-32 wide:justify-self-center">
        <SideButton game={game} side="away" mine={mine} full={full} modelSide={modelPick ? side : null} onTap={onTap} />
        <SideButton game={game} side="home" mine={mine} full={full} modelSide={modelPick ? side : null} onTap={onTap} />
        {game.locked ? (
          <span data-slot="closed" className="text-center text-caption text-locked">
            {closed}
          </span>
        ) : null}
      </div>

      <dl className="col-span-2 grid grid-cols-4 gap-2 rounded-md bg-secondary px-2 py-1.5 text-label wide:contents">
        <div className="min-w-0 wide:col-start-3 wide:row-start-1 wide:text-right">
          <dt className="text-caption text-muted-foreground uppercase wide:hidden">Contest</dt>
          <dd className="font-semibold whitespace-nowrap">
            {formatSpread(game.contest_spread_home, home, away)}
          </dd>
          {game.market_spread_home !== null ? (
            <dd className="flex flex-wrap items-center gap-1 text-caption text-muted-foreground wide:justify-end">
              <span>{`mkt ${formatLineNumber(game.market_spread_home)}`}</span>
              {chip ? (
                <span
                  data-slot="line-chip"
                  data-tone={chip.tone}
                  className={cn(
                    "inline-flex h-5 items-center rounded-sm border px-1 text-caption font-medium whitespace-nowrap",
                    game.locked ? "border-border text-locked" : CHIP_TONE[chip.tone],
                  )}
                >
                  {chip.text}
                </span>
              ) : null}
            </dd>
          ) : null}
        </div>

        <div className="min-w-0 wide:col-start-4 wide:row-start-1 wide:text-center">
          <dt className="text-caption text-muted-foreground uppercase wide:hidden">Model</dt>
          <dd className={cn(nfl && "text-muted-foreground italic")}>
            {game.model ? formatModelLine(game.model.pred_margin, home, away) : "No model yet"}
          </dd>
        </div>

        <div className="min-w-0 wide:col-start-5 wide:row-start-1 wide:text-right">
          <dt className="text-caption text-muted-foreground uppercase wide:hidden">{nfl ? "Gap" : "Edge"}</dt>
          <dd>
            {game.model ? (
              <Badge variant={game.locked ? "locked" : modelPick ? "edge" : "quiet"}>
                {formatEdge(game.model.edge, home, away)}
              </Badge>
            ) : (
              <span className="text-label text-muted-foreground">{nflGapText(game)}</span>
            )}
          </dd>
        </div>

        <div className="min-w-0 wide:col-start-6 wide:row-start-1">
          <dt className="text-caption text-muted-foreground uppercase wide:hidden">Cover</dt>
          <dd className="flex flex-col">
            <span className="flex items-center gap-1.5 font-semibold">
              {cover}
              <span aria-hidden className="hidden h-1 w-6 rounded-full bg-border sm:block">
                <span
                  className={cn("block h-1 rounded-full", modelPick ? "bg-edge" : "bg-input")}
                  style={{ width: `${Math.round(pct * 100)}%` }}
                />
              </span>
            </span>
            <span className="text-caption font-normal text-muted-foreground">
              {game.model ? (side ? sideLabel(game, side) : "") : impliedText(game) ? "mkt-implied" : ""}
            </span>
          </dd>
        </div>
      </dl>
    </li>
  );
}

function SideButton({
  game,
  side,
  mine,
  full,
  modelSide,
  onTap,
}: {
  game: ContestGame;
  side: Side;
  mine: ContestEntry | undefined;
  full: boolean;
  /** The model's side on an open top-N game, for the dot */
  modelSide: Side | null;
  onTap: (game: ContestGame, side: Side) => void;
}) {
  const selected = mine?.side === side;
  const blocked = !mine && full;
  const label = sideLabel(game, side);
  return (
    <button
      type="button"
      data-slot="side-button"
      data-side={side}
      data-state={game.locked ? "locked" : selected ? "selected" : blocked ? "full" : "open"}
      aria-pressed={selected}
      aria-disabled={blocked || undefined}
      disabled={game.locked}
      onClick={() => onTap(game, side)}
      className={cn(
        "relative inline-flex min-h-11 min-w-11 items-center justify-center gap-1 rounded-md border px-3 text-label whitespace-nowrap",
        selected && "border-foreground bg-foreground font-semibold text-background",
        !selected && modelSide === side && "border-edge font-semibold",
        !selected && modelSide !== side && "border-input font-medium",
        blocked && "cursor-not-allowed text-muted-foreground opacity-60",
        game.locked && "cursor-not-allowed border-border font-medium text-locked opacity-70",
      )}
    >
      {selected ? <Check aria-hidden className="size-3.5" /> : null}
      {label}
      {modelSide === side ? (
        <span
          aria-hidden
          data-slot="model-dot"
          className={cn(
            "absolute -top-1 -right-1 size-2.5 rounded-full bg-edge ring-2",
            selected ? "ring-foreground" : "ring-card",
          )}
        />
      ) : null}
    </button>
  );
}

function Legend() {
  return (
    <div className="flex flex-col gap-1.5 px-3 py-3 text-caption text-muted-foreground">
      <p className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="size-2 rounded-full bg-edge" />
          Model&apos;s side
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="rounded-sm border border-pos px-1 text-pos">≠</span>
          contest line better than market for the ranked side
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="rounded-sm border border-neg px-1 text-neg">≠</span>
          worse
        </span>
        <span>~ = market-implied (NFL, no model yet)</span>
      </p>
      <p>Tap a side to pick · tap it again to clear · tap the other side to switch</p>
    </div>
  );
}
