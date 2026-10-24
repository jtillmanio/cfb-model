// The dispatcher (TASK-025, D-122): a Cloudflare Worker whose Cron Trigger ticks every 15 minutes
// and starts each GitHub Actions workflow that is due at that ET time with a workflow_dispatch.
// GitHub's own `schedule` trigger ran the backup 5–8 hours late; this starts it within minutes, and
// doing the ET conversion here keeps each job at the same ET time across daylight-saving changes.

type Weekday = "Sun" | "Mon" | "Tue" | "Wed" | "Thu" | "Fri" | "Sat";

export interface Entry {
  /** Workflow file in .github/workflows/ (it must be on the default branch, D-108). */
  workflow: string;
  days: "daily" | readonly Weekday[];
  /** ET wall-clock time, "HH:MM" on a quarter hour. Never 01:00–02:59: DST repeats or skips it. */
  time: string;
  /** workflow_dispatch inputs, when the run must differ from a hand run's defaults. */
  inputs?: Readonly<Record<string, string>>;
}

/** Add a job by adding a line (README › Dispatcher). */
export const SCHEDULE: readonly Entry[] = [
  { workflow: "backup.yml", days: "daily", time: "03:30" },
  { workflow: "results.yml", days: ["Sun", "Mon"], time: "06:00" },
  { workflow: "vercel-cleanup.yml", days: ["Mon"], time: "06:15", inputs: { dry_run: "false" } },
  { workflow: "lines.yml", days: "daily", time: "08:00" },
  { workflow: "lines.yml", days: ["Thu", "Fri"], time: "19:00" },
];

export interface Env {
  GITHUB_DISPATCH_TOKEN: string;
  /** "owner/name", from wrangler.jsonc vars. */
  GITHUB_REPO: string;
  /** Branch the workflows run on, from wrangler.jsonc vars. */
  GITHUB_REF: string;
}

const easternTime = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  weekday: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/**
 * The entries due in the ET quarter-hour slot holding `now`. A tick that runs late but inside
 * its slot still fires; a slot with no tick is not retried.
 */
export function due(now: Date, schedule: readonly Entry[] = SCHEDULE): Entry[] {
  const parts = Object.fromEntries(easternTime.formatToParts(now).map((p) => [p.type, p.value]));
  const slot = String(Math.floor(Number(parts.minute) / 15) * 15).padStart(2, "0");
  const time = `${parts.hour}:${slot}`;
  const weekday = parts.weekday as Weekday;
  return schedule.filter(
    (e) => e.time === time && (e.days === "daily" || e.days.includes(weekday)),
  );
}

/**
 * POSTs one workflow_dispatch per entry, with its inputs. A failure is logged and the rest are
 * still sent. Returns the workflows that failed.
 */
export async function dispatch(
  env: Env,
  entries: readonly Pick<Entry, "workflow" | "inputs">[],
  fetchFn: typeof fetch = fetch,
): Promise<string[]> {
  const failed: string[] = [];
  for (const { workflow, inputs } of entries) {
    const url = `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/${workflow}/dispatches`;
    try {
      const response = await fetchFn(url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GITHUB_DISPATCH_TOKEN}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          // GitHub refuses API requests without a User-Agent.
          "User-Agent": "cfb-dispatcher",
        },
        body: JSON.stringify(inputs ? { ref: env.GITHUB_REF, inputs } : { ref: env.GITHUB_REF }),
      });
      if (response.ok) {
        console.log(`dispatched ${workflow} on ${env.GITHUB_REF}`);
      } else {
        console.error(`dispatch ${workflow} failed: ${response.status} ${await response.text()}`);
        failed.push(workflow);
      }
    } catch (error) {
      console.error(`dispatch ${workflow} failed: ${String(error)}`);
      failed.push(workflow);
    }
  }
  return failed;
}

export default {
  async scheduled(controller, env) {
    const entries = due(new Date(controller.scheduledTime));
    if (entries.length === 0) return;
    const failed = await dispatch(env, entries);
    // Throwing marks the Cron event as failed in the Cloudflare dashboard.
    if (failed.length > 0) throw new Error(`dispatch failed for ${failed.join(", ")}`);
  },
} satisfies ExportedHandler<Env>;
