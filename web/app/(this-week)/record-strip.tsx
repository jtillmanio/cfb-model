import { ChevronRight, Clock } from "lucide-react";

import type { RecordStrip, StripState } from "@/lib/slate";
import { cn } from "@/lib/utils";

// The live record strip (F-32, design/README.md › Components) and its empty note. One tree for
// every width, laid out by CSS as the boards draw it:
//   below 768   56px, two lines: the stats, then the segments and the live note
//   768 to 1439 44px, one line, no live note and no call to action
//   1440 up     40px, one line, with the live note and the "Show picks" call to action

const LIVE_STRIPES =
  "bg-[repeating-linear-gradient(135deg,color-mix(in_oklch,var(--live)_60%,transparent)_0_3px,transparent_3px_6px)] border-live";

const SEGMENT: Record<StripState, string> = {
  won: "bg-pos border-pos",
  lost: "bg-neg border-neg",
  push: "bg-muted-foreground border-muted-foreground",
  covering: LIVE_STRIPES,
  push_live: LIVE_STRIPES,
  not_yet: LIVE_STRIPES,
  to_play: "bg-transparent border-input",
};

export function Segments({ strip }: { strip: RecordStrip }) {
  return (
    <span data-slot="strip-segments" className="flex flex-none gap-0.5">
      {strip.segments.map((segment, i) => (
        <span
          key={i}
          title={segment.label}
          data-state={segment.state}
          className={cn(
            "box-border h-3 w-1.75 rounded-xs border md:h-3.5 md:w-2.25",
            SEGMENT[segment.state],
          )}
        />
      ))}
    </span>
  );
}

/** The sentence a screen reader gets for the whole strip. */
export function stripSentence(strip: RecordStrip): string {
  const live =
    strip.live === 0
      ? ""
      : `, ${strip.live} live${strip.liveNote ? ` (${strip.liveNote})` : ""}`;
  return `This week ${strip.record}${live}, ${strip.toPlay} to play, ${strip.units}`;
}

const DOT = <span className="text-muted-foreground">·</span>;

/** The strip as a button that toggles Picks only. */
export function RecordStripButton({
  strip,
  pressed,
  onToggle,
}: {
  strip: RecordStrip;
  pressed: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      data-slot="record-strip"
      aria-pressed={pressed}
      aria-label={`${stripSentence(strip)}. ${pressed ? "Showing picks only; show all games" : "Show picks only"}`}
      title="Tap to filter the slate to picks"
      onClick={onToggle}
      className={cn(
        "flex min-h-14 w-full items-center gap-2.5 rounded-lg border bg-card px-3 py-2 text-left text-label",
        "hover:border-input md:h-11 md:min-h-0 md:px-3.5 wide:h-10",
        pressed && "border-input",
      )}
    >
      <span className="flex min-w-0 flex-1 flex-col gap-1.25 md:flex-row md:items-center md:gap-3.5">
        <span className="flex items-center gap-1.75 whitespace-nowrap md:contents md:gap-2">
          <span className="text-caption text-muted-foreground md:order-1">This week</span>
          <span className="flex items-center gap-1.75 whitespace-nowrap md:order-3 md:gap-2 md:text-body">
            <span data-slot="strip-record" className="font-semibold">
              {strip.record}
            </span>
            {strip.live > 0 ? (
              <>
                {DOT}
                <span className="inline-flex items-center gap-1 font-semibold text-live md:gap-1.25">
                  <span aria-hidden className="size-1.5 rounded-full bg-current" />
                  {strip.live} live
                </span>
                {strip.liveNote ? (
                  <span className="hidden text-muted-foreground wide:inline">({strip.liveNote})</span>
                ) : null}
              </>
            ) : null}
            {DOT}
            <span>
              <b className="font-semibold">{strip.toPlay}</b>{" "}
              <span className="text-muted-foreground">to play</span>
            </span>
            {DOT}
            <span
              className={cn(
                "font-semibold",
                strip.units.startsWith("+") ? "text-pos" : strip.units.startsWith("0") ? "" : "text-neg",
              )}
            >
              {strip.units}
            </span>
          </span>
        </span>
        <span className="flex items-center gap-2 md:contents">
          <span className="md:order-2">
            <Segments strip={strip} />
          </span>
          {strip.liveNote ? (
            <span className="truncate text-caption text-muted-foreground md:hidden">{strip.liveNote}</span>
          ) : null}
        </span>
      </span>
      <ChevronRight aria-hidden className="size-3.5 shrink-0 text-muted-foreground md:hidden" />
      <span className="hidden items-center gap-1 text-caption whitespace-nowrap text-muted-foreground wide:inline-flex">
        {pressed ? "Showing picks · show all" : "Show picks"}
        <ChevronRight aria-hidden className="size-3" />
      </span>
    </button>
  );
}

/** The dashed note that stands in for the strip when the week has no picks (F-32). */
export function NoPicksStrip({ title, body }: { title: string; body: string }) {
  return (
    <div
      data-slot="no-picks"
      className="flex min-h-14 items-start gap-2.5 rounded-lg border border-dashed px-3 py-2.5 text-label md:min-h-10 md:items-center md:px-3.5 md:py-2 md:text-body"
    >
      <Clock aria-hidden className="mt-0.5 size-3.5 shrink-0 text-muted-foreground md:mt-0" />
      <span className="flex min-w-0 flex-col gap-0.5 md:flex-row md:gap-2.5">
        <span className="font-semibold whitespace-nowrap">{title}</span>
        <span className="text-caption text-muted-foreground md:text-body">{body}</span>
      </span>
    </div>
  );
}
