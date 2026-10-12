import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { decode, encode } from "next-auth/jwt";
import { afterEach, describe, expect, it } from "vitest";

import {
  aggregateRoute,
  BUDGETED,
  baselinePr,
  baselineRun,
  eventInputs,
  findComment,
  forbiddenPath,
  gateProblems,
  guardMessage,
  headerSecrets,
  MARKER,
  measurable,
  median,
  mergeMetrics,
  mintSession,
  renderComment,
  scrubLhr,
  scrubText,
  sessionCookieName,
  sessionHeaders,
  summariseLhr,
  unbudgeted,
} from "../../scripts/perf/lib/perf.mjs";
import { ROUTES } from "../../scripts/perf/routes.mjs";

// The Lighthouse job's decisions (02 › Performance checks (Lighthouse), D-101), fed fixture
// Lighthouse results instead of a real run: no network, no Chrome, no database (TASK-007).

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const BASE = "https://cfb-model-git-feat-x-justin-tillman.vercel.app";
const PRODUCTION = "https://cfb-model.vercel.app";

type Request = { url: string; type: string; size: number; mime?: string };

// A Lighthouse result cut down to the fields the job reads. The document is 10,000 bytes.
function lhr({
  path = "/teams",
  requests = [] as Request[],
  cls = 0.01,
  a11y = 0.95,
  timings = { ttfb: 120.4, fcp: 900, lcp: 1400, tbt: 80 },
} = {}) {
  return {
    finalDisplayedUrl: BASE + path,
    configSettings: { extraHeaders: { Cookie: "x=1" } as Record<string, string> | null },
    categories: { accessibility: { score: a11y } },
    audits: {
      metrics: { details: { items: [{ timeToFirstByte: timings.ttfb }] } },
      "first-contentful-paint": { numericValue: timings.fcp },
      "largest-contentful-paint": { numericValue: timings.lcp },
      "total-blocking-time": { numericValue: timings.tbt },
      "cumulative-layout-shift": { numericValue: cls },
      "network-requests": {
        details: {
          items: [
            { url: BASE + path, resourceType: "Document", transferSize: 10_000, mimeType: "text/html" },
            ...requests.map((r) => ({
              url: r.url.startsWith("http") ? r.url : BASE + r.url,
              resourceType: r.type,
              transferSize: r.size,
              mimeType: r.mime ?? "",
            })),
          ],
        },
      },
    } as Record<string, unknown>,
  };
}

// A route's three runs, each the same fixture result.
const runs = (result: ReturnType<typeof lhr>, path = "/teams") => {
  const load = summariseLhr(result);
  return aggregateRoute({ path, loads: [load, load, load] });
};

// A page that loads `docBytes` of document + RSC, `jsBytes` of JS in one script, and `requests`
// requests in total (padding with 1-byte images).
function page({ docBytes = 12_000, jsBytes = 140_000, requests = 15, cls = 0.01, a11y = 95 } = {}) {
  const fill = Math.max(0, requests - 3);
  return lhr({
    cls,
    a11y: a11y / 100,
    requests: [
      { url: "/_next/static/chunks/main.js", type: "Script", size: jsBytes },
      { url: "/teams?_rsc=1", type: "Fetch", size: docBytes - 10_000, mime: "text/x-component" },
      ...Array.from({ length: fill }, (_, i) => ({ url: `/img/${i}.png`, type: "Image", size: 1 })),
    ],
  });
}

const BUDGET = { teams: { docBytes: 15_000, jsBytes: 150_000, requests: 20, a11y: 95 } };
const gate = (result: ReturnType<typeof lhr>, budget: Parameters<typeof gateProblems>[1] = BUDGET) =>
  gateProblems({ teams: runs(result) }, budget);

