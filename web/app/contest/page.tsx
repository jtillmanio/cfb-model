import { Trophy } from "lucide-react";
import type { Metadata } from "next";
import { connection } from "next/server";
import { Suspense } from "react";

import { ApiUnreachable } from "@/components/shell/api-unreachable";
import { AppShell } from "@/components/shell/app-shell";
import { TeamChip } from "@/components/team-chip";
import { getContest } from "@/lib/api";
import {
  CONTEST_ZONE,
  type ContestGame,
  type ContestPage,
  contestWeek,
  rulesLine,
  weekSource,
} from "@/lib/contest";
import { formatKickoff, formatSpread } from "@/lib/format";
import { raceWakeNote } from "@/lib/login";

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
// its games, which TASK-073 ranks into the slate, pick tray and results.
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

  // Settled within 1.5 s: draw the page.
  if ((await raceWakeNote(call)) === "ready") return <ContestView result={await call} contestId={contestId} />;

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
          <WeekGames games={page.games} />
        </PasteFlow>
      </ContestMain>
    </AppShell>
  );
}

// The confirmed week's games, as stored: TASK-073 replaces this list with the ranked slate.
function WeekGames({ games }: { games: readonly ContestGame[] }) {
  return (
    <ul data-slot="contest-week" aria-label="This week's contest games" className="rounded-lg border bg-card">
      {games.map((g) => {
        const home = g.home.abbreviation ?? g.home.school;
        const away = g.away.abbreviation ?? g.away.school;
        return (
          <li
            key={g.id}
            data-slot="contest-game"
            className="grid min-h-14 grid-cols-[minmax(0,1fr)_auto] md:min-h-16 items-center gap-x-3 gap-y-0.5 border-b px-3 py-2 last:border-b-0 md:grid-cols-[40px_112px_minmax(0,1fr)_120px]"
          >
            <span className="w-fit rounded-sm bg-secondary px-1 text-caption font-semibold tracking-wider text-muted-foreground max-md:hidden">
              {g.sport_id.toUpperCase()}
            </span>
            <span className="text-label text-muted-foreground max-md:col-span-2 max-md:row-start-2">
              {g.locked ? "Locked" : formatKickoff(g.kickoff_at, g.game_date, { zone: CONTEST_ZONE, inTable: true })}
            </span>
            <span className="flex min-w-0 flex-wrap items-center gap-1.5 text-label">
              <TeamChip abbreviation={away} school={g.away.school} logoUrl={g.away.logo_url} color={g.away.color} locked={g.locked} />
              <span className="text-muted-foreground">{g.neutral_site ? "vs" : "@"}</span>
              <TeamChip abbreviation={home} school={g.home.school} logoUrl={g.home.logo_url} color={g.home.color} locked={g.locked} />
            </span>
            <span className="text-right text-label font-semibold whitespace-nowrap">
              {formatSpread(g.contest_spread_home, home, away)}
            </span>
          </li>
        );
      })}
    </ul>
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
