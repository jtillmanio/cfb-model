import type { Metadata } from "next";
import { connection } from "next/server";
import { Suspense } from "react";

import { AppShell } from "@/components/shell/app-shell";
import { getTeams } from "@/lib/api";
import { raceWakeNote } from "@/lib/login";
import { sortTeams, type TeamsResponse } from "@/lib/teams";

import { TeamsLoading } from "./loading";
import { EmptyTeams, TeamsPage, TeamTable } from "./team-table";

export const metadata: Metadata = { title: "Teams · CFB Model" };

// The page's one API call carries the shell's data too (D-156), so the shell is drawn here,
// around the content, not in a layout that can't see the response (TASK-054).
export default async function Teams() {
  // Request-time data: never prerendered at build, streamed behind loading.tsx.
  await connection();
  const call = getTeams();

  // Answered within 1.5 s (or failed: error.tsx takes it): draw the page.
  if ((await raceWakeNote(call)) === "ready") return <TeamsReady data={await call} />;

  // Still waiting: the skeleton with the "Waking up the database…" note, until the same call
  // settles (D-072, D-097). No second call is made.
  return (
    <Suspense fallback={<TeamsLoading wake />}>
      <TeamsWhenAwake call={call} />
    </Suspense>
  );
}

async function TeamsWhenAwake({ call }: { call: Promise<TeamsResponse> }) {
  return <TeamsReady data={await call} />;
}

function TeamsReady({ data }: { data: TeamsResponse }) {
  const sorted = sortTeams(data.teams);
  return (
    <AppShell active="teams" path="/teams" shell={data.shell} state="ready">
      <TeamsPage caption={`Every FBS team · ${sorted.length}`}>
        {sorted.length === 0 ? <EmptyTeams /> : <TeamTable teams={sorted} />}
      </TeamsPage>
    </AppShell>
  );
}
