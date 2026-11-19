import { RefreshCw } from "lucide-react";

import { type ImportPreview, movedRows, movedTitle, teamAbbr } from "@/lib/contest";

import { TeamDot } from "./team-picker";

// RepasteDiff (C2e, Components › Added in pass 2026-10-07): before Confirm, the rows whose contest
// line differs from the week's current one, line then → now. The board's cover %, rank and
// "for the model's side" columns are illustrative and not in the preview response, so they wait
// for TASK-079; once confirmed, the slate (TASK-073) ranks on the new lines.

export function RepasteDiff({ preview }: { preview: ImportPreview }) {
  const moved = movedRows(preview);
  if (moved.length === 0) return null;
  const same = preview.rows.length - moved.length;
  return (
    <section
      data-slot="repaste-diff"
      aria-label="Contest lines that moved"
      className="flex flex-col overflow-hidden rounded-lg border border-input bg-card"
    >
      <div className="flex items-start gap-2.5 border-b px-3.5 py-3">
        <RefreshCw aria-hidden className="mt-0.5 size-4 shrink-0" />
        <div className="flex min-w-0 flex-col gap-0.5">
          <h2 className="text-body font-semibold">{movedTitle(preview.changes)}</h2>
          <p className="text-label text-muted-foreground">
            Confirm saves the new lines. Your picks keep the line you picked them at.
            {same > 0 ? ` The other ${same} game${same === 1 ? " is" : "s are"} unchanged.` : ""}
          </p>
        </div>
      </div>
      <div className="hidden h-8 grid-cols-[minmax(0,1fr)_240px] items-center gap-x-4 border-b px-3.5 text-caption font-medium text-muted-foreground md:grid">
        <span>Game</span>
        <span>Contest line, then → now</span>
      </div>
      <ul>
        {moved.map((row) => (
          <li
            key={row.index}
            data-slot="moved-row"
            className="grid min-h-11 grid-cols-1 items-center gap-x-4 gap-y-1 border-b px-3.5 py-2 last:border-b-0 md:grid-cols-[minmax(0,1fr)_240px] md:py-0"
          >
            <span className="flex min-w-0 items-center gap-1.5 text-label">
              <TeamDot color={row.away.color} />
              <span className="font-medium whitespace-nowrap">{teamAbbr(row.away)}</span>
              <span className="text-muted-foreground">@</span>
              <TeamDot color={row.home.color} />
              <span className="font-medium whitespace-nowrap">{teamAbbr(row.home)}</span>
            </span>
            <span className="flex items-center gap-1.5 text-label whitespace-nowrap">
              <span className="text-muted-foreground">{row.was}</span>
              <span aria-label="moved to" className="text-muted-foreground">
                →
              </span>
              <span className="font-semibold">{row.now}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