describe("summariseLhr", () => {
  const s = summariseLhr(
    lhr({
      requests: [
        { url: "/_next/static/chunks/a.js", type: "Script", size: 70_000 },
        { url: "/_next/static/chunks/b.js", type: "Script", size: 30_000 },
        { url: "/login?_rsc=x1", type: "Fetch", size: 1_000, mime: "text/x-component" },
        { url: "/_next-live/feedback/feedback.js", type: "Script", size: 157 },
        { url: "https://vercel.live/feedback/x.js", type: "Script", size: 9_999 },
      ],
    }),
  );

  it("counts document + RSC, JS and requests, leaving Vercel's extras out", () => {
    expect(s.docBytes).toBe(11_000);
    expect(s.jsBytes).toBe(100_000);
    expect(s.requests).toBe(4);
  });

  it("reads the four timings, CLS, the accessibility score and where the load ended", () => {
    expect(s).toMatchObject({ landedOn: "/teams", ttfb: 120, fcp: 900, lcp: 1400, tbt: 80, cls: 0.01, a11y: 95 });
  });

  it("takes the median of the runs, ignoring missing values", () => {
    expect(median([3, 1, 2])).toBe(2);
    expect(median([4, null, 2])).toBe(3);
    expect(median([])).toBeNull();
  });
});

describe("AC-1: each gated number passes at budget and fails just over it", () => {
  it("passes a route exactly at every budget", () => {
    expect(gate(page({ docBytes: 15_000, jsBytes: 150_000, requests: 20, a11y: 95 }))).toEqual([]);
  });

  it("fails document + RSC bytes one over, naming the route and the number", () => {
    expect(gate(page({ docBytes: 15_001 }))).toEqual([
      "teams: document + RSC 15,001 bytes is over the budget of 15,000 bytes",
    ]);
  });

  it("fails JS bytes one over", () => {
    expect(gate(page({ jsBytes: 150_001 }))).toEqual(["teams: JS 150,001 bytes is over the budget of 150,000 bytes"]);
  });

  it("fails one request over", () => {
    expect(gate(page({ requests: 21 }))).toEqual(["teams: requests 21 is over the budget of 20"]);
  });

  it("fails CLS at 0.1, not below it", () => {
    expect(gate(page({ cls: 0.099 }))).toEqual([]);
    expect(gate(page({ cls: 0.1 }))).toEqual(["teams: CLS 0.100 is 0.1 or more"]);
  });

  it("fails accessibility one below the recorded score", () => {
    expect(gate(page({ a11y: 94 }))).toEqual(["teams: accessibility 94 is below the recorded 95"]);
  });

  it("gates on the median of the runs, so one outlier run doesn't fail", () => {
    const loads = [page({ requests: 99 }), page(), page()].map(summariseLhr);
    expect(gateProblems({ teams: aggregateRoute({ path: "/teams", loads }) }, BUDGET)).toEqual([]);
  });

  it("reads the budget keys docs/02 says budget.json holds", () => {
    const doc = readFileSync(join(ROOT, "docs/02-architecture.md"), "utf8");
    const line = doc.split("\n").find((l) => l.includes("`budget.json` (per route:"));
    const documented = line?.match(/`budget\.json` \(per route: ([^)]+)\)/)?.[1].match(/`(\w+)`/g)?.map((k) => k.slice(1, -1));
    expect(documented).toBeTruthy();
    expect([...BUDGETED.map((b) => b.key), "a11y"].sort()).toEqual([...documented!].sort());
  });

  it("doesn't gate a route with no budget yet, and lists it", () => {
    expect(gate(page({ jsBytes: 9e9 }), {})).toEqual([]);
    expect(unbudgeted({ teams: runs(page()) }, {})).toEqual(["teams"]);
    expect(unbudgeted({ teams: runs(page()) }, BUDGET)).toEqual([]);
  });
});

