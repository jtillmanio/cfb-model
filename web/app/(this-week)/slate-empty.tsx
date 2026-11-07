import { CalendarOff, ListOrdered, Target } from "lucide-react";
import Link from "next/link";

import { offseasonNote } from "@/lib/slate";

const LINK =
  "inline-flex h-8 items-center gap-1.5 rounded-md border border-input px-3 text-label font-medium hover:bg-accent max-md:h-11";

// The off-season frame (TASK-057, AC-5; design: App States › offseason): a dashed "No games this
// week" with no table, chips or strip. It says which rule produced it and what comes next. The
// season is the shell's, never a guess at the next one.

export function SlateEmpty({
  season,
  nextKickoffAt,
}: {
  season: number | null;
  nextKickoffAt: string | null | undefined;
}) {
  const note = offseasonNote(season, nextKickoffAt);
  return (
    <div className="rounded-lg border bg-card p-4">
      <div
        data-slot="slate-empty"
        className="flex flex-col items-center gap-2 rounded-md border border-dashed px-4 py-20 text-center"
      >
        <CalendarOff aria-hidden className="size-6 text-muted-foreground" />
        <h2 className="text-panel font-semibold">{note.title}</h2>
        <p className="max-w-125 text-body text-muted-foreground">{note.body}</p>
        {note.kickoff ? <p className="text-label text-muted-foreground">{note.kickoff}</p> : null}
        <div className="mt-3 flex flex-wrap justify-center gap-2">
          <Link href="/rankings" prefetch={false} className={LINK}>
            <ListOrdered aria-hidden className="size-3.5" />
            See final rankings
          </Link>
          <Link href="/performance" prefetch={false} className={LINK}>
            <Target aria-hidden className="size-3.5" />
            See the model&apos;s record
          </Link>
        </div>
      </div>
    </div>
  );
}
