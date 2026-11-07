import { ChevronDown, ChevronLeft, ChevronRight, Menu, Search } from "lucide-react";
import Link from "next/link";

import { weekHref, weekLabel, weekNeighbours } from "@/lib/slate";
import { activeTab, MOBILE_TABS, type NavId, SHELL_COPY, type ShellView } from "@/lib/shell";
import { cn } from "@/lib/utils";

import { MORE_SHEET_ID } from "./mobile-tabs";
import { Bar, LiveDot, LogoMark, NAV_ICONS, type ShellState } from "./sidebar";
import { WEEK_PICKER_ID, WeekPicker, type WeekNav } from "./week-picker";

// The top bar at every width (design/README.md › Navigation):
// - xl (This Week Desktop): week label, the "Search teams ⌘K" box, "Updated …".
// - md (This Week Tablet, C16c): logo, "CFB · 2026 · Week 6", "Updated …", then a nav row.
// - phone (This Week Mobile): "CFB" | week, search.
// The week label names the week; on This Week (which passes `weekNav`, TASK-061) it steps: arrows
// at xl and a label that opens the season/week list at every width. Other screens keep the static
// label until their own tasks need it. Search is
// inert until the ⌘K palette (M8.6, D-088); the alerts bell is hidden until F-14.

function Status({ view, state }: { view: ShellView; state: ShellState }) {
  if (state === "loading") return <Bar className="hidden h-3 w-36 md:inline-block" />;
  if (state === "error") {
    return (
      <span className="hidden items-center gap-1.5 text-caption font-medium md:inline-flex">
        <span aria-hidden className="size-1.5 rounded-full bg-destructive" />
        {SHELL_COPY.down}
      </span>
    );
  }
  return view.updated ? (
    <span className="hidden text-caption text-muted-foreground md:inline">{view.updated}</span>
  ) : null;
}

function Week({
  week,
  state,
  className,
}: {
  week: string | null;
  state: ShellState;
  className?: string;
}) {
  if (state === "loading") return <Bar className={cn("h-3.5 w-24", className)} />;
  return week ? <span className={className}>{week}</span> : null;
}

function SectionsNav({ active }: { active: NavId }) {
  const lit = activeTab(active);
  const item = "flex h-12 items-center gap-2 border-b-2 px-3 text-label";
  const on = "border-foreground font-semibold text-foreground";
  const off = "border-transparent font-medium text-muted-foreground hover:text-foreground";
  return (
    <nav aria-label="Sections" className="hidden gap-1 border-t px-5 md:flex xl:hidden">
      {MOBILE_TABS.map((tab) => {
        const Icon = NAV_ICONS[tab.id];
        return (
          <Link
            key={tab.id}
            href={tab.href}
            prefetch={false}
            aria-current={lit === tab.id ? "page" : undefined}
            className={cn(item, lit === tab.id ? on : off)}
          >
            <Icon aria-hidden className="size-4 shrink-0" />
            {tab.label}
          </Link>
        );
      })}
      <button
        type="button"
        popoverTarget={MORE_SHEET_ID}
        aria-current={lit === "more" ? "page" : undefined}
        className={cn(item, lit === "more" ? on : off)}
      >
        <Menu aria-hidden className="size-4 shrink-0" />
        {SHELL_COPY.more}
      </button>
    </nav>
  );
}

// The desktop week box: [‹][2026 · Week 5 ⌄][›]. An arrow at either end of the list is disabled.
function DesktopWeek({ nav }: { nav: WeekNav & { shown: NonNullable<WeekNav["shown"]> } }) {
  const { previous, next } = weekNeighbours(nav.weeks, nav.shown);
  const arrow = "inline-flex size-8 items-center justify-center text-muted-foreground";
  const step = (to: typeof previous, label: string, Icon: typeof ChevronLeft) =>
    to === null ? (
      <span role="link" aria-disabled="true" aria-label={label} className={cn(arrow, "opacity-40")}>
        <Icon aria-hidden className="size-4" />
      </span>
    ) : (
      <Link
        href={weekHref(to, nav.coming)}
        prefetch={false}
        aria-label={label}
        className={cn(arrow, "hover:bg-accent hover:text-foreground")}
      >
        <Icon aria-hidden className="size-4" />
      </Link>
    );
  return (
    <span className="hidden h-8 items-center overflow-hidden rounded-md border border-input xl:inline-flex">
      {step(previous, "Previous week", ChevronLeft)}
      <button
        type="button"
        popoverTarget={WEEK_PICKER_ID}
        className="inline-flex h-8 items-center gap-1.5 border-x border-input px-3 text-label font-semibold whitespace-nowrap hover:bg-accent"
      >
        {weekLabel(nav.shown)}
        <ChevronDown aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
      </button>
      {step(next, "Next week", ChevronRight)}
    </span>
  );
}

