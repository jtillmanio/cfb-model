import type { ReactNode } from "react";

import { AppShell } from "@/components/shell/app-shell";
import { cn } from "@/lib/utils";

// Drawn at the loaded size inside the shell (Loading States › Contest: the slate frame): the real
// title, the contest and rules line as bars, the week's toolbar, and ten games as bars at the
// slate's row height (64px from 768, a card on a phone). The shell's nav is real and its data
// values are bars. With `wake`, the "Waking up the database…" note shows too (page.tsx, after
// 1.5 s with no answer). The pulse stops under reduced motion.

const BAR = "animate-pulse rounded-sm bg-muted motion-reduce:animate-none";
const GAMES = 10;

export function ContestMain({ children }: { children: ReactNode }) {
  return <main className="mx-auto w-full max-w-304 px-4 py-6 md:px-6">{children}</main>;
}

export function ContestHeader({ name, line }: { name?: ReactNode; line?: ReactNode }) {
  return (
    <header className="mb-4 flex flex-col gap-0.5">
      <div className="flex flex-wrap items-center gap-2.5">
        <h1 className="text-section font-semibold tracking-[-0.005em] md:text-title">Contest</h1>
        {name ? (
          <span className="inline-flex h-6.5 items-center rounded-md border px-2.5 text-label font-medium">{name}</span>
        ) : null}
      </div>
      {line ? <p className="text-caption text-muted-foreground">{line}</p> : null}
    </header>
  );
}

function GameBars() {
  return (
    <div
      data-slot="skeleton-row"
      className="flex h-22 flex-col justify-center gap-2 border-b px-3 last:border-b-0 md:h-16 md:flex-row md:items-center md:gap-4"
    >
      <span className={cn(BAR, "block h-3.5 w-24 md:w-10")} />
      <span className={cn(BAR, "block h-3.5 w-48 md:w-56")} />
      <span className="hidden flex-1 md:block" />
      <span className={cn(BAR, "block h-3.5 w-32 md:w-72")} />
    </div>
  );
}

export function ContestLoading({ wake = false }: { wake?: boolean }) {
  return (
    <AppShell active="contest" path="/contest" shell={null} state="loading" wake={wake}>
      <ContestMain>
        <ContestHeader
          name={<span className={cn(BAR, "inline-block h-3.5 w-32")} />}
          line={<span className={cn(BAR, "mt-1 inline-block h-3 w-72 max-w-full")} />}
        />
        <div role="status" aria-label="Loading the contest">
          <div className="mb-3 flex min-h-11 items-center gap-3">
            <span className={cn(BAR, "block h-3 w-56")} />
            <span className="flex-1" />
            <span className={cn(BAR, "block h-8 w-44 rounded-md")} />
          </div>
          <div className="rounded-lg border bg-card">
            {Array.from({ length: GAMES }, (_, i) => (
              <GameBars key={i} />
            ))}
          </div>
        </div>
      </ContestMain>
    </AppShell>
  );
}

export default function Loading() {
  return <ContestLoading />;
}
