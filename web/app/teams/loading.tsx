import { TeamsPage } from "./team-table";

const ROWS = 10;

// Drawn at the loaded size: same header, 40px table header, 48px rows, caption footer.
export default function Loading() {
  return (
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
  );
}
