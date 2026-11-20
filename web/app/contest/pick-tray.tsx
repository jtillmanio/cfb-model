"use client";

import { ArrowLeftRight, Check, ChevronUp, CircleAlert, Copy, Lock, Plus, Sparkles, X } from "lucide-react";
import { useOptimistic, useState, useTransition } from "react";

import {
  applyTap,
  type ContestEntry,
  type ContestGame,
  copyText,
  fillFromModel,
  type Side,
  sharedCount,
  sideLabel,
  slateLayout,
  tapOutcome,
  type TapOutcome,
  trayCard,
  trayOrder,
} from "@/lib/contest";
import { cn } from "@/lib/utils";

import { addEntries, addEntry, removeEntry, type WriteResult } from "./actions";
import { RankedSlate } from "./ranked-slate";

// The pick tray and the state it shares with the slate (S-02, TASK-073; Contest Desktop `tray`,
// Contest Mobile's bottom bar, C2c, C2d, C2f). `ContestPicks` owns your picks: a tap in the slate
// shows in the tray at once (`useOptimistic` over the response's entries), is saved by a Server
// Action, and a failed save puts the picks back as they were and says so. One DOM serves every
// width: the 320px panel from 1024, a bar over the tab bar below it that opens to the full tray.

type WriteFailure = Exclude<WriteResult, { kind: "saved" }>;

/** A Server Action call that never reached the server rejects (a dropped connection): that is a
 *  failed save, so it shows the failed-save state instead of reaching the route's error boundary. */
const DROPPED: WriteFailure = { kind: "failed", message: "Connection dropped" };
const dropped = (): WriteFailure => DROPPED;

/** A refused tap or a failed save. `kept` is the number of picks left as they were (C2c, C2f). */
type Notice = { title: string; reason: string; kept: number | null; retry: (() => void) | null };

const BUTTON = "inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-md px-3 text-label font-medium";
const OUTLINE = cn(BUTTON, "border border-input hover:bg-accent");

export function ContestPicks({
  contestId,
  contestName,
  period,
  picks,
  games,
  entries: saved,
}: {
  contestId: number;
  contestName: string;
  period: number;
  /** `rules.picks_per_period` */
  picks: number;
  games: readonly ContestGame[];
  entries: readonly ContestEntry[];
}) {
  const [entries, show] = useOptimistic(
    saved,
    (current, change: { game: ContestGame; side: Side; outcome: TapOutcome; at: string }) =>
      applyTap(current, change.game, change.side, change.outcome, change.at),
  );
  const [saving, startTransition] = useTransition();
  const [notice, setNotice] = useState<Notice | null>(null);
  const layout = slateLayout(games);

  function failure(
    game: ContestGame,
    side: Side,
    outcome: TapOutcome,
    result: WriteFailure,
    retry: () => void,
    kept: number = saved.length,
  ): Notice {
    const what = outcome === "remove" ? `Couldn't remove ${sideLabel(game, side)}` : `Couldn't save ${sideLabel(game, side)}`;
    return result.kind === "refused"
      ? { title: what, reason: result.message, kept, retry: null }
      : { title: what, reason: "Connection dropped", kept, retry };
  }

  function tap(game: ContestGame, side: Side) {
    const outcome = tapOutcome(entries, game, side, picks);
    if (outcome === "locked") return;
    if (outcome === "full") {
      setNotice({
        title: `Your ${picks} picks are in`,
        reason: "Remove one to add another, or tap the other side of a pick to switch it.",
        kept: null,
        retry: null,
      });
      return;
    }
    setNotice(null);
    startTransition(async () => {
      show({ game, side, outcome, at: new Date().toISOString() });
      const result: WriteResult = await (
        outcome === "remove" ? removeEntry(contestId, game.id) : addEntry(contestId, game.id, side)
      ).catch(dropped);
      if (result.kind !== "saved") setNotice(failure(game, side, outcome, result, () => tap(game, side)));
    });
  }

  function fill() {
    const todo = fillFromModel(games, entries, picks);
    if (todo.length === 0) return;
    setNotice(null);
    startTransition(async () => {
      const at = new Date().toISOString();
      for (const { game, side } of todo) show({ game, side, outcome: "add", at });
      const result = await addEntries(
        contestId,
        todo.map(({ game, side }) => ({ game_id: game.id, side })),
      ).catch((): WriteResult & { done: number } => ({ ...DROPPED, done: 0 }));
      if (result.kind !== "saved") {
        // The picks before the one that failed are saved; the notice names the one that wasn't.
        const failed = todo[Math.min(result.done, todo.length - 1)];
        setNotice(failure(failed.game, failed.side, "add", result, fill, saved.length + result.done));
      }
    });
  }

  return (
    <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start lg:gap-6">
      <div className="flex min-w-0 flex-col gap-3">
        {layout.allLocked ? (
          <p
            data-slot="all-locked"
            className="flex items-center gap-2 rounded-lg border bg-card px-3 py-3 text-body text-muted-foreground"
          >
            <Lock aria-hidden className="size-4 shrink-0" />
            Every game has kicked off. Picks are final and results follow each game.
          </p>
        ) : null}
        <RankedSlate games={games} entries={entries} picks={picks} onTap={tap} />
      </div>
      <PickTray
        games={games}
        entries={entries}
        contestName={contestName}
        period={period}
        picks={picks}
        notice={notice}
        saving={saving}
        onDismiss={() => setNotice(null)}
        onTap={tap}
        onFill={fill}
      />
    </div>
  );
}

