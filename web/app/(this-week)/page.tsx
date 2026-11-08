import type { Metadata } from "next";
import { connection } from "next/server";
import { Suspense } from "react";

import { ApiUnreachable } from "@/components/shell/api-unreachable";
import { AppShell } from "@/components/shell/app-shell";
import { getSlate } from "@/lib/api";
import { raceWakeNote } from "@/lib/login";
import { comingWeek, parseWeekParams, shownWeek, type Slate, type SlateWeek, weekHref } from "@/lib/slate";

import { SlateLoading } from "./loading";
import { SlatePage, SlateView } from "./slate";

export const metadata: Metadata = { title: "This Week · CFB Model" };

const REQUEST = "GET /api/py/slate";

type Result = { ok: true; data: Slate } | { ok: false };

// This Week (S-01, TASK-056). The page's one API call carries the shell's data too (D-156), so
// the shell is drawn here, around the content (D-157). A failed call is caught here and drawn on
// the server too ("API unreachable" inside the shell), so the client error boundary never has to
// draw the shell.
//
// The week comes from the URL (TASK-061): `/` is the coming week, `/?season=2026&week=5` another
// one (`&type=postseason` for the postseason); a bad or partial query falls back to the coming week.
export default async function ThisWeek({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  // Request-time data: never prerendered at build, streamed behind loading.tsx.
  await connection();
  const asked = parseWeekParams(await searchParams);
  const call: Promise<Result> = getSlate(asked).then(
    (data) => ({ ok: true, data }),
    (error: unknown) => {
      console.error(`${REQUEST} failed`, error);
      return { ok: false };
    },
  );

  // Settled within 1.5 s: draw the page.
  if ((await raceWakeNote(call)) === "ready") return <ThisWeekView result={await call} asked={asked} />;

  // Still waiting: the skeleton with the "Waking up the database…" note, until the same call
  // settles (D-072, D-097). No second call is made.
  return (
    <Suspense fallback={<SlateLoading wake />}>
      <ThisWeekWhenAwake call={call} asked={asked} />
    </Suspense>
  );
}

async function ThisWeekWhenAwake({ call, asked }: { call: Promise<Result>; asked: SlateWeek | null }) {
  return <ThisWeekView result={await call} asked={asked} />;
}

function ThisWeekView({ result, asked }: { result: Result; asked: SlateWeek | null }) {
  if (!result.ok) {
    return (
      <AppShell active="this-week" path={asked ? weekHref(asked, null) : "/"} shell={null} state="error">
        <SlatePage caption="Couldn't load this week's games">
          <ApiUnreachable request={REQUEST} />
        </SlatePage>
      </AppShell>
    );
  }
  const { data } = result;
  const shown = shownWeek(data);
  const coming = comingWeek(data.shell);
  return (
    <AppShell
      active="this-week"
      path={shown ? weekHref(shown, coming) : "/"}
      shell={data.shell}
      state="ready"
      weekNav={{ shown, coming, weeks: data.weeks }}
    >
      <SlateView slate={data} />
    </AppShell>
  );
}
