import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { getHealth } from "@/lib/api";
import { raceWakeNote, safeNextPath } from "@/lib/login";

import { LoginCard, WakingNotice } from "../login-card";

export const metadata: Metadata = { title: "Signing in · CFB Model" };

// Waits on the race below before drawing anything: an awake database never sees the card.
export const instant = false;

// Every sign-in returns here (behind the gate) before opening the page it asked for, so a cold
// database shows "Waking up the database…" instead of a blank wait (TASK-002 AC-3, D-072).
// The health call runs on the server; the browser never calls the API (hard rule 5).
export default async function Continue({ searchParams }: PageProps<"/login/continue">) {
  const to = safeNextPath((await searchParams).to);
  const health = getHealth();

  // Awake within 1.5 s: redirect before anything is drawn. With cacheComponents Next has already
  // committed a 200 by then, so this is a client-side redirect, not a 307. A failed call
  // redirects too; the target page shows its own error.
  if ((await raceWakeNote(health)) === "ready") redirect(to);

  // Still waking: stream the card now, then redirect once the call settles. Mid-stream, Next
  // turns redirect() into a client-side one.
  return (
    <LoginCard>
      <WakingNotice />
      <Suspense>
        <RedirectWhenAwake health={health} to={to} />
      </Suspense>
    </LoginCard>
  );
}

async function RedirectWhenAwake({
  health,
  to,
}: {
  health: Promise<unknown>;
  to: string;
}): Promise<never> {
  await health.catch(() => undefined);
  redirect(to);
}
