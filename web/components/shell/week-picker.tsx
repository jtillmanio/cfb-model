"use client";

import { X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import {
  isShownWeek,
  type SlateWeek,
  weekHref,
  weekLabel,
} from "@/lib/slate";
import { cn } from "@/lib/utils";

// A client module, so it can't import the server-drawn shell (D-157): the live dot is drawn here.
function LiveDot({ className }: { className?: string }) {
  return <span aria-hidden className={cn("size-2 shrink-0 rounded-full bg-live", className)} />;
}

// The season/week list the top bar's week label opens (TASK-061), laid out after the Rankings
// time machine (Rankings Desktop / Mobile). An HTML `popover`, like the More sheet: the browser
// opens it from the label (`popoverTarget`), closes it on Esc or an outside tap and puts it in
// the top layer.
// - 768 and up: a panel under the label with a season column and a four-column week grid;
//   choosing a week goes straight to it.
// - Phones: a bottom sheet with season chips, the week grid and a "Show …" button; a tap on a
//   week only marks it, so a slip of the thumb doesn't load a page.
// Every target on the sheet is at least 44px. Week 0 isn't listed (the API refuses it).

export const WEEK_PICKER_ID = "shell-week-picker";

/** Where the panel opens from 768 up: under the label, from the trigger's own box. */
const WIDE = "(min-width: 768px)";

export type WeekNav = {
  /** The week on screen; null in the off-season, when the label stays static. */
  shown: SlateWeek | null;
  /** The shell's coming week: the live dot, and `/`. */
  coming: SlateWeek | null;
  /** Every week with games, oldest first. */
  weeks: SlateWeek[];
};

export function WeekPicker({ nav }: { nav: WeekNav }) {
  const { shown, coming, weeks } = nav;
  const router = useRouter();
  const panel = useRef<HTMLDivElement>(null);
  const [season, setSeason] = useState<number | undefined>((shown ?? coming)?.season);
  const [pending, setPending] = useState<SlateWeek | null>(shown);

  const seasons = [...new Set(weeks.map((w) => w.season))].sort((a, b) => b - a);
  const earliest = seasons[seasons.length - 1];
  const inSeason = weeks.filter((w) => w.season === season);

  // Each opening starts from the week on screen. From 768 the panel is placed under whichever
  // trigger is on screen at this width (the label is drawn once per layout); on a phone the CSS
  // sheet sits at the bottom.
  function opening(event: React.ToggleEvent<HTMLDivElement>) {
    const el = panel.current;
    if (event.newState !== "open" || el === null) return;
    setSeason((shown ?? coming)?.season);
    setPending(shown);
    el.style.top = el.style.left = "";
    if (!window.matchMedia(WIDE).matches) return;
    const trigger = [
      ...document.querySelectorAll<HTMLElement>(`[popovertarget="${WEEK_PICKER_ID}"]`),
    ].find((t) => t.offsetParent !== null);
    const box = trigger?.getBoundingClientRect();
    el.style.top = `${(box?.bottom ?? 56) + 6}px`;
    el.style.left = `${box?.left ?? 24}px`;
  }

  function choose(week: SlateWeek) {
    if (window.matchMedia(WIDE).matches) {
      panel.current?.hidePopover();
      router.push(weekHref(week, coming));
    } else {
      setPending(week);
    }
  }

  const target = "inline-flex items-center justify-center rounded-md text-body md:h-8 md:text-label";

  return (
    <div
      ref={panel}
      id={WEEK_PICKER_ID}
      popover="auto"
      role="dialog"
      aria-label="Choose a week"
      onToggle={opening}
      // No display utility on the popover itself: the browser hides it with display:none when closed.
      className={cn(
        "inset-x-0 top-auto bottom-0 mx-auto w-full max-w-lg rounded-t-xl border bg-popover p-0 text-popover-foreground backdrop:bg-background/60",
        "md:inset-auto md:m-0 md:w-96 md:max-w-none md:rounded-lg md:shadow-lg md:backdrop:bg-transparent",
      )}
    >
      <div className="flex flex-col gap-3 px-3 pt-3 pb-4 md:gap-2.5 md:p-3">
        <div className="flex items-center justify-between px-1">
          <div className="flex flex-col">
            <h2 className="text-section font-semibold md:text-label">Week</h2>
            <span className="text-caption text-muted-foreground">
              Season · back to {earliest}
            </span>
          </div>
          <button
            type="button"
            popoverTarget={WEEK_PICKER_ID}
            popoverTargetAction="hide"
            aria-label="Close"
            className="inline-flex size-11 items-center justify-center rounded-md text-muted-foreground hover:bg-accent md:hidden"
          >
            <X aria-hidden className="size-4.5" />
          </button>
        </div>

        <div className="flex flex-col gap-3 md:flex-row md:gap-3">
          <div
            role="group"
            aria-label="Season"
            className="flex gap-1.5 overflow-x-auto md:w-20 md:shrink-0 md:flex-col md:overflow-visible"
          >
            {seasons.map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={s === season}
                onClick={() => setSeason(s)}
                className={cn(
                  target,
                  "min-h-11 px-3.5 font-medium md:min-h-0 md:justify-start md:px-2.5",
                  s === season ? "bg-accent font-semibold" : "text-muted-foreground hover:bg-accent",
                )}
              >
                {s}
              </button>
            ))}
          </div>

          <div role="group" aria-label="Week" className="grid flex-1 grid-cols-4 content-start gap-1.5">
            {inSeason.map((week) => {
              const on = isShownWeek(week, shown);
              const marked = isShownWeek(week, pending);
              const live = isShownWeek(week, coming);
              return (
                <button
                  key={`${week.season_type}-${week.week}`}
                  type="button"
                  aria-label={weekLabel(week)}
                  aria-current={on ? "true" : undefined}
                  aria-pressed={marked}
                  onClick={() => choose(week)}
                  className={cn(
                    target,
                    "relative min-h-11 gap-1.5 border font-medium md:min-h-0",
                    marked ? "border-foreground bg-accent font-semibold" : "border-input hover:bg-accent",
                  )}
                >
                  {week.season_type === "postseason" ? "Post" : week.week}
                  {live ? <LiveDot className="size-1.5" /> : null}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between md:gap-3">
          {coming !== null ? (
            <Link
              href="/"
              prefetch={false}
              onClick={() => panel.current?.hidePopover()}
              className={cn(target, "min-h-11 gap-1.5 px-3 font-medium hover:bg-accent md:min-h-0")}
            >
              <LiveDot />
              This week
            </Link>
          ) : (
            <span />
          )}
          {pending !== null ? (
            <Link
              href={weekHref(pending, coming)}
              prefetch={false}
              onClick={() => panel.current?.hidePopover()}
              className={cn(
                target,
                "min-h-11 bg-primary px-4 font-semibold text-primary-foreground hover:opacity-90 md:hidden",
              )}
            >
              Show {weekLabel(pending)}
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  );
}