describe("AC-2: forbidden requests, Vercel extras, and routes that didn't measure", () => {
  it("fails a page load that prefetches an /api/py/* URL, naming the URL", () => {
    const result = page();
    result.audits["network-requests"] = lhr({
      requests: [{ url: "/api/py/teams?_rsc=abc", type: "Fetch", size: 400, mime: "text/x-component" }],
    }).audits["network-requests"];
    const [problem, ...rest] = gate(result);
    expect(problem).toMatch(/^teams: requested \/api\/py\/teams during a page load or prefetch/);
    // The comment is Markdown: a bare <a> or <Link> would render as HTML and vanish.
    expect(problem).toContain("`<a>`, never `<Link>`");
    expect(rest).toEqual([]);
  });

  it("fails a forbidden request made by any one of the runs", () => {
    const bad = lhr({ requests: [{ url: "/api/py/health", type: "Fetch", size: 10 }] });
    const loads = [page(), bad, page()].map(summariseLhr);
    expect(gateProblems({ teams: aggregateRoute({ path: "/teams", loads }) }, BUDGET)[0]).toContain("/api/py/health");
  });

  it("forbids only the Python API's paths", () => {
    expect(forbiddenPath(`${BASE}/api/py/teams?x=1`)).toBe("/api/py/teams");
    expect(forbiddenPath(`${BASE}/api/py`)).toBe("/api/py");
    expect(forbiddenPath(`${BASE}/api/pyx`)).toBeNull();
    expect(forbiddenPath(`${BASE}/teams`)).toBeNull();
    expect(forbiddenPath("not a url")).toBeNull();
  });

  it("leaves vercel.live and _next-live out of the request count and bytes", () => {
    const extras = [
      { url: "https://vercel.live/toolbar.js", type: "Script", size: 50_000 },
      { url: "/_next-live/feedback/x.js", type: "Script", size: 50_000 },
    ];
    type Requests = { details: { items: object[] } };
    const withExtras = page({ requests: 20, jsBytes: 150_000 });
    const items = (withExtras.audits["network-requests"] as Requests).details.items;
    items.push(...(lhr({ requests: extras }).audits["network-requests"] as Requests).details.items.slice(1));
    expect(summariseLhr(withExtras)).toMatchObject({ requests: 20, jsBytes: 150_000 });
    expect(gate(withExtras)).toEqual([]);
  });

  it("fails a route whose every run errored, saying it never finished measuring", () => {
    const route = aggregateRoute({ path: "/teams", loads: [{ error: "Lighthouse exited 1" }, { error: "timeout" }] });
    expect(gateProblems({ teams: route }, BUDGET)).toEqual(["teams: never finished measuring (Lighthouse exited 1)"]);
  });

  it("fails a route whose job wrote no metrics", () => {
    expect(gateProblems({ teams: runs(page()) }, BUDGET, ["login", "teams"])).toEqual([
      "login: never finished measuring (its job wrote no metrics)",
    ]);
  });

  it("fails a route that ended on /login, saying the session didn't take", () => {
    const [problem] = gate(lhr({ path: "/login" }));
    expect(problem).toMatch(/^teams: loaded \/teams and ended on \/login: the session didn't take/);
  });
});

describe("AC-3: measurable", () => {
  const preview = {
    eventName: "deployment_status",
    environment: "Preview",
    state: "success",
    deploymentUrl: `${BASE}/`,
    productionUrl: PRODUCTION,
  };
  const hand = { eventName: "workflow_dispatch", inputUrl: BASE, productionUrl: PRODUCTION };

  it("measures a preview that finished deploying", () => {
    expect(measurable(preview)).toEqual({ url: BASE });
  });

  it("refuses every deployment state other than success", () => {
    for (const state of ["failure", "error", "inactive", "pending", "in_progress", "queued"]) {
      expect(measurable({ ...preview, state }), state).toEqual({ skip: `deployment is ${state}, not success` });
    }
  });

  it("skips a deployment that isn't on the Preview environment", () => {
    expect(measurable({ ...preview, environment: "Production" })).toHaveProperty("skip");
  });

  it("refuses the production URL on a hand run unless allow_production is set", () => {
    expect(measurable({ ...hand, inputUrl: `${PRODUCTION}/teams` })).toHaveProperty("problem");
    expect(measurable({ ...hand, inputUrl: PRODUCTION, allowProduction: false })).toHaveProperty("problem");
    expect(measurable({ ...hand, inputUrl: PRODUCTION, allowProduction: true })).toEqual({ url: PRODUCTION });
  });

  it("refuses a preview event that carries the production URL", () => {
    expect(measurable({ ...preview, deploymentUrl: PRODUCTION })).toHaveProperty("problem");
  });

  it("takes a hand run's preview URL, and refuses anything that isn't an https URL", () => {
    expect(measurable(hand)).toEqual({ url: BASE });
    expect(measurable({ ...hand, inputUrl: "http://example.com" })).toHaveProperty("problem");
    expect(measurable({ ...hand, inputUrl: "nope" })).toHaveProperty("problem");
    expect(measurable({ eventName: "push" })).toHaveProperty("skip");
  });

  it("reads its inputs from the GitHub event payload", () => {
    const deployment = {
      deployment: { sha: "abc", environment: "Preview" },
      deployment_status: { state: "success", environment: "Preview", environment_url: `${BASE}/`, target_url: "https://vercel.com/x" },
    };
    expect(measurable(eventInputs("deployment_status", deployment, PRODUCTION))).toEqual({ url: BASE });
    const failedDeploy = { ...deployment, deployment_status: { ...deployment.deployment_status, state: "failure" } };
    expect(measurable(eventInputs("deployment_status", failedDeploy, PRODUCTION))).toHaveProperty("skip");

    const dispatch = (allow: unknown) => ({ inputs: { url: PRODUCTION, allow_production: allow } });
    expect(measurable(eventInputs("workflow_dispatch", dispatch("false"), PRODUCTION))).toHaveProperty("problem");
    expect(measurable(eventInputs("workflow_dispatch", dispatch(true), PRODUCTION))).toEqual({ url: PRODUCTION });
    expect(measurable(eventInputs("workflow_dispatch", dispatch("true"), PRODUCTION))).toEqual({ url: PRODUCTION });
  });
});

describe("AC-4: secrets stay out of the reports", () => {
  const AUTH_SECRET = "preview-auth-secret-0123456789abcdefghij";
  const BYPASS = "bypass-secret-value-0123456789";

  async function signedInHeaders() {
    const cookie = await mintSession({ url: BASE, secret: AUTH_SECRET, githubId: "4242", encode });
    return { cookie, headers: sessionHeaders({ cookie, bypass: BYPASS }) };
  }

  it("scrubs every secret and the minted cookie from a Lighthouse JSON and HTML report", async () => {
    const { cookie, headers } = await signedInHeaders();
    const secrets = [AUTH_SECRET, BYPASS, ...headerSecrets(headers.signedIn)];
    const report = lhr();
    report.configSettings.extraHeaders = headers.signedIn;
    report.audits.note = { text: `sent ${headers.signedIn.Cookie} with ${AUTH_SECRET}` };
    const html = `<html><script>window.__LIGHTHOUSE_JSON__ = ${JSON.stringify(report)};</script>
      <p>x-vercel-protection-bypass: ${BYPASS}</p><p>${cookie.value}</p></html>`;

    const json = JSON.stringify(scrubLhr(report, secrets));
    const cleanHtml = scrubText(html, secrets);
    for (const text of [json, cleanHtml]) {
      for (const secret of [AUTH_SECRET, BYPASS, cookie.value]) expect(text).not.toContain(secret);
      expect(text).toContain("[redacted]");
    }
    expect(JSON.parse(json).configSettings.extraHeaders).toBeNull();
    expect(report.configSettings.extraHeaders).not.toBeNull(); // the input is left alone
    expect(guardMessage([{ name: "teams-1.json", text: json }, { name: "teams-1.html", text: cleanHtml }], secrets))
      .toBeNull();
  });

  it("fails on a file that still holds one, naming the file and never the value", async () => {
    const { cookie, headers } = await signedInHeaders();
    const secrets = [AUTH_SECRET, BYPASS, ...headerSecrets(headers.signedIn)];
    const files = [
      { name: "reports/teams-1.json", text: "{}" },
      { name: "reports/teams-2.html", text: `<p>${cookie.value}</p>` },
      { name: "reports/login-1.html", text: `bypass ${BYPASS}` },
    ];
    const message = guardMessage(files, secrets);
    expect(message).toContain("reports/teams-2.html");
    expect(message).toContain("reports/login-1.html");
    expect(message).not.toContain("reports/teams-1.json");
    for (const secret of [AUTH_SECRET, BYPASS, cookie.value]) expect(message).not.toContain(secret);
  });

  it("ignores empty or missing secrets rather than redacting everything", () => {
    expect(scrubText("plain text", ["", undefined, null])).toBe("plain text");
    expect(guardMessage([{ name: "a.json", text: "{}" }], ["", undefined])).toBeNull();
  });
});

describe("mintSession: the session cookie Auth.js reads", () => {
  it("is named for https on a preview and for http locally", () => {
    expect(sessionCookieName(BASE)).toBe("__Secure-authjs.session-token");
    expect(sessionCookieName("http://127.0.0.1:3000")).toBe("authjs.session-token");
  });

  it("decodes with the preview AUTH_SECRET to the allowlisted GitHub ID", async () => {
    const cookie = await mintSession({ url: BASE, secret: "s".repeat(40), githubId: "4242", encode });
    expect(cookie.name).toBe("__Secure-authjs.session-token");
    const token = await decode({ token: cookie.value, secret: "s".repeat(40), salt: cookie.name });
    expect(token?.sub).toBe("4242");
    expect(await decode({ token: cookie.value, secret: "t".repeat(40), salt: cookie.name }).catch(() => null))
      .toBeNull();
  });

  it("refuses to mint without a secret or a GitHub ID", async () => {
    await expect(mintSession({ url: BASE, secret: "", githubId: "4242", encode })).rejects.toThrow(/AUTH_SECRET/);
    await expect(mintSession({ url: BASE, secret: "s".repeat(40), githubId: "", encode })).rejects.toThrow(
      /AUTH_ALLOWED_GITHUB_ID/,
    );
  });

  it("puts the cookie only in the signed-in headers, and the bypass in both", () => {
    const cookie = { name: "__Secure-authjs.session-token", value: "abc.def" };
    const { signedIn, signedOut } = sessionHeaders({ cookie, bypass: "b" });
    expect(signedIn).toEqual({
      "x-vercel-skip-toolbar": "1",
      "x-vercel-protection-bypass": "b",
      Cookie: "__Secure-authjs.session-token=abc.def",
    });
    expect(signedOut).toEqual({ "x-vercel-skip-toolbar": "1", "x-vercel-protection-bypass": "b" });
    expect(sessionHeaders({ cookie }).signedOut).toEqual({ "x-vercel-skip-toolbar": "1" });
    expect(headerSecrets(signedIn)).toEqual(["b", "__Secure-authjs.session-token=abc.def", "abc.def"]);
  });

  it("uses the @auth/core version next-auth installs, so the cookie format can't drift", () => {
    const perf = JSON.parse(readFileSync(join(ROOT, "scripts/perf/package.json"), "utf8"));
    const lock = readFileSync(join(ROOT, "pnpm-lock.yaml"), "utf8");
    const installed = lock.match(/\n {2}next-auth@[^\n]+:\n {4}dependencies:\n {6}'@auth\/core': ([^\s(]+)/)?.[1];
    expect(installed).toBeTruthy();
    expect(perf.dependencies["@auth/core"]).toBe(installed);
  });
});

describe("AC-5: the PR comment and the baseline", () => {
  const route = () => {
    const loads = [
      lhr({ timings: { ttfb: 3000, fcp: 2500, lcp: 4000, tbt: 300 } }),
      lhr({ timings: { ttfb: 100, fcp: 900, lcp: 1400, tbt: 80 } }),
      lhr({ timings: { ttfb: 140, fcp: 950, lcp: 1600, tbt: 90 } }),
    ].map(summariseLhr);
    return aggregateRoute({ path: "/teams", loads });
  };
  const current = { url: BASE, sha: "abcdef1234", lighthouse: "13.5.0", routes: { teams: route() } };

  it("is one Markdown body that starts with the fixed marker", () => {
    const md = renderComment({ current, baseline: null, budget: BUDGET, problems: [] });
    expect(MARKER).toMatch(/^<!-- .+ -->$/);
    expect(md.startsWith(`${MARKER}\n`)).toBe(true);
    expect(md.split(MARKER)).toHaveLength(2);
    expect(md).toContain("within budget");
  });

  it("reports TTFB, FCP, LCP and TBT as first hit / median, with no baseline", () => {
    const md = renderComment({ current, baseline: null, budget: BUDGET, problems: [] });
    expect(md).toContain("| Route | TTFB | FCP | LCP | TBT |");
    expect(md).toContain("| `/teams` | 3.00 s / 140 ms | 2.50 s / 950 ms | 4.00 s / 1.60 s | 300 ms / 90 ms |");
    expect(md).toContain("No baseline");
  });

  it("shows the baseline's median beside each timing", () => {
    const baseline = {
      pr: 47,
      at: "2026-10-05T12:00:00Z",
      routes: { teams: { median: { ttfb: 200, fcp: 1000, lcp: 2000, tbt: 100 } } },
    };
    const md = renderComment({ current, baseline, budget: BUDGET, problems: [] });
    expect(md).toContain(
      "| `/teams` | 3.00 s / 140 ms (base 200 ms) | 2.50 s / 950 ms (base 1.00 s) | 4.00 s / 1.60 s (base 2.00 s) | 300 ms / 90 ms (base 100 ms) |",
    );
    expect(md).toContain("PR #47's preview, 2026-10-05");
    expect(md).not.toContain("No baseline");
  });

  it("says no baseline for a route the baseline didn't measure", () => {
    const baseline = { pr: 47, at: "2026-10-05T12:00:00Z", routes: {} };
    expect(renderComment({ current, baseline, budget: BUDGET, problems: [] })).toContain(
      "3.00 s / 140 ms (no baseline)",
    );
  });

  it("never fails on timings, however slow", () => {
    const slow = lhr({ timings: { ttfb: 60_000, fcp: 60_000, lcp: 90_000, tbt: 30_000 } });
    expect(gate(slow)).toEqual([]);
  });

  it("lists the problems and the routes with no budget", () => {
    const md = renderComment({
      current,
      baseline: null,
      budget: {},
      problems: ["teams: requested /api/py/teams during a page load or prefetch"],
      missingBudget: ["teams"],
    });
    expect(md).toContain("1 problem");
    expect(md).toContain("- teams: requested /api/py/teams during a page load or prefetch");
    expect(md).toContain("**No budget recorded** for `teams`");
  });

  it("finds its own earlier comment by the marker", () => {
    const comments = [
      { id: 1, body: "looks good" },
      { id: 2, body: `${MARKER}\n### Lighthouse` },
    ];
    expect(findComment(comments)?.id).toBe(2);
    expect(findComment([{ id: 1, body: "x" }])).toBeUndefined();
  });

  it("picks the newest merged PR other than this one", () => {
    const pulls = [
      { number: 50, merged_at: null },
      { number: 48, merged_at: "2026-10-05T10:00:00Z" },
      { number: 49, merged_at: "2026-10-06T10:00:00Z" },
    ];
    expect(baselinePr(pulls)?.number).toBe(49);
    expect(baselinePr(pulls, [49])?.number).toBe(48);
    expect(baselinePr([{ number: 50, merged_at: null }])).toBeNull();
  });

  it("picks that PR's newest green run", () => {
    const list = [
      { id: 1, status: "completed", conclusion: "success", created_at: "2026-10-05T10:00:00Z" },
      { id: 2, status: "completed", conclusion: "failure", created_at: "2026-10-05T11:00:00Z" },
      { id: 3, status: "completed", conclusion: "success", created_at: "2026-10-05T12:00:00Z" },
      { id: 4, status: "in_progress", conclusion: null, created_at: "2026-10-05T13:00:00Z" },
    ];
    expect(baselineRun(list)?.id).toBe(3);
    expect(baselineRun(list.slice(1, 2))).toBeNull();
  });

  it("merges the per-route jobs' metrics in the route list's order", () => {
    const part = (id: string, at: string) => ({
      url: BASE,
      sha: "abc",
      lighthouse: "13.5.0",
      measuredAt: at,
      routes: { [id]: { path: `/${id}`, loads: [summariseLhr(page())] } },
    });
    const merged = mergeMetrics([part("teams", "2026-10-11T05:02:00Z"), part("login", "2026-10-11T05:01:00Z")], [
      "login",
      "teams",
    ]);
    expect(Object.keys(merged.routes)).toEqual(["login", "teams"]);
    expect(merged.measuredAt).toBe("2026-10-11T05:01:00Z");
    expect(() => mergeMetrics([], ["login"])).toThrow(/no route was measured/);
  });
});

describe("AC-6: the route list (scripts/perf/routes.mjs)", () => {
  // `/` only redirects to /teams until This Week takes it over in Phase 4; then it gets a route.
  const EXEMPT = new Set(["/"]);

  // Top-level screens: web/app/page.tsx is `/`, and each web/app/<segment>/ with a page.tsx, directly
  // or under a (group). Route handlers (api), private folders and dynamic segments aren't screens.
  function topLevelScreens(appDir: string): string[] {
    const hasPage = (dir: string): boolean =>
      readdirSync(dir, { withFileTypes: true }).some((e) =>
        e.isFile() ? e.name === "page.tsx" : /^\(.+\)$/.test(e.name) && hasPage(join(dir, e.name)),
      );
    const segments = readdirSync(appDir, { withFileTypes: true })
      .filter((e) => e.isDirectory() && e.name !== "api" && !/^[([@_]/.test(e.name))
      .filter((e) => hasPage(join(appDir, e.name)))
      .map((e) => `/${e.name}`);
    return [...(hasPage(appDir) ? ["/"] : []), ...segments];
  }

  const unlisted = (appDir: string) => {
    const listed = new Set(ROUTES.map((r) => r.path));
    return topLevelScreens(appDir).filter((s) => !listed.has(s) && !EXEMPT.has(s));
  };

  let tmp: string | undefined;
  afterEach(() => {
    if (tmp) rmSync(tmp, { recursive: true, force: true });
    tmp = undefined;
  });

  it("lists /login signed out and /teams signed in, with unique ids", () => {
    expect(ROUTES).toContainEqual({ id: "login", path: "/login", signedIn: false });
    expect(ROUTES).toContainEqual({ id: "teams", path: "/teams", signedIn: true });
    expect(new Set(ROUTES.map((r) => r.id)).size).toBe(ROUTES.length);
  });

  it("has a route for every top-level page under web/app/", () => {
    expect(topLevelScreens(join(ROOT, "web/app"))).toEqual(expect.arrayContaining(["/login", "/teams"]));
    expect(unlisted(join(ROOT, "web/app"))).toEqual([]);
  });

  it("catches a top-level page with no route", () => {
    tmp = mkdtempSync(join(tmpdir(), "perf-routes-"));
    for (const dir of ["login", "teams", "(main)/picks", "api/py", "_parts"]) mkdirSync(join(tmp, dir), { recursive: true });
    for (const file of ["page.tsx", "login/page.tsx", "teams/page.tsx", "(main)/picks/page.tsx", "_parts/page.tsx"]) {
      writeFileSync(join(tmp, file), "");
    }
    mkdirSync(join(tmp, "rankings/(list)"), { recursive: true });
    writeFileSync(join(tmp, "rankings/(list)/page.tsx"), "");
    expect(unlisted(tmp)).toEqual(["/rankings"]);
  });
});
