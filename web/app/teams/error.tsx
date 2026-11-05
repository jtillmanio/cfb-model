"use client";

import { ApiUnreachable } from "@/components/shell/api-unreachable";

import { TeamsPage } from "./team-table";

// A fallback for anything page.tsx doesn't catch itself. page.tsx draws "API unreachable" inside
// the shell when its one API call fails; this boundary only sees an unexpected error, and it
// draws no shell, so the shell's code never ships to the browser (D-157).
export default function TeamsError({ retry }: { error: unknown; retry: () => void }) {
  return (
    <TeamsPage caption="Every FBS team">
      <ApiUnreachable request="GET /api/py/teams" retry={retry} />
    </TeamsPage>
  );
}