function PickTray({
  games,
  entries,
  contestName,
  period,
  picks,
  notice,
  saving,
  onDismiss,
  onTap,
  onFill,
}: {
  games: readonly ContestGame[];
  entries: readonly ContestEntry[];
  contestName: string;
  period: number;
  picks: number;
  notice: Notice | null;
  /** A pick is being saved */
  saving: boolean;
  onDismiss: () => void;
  onTap: (game: ContestGame, side: Side) => void;
  onFill: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState<"done" | "failed" | null>(null);
  const { allLocked } = slateLayout(games);
  const ordered = trayOrder(entries);
  const cards = ordered.flatMap((entry) => {
    const game = games.find((g) => g.id === entry.game_id);
    return game ? [{ entry, game, card: trayCard(game, entry, picks) }] : [];
  });
  const count = cards.length;
  const slots = Math.max(0, picks - count);
  const suggestions = allLocked ? [] : fillFromModel(games, entries, picks);
  const shared = sharedCount(entries, games);
  const summary = [...cards.map(({ card }) => card.line), ...(slots > 0 && !allLocked ? [`${slots} open`] : [])].join(" · ");

  async function copy() {
    try {
      await navigator.clipboard.writeText(copyText(contestName, period, entries, games));
      setCopied("done");
    } catch {
      setCopied("failed");
    }
  }

  return (
    <aside
      data-slot="pick-tray"
      data-open={open ? "" : undefined}
      data-saving={saving ? "" : undefined}
      aria-label="Your picks"
      className="sticky bottom-16 z-10 md:bottom-0 -mx-4 max-h-3/4 overflow-y-auto border-t bg-card px-4 md:-mx-6 md:px-6 lg:sticky lg:top-6 lg:bottom-auto lg:mx-0 lg:max-h-none lg:self-start lg:overflow-visible lg:rounded-lg lg:border lg:p-4"
    >
      {notice ? (
        <div
          role="alert"
          data-slot="pick-notice"
          className="mt-2 mb-2 flex items-start gap-2 rounded-md border border-destructive bg-secondary p-3 text-label lg:mt-0"
        >
          <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-destructive" />
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="font-semibold">{notice.title}</span>
            {notice.kept === null ? (
              <span className="text-muted-foreground">{notice.reason}</span>
            ) : (
              <>
                <span className="text-muted-foreground max-lg:hidden">
                  {`${notice.reason} · your picks are unchanged, ${notice.kept} of ${picks}`}
                </span>
                <span className="text-muted-foreground lg:hidden">{`Picks unchanged · ${notice.kept} of ${picks}`}</span>
              </>
            )}
          </div>
          {notice.retry ? (
            <button type="button" className={OUTLINE} onClick={notice.retry}>
              Retry
            </button>
          ) : null}
          <button type="button" aria-label="Dismiss" className={cn(BUTTON, "text-muted-foreground")} onClick={onDismiss}>
            <X aria-hidden className="size-4" />
          </button>
        </div>
      ) : null}

      <div className="flex flex-col gap-1.5 py-2 lg:pt-0">
        <div className="flex items-center gap-2">
          <h2 className="flex flex-1 items-baseline gap-2 text-panel font-semibold">
            Your picks <span data-slot="pick-count">{`${count} of ${picks}`}</span>
          </h2>
          <button
            type="button"
            aria-expanded={open}
            aria-controls="pick-tray-body"
            aria-label={open ? "Hide your picks" : "Show your picks"}
            onClick={() => setOpen(!open)}
            className={cn(BUTTON, "text-muted-foreground lg:hidden")}
          >
            <ChevronUp aria-hidden className={cn("size-4 transition-transform", open && "rotate-180")} />
          </button>
        </div>
        <div aria-hidden className={cn("grid-cols-4 gap-1 lg:grid", open ? "grid" : "hidden")}>
          {Array.from({ length: picks }, (_, i) => (
            <span key={i} className={cn("h-1.5 rounded-xs", i < count ? "bg-foreground" : "bg-secondary")} />
          ))}
        </div>
        <p className={cn("text-caption text-muted-foreground lg:block", open ? "block" : "hidden")}>
          {count > 0 ? `${shared} of ${count} match the model · ` : ""}
          {allLocked ? "all games locked, picks are final" : "tap a side in the slate to add"}
        </p>
        <p className="text-caption text-muted-foreground lg:hidden">{summary}</p>
      </div>

      <div id="pick-tray-body" className={cn("flex-col gap-3 pb-3 lg:flex lg:pb-0", open ? "flex" : "hidden")}>
        <ul aria-label="Your picks this week" className="flex flex-col gap-3">
          {cards.map(({ entry, game, card }) => (
            <li
              key={entry.game_id}
              data-slot="tray-card"
              data-game={game.id}
              className="flex flex-col gap-2 rounded-lg border p-3"
            >
              <div className="flex items-center gap-2">
                <span className="text-panel font-semibold">{card.line}</span>
                <span
                  data-slot="pick-badge"
                  className={cn(
                    "ml-auto inline-flex h-6 items-center gap-1 rounded-full px-2 text-label whitespace-nowrap",
                    card.match && "bg-edge font-semibold text-edge-foreground",
                    card.against && "border border-neg text-neg",
                    !card.match && !card.against && "border border-dashed text-muted-foreground",
                  )}
                >
                  {card.match ? <Check aria-hidden className="size-3" /> : null}
                  {card.badge}
                </span>
              </div>
              <p className="text-label text-muted-foreground">{card.matchup}</p>
              <p className="flex items-start gap-2 text-label">
                <Lock aria-hidden className="mt-0.5 size-3.5 shrink-0" />
                {card.lockedIn}
              </p>
              <p className="flex items-start gap-2 text-label text-muted-foreground">
                <Sparkles aria-hidden className="mt-0.5 size-3.5 shrink-0" />
                {card.why}
              </p>
              <div className="flex flex-wrap items-center gap-2 border-t pt-2">
                {card.locked ? (
                  <span className="text-label text-locked">Locked at kickoff · pick is final</span>
                ) : (
                  <>
                    <button type="button" className={OUTLINE} onClick={() => onTap(game, card.switchTo)}>
                      <ArrowLeftRight aria-hidden className="size-3.5" />
                      {card.switchLabel}
                    </button>
                    <button
                      type="button"
                      aria-label={`Remove ${card.line}`}
                      className={cn(BUTTON, "text-muted-foreground hover:bg-accent hover:text-foreground")}
                      onClick={() => onTap(game, entry.side)}
                    >
                      Remove
                    </button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>

        {suggestions.length > 0 ? (
          <button type="button" data-slot="fill" className={cn(OUTLINE, "w-full")} onClick={onFill}>
            <span aria-hidden className="size-2 rounded-full bg-edge" />
            {count === 0
              ? `Use the model's top ${picks}`
              : `Fill ${suggestions.length} open slot${suggestions.length === 1 ? "" : "s"} with model's picks`}
          </button>
        ) : null}

        {Array.from({ length: slots }, (_, i) => {
          const next = suggestions.at(i);
          return (
            <div
              key={i}
              data-slot="open-slot"
              className="flex items-center gap-3 rounded-lg border border-dashed p-3 text-label text-muted-foreground"
            >
              {next ? (
                <>
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span className="text-caption">Open slot</span>
                    <span className="text-body font-semibold text-foreground">{sideLabel(next.game, next.side)}</span>
                    <span className="text-caption">{`Model #${next.game.rank}`}</span>
                  </div>
                  <button
                    type="button"
                    aria-label={`Add ${sideLabel(next.game, next.side)}`}
                    className={OUTLINE}
                    onClick={() => onTap(next.game, next.side)}
                  >
                    <Plus aria-hidden className="size-3.5" />
                    Add
                  </button>
                </>
              ) : (
                <span className="italic">{allLocked ? "Empty · no games left to pick" : "Open slot"}</span>
              )}
            </div>
          );
        })}

        <div className="flex flex-col gap-2 border-t pt-3">
          <p className="text-caption text-muted-foreground">
            Picks save the moment you tap. Each one can be switched or removed until its game kicks off.
          </p>
          <button
            type="button"
            className={cn(OUTLINE, "w-full")}
            disabled={count === 0}
            onClick={copy}
          >
            <Copy aria-hidden className="size-4" />
            Copy picks to enter on Splash
          </button>
          <p role="status" className="min-h-4 text-caption text-muted-foreground">
            {copied === "done" ? "Copied. Paste it where you enter your picks." : null}
            {copied === "failed" ? "Couldn't copy. Select your picks above and copy them by hand." : null}
          </p>
        </div>
      </div>
    </aside>
  );
}
