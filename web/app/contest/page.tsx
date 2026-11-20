import { Trophy } from "lucide-react";
import type { Metadata } from "next";
import { headers } from "next/headers";
import { connection } from "next/server";
import { Suspense } from "react";

import { ApiUnreachable } from "@/components/shell/api-unreachable";
import { AppShell } from "@/components/shell/app-shell";
import { getContest } from "@/lib/api";
import { type ContestPage, contestWeek, rulesLine, weekSource } from "@/lib/contest";
import { raceWakeNote } from "@/lib/login";

import { ContestTabs } from "./contest-tabs";
import { ContestHeader, ContestLoading, ContestMain } from "./loading";
import { PasteFlow } from "./paste-flow";

export const metadata: Metadata = { title: "Contest · CFB Model" };

const REQUEST = "GET /api/py/contest";

type Result = { ok: true; data: ContestPage | null } | { ok: false };

// Contest (S-02, TASK-072). The page's one API call (D-175) is the contest's week with the shell
// block (D-156), so the shell is drawn here around the content (D-157), and a failed call is drawn
// here too ("API unreachable" inside the shell). `?contest=<id>` opens another of your contests;
// without it the API serves your first live one (until `user_settings`, M8.7).
//
// A week with no slate shows the paste hero; a confirmed week shows its source and Re-paste, and
// its tabs (TASK-073): the ranked slate with the pick tray, Results & standing, and Rules.
export default async function Contest({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  // Request-time data: never prerendered at build, streamed behind loading.tsx.
  await connection();
  const contestId = parseContestId((await searchParams).contest);
  const call: Promise<Result> = getContest(contestId).then(
    (data) => ({ ok: true, data }),
    (error: unknown) => {
      console.error(`${REQUEST} failed`, error);
      return { ok: false };
    },
  );

  // A Server Action's refresh() (a pick or a standing was saved) re-renders this page with the
  // action's request headers. The tab, the tray and the picks are already on screen, so wait for
  // the call and keep them, rather than swapping them for the skeleton after 1.5 s.
  const refreshed = (await headers()).has("next-action");

  // Settled within 1.5 s: draw the page.
  if (refreshed || (await raceWakeNote(call)) === "ready") {
    return <ContestView result={await call} contestId={contestId} />;
  }

  // Still waiting: the skeleton with the "Waking up the database…" note, until the same call
  // settles (D-072, D-097). No second call is made.
  return (
    <Suspense fallback={<ContestLoading wake />}>
      <ContestWhenAwake call={call} contestId={contestId} />
    </Suspense>
  );
}

/** `?contest=12` → 12; anything else is your default contest. */
function parseContestId(raw: string | string[] | undefined): number | null {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value !== undefined && /^[1-9]\d{0,15}$/.test(value) ? Number(value) : null;
}

async function ContestWhenAwake({ call, contestId }: { call: Promise<Result>; contestId: number | null }) {
  return <ContestView result={await call} contestId={contestId} />;
}

function ContestView({ result, contestId }: { result: Result; contestId: number | null }) {
  const path = contestId === null ? "/contest" : `/contest?contest=${contestId}`;
  if (!result.ok) {
    return (
      <AppShell active="contest" path={path} shell={null} state="error">
        <ContestMain>
          <ContestHeader />
          <ApiUnreachable request={REQUEST} />
        </ContestMain>
      </AppShell>
    );
  }
  const page = result.data;
  if (page === null) {
    return (
      <AppShell active="contest" path={path} shell={null} state="ready">
        <ContestMain>
          <ContestHeader />
          <NoContest />
        </ContestMain>
      </AppShell>
    );
  }
  const week = contestWeek(page);
  // A new snapshot (a confirm) or another week remounts the flow, so it closes on the saved week.
  const key = `${page.contest.id}-${week.period}-${week.paste}-${page.games.map((g) => g.contest_line_id).join(".")}`;
  return (
    <AppShell active="contest" path={path} shell={page.shell} state="ready">
      <ContestMain>
        <ContestHeader name={page.contest.name} line={rulesLine(page.contest.rules, week.period)} />
        <PasteFlow
          key={key}
          contestId={page.contest.id}
          period={week.period}
          rules={page.contest.rules}
          hero={week.paste}
          source={weekSource(page.games)}
          weekOpen={page.games.some((g) => !g.locked)}
        >
          <ContestTabs page={page} period={week.period} />
        </PasteFlow>
      </ContestMain>
    </AppShell>
  );
}

// No contest to paste into: production until the owner creates theirs (TASK-075). Not drawn; a
// dashed empty state like This Week's off-season, with no action ("Add contest" isn't designed).
function NoContest() {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div
        data-slot="contest-empty"
        className="flex flex-col items-center gap-2 rounded-md border border-dashed px-4 py-20 text-center"
      >
        <Trophy aria-hidden className="size-6 text-muted-foreground" />
        <h2 className="text-panel font-semibold">No contest yet</h2>
        <p className="max-w-125 text-body text-muted-foreground">
          Once your contest is set up, paste its weekly page here and the model ranks the games against its lines.
        </p>
      </div>
    </div>
  );
}
