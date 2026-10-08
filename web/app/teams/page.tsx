import type { Metadata } from "next";
import { connection } from "next/server";

import { getTeams } from "@/lib/api";
import { sortTeams } from "@/lib/teams";

import { EmptyTeams, TeamsPage, TeamTable } from "./team-table";

export const metadata: Metadata = { title: "Teams · CFB Model" };

export default async function Teams() {
  // Request-time data: never prerendered at build, streamed behind loading.tsx.
  await connection();
  const { teams } = await getTeams();
  const sorted = sortTeams(teams);

  return (
    <TeamsPage caption={`Every FBS team · ${sorted.length}`}>
      {sorted.length === 0 ? <EmptyTeams /> : <TeamTable teams={sorted} />}
    </TeamsPage>
  );
}
