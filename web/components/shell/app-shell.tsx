import { CloudOff, LoaderCircle, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

import { type NavId, type Shell, SHELL_COPY, shellView } from "@/lib/shell";

import { MobileTabs, MoreSheet } from "./mobile-tabs";
import { Sidebar, type ShellState } from "./sidebar";
import { TopBar } from "./top-bar";
import type { WeekNav } from "./week-picker";

// S-16 app shell (TASK-054). Each page draws it around its own content with its response's
// `shell` block, so the shell costs no API call of its own (hard rule 5, D-156); loading.tsx
// and error.tsx draw it with no data. Nothing here imports server-only code, so the client
// error boundary can render it.
//
// Widths (design/README.md › Breakpoints): the sidebar at xl (1280+); the top bar with its nav
// row from md (768); the bottom tab bar below md.

export function AppShell({
  active,
  shell,
  state,
  path,
  wake = false,
  weekNav,
  children,
}: {
  /** The screen the nav marks as current. */
  active: NavId;
  /** The response's shell block; null while loading or after an error. */
  shell: Shell | null;
  state: ShellState;
  /** This page's path: the stale banner's Refresh reloads it. */
  path: string;
  /** Show the "Waking up the database…" note (the page is still loading after 1.5 s). */
  wake?: boolean;
  /** The week selector (TASK-061): only This Week passes it; every other screen keeps the static label. */
  weekNav?: WeekNav;
  children: ReactNode;
}) {
  const view = shellView(state === "ready" ? shell : null);
  return (
    <div className="flex min-h-dvh">
      <Sidebar active={active} card={view.card} picks={view.picks} state={state} />
      <div className="flex min-w-0 flex-1 flex-col pb-16 md:pb-0">
        <TopBar active={active} view={view} state={state} weekNav={state === "ready" ? weekNav : undefined} />
        {view.stale ? <StaleBanner text={view.stale} path={path} /> : null}
        {children}
      </div>
      <MobileTabs active={active} />
      <MoreSheet active={active} card={view.card} />
      {wake ? <WakeNote /> : null}
    </div>
  );
}

// Neutral, not an error colour (C16a, C16b): lines more than 24 h old. D-096 drops the design's
// saved-copy sentence; there is no saved copy. Refresh is a plain link, so it reloads the page.
export function StaleBanner({ text, path }: { text: string; path: string }) {
  return (
    <div className="mx-auto w-full max-w-304 px-4 pt-3 md:px-6 xl:px-8">
      <div
        role="status"
        aria-label={text}
        className="flex items-center gap-2.5 rounded-lg border bg-muted py-1 pr-1 pl-3 text-label md:rounded-md md:py-2.5 md:pr-3.5 md:pl-3.5"
      >
        <CloudOff aria-hidden className="size-4 shrink-0" />
        <span className="flex-1 font-semibold">{text}</span>
        <a
          href={path}
          className="inline-flex h-11 items-center gap-1.5 rounded-md px-3 text-body font-medium whitespace-nowrap hover:bg-accent md:h-8 md:border md:border-input md:text-label"
        >
          <RefreshCw aria-hidden className="hidden size-3.5 md:block" />
          {SHELL_COPY.refresh}
        </a>
      </div>
    </div>
  );
}

// "Waking up the database…" after 1.5 s with no data (design/README.md › Feedback; Loading
// States): a quiet pill bottom-right on desktop, above the tab bar on phones. Not an error.
export function WakeNote() {
  return (
    <div
      role="status"
      className="fixed bottom-19 left-1/2 z-30 flex h-9 -translate-x-1/2 items-center gap-2 rounded-lg border bg-popover px-3 text-label whitespace-nowrap text-muted-foreground shadow-lg md:right-6 md:bottom-6 md:left-auto md:translate-x-0"
    >
      <LoaderCircle aria-hidden className="size-3.5 shrink-0" />
      {SHELL_COPY.waking}
    </div>
  );
}