export function TopBar({
  active,
  view,
  state,
  weekNav,
}: {
  active: NavId;
  view: ShellView;
  state: ShellState;
  weekNav?: WeekNav;
}) {
  const nav = weekNav?.shown ? { ...weekNav, shown: weekNav.shown } : null;
  return (
    <header className="sticky top-0 z-10 border-b bg-card xl:bg-background">
      <div className="flex h-13 items-center gap-1 pl-3 pr-1 md:h-14 md:gap-2.5 md:px-6 xl:gap-3">
        {/* Phone: sport | week. */}
        <span className="inline-flex h-11 items-center gap-1 px-1.5 text-label font-semibold md:hidden">
          <LiveDot className="size-1.75" />
          {SHELL_COPY.sportShort}
        </span>
        {state === "loading" || view.week ? (
          <span aria-hidden className="h-5 w-px bg-border md:hidden" />
        ) : null}
        {nav ? (
          <button
            type="button"
            popoverTarget={WEEK_PICKER_ID}
            className="inline-flex h-11 items-center gap-1 px-2 text-body font-semibold md:hidden"
          >
            {weekLabel(nav.shown)}
            <ChevronDown aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
          </button>
        ) : (
          <Week
            week={view.week}
            state={state}
            className="inline-flex h-11 items-center px-2 text-body font-semibold md:hidden"
          />
        )}

        {/* Tablet: logo, then sport and week in one box. */}
        <span className="hidden md:inline-flex xl:hidden">
          <LogoMark />
        </span>
        {(() => {
          const box = (
            <>
              <LiveDot className="size-1.75" />
              {SHELL_COPY.sportShort}
              {nav ? ` · ${weekLabel(nav.shown)}` : state !== "loading" && view.week ? ` · ${view.week}` : null}
              <ChevronDown aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
            </>
          );
          const cls =
            "hidden h-8 items-center gap-1.5 rounded-md border border-input px-2.5 text-label font-semibold md:inline-flex xl:hidden";
          return nav ? (
            <button type="button" popoverTarget={WEEK_PICKER_ID} className={cn(cls, "hover:bg-accent")}>
              {box}
            </button>
          ) : (
            <span className={cls}>{box}</span>
          );
        })()}

        {/* Desktop: the week box (none with no week to name) and the search box. */}
        {nav ? (
          <DesktopWeek nav={nav} />
        ) : state === "loading" || view.week ? (
          <span className="hidden h-8 items-center rounded-md border border-input px-3 text-label font-semibold whitespace-nowrap xl:inline-flex">
            <Week week={view.week} state={state} />
          </span>
        ) : null}
        <span
          aria-disabled
          className="hidden h-8 w-80 items-center gap-2 rounded-md border border-input px-2.5 text-label text-muted-foreground xl:inline-flex"
        >
          <Search aria-hidden className="size-3.5 shrink-0" />
          <span className="flex-1">{SHELL_COPY.search}</span>
          <kbd className="inline-flex h-5 items-center rounded-sm border bg-muted px-1.5 font-mono text-caption font-medium">
            ⌘K
          </kbd>
        </span>

        <span className="flex-1" />
        <Status view={view} state={state} />
        <span
          aria-hidden
          className="inline-flex size-11 items-center justify-center text-muted-foreground md:text-foreground xl:hidden"
        >
          <Search className="size-4.5" />
        </span>
      </div>
      <SectionsNav active={active} />
      {weekNav?.shown ? <WeekPicker nav={weekNav} /> : null}
    </header>
  );
}
