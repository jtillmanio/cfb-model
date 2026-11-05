import { AppShell } from "@/components/shell/app-shell";

import { TeamsPage } from "./team-table";

const ROWS = 10;

// Drawn at the loaded size inside the shell: same header, 40px table header, 48px rows, caption
// footer; the shell's nav is real and its data values are bars. With `wake`, the "Waking up the
// database…" note shows too (page.tsx, after 1.5 s with no answer).
export function TeamsLoading({ wake = false }: { wake?: boolean }) {
  return (
    <AppShell active="teams" path="/teams" shell={null} state="loading" wake={wake}>
      <TeamsPage caption="Every FBS team">
        <div
          role="status"
          aria-label="Loading teams"
          className="overflow-hidden rounded-lg border bg-card"
        >
          <div className="h-10 border-b" />
          {Array.from({ length: ROWS }, (_, i) => (
            <div key={i} className="flex h-12 items-center gap-4 border-b px-3 pl-4">
              <span className="size-5 shrink-0 animate-pulse rounded-full bg-muted motion-reduce:animate-none" />
              <span className="h-3.5 w-40 animate-pulse rounded-sm bg-muted motion-reduce:animate-none" />
            </div>
          ))}
          <div className="h-10" />
        </div>
      </TeamsPage>
    </AppShell>
  );
}

export default function Loading() {
  return <TeamsLoading />;
}
