import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import worker, { dispatch, due as dueEntries, SCHEDULE, type Entry, type Env } from "./index";

/** The workflow files due at `now`. */
const due = (now: Date, schedule?: readonly Entry[]) =>
  dueEntries(now, schedule).map((e) => e.workflow);
const entries = (...workflows: string[]) => workflows.map((workflow) => ({ workflow }));

const env: Env = {
  GITHUB_DISPATCH_TOKEN: "test-token",
  GITHUB_REPO: "owner/repo",
  GITHUB_REF: "main",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("due (AC-1)", () => {
  it("fires the backup at 03:30 ET in EDT and EST", () => {
    expect(due(new Date("2026-10-17T07:30:00Z"))).toEqual(["backup.yml"]); // EDT, UTC-4
    expect(due(new Date("2026-11-07T08:30:00Z"))).toEqual(["backup.yml"]); // EST, UTC-5
  });

  it("does not fire at 02:30 EST, the old 07:30 UTC cron time", () => {
    expect(due(new Date("2026-11-07T07:30:00Z"))).toEqual([]);
  });

  it("does not fire in the slots either side of 03:30 ET", () => {
    for (const tick of [
      "2026-10-17T07:15:00Z",
      "2026-10-17T07:45:00Z",
      "2026-11-07T08:15:00Z",
      "2026-11-07T08:45:00Z",
    ]) {
      expect(due(new Date(tick)), tick).toEqual([]);
    }
  });

  it("fires on a tick that runs late but inside its quarter-hour slot", () => {
    expect(due(new Date("2026-10-17T07:44:59Z"))).toEqual(["backup.yml"]);
  });

  it("matches weekday entries on their ET weekday only", () => {
    const schedule = [{ workflow: "results.yml", days: ["Sun"], time: "06:00" }] as const;
    // 2026-10-18 06:00 EDT is Sunday; the same UTC instant a day earlier is Saturday.
    expect(due(new Date("2026-10-18T10:00:00Z"), schedule)).toEqual(["results.yml"]);
    expect(due(new Date("2026-10-17T10:00:00Z"), schedule)).toEqual([]);
  });

  it("fires results Sun and Mon 06:00 ET; lines daily 08:00 and Thu/Fri 19:00 ET", () => {
    // EDT (UTC-4): Sunday 2026-10-25, Monday 10-26, Tuesday 10-27, Thursday 10-29, Saturday 10-31.
    expect(due(new Date("2026-10-25T10:00:00Z"))).toEqual(["results.yml"]);
    expect(due(new Date("2026-10-26T10:00:00Z"))).toEqual(["results.yml"]);
    expect(due(new Date("2026-10-27T10:00:00Z"))).toEqual([]);
    expect(due(new Date("2026-10-25T12:00:00Z"))).toEqual(["lines.yml"]);
    expect(due(new Date("2026-10-29T23:00:00Z"))).toEqual(["lines.yml"]);
    expect(due(new Date("2026-10-31T23:00:00Z"))).toEqual(["scores.yml"]); // Saturday: no lines
    // EST (UTC-5): Sunday 2026-11-08, Friday 11-13.
    expect(due(new Date("2026-11-08T11:00:00Z"))).toEqual(["results.yml"]);
    expect(due(new Date("2026-11-08T10:00:00Z"))).toEqual([]);
    expect(due(new Date("2026-11-08T13:00:00Z"))).toEqual(["lines.yml"]);
    expect(due(new Date("2026-11-14T00:00:00Z"))).toEqual(["lines.yml"]);
  });

  it("fires rate-and-predict Sun 09:00 ET only, for real rather than a dry run (TASK-046)", () => {
    // Sunday 2026-10-25 09:00 EDT; Sunday 2026-11-08 09:00 EST; Monday 2026-10-26 09:00 EDT.
    expect(dueEntries(new Date("2026-10-25T13:00:00Z"))).toEqual([
      { workflow: "rate-and-predict.yml", days: ["Sun"], time: "09:00" },
    ]);
    expect(due(new Date("2026-11-08T14:00:00Z"))).toEqual(["rate-and-predict.yml"]);
    expect(due(new Date("2026-11-08T13:00:00Z"))).toEqual(["lines.yml"]); // 08:00 EST
    expect(due(new Date("2026-10-26T13:00:00Z"))).toEqual([]);
  });

  it("fires the Vercel cleanup Mondays 06:15 ET, for real rather than a dry run (D-126)", () => {
    // Monday 2026-10-26 06:15 EDT; Monday 2026-11-09 06:15 EST; Sunday 2026-10-25 06:15 EDT.
    expect(dueEntries(new Date("2026-10-26T10:15:00Z"))).toEqual([
      { workflow: "vercel-cleanup.yml", days: ["Mon"], time: "06:15", inputs: { dry_run: "false" } },
    ]);
    expect(due(new Date("2026-11-09T11:15:00Z"))).toEqual(["vercel-cleanup.yml"]);
    expect(due(new Date("2026-10-25T10:15:00Z"))).toEqual([]);
  });

  describe("scores (TASK-074 AC-5)", () => {
    const scores = (now: string) =>
      dueEntries(new Date(now))
        .filter((e) => e.workflow === "scores.yml")
        .map((e) => e.inputs?.sport ?? "all");

    it("fires every 30 minutes Thu and Fri 19:30 to 00:30 ET, CFB and NFL", () => {
      // EDT (UTC-4): Thursday 2026-10-29, Friday 10-30, Saturday 10-31.
      expect(scores("2026-10-29T23:15:00Z")).toEqual([]); // Thu 19:15
      expect(scores("2026-10-29T23:30:00Z")).toEqual(["all"]); // Thu 19:30
      expect(scores("2026-10-30T00:45:00Z")).toEqual([]); // Thu 20:45: off the half hour
      expect(scores("2026-10-30T03:00:00Z")).toEqual(["all"]); // Thu 23:00
      expect(scores("2026-10-30T04:30:00Z")).toEqual(["all"]); // Fri 00:30
      expect(scores("2026-10-30T05:00:00Z")).toEqual([]); // Fri 01:00
      expect(scores("2026-10-30T22:30:00Z")).toEqual([]); // Fri 18:30
      expect(scores("2026-10-31T04:30:00Z")).toEqual(["all"]); // Sat 00:30, Friday's window
    });

    it("fires Sat 12:00 ET to Sun 00:30, and Sun 03:00 for late finals", () => {
      // EST (UTC-5): Saturday 2026-11-14, Sunday 11-15.
      expect(scores("2026-11-14T16:30:00Z")).toEqual([]); // Sat 11:30
      expect(scores("2026-11-14T17:00:00Z")).toEqual(["all"]); // Sat 12:00
      expect(scores("2026-11-15T04:30:00Z")).toEqual(["all"]); // Sat 23:30
      expect(scores("2026-11-15T05:30:00Z")).toEqual(["all"]); // Sun 00:30
      expect(scores("2026-11-15T06:00:00Z")).toEqual([]); // Sun 01:00
      expect(scores("2026-11-15T08:00:00Z")).toEqual(["all"]); // Sun 03:00
      expect(scores("2026-11-15T08:30:00Z")).toEqual([]); // Sun 03:30, the backup's
    });

    it("fires NFL-only Sun 13:30 to Mon 00:30 and Mon 20:30 to Tue 00:30 ET", () => {
      // EST: Sunday 2026-11-15, Monday 11-16, Tuesday 11-17.
      expect(scores("2026-11-15T18:00:00Z")).toEqual([]); // Sun 13:00
      expect(scores("2026-11-15T18:30:00Z")).toEqual(["nfl"]); // Sun 13:30
      expect(scores("2026-11-16T01:30:00Z")).toEqual(["nfl"]); // Sun 20:30
      expect(scores("2026-11-16T05:30:00Z")).toEqual(["nfl"]); // Mon 00:30
      expect(scores("2026-11-16T06:00:00Z")).toEqual([]); // Mon 01:00
      expect(scores("2026-11-17T01:00:00Z")).toEqual([]); // Mon 20:00
      expect(scores("2026-11-17T01:30:00Z")).toEqual(["nfl"]); // Mon 20:30
      expect(scores("2026-11-17T05:30:00Z")).toEqual(["nfl"]); // Tue 00:30
      expect(scores("2026-11-18T01:30:00Z")).toEqual([]); // Tue 20:30
      expect(scores("2026-11-19T01:30:00Z")).toEqual([]); // Wed 20:30
    });

    it("starts at most one scores run a slot, 49 CFB runs (CFBD calls) a week", () => {
      let cfb = 0;
      // Every quarter hour of an EST week, Sunday 2026-11-15 00:00 ET onwards.
      for (let t = Date.parse("2026-11-15T05:00:00Z"); t < Date.parse("2026-11-22T05:00:00Z"); t += 15 * 60_000) {
        const found = scores(new Date(t).toISOString());
        expect(found.length, new Date(t).toISOString()).toBeLessThanOrEqual(1);
        if (found[0] === "all") cfb += 1;
      }
      expect(cfb).toBe(49);
    });
  });

  it("has no entry between 01:00 and 02:59 ET, and every entry is on a quarter hour", () => {
    for (const entry of SCHEDULE) {
      const [hour, minute] = entry.time.split(":").map(Number);
      expect(hour === 1 || hour === 2, entry.workflow).toBe(false);
      expect(minute % 15, entry.workflow).toBe(0);
    }
  });
});

describe("dispatch (AC-2)", () => {
  it("sends one POST per due workflow with ref main and the bearer token", async () => {
    const fetchFn = vi.fn(async () => new Response(null, { status: 204 }));

    const failed = await dispatch(env, entries("backup.yml"), fetchFn);

    expect(failed).toEqual([]);
    expect(fetchFn).toHaveBeenCalledTimes(1);
    const [url, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://api.github.com/repos/owner/repo/actions/workflows/backup.yml/dispatches");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ ref: "main" });
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer test-token");
    expect(headers.get("User-Agent")).toBeTruthy();
  });

  it("sends an entry's inputs with the ref", async () => {
    vi.spyOn(console, "log").mockImplementation(() => {});
    const fetchFn = vi.fn(async () => new Response(null, { status: 204 }));

    await dispatch(env, [{ workflow: "vercel-cleanup.yml", inputs: { dry_run: "false" } }], fetchFn);

    const [, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ ref: "main", inputs: { dry_run: "false" } });
  });

  it("logs a non-2xx with its status and body and still sends the rest", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(console, "log").mockImplementation(() => {});
    const fetchFn = vi
      .fn()
      .mockResolvedValueOnce(new Response('{"message":"No ref found for: main"}', { status: 422 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    const failed = await dispatch(env, entries("first.yml", "second.yml"), fetchFn);

    expect(fetchFn).toHaveBeenCalledTimes(2);
    expect(String(fetchFn.mock.calls[1][0])).toContain("/workflows/second.yml/dispatches");
    expect(failed).toEqual(["first.yml"]);
    const logged = error.mock.calls.flat().join(" ");
    expect(logged).toContain("first.yml");
    expect(logged).toContain("422");
    expect(logged).toContain("No ref found for: main");
  });

  it("treats a network error like a failed dispatch and still sends the rest", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(console, "log").mockImplementation(() => {});
    const fetchFn = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("network down"))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    expect(await dispatch(env, entries("first.yml", "second.yml"), fetchFn)).toEqual(["first.yml"]);
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });
});

describe("scheduled handler", () => {
  const controller = (iso: string) =>
    ({ scheduledTime: Date.parse(iso), cron: "*/15 * * * *", noRetry() {} }) as ScheduledController;

  it("dispatches what is due at the event's scheduled time", async () => {
    vi.spyOn(console, "log").mockImplementation(() => {});
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));

    await worker.scheduled(controller("2026-10-17T07:30:00Z"), env);

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(String(fetchSpy.mock.calls[0][0])).toContain("/workflows/backup.yml/dispatches");
  });

  it("sends nothing when nothing is due", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    await worker.scheduled(controller("2026-10-17T07:15:00Z"), env);

    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("throws after a failed dispatch so the Cron event shows as failed", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("Bad credentials", { status: 401 }));

    await expect(
      worker.scheduled(controller("2026-10-17T07:30:00Z"), env),
    ).rejects.toThrow("backup.yml");
  });
});

describe("secrets (AC-3)", () => {
  it("has no token-shaped string in the package", () => {
    const root = join(import.meta.dirname, "..");
    const tokenShaped = /github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{36}/;
    const walk = (dir: string): string[] =>
      readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
        if (entry.name === "node_modules" || entry.name.startsWith(".wrangler")) return [];
        const path = join(dir, entry.name);
        return entry.isDirectory() ? walk(path) : [path];
      });

    const files = walk(root);
    expect(files.length).toBeGreaterThan(3);
    for (const file of files) {
      expect(tokenShaped.test(readFileSync(file, "utf8")), file).toBe(false);
    }
  });
});
