import { FilterChips } from "@/components/filter-chips";
import { AppShell } from "@/components/shell/app-shell";
import { cn } from "@/lib/utils";

import { SlateColumnHeader, SlateFrame, SlatePage } from "./slate";

// Drawn at the loaded size inside the shell: the real title and column headers, each window's
// heading and each game as bars at the loaded heights (a card on a phone, 56px at 768, 44px at
// 1440). The shell's nav is real and its data values are bars. With `wake`, the "Waking up the
// database…" note shows too (page.tsx, after 1.5 s with no answer).

/** Games per window in the skeleton; a typical slate is a few windows of a few games. */
const WINDOWS = [3, 4, 3];

const BAR = "animate-pulse rounded-sm bg-muted motion-reduce:animate-none";

function RowBars() {
  return (
    <div
      data-slot="skeleton-row"
      className={cn(
        "h-52 rounded-lg border bg-card p-3.5",
        "md:flex md:h-14 md:items-center md:gap-4 md:rounded-none md:border-0 md:border-b md:bg-transparent md:px-3 md:pl-11",
        "wide:h-11",
      )}
    >
      <span className={cn(BAR, "block h-3.5 w-16")} />
      <div className="mt-3 flex flex-col gap-2 md:mt-0">
        <span className={cn(BAR, "block h-3.5 w-40")} />
        <span className={cn(BAR, "block h-3.5 w-32")} />
      </div>
      <span className="hidden flex-1 md:block" />
      <span className={cn(BAR, "mt-6 block h-3.5 w-3/4 md:mt-0 md:w-56")} />
    </div>
  );
}

/** The record strip as a bar at its loaded heights: 56px on a phone, 44 at 768, 40 at 1440. */
function StripBar() {
  return (
    <div
      data-slot="skeleton-strip"
      className="mb-3 flex h-14 items-center gap-3 rounded-lg border bg-card px-3 md:h-11 md:px-3.5 wide:h-10"
    >
      <span className={cn(BAR, "block h-3.5 w-24")} />
      <span className={cn(BAR, "block h-3.5 w-40 md:w-64")} />
    </div>
  );
}

export function SlateLoading({ wake = false }: { wake?: boolean }) {
  return (
    <AppShell active="this-week" path="/" shell={null} state="loading" wake={wake}>
      <SlatePage caption={<span className={cn(BAR, "inline-block h-4 w-56 align-middle")} />}>
        <StripBar />
        <div className="mb-3">
          <FilterChips
            label="Filter games"
            defaultSelected={["all"]}
            options={[
              { value: "all", label: "All" },
              {
                value: "picks",
                label: (
                  <>
                    Picks<span className="max-md:hidden"> only</span>
                  </>
                ),
              },
            ]}
          />
        </div>
        <div role="status" aria-label="Loading this week's games">
          <SlateFrame>
            <SlateColumnHeader />
            {WINDOWS.map((games, w) => (
              <div key={w}>
                <div className="flex h-8 items-center px-1 md:h-7 md:border-b md:bg-background md:px-3 md:pl-11">
                  <span className={cn(BAR, "block h-3 w-44")} />
                </div>
                <div className="flex flex-col gap-2.5 pb-3 md:block md:pb-0">
                  {Array.from({ length: games }, (_, i) => (
                    <RowBars key={i} />
                  ))}
                </div>
              </div>
            ))}
            <div className="h-10" />
          </SlateFrame>
        </div>
      </SlatePage>
    </AppShell>
  );
}

export default function Loading() {
  return <SlateLoading />;
}
