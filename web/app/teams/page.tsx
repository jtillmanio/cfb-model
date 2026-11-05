import type { Metadata } from "next";
import { connection } from "next/server";
import { Suspense } from "react";

import { ApiUnreachable } from "@/components/shell/api-unreachable";
import { AppShell } from "@/components/shell/app-shell";
import { getTeams } from "@/lib/api";
import { raceWakeNote } from "@/lib/login";
import { sortTeams, type TeamsResponse } from "@/lib/teams";

import { TeamsLoading } from "./loading";
import { EmptyTeams, TeamsPage, TeamTable } from "./team-table";

export const metadata: Metadata = { title: "Teams · CFB Model" };

const REQUEST = "GET /api/py/teams";

type Result = { ok: true; data: TeamsResponse } | { ok: false };

// The page's one API call carries the shell's data too (D-156), so the shell is drawn here,
// around the content, not in a layout that can't see the response (TASK-054, D-157). A failed
// call is caught here and drawn on the server too ("API unreachable" inside the shell), so the
// client error boundary never has to draw the shell.
export default async function Teams() {
  // Request-time data: never prerendered at build, streamed behind loading.tsx.
  await connection();
  const call: Promise<Result> = getTeams().then(
    (data) => ({ ok: true, data }),
    (error: unknown) => {
      console.error(`${REQUEST} failed`, error);
      return { ok: false };
    },
  );

  // Settled within 1.5 s: draw the page.
  if ((await raceWakeNote(call)) === "ready") return <TeamsView result={await call} />;

  // Still waiting: the skeleton with the "Waking up the database…" note, until the same call
  // settles (D-072, D-097). No second call is made.
  return (
    <Suspense fallback={<TeamsLoading wake />}>
      <TeamsWhenAwake call={call} />
    </Suspense>
  );
}

async function TeamsWhenAwake({ call }: { call: Promise<Result> }) {
  return <TeamsView result={await call} />;
}

function TeamsView({ result }: { result: Result }) {
  if (!result.ok) {
    return (
      <AppShell active="teams" path="/teams" shell={null} state="error">
        <TeamsPage caption="Every FBS team">
          <ApiUnreachable request={REQUEST} />
        </TeamsPage>
      </AppShell>
    );
  }
  const { data } = result;
  const sorted = sortTeams(data.teams);
  return (
    <AppShell active="teams" path="/teams" shell={data.shell} state="ready">
      <TeamsPage caption={`Every FBS team · ${sorted.length}`}>
        {sorted.length === 0 ? <EmptyTeams /> : <TeamTable teams={sorted} />}
      </TeamsPage>
    </AppShell>
  );
}
