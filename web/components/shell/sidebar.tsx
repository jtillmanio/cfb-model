import {
  Activity,
  CalendarDays,
  ChevronRight,
  ChevronsUpDown,
  FlaskConical,
  ListOrdered,
  type LucideIcon,
  Settings,
  Shield,
  Target,
  Trophy,
} from "lucide-react";
import Link from "next/link";

import { NAV, type NavId, SETTINGS, SHELL_COPY, type ShellCard } from "@/lib/shell";
import { cn } from "@/lib/utils";

// Desktop sidebar (design/README.md › Navigation; This Week Desktop): 224px, `--card`, right
// border. Drawn at xl (1280+); the top-bar nav and the tab bar take over below that.

/** The lucide icon each screen uses, everywhere the nav is drawn. */
export const NAV_ICONS: Record<NavId, LucideIcon> = {
  "this-week": CalendarDays,
  picks: Target,
  contest: Trophy,
  rankings: ListOrdered,
  teams: Shield,
  performance: Activity,
  lab: FlaskConical,
  settings: Settings,
};

/** A data value still loading: a bar where the text will be (design/README.md › Feedback). */
export function Bar({ className }: { className: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-block animate-pulse rounded-sm bg-muted motion-reduce:animate-none",
        className,
      )}
    />
  );
}

export type ShellState = "ready" | "loading" | "error";

export function Wordmark() {
  return (
    <div className="flex h-8 items-center gap-2.5 px-1.5">
      <LogoMark />
      <span className="text-body font-semibold tracking-tight">{SHELL_COPY.wordmark}</span>
    </div>
  );
}

export function LogoMark() {
  return (
    <span
      aria-hidden
      className="flex size-6 shrink-0 items-center justify-center rounded-md bg-foreground font-mono text-caption font-bold text-background"
    >
      CF
    </span>
  );
}

export function LiveDot({ className }: { className?: string }) {
  return <span aria-hidden className={cn("size-2 shrink-0 rounded-full bg-live", className)} />;
}

function NavLink({
  id,
  label,
  href,
  active,
  badge,
}: {
  id: NavId;
  label: string;
  href: string;
  active: boolean;
  badge?: string | null;
}) {
  const Icon = NAV_ICONS[id];
  return (
    <Link
      href={href}
      // Most targets aren't built yet and would 404; prefetching them is wasted requests.
      prefetch={false}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex h-8.5 items-center gap-2.5 rounded-md px-2.5 text-label",
        active
          ? "bg-accent font-semibold text-foreground"
          : "font-medium text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      <Icon aria-hidden className="size-4 shrink-0" />
      <span className="flex-1">{label}</span>
      {badge ? <span className="text-caption">{badge}</span> : null}
    </Link>
  );
}

function TrackRecordCard({ card, state }: { card: ShellCard | null; state: ShellState }) {
  return (
    <Link
      href="/performance"
      prefetch={false}
      className="flex flex-col gap-1.5 rounded-lg border bg-background p-3 hover:border-input"
    >
      <span className="text-caption text-muted-foreground">
        {state === "ready" && card ? card.label : "Model"}
      </span>
      {state === "loading" ? (
        <>
          <Bar className="h-5 w-28" />
          <Bar className="h-4 w-full" />
        </>
      ) : state === "error" ? (
        <span className="text-label text-muted-foreground">{SHELL_COPY.cardDown}</span>
      ) : card ? (
        <>
          <span className="flex items-baseline gap-2">
            <span className="text-panel font-semibold">{card.record}</span>
            <span className="text-label">{card.winRate}</span>
          </span>
          <span className="flex items-center gap-2 text-caption whitespace-nowrap">
            <span
              className={cn(
                "font-semibold",
                card.unitsTone === "pos" && "text-pos",
                card.unitsTone === "neg" && "text-neg",
              )}
            >
              {card.units}
            </span>
            <span className="text-muted-foreground">{card.clv}</span>
            <span className="flex-1" />
            <span className="text-muted-foreground">{SHELL_COPY.trackRecord}</span>
            <ChevronRight aria-hidden className="size-3 shrink-0 text-muted-foreground" />
          </span>
        </>
      ) : (
        <span className="flex items-center gap-2 text-caption text-muted-foreground">
          <span className="flex-1">No graded picks yet</span>
          <span>{SHELL_COPY.trackRecord}</span>
          <ChevronRight aria-hidden className="size-3 shrink-0" />
        </span>
      )}
    </Link>
  );
}

export function Sidebar({
  active,
  card,
  picks,
  state,
}: {
  active: NavId;
  card: ShellCard | null;
  picks: string | null;
  state: ShellState;
}) {
  return (
    <aside
      aria-label="Sidebar"
      className="sticky top-0 hidden h-dvh w-56 shrink-0 flex-col gap-4 overflow-y-auto border-r bg-card p-3 xl:flex"
    >
      <Wordmark />
      {/* College football only until the NFL lands ("Later", in More); the switcher is inert. */}
      <div className="flex h-8 items-center gap-2 rounded-md border border-input px-2.5 text-label font-semibold">
        <LiveDot />
        <span className="flex-1">{SHELL_COPY.sport}</span>
        <ChevronsUpDown aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
      </div>
      <nav aria-label="Main" className="flex flex-col gap-0.5">
        {NAV.map((item) => (
          <NavLink
            key={item.id}
            {...item}
            active={item.id === active}
            badge={item.id === "picks" ? picks : null}
          />
        ))}
      </nav>
      <div className="flex-1" />
      <TrackRecordCard card={card} state={state} />
      <div className="flex flex-col gap-0.5 border-t pt-2">
        <NavLink {...SETTINGS} active={active === "settings"} />
      </div>
    </aside>
  );
}
