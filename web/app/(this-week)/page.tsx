import type { Metadata } from "next";
import { connection } from "next/server";
import { Suspense } from "react";

import { ApiUnreachable } from "@/components/shell/api-unreachable";
import { AppShell } from "@/components/shell/app-shell";
import { getSlate } from "@/lib/api";
import { raceWakeNote } from "@/lib/login";
import type { Slate } from "@/lib/slate";

import { SlateLoading } from "./loading";
import { SlatePage, SlateView } from "./slate";

export const metadata: Metadata = { title: "This Week · CFB Model" };

const REQUEST = "GET /api/py/slate";

type Result = { ok: true; data: Slate } | { ok: false };

// This Week (S-01, TASK-056). The page's one API call carries the shell's data too (D-156), so
// the shell is drawn here, around the content (D-157). A failed call is caught here and drawn on
// the server too ("API unreachable" inside the shell), so the client error boundary never has to
// draw the shell.
export default async function ThisWeek() {
  // Request-time data: never prerendered at build, streamed behind loading.tsx.
  await connection();
  const call: Promise<Result> = getSlate().then(
    (data) => ({ ok: true, data }),
    (error: unknown) => {
      console.error(`${REQUEST} failed`, error);
      return { ok: false };
    },
  );

  // Settled within 1.5 s: draw the page.
  if ((await raceWakeNote(call)) === "ready") return <ThisWeekView result={await call} />;

  // Still waiting: the skeleton with the "Waking up the database…" note, until the same call
  // settles (D-072, D-097). No second call is made.
  return (
    <Suspense fallback={<SlateLoading wake />}>
      <ThisWeekWhenAwake call={call} />
    </Suspense>
  );
}

async function ThisWeekWhenAwake({ call }: { call: Promise<Result> }) {
  return <ThisWeekView result={await call} />;
}

function ThisWeekView({ result }: { result: Result }) {
  if (!result.ok) {
    return (
      <AppShell active="this-week" path="/" shell={null} state="error">
        <SlatePage caption="Couldn't load this week's games">
          <ApiUnreachable request={REQUEST} />
        </SlatePage>
      </AppShell>
    );
  }
  const { data } = result;
  return (
    <AppShell active="this-week" path="/" shell={data.shell} state="ready">
      <SlateView slate={data} />
    </AppShell>
  );
}
