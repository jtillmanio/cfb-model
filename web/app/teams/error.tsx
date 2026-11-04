"use client";

import { AppShell } from "@/components/shell/app-shell";
import { ApiUnreachable } from "@/components/shell/api-unreachable";

import { TeamsPage } from "./team-table";

// The page's one API call failed (S-16 "API unreachable", journey 8): the shell stays, with no
// data, and the card retries. Production hides server error messages, so every failure reads as
// unreachable (TASK-054 Follow-ups).
export default function TeamsError({ error, retry }: { error: unknown; retry: () => void }) {
  return (
    <AppShell active="teams" path="/teams" shell={null} state="error">
      <TeamsPage caption="Every FBS team">
        <ApiUnreachable request="GET /api/py/teams" error={error} retry={retry} />
      </TeamsPage>
    </AppShell>
  );
}
