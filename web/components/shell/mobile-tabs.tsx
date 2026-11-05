import { Check, ChevronRight, Ellipsis, Monitor, X } from "lucide-react";
import Link from "next/link";

import { activeTab, MOBILE_TABS, MORE_ITEMS, type NavId, SHELL_COPY, type ShellCard } from "@/lib/shell";
import { cn } from "@/lib/utils";

import { LiveDot, NAV_ICONS } from "./sidebar";

// Phones (This Week Mobile): a 64px bottom tab bar with This Week, Picks, Contest, Rankings and
// More, every target at least 44px. More opens a sheet (B8a, App States Mobile frame "more") that
// the 768 nav row opens too. The sheet is an HTML `popover`, so it needs no client JS: the
// browser opens it, closes it on Esc or an outside tap, and puts it in the top layer.

export const MORE_SHEET_ID = "shell-more";

export function MobileTabs({ active }: { active: NavId }) {
  const lit = activeTab(active);
  const tab = "flex flex-1 flex-col items-center justify-center gap-0.75 text-caption";
  const pill = (on: boolean) =>
    cn("inline-flex h-7 w-12 items-center justify-center rounded-full", on && "bg-accent");
  const tone = (on: boolean) =>
    on ? "font-semibold text-foreground" : "font-medium text-muted-foreground";
  return (
    <nav
      aria-label="Tabs"
      className="fixed inset-x-0 bottom-0 z-20 flex h-16 border-t bg-card md:hidden"
    >
      {MOBILE_TABS.map((item) => {
        const Icon = NAV_ICONS[item.id];
        const on = lit === item.id;
        return (
          <Link
            key={item.id}
            href={item.href}
            prefetch={false}
            aria-current={on ? "page" : undefined}
            className={cn(tab, tone(on))}
          >
            <span className={pill(on)}>
              <Icon aria-hidden className="size-4.5" />
            </span>
            {item.label}
          </Link>
        );
      })}
      <button
        type="button"
        popoverTarget={MORE_SHEET_ID}
        aria-current={lit === "more" ? "page" : undefined}
        className={cn(tab, tone(lit === "more"))}
      >
        <span className={pill(lit === "more")}>
          <Ellipsis aria-hidden className="size-4.5" />
        </span>
        {SHELL_COPY.more}
      </button>
    </nav>
  );
}

export function MoreSheet({ active, card }: { active: NavId; card: ShellCard | null }) {
  const subs: Partial<Record<NavId, string>> = card
    ? { performance: `${SHELL_COPY.trackRecord} · ${card.record} · ${card.units}` }
    : {};
  return (
    // No display utility on the popover itself: the browser hides it with display:none when
    // closed, and a `flex` here would override that.
    <div
      id={MORE_SHEET_ID}
      popover="auto"
      role="dialog"
      aria-label={SHELL_COPY.more}
      className="inset-x-0 top-auto bottom-16 mx-auto w-full max-w-lg rounded-t-xl border bg-popover p-0 text-popover-foreground backdrop:bg-background/60 md:bottom-0"
    >
      <div className="flex flex-col gap-1.5 px-3 pt-3 pb-4">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-section font-semibold">{SHELL_COPY.more}</h2>
          <button
            type="button"
            popoverTarget={MORE_SHEET_ID}
            popoverTargetAction="hide"
            aria-label="Close"
            className="inline-flex size-11 items-center justify-center rounded-md text-muted-foreground hover:bg-accent"
          >
            <X aria-hidden className="size-4.5" />
          </button>
        </div>
        <ul className="mb-3.5 overflow-hidden rounded-lg border bg-card">
          {MORE_ITEMS.map((item) => {
            const Icon = NAV_ICONS[item.id];
            return (
              <li key={item.id} className="border-b last:border-b-0">
                <Link
                  href={item.href}
                  prefetch={false}
                  aria-current={item.id === active ? "page" : undefined}
                  className="flex min-h-15 items-center gap-3 px-3.5 py-2 hover:bg-accent"
                >
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                    <Icon aria-hidden className="size-4" />
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="text-body font-medium">{item.label}</span>
                    <span className="text-caption text-muted-foreground">
                      {subs[item.id] ?? item.sub}
                    </span>
                  </span>
                  {item.desktopOnly ? (
                    <span className="inline-flex h-5.5 items-center gap-1 rounded-full border px-2 text-caption font-medium whitespace-nowrap text-muted-foreground">
                      <Monitor aria-hidden className="size-3" />
                      Best on desktop
                    </span>
                  ) : null}
                  <ChevronRight aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
                </Link>
              </li>
            );
          })}
        </ul>
        <span className="px-1 text-caption font-semibold tracking-wide text-muted-foreground uppercase">
          Sport
        </span>
        <div className="overflow-hidden rounded-lg border bg-card">
          <div className="flex min-h-13 items-center gap-3 border-b px-3.5">
            <LiveDot />
            <span className="flex-1 text-body font-semibold">{SHELL_COPY.sport}</span>
            <Check aria-label="Selected" className="size-4.5" />
          </div>
          <div className="flex min-h-13 items-center gap-3 px-3.5 text-muted-foreground">
            <span aria-hidden className="size-2 shrink-0 rounded-full border border-input" />
            <span className="flex-1 text-body">NFL</span>
            <span className="text-caption font-semibold tracking-wide uppercase">
              {SHELL_COPY.later}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
