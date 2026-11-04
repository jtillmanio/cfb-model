"use client";

import { ChevronDown, CircleAlert, LoaderCircle, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState, useTransition } from "react";

// "API unreachable" (App States Desktop / Mobile, frame "apierror"): the frame stays, the card
// says what failed, and it retries on its own with backoff. D-096: there is no saved copy, so the
// design's saved-copy sentence is dropped. D-097: the cold-start note gives no number.

/** Seconds before each automatic retry: 15 s, then 30 s, doubling up to 2 min. */
export const BACKOFF_SECONDS = [15, 30, 60, 120] as const;
const [FIRST_WAIT] = BACKOFF_SECONDS;

export const UNREACHABLE_COPY = {
  title: "Couldn't reach the server",
  body: (attempts: number) =>
    `The API didn't answer after ${attempts} ${attempts === 1 ? "try" : "tries"}.`,
  retry: "Retry",
  retrying: "Retrying…",
  countdown: (seconds: number) => `Trying again in ${seconds}s`,
  details: "Details",
  next: "auto-retry with backoff, up to 2 min",
  coldStart: "If the server was idle, the database can take a few seconds to start.",
} as const;

function digest(error: unknown): string | null {
  if (error instanceof Error && "digest" in error && typeof error.digest === "string") {
    return error.digest;
  }
  return null;
}

export function ApiUnreachable({
  request,
  error,
  retry,
}: {
  /** The page's one API call, e.g. "GET /api/py/teams". */
  request: string;
  error: unknown;
  /** error.js's `retry`: re-fetches and re-renders the segment. */
  retry: () => void;
}) {
  const [{ attempts, left }, setRun] = useState<{ attempts: number; left: number }>({
    attempts: 1,
    left: FIRST_WAIT,
  });
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();

  const again = useCallback(() => {
    setRun((run) => ({
      attempts: run.attempts + 1,
      left: BACKOFF_SECONDS[Math.min(run.attempts, BACKOFF_SECONDS.length - 1)],
    }));
    startTransition(() => retry());
  }, [retry]);

  useEffect(() => {
    if (pending) return;
    const timer = setTimeout(() => {
      if (left > 1) setRun((run) => ({ ...run, left: run.left - 1 }));
      else again();
    }, 1000);
    return () => clearTimeout(timer);
  }, [left, pending, again]);

  const id = digest(error);
  const button =
    "inline-flex h-11 items-center justify-center gap-1.5 rounded-md px-3 text-body font-medium md:h-8 md:text-label";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-center rounded-lg border bg-card p-3 md:min-h-140 md:px-6 md:pt-24 md:pb-12">
        <div
          role="alert"
          className="flex h-fit w-full max-w-140 gap-3 rounded-md border border-destructive bg-destructive/8 p-3.5 md:p-4"
        >
          <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-destructive" />
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <p className="text-panel font-semibold">{UNREACHABLE_COPY.title}</p>
            <p className="text-label">{UNREACHABLE_COPY.body(attempts)}</p>
            <div className="flex flex-col gap-2 md:flex-row md:items-center">
              <button
                type="button"
                onClick={again}
                disabled={pending}
                className={`${button} bg-secondary text-secondary-foreground hover:bg-accent disabled:text-muted-foreground`}
              >
                {pending ? (
                  <LoaderCircle
                    aria-hidden
                    className="size-3.5 animate-spin motion-reduce:animate-none"
                  />
                ) : (
                  <RefreshCw aria-hidden className="size-3.5" />
                )}
                {pending ? UNREACHABLE_COPY.retrying : UNREACHABLE_COPY.retry}
              </button>
              <button
                type="button"
                aria-expanded={open}
                onClick={() => setOpen(!open)}
                className={`${button} hover:bg-accent`}
              >
                {UNREACHABLE_COPY.details}
                <ChevronDown
                  aria-hidden
                  className={`size-3.5 text-muted-foreground ${open ? "rotate-180" : ""}`}
                />
              </button>
              <span className="hidden flex-1 md:block" />
              {pending ? null : (
                <span className="text-center text-caption text-muted-foreground">
                  {UNREACHABLE_COPY.countdown(left)}
                </span>
              )}
            </div>
            {open ? (
              <dl className="mt-1 flex flex-col gap-1 rounded-md border bg-background px-3 py-2.5 font-mono text-caption">
                <Row term="request" value={request} />
                <Row term="result" value={id ? `failed · error ${id}` : "no answer"} />
                <Row term="next" value={UNREACHABLE_COPY.next} />
              </dl>
            ) : null}
          </div>
        </div>
      </div>
      <p className="px-1.5 text-caption text-muted-foreground">{UNREACHABLE_COPY.coldStart}</p>
    </div>
  );
}

function Row({ term, value }: { term: string; value: string }) {
  return (
    <div className="flex gap-3">
      <dt className="w-24 shrink-0 text-muted-foreground">{term}</dt>
      <dd className="min-w-0 break-words">{value}</dd>
    </div>
  );
}
