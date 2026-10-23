import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { decode, encode } from "next-auth/jwt";
import { afterEach, describe, expect, it } from "vitest";

import { SKIP_PREFIXES } from "../../scripts/lib/ci-scope.mjs";
import {
  aggregateRoute,
  BASELINE_EVENT,
  BUDGETED,
  baselineCandidates,
  baselinePr,
  baselineRun,
  budgetFrom,
  budgetTable,
  checkRun,
  chromeVersion,
  eventInputs,
  FIXTURE_URL,
  findComment,
  forbiddenPath,
  gateProblems,
  guardMessage,
  headerSecrets,
  MARKER,
  MARKERS,
  measurable,
  median,
  mergeMetrics,
  metricsParts,
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
import { TEST_API_JWT_SECRET, TEST_AUTH_SECRET, TEST_GITHUB_ID } from "../e2e/test-env";

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
    expect(measurable(preview)).toEqual({ mode: "preview", url: BASE });
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
    expect(measurable({ ...hand, inputUrl: PRODUCTION, allowProduction: true })).toEqual({
      mode: "preview",
      url: PRODUCTION,
    });
  });

  it("refuses a preview event that carries the production URL", () => {
    expect(measurable({ ...preview, deploymentUrl: PRODUCTION })).toHaveProperty("problem");
  });

  it("takes a hand run's preview URL, and refuses anything that isn't an https URL", () => {
    expect(measurable(hand)).toEqual({ mode: "preview", url: BASE });
    expect(measurable({ ...hand, inputUrl: "http://example.com" })).toHaveProperty("problem");
    expect(measurable({ ...hand, inputUrl: "nope" })).toHaveProperty("problem");
    expect(measurable({ eventName: "push" })).toHaveProperty("skip");
  });

  it("reads its inputs from the GitHub event payload", () => {
    const deployment = {
      deployment: { sha: "abc", environment: "Preview" },
      deployment_status: { state: "success", environment: "Preview", environment_url: `${BASE}/`, target_url: "https://vercel.com/x" },
    };
    expect(measurable(eventInputs("deployment_status", deployment, PRODUCTION))).toEqual({ mode: "preview", url: BASE });
    const failedDeploy = { ...deployment, deployment_status: { ...deployment.deployment_status, state: "failure" } };
    expect(measurable(eventInputs("deployment_status", failedDeploy, PRODUCTION))).toHaveProperty("skip");

    const dispatch = (allow: unknown) => ({ inputs: { url: PRODUCTION, allow_production: allow } });
    const prod = { mode: "preview", url: PRODUCTION };
    expect(measurable(eventInputs("workflow_dispatch", dispatch("false"), PRODUCTION))).toHaveProperty("problem");
    expect(measurable(eventInputs("workflow_dispatch", dispatch(true), PRODUCTION))).toEqual(prod);
    expect(measurable(eventInputs("workflow_dispatch", dispatch("true"), PRODUCTION))).toEqual(prod);
  });
});

describe("TASK-027 AC-1: a pull request is measured on the fixture build (D-125)", () => {
  it("measures a pull request on the build served inside the job, never a Vercel URL", () => {
    expect(FIXTURE_URL).toBe("http://127.0.0.1:3100");
    expect(measurable({ eventName: "pull_request", productionUrl: PRODUCTION })).toEqual({
      mode: "fixture",
      url: FIXTURE_URL,
    });
    expect(measurable(eventInputs("pull_request", { pull_request: { number: 7 } }, PRODUCTION))).toEqual({
      mode: "fixture",
      url: FIXTURE_URL,
    });
  });

  it("builds the fixture on a hand run given no URL, and measures a preview when given one", () => {
    for (const url of [undefined, ""]) {
      expect(measurable(eventInputs("workflow_dispatch", { inputs: { url } }, PRODUCTION))).toEqual({
        mode: "fixture",
        url: FIXTURE_URL,
      });
    }
    expect(measurable(eventInputs("workflow_dispatch", { inputs: { url: BASE } }, PRODUCTION))).toEqual({
      mode: "preview",
      url: BASE,
    });
  });

  it("gates a fixture run on every problem D-101 lists", () => {
    const heavy = runs(page({ docBytes: 99_000, cls: 0.2 }));
    const { problems, noticed } = checkRun({ mode: "fixture", routes: { teams: heavy }, budget: BUDGET });
    expect(problems).toEqual([
      "teams: document + RSC 99,000 bytes is over the budget of 15,000 bytes",
      "teams: CLS 0.200 is 0.1 or more",
    ]);
    expect(noticed).toEqual([]);
    expect(checkRun({ mode: "fixture", routes: {}, budget: BUDGET, expected: ["teams"] }).problems).toEqual([
      "teams: never finished measuring (its job wrote no metrics)",
    ]);
  });

  it("says how to fix a session that didn't take without naming one run's secret", () => {
    const [problem] = gate(lhr({ path: "/login" }));
    expect(problem).toContain("the session didn't take");
    expect(problem).toContain("web/e2e/test-env.ts");
    expect(problem).toContain("PREVIEW_AUTH_SECRET");
  });
});

describe("TASK-027 AC-3: a preview run reports, never gates", () => {
  const heavy = () => runs(page({ docBytes: 99_000, cls: 0.2 }));

  it("finds no gate problem in a preview over budget with a CLS of 0.2", () => {
    const { problems, noticed } = checkRun({ mode: "preview", routes: { teams: heavy() }, budget: BUDGET });
    expect(problems).toEqual([]);
    // Compared with no budget (budgets are the fixture's), but a shift or an API call is still worth a look.
    expect(noticed).toEqual(["teams: CLS 0.200 is 0.1 or more"]);
  });

  it("notices a forbidden request or a route that didn't measure, and still gates nothing", () => {
    const api = runs(lhr({ requests: [{ url: "/api/py/teams", type: "Fetch", size: 10 }] }));
    const { problems, noticed } = checkRun({
      mode: "preview",
      routes: { teams: api },
      budget: BUDGET,
      expected: ["login", "teams"],
    });
    expect(problems).toEqual([]);
    expect(noticed).toHaveLength(2);
    expect(noticed[0]).toMatch(/^login: never finished measuring/);
    expect(noticed[1]).toMatch(/^teams: requested \/api\/py\/teams/);
  });

  it("labels the preview comment reported only, with no budgets and no failure", () => {
    const md = renderComment({
      mode: "preview",
      current: { url: BASE, sha: "abcdef1234", lighthouse: "13.5.0", routes: { teams: heavy() } },
      baseline: null,
      budget: BUDGET,
      problems: [],
      noticed: ["teams: CLS 0.200 is 0.1 or more"],
    });
    expect(md.startsWith(`${MARKERS.preview}\n`)).toBe(true);
    expect(md).toContain("reported only, never gated");
    expect(md).toContain("- teams: CLS 0.200 is 0.1 or more");
    expect(md).toContain("| `/teams` | 96.7 KB | 136.7 KB | 15 | 0.200 | 95 |");
    expect(md).not.toMatch(/budget|Fails the job|within budget/i);
  });
});

describe("TASK-027 AC-4: one comment per kind of run, and a baseline of the same kind", () => {
  it("gives the fixture run and the preview run their own markers", () => {
    expect(MARKERS.fixture).toBe(MARKER);
    expect(MARKERS.preview).toMatch(/^<!-- .+ -->$/);
    expect(MARKERS.preview.startsWith(MARKERS.fixture)).toBe(false);
    const comments = [
      { id: 1, body: `${MARKERS.preview}\n### Lighthouse` },
      { id: 2, body: `${MARKERS.fixture}\n### Lighthouse` },
    ];
    expect(findComment(comments)?.id).toBe(2);
    expect(findComment(comments, MARKERS.fixture)?.id).toBe(2);
    expect(findComment(comments, MARKERS.preview)?.id).toBe(1);
  });

  it("compares a fixture run with pull_request runs and a preview with deployment runs", () => {
    expect(BASELINE_EVENT).toEqual({ fixture: "pull_request", preview: "deployment_status" });
    const list = [
      { id: 1, event: "pull_request", status: "completed", conclusion: "success", created_at: "2026-10-05T10:00:00Z" },
      { id: 2, event: "deployment_status", status: "completed", conclusion: "success", created_at: "2026-10-05T12:00:00Z" },
      { id: 3, event: "workflow_dispatch", status: "completed", conclusion: "success", created_at: "2026-10-05T13:00:00Z" },
    ];
    expect(baselineRun(list, "pull_request")?.id).toBe(1);
    expect(baselineRun(list, "deployment_status")?.id).toBe(2);
    expect(baselineRun(list.slice(1), "pull_request")).toBeNull();
  });

  it("walks back through merged PRs, newest first, so a docs-only PR with no run is passed over", () => {
    const pulls = Array.from({ length: 14 }, (_, i) => ({
      number: 40 + i,
      merged_at: i === 13 ? null : `2026-10-${String(i + 1).padStart(2, "0")}T10:00:00Z`,
    }));
    const order = baselineCandidates(pulls, [52]).map((p) => p.number);
    expect(order).toEqual([51, 50, 49, 48, 47, 46, 45, 44, 43, 42]);
    expect(baselineCandidates(pulls, [], 3).map((p) => p.number)).toEqual([52, 51, 50]);
    expect(baselinePr(pulls, [52])?.number).toBe(51);
  });

  it("merges the one fixture artifact, which download-artifact puts straight in the folder", () => {
    // Run 40015971648: one artifact matched, so parts/metrics.json was the part, and merge skipped it.
    expect(metricsParts(["/tmp/parts/metrics.json"])).toEqual(["/tmp/parts/metrics.json"]);
    expect(
      metricsParts([
        "/tmp/parts/lighthouse-metrics-login/metrics.json",
        "C:\\tmp\\parts\\lighthouse-metrics-teams\\metrics.json",
        "/tmp/parts/lighthouse-metrics-teams/notes.txt",
        "/tmp/parts/old-metrics.json",
      ]),
    ).toEqual(["/tmp/parts/lighthouse-metrics-login/metrics.json", "C:\\tmp\\parts\\lighthouse-metrics-teams\\metrics.json"]);
  });

  it("names the kind of run the timings are compared with", () => {
    const current = { url: FIXTURE_URL, sha: "abcdef1234", lighthouse: "13.5.0", routes: { teams: runs(page()) } };
    const baseline = { pr: 47, at: "2026-10-05T12:00:00Z", routes: {} };
    expect(renderComment({ current, baseline, budget: BUDGET, problems: [] })).toContain(
      "PR #47's fixture run, 2026-10-05",
    );
    expect(renderComment({ mode: "preview", current, baseline, budget: BUDGET, problems: [] })).toContain(
      "PR #47's preview, 2026-10-05",
    );
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
    expect(md).toContain("PR #47's fixture run, 2026-10-05");
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

// TASK-008: the workflow itself, and the budgets it set from its first preview run.

/** A repo file's text, or "" when it is missing, so each case below fails on its own. */
const repoText = (path: string) => {
  try {
    return readFileSync(join(ROOT, path), "utf8");
  } catch {
    return "";
  }
};

describe("TASK-008 AC-1: .github/workflows/lighthouse.yml has 02's shape", () => {
  const WORKFLOW = repoText(".github/workflows/lighthouse.yml");
  // Comments say what the workflow does in words that would satisfy these checks; read only code.
  const code = WORKFLOW.split("\n")
    .map((l) => l.replace(/(^|\s)#.*$/, ""))
    .join("\n");
  const jobsAt = code.indexOf("\njobs:\n");
  // Each job's text, from its `  name:` line to the next job's.
  const jobs = Object.fromEntries(
    [...code.slice(jobsAt).matchAll(/^ {2}([a-z]+):\n([\s\S]*?)(?=^ {2}[a-z]+:\n|(?![\s\S]))/gm)].map((m) => [m[1], m[2]]),
  );
  const steps = (job: string) => (jobs[job] ?? "").split(/^ {6}- /m).slice(1);

  it("runs on a pull request, a deployment's status and by hand, with no permissions at the top", () => {
    expect(code).toMatch(/^on:\n {2}pull_request:\n {4}paths-ignore:\n(?: {6}- .+\n)+ {2}deployment_status:\n {2}workflow_dispatch:\n/m);
    expect(code).toMatch(/^ {6}url:\n[\s\S]*?required: false[\s\S]*?^ {6}allow_production:\n[\s\S]*?type: boolean/m);
    expect(code.slice(0, jobsAt)).toMatch(/^permissions: \{\}$/m);
  });

  it("plans, measures a preview one route per job or the fixture in one job, then reports", () => {
    expect(Object.keys(jobs)).toEqual(["plan", "measure", "fixture", "report"]);
    expect(jobs.measure).toMatch(/^ {4}needs: plan$/m);
    expect(jobs.measure).toMatch(/^ {4}if: needs\.plan\.outputs\.mode == 'preview'$/m);
    expect(jobs.fixture).toMatch(/^ {4}needs: plan$/m);
    expect(jobs.fixture).toMatch(/^ {4}if: needs\.plan\.outputs\.mode == 'fixture'$/m);
    expect(jobs.report).toMatch(/^ {4}needs: \[plan, measure, fixture\]$/m);
    expect(jobs.measure).toMatch(/^ {6}fail-fast: false$/m);
    expect(jobs.measure).toMatch(/^ {8}route: \$\{\{ fromJSON\(needs\.plan\.outputs\.routes\) \}\}$/m);
    // plan's group is `pr-<n>`, so the measuring jobs' group is lighthouse-pr-<n>-<route>.
    expect(jobs.measure).toMatch(
      /concurrency:\n {6}group: lighthouse-\$\{\{ needs\.plan\.outputs\.group \}\}-\$\{\{ matrix\.route \}\}\n {6}cancel-in-progress: true/,
    );
    // The report runs when a route's job failed, so that route is reported; not when cancelled.
    expect(jobs.report).toMatch(/if: \$\{\{ !cancelled\(\)/);
    // A preview's report and the fixture's never cancel each other.
    expect(jobs.report).toMatch(/group: lighthouse-\$\{\{ needs\.plan\.outputs\.group \}\}-\$\{\{ needs\.plan\.outputs\.mode \}\}-report/);
  });

  it("gives only the report job pull-requests: write, and no job anything else to write", () => {
    expect(jobs.report).toMatch(/^ {6}pull-requests: write$/m);
    for (const job of ["plan", "measure", "fixture"]) expect(jobs[job]).not.toMatch(/: write/);
    expect(jobs.report.match(/: write/g)).toHaveLength(1);
  });

  it("hands secrets to steps only as env: lines", () => {
    const lines = code.split("\n").filter((l) => l.includes("secrets."));
    expect(lines.length).toBeGreaterThan(0);
    for (const line of lines) expect(line).toMatch(/^\s+[A-Z0-9_]+: \$\{\{ secrets\.[A-Z0-9_]+ \}\}$/);
    expect(new Set(lines.map((l) => l.trim()))).toEqual(
      new Set([
        "AUTH_SECRET: ${{ secrets.PREVIEW_AUTH_SECRET }}",
        "VERCEL_AUTOMATION_BYPASS_SECRET: ${{ secrets.VERCEL_AUTOMATION_BYPASS_SECRET }}",
      ]),
    );
    expect(code).toMatch(/^\s+AUTH_ALLOWED_GITHUB_ID: \$\{\{ vars\.AUTH_ALLOWED_GITHUB_ID \}\}$/m);
  });

  it("signs in with the bypass, measures, guards, then forgets the session even on failure", () => {
    const measure = steps("measure");
    const at = (text: string) => measure.findIndex((s) => s.includes(text));
    const order = ["mint-session.mjs", "measure.mjs", "report.mjs guard", 'rm -rf "$HEADERS_DIR"', "upload-artifact"];
    expect(order.map(at)).toEqual([...order.map(at)].sort((a, b) => a - b));
    expect(order.map(at)).not.toContain(-1);
    // mint-session writes the bypass into both header files; measure.mjs hands Lighthouse one of them.
    expect(measure[at("mint-session.mjs")]).toContain("VERCEL_AUTOMATION_BYPASS_SECRET:");
    expect(measure[at('rm -rf "$HEADERS_DIR"')]).toMatch(/^ {8}if: always\(\)$/m);
    expect(code).toMatch(/HEADERS_DIR=\$RUNNER_TEMP\/lh-session/);
    expect(code).toMatch(/OUT_DIR=\$RUNNER_TEMP\/lighthouse\b/);
  });

  it("keeps its artifacts 14 days and never sends a report to LHCI's public storage", () => {
    const uploads = code.split(/^ {6}- /m).filter((s) => s.includes("upload-artifact"));
    expect(uploads).toHaveLength(5);
    for (const u of uploads) expect(u).toMatch(/retention-days: 14\n/);
    expect(WORKFLOW).not.toMatch(/lhci|temporary-public-storage/i);
  });

  it("installs Lighthouse only from scripts/perf, caching on its lockfile", () => {
    for (const job of ["measure", "fixture"]) expect(jobs[job]).toContain("npm ci --prefix scripts/perf");
    expect(jobs.measure).toMatch(/cache-dependency-path: scripts\/perf\/package-lock\.json/);
    expect(jobs.measure).not.toMatch(/pnpm/);
    expect(code).not.toMatch(/pnpm (add|dlx)|npx\b/);
  });
});

describe("TASK-027 AC-1: the fixture job serves the seeded test DB the way e2e does", () => {
  const code = repoText(".github/workflows/lighthouse.yml")
    .split("\n")
    .map((l) => l.replace(/(^|\s)#.*$/, ""))
    .join("\n");
  const fixture = code.match(/^ {2}fixture:\n([\s\S]*?)(?=^ {2}[a-z]+:\n|(?![\s\S]))/m)?.[1] ?? "";
  const steps = fixture.split(/^ {6}- /m).slice(1);

  it("migrates and seeds the test DB, builds once, serves it, signs in, measures, guards, forgets, uploads", () => {
    const at = (text: string) => steps.findIndex((s) => s.includes(text));
    const order = [
      "./.github/actions/start-postgres",
      "pnpm db:migrate:test",
      "pnpm db:seed",
      "pnpm build",
      "uvicorn api.main:app",
      "pnpm --dir web start --port 3100",
      "mint-session.mjs",
      "measure.mjs",
      "report.mjs guard",
      'rm -rf "$HEADERS_DIR"',
      "upload-artifact",
    ];
    expect(order.map(at)).not.toContain(-1);
    expect(order.map(at)).toEqual([...order.map(at)].sort((a, b) => a - b));
    // One build for every route: no matrix, and no build anywhere else in the workflow.
    expect(code.match(/pnpm build/g)).toHaveLength(1);
    expect(fixture).not.toMatch(/matrix|PERF_ROUTES/);
    expect(steps[at('rm -rf "$HEADERS_DIR"')]).toMatch(/^ {8}if: always\(\)$/m);
  });

  it("uses no repository secret, only e2e's test values, and the local URL", () => {
    expect(fixture).not.toMatch(/secrets\.|vars\.|VERCEL/);
    expect(fixture).toContain(`AUTH_SECRET: ${TEST_AUTH_SECRET}\n`);
    expect(fixture).toContain(`AUTH_ALLOWED_GITHUB_ID: "${TEST_GITHUB_ID}"\n`);
    expect(fixture).toContain(`API_JWT_SECRET: ${TEST_API_JWT_SECRET}\n`);
    expect(fixture).toContain("TEST_DATABASE_URL: postgresql://ci:ci@localhost:5432/cfb_test\n");
    expect(fixture).toMatch(/APP_ENV=test\b/);
    expect(fixture).toContain("TARGET_URL: ${{ needs.plan.outputs.url }}");
    expect(fixture).toContain("PERF_MODE: fixture");
  });

  it("skips the same docs-only changes CI's scope step skips", () => {
    const block = code.match(/^ {2}pull_request:\n {4}paths-ignore:\n((?: {6}- .+\n)+)/m)?.[1] ?? "";
    const ignored = block
      .trim()
      .split("\n")
      .map((l) => l.trim().replace(/^- /, "").replace(/^"(.*)"$/, "$1"));
    expect(ignored).toEqual([...SKIP_PREFIXES.map((p) => `${p}**`), "*.md"]);
  });
});

describe("TASK-008 AC-3: budgets from a run, by 02's rule", () => {
  const load = (o: Parameters<typeof page>[0] = {}) => summariseLhr(page(o));
  const metrics = (loads: ReturnType<typeof load>[], mode: "fixture" | "preview" | undefined = "fixture") => ({
    mode,
    url: BASE,
    sha: "abc1234",
    lighthouse: "13.5.0",
    chrome: "141.0.7390.54",
    measuredAt: "2026-10-13T12:00:00Z",
    runs: loads.length,
    routes: { teams: { path: "/teams", loads } },
  });

  it("is the median + 20%, bytes rounded up to the next 1,000, requests up to a whole one", () => {
    const steady = load({ docBytes: 10_000, jsBytes: 100_001, requests: 16, a11y: 95 });
    const { routes } = budgetFrom(metrics([steady, steady, steady]));
    // 12,000 exactly stays 12,000; 120,001.2 → 121,000; 19.2 → 20.
    expect(routes).toEqual({ teams: { docBytes: 12_000, jsBytes: 121_000, requests: 20, a11y: 95 } });
  });

  it("takes the accessibility score as measured, without headroom", () => {
    const loads = [load({ a11y: 92 }), load({ a11y: 100 }), load({ a11y: 96 })];
    expect(budgetFrom(metrics(loads)).routes.teams.a11y).toBe(96);
  });

  it("uses the median run, so one heavy run doesn't raise the budget", () => {
    const loads = [load({ jsBytes: 100_000 }), load({ jsBytes: 100_500 }), load({ jsBytes: 400_000 })];
    expect(budgetFrom(metrics(loads)).routes.teams.jsBytes).toBe(121_000);
  });

  it("records the medians and versions the budgets came from", () => {
    const steady = load({ docBytes: 10_000, jsBytes: 100_000, requests: 15, a11y: 95 });
    const { measured } = budgetFrom(metrics([steady, steady, steady]));
    expect(measured).toMatchObject({
      url: BASE,
      sha: "abc1234",
      lighthouse: "13.5.0",
      chrome: "141.0.7390.54",
      at: "2026-10-13T12:00:00Z",
      medians: { teams: { docBytes: 10_000, jsBytes: 100_000, requests: 15, a11y: 95 } },
    });
  });

  it("flags bytes that move 1% or more between runs, and passes steadier ones", () => {
    const loads = [load({ jsBytes: 100_000 }), load({ jsBytes: 100_500 }), load({ jsBytes: 101_100 })];
    expect(budgetFrom(metrics(loads)).unsteady).toEqual(["teams: JS moves 1.1% between runs (100,000–101,100 bytes)"]);
    const close = [load({ jsBytes: 100_000 }), load({ jsBytes: 100_500 }), load({ jsBytes: 100_900 })];
    expect(budgetFrom(metrics(close)).unsteady).toEqual([]);
  });

  it("TASK-027: sets budgets only from a fixture run, never a preview's (D-125)", () => {
    const steady = load();
    expect(() => budgetFrom(metrics([steady, steady, steady], "preview"))).toThrow(/fixture run/);
    expect(() => budgetFrom({ ...metrics([steady, steady, steady]), mode: undefined })).toThrow(/fixture run/);
  });

  it("refuses a route that didn't measure, or that ended somewhere else", () => {
    expect(() => budgetFrom(metrics([]))).toThrow(/teams: no run finished/);
    const atLogin = summariseLhr(lhr({ path: "/login" }));
    expect(() => budgetFrom(metrics([atLogin, atLogin, atLogin]))).toThrow(/teams: ended on \/login/);
  });

  it("reads the Chrome version from the user agent Lighthouse ran", () => {
    const ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/141.0.7390.54 Safari/537.36";
    expect(chromeVersion({ environment: { hostUserAgent: ua } })).toBe("141.0.7390.54");
    expect(chromeVersion({})).toBeNull();
  });
});

describe("TASK-008 AC-4: budget.json, the route list and the table in docs/02 agree", () => {
  type Budget = { measured: { lighthouse: string; chrome: string } | null; routes: Record<string, Record<string, number>> };
  const BUDGET_JSON: Budget = JSON.parse(repoText("scripts/perf/budget.json") || '{ "measured": null, "routes": {} }');
  const DOC = repoText("docs/02-architecture.md");
  const COLUMNS = ["docBytes", "jsBytes", "requests", "a11y"] as const;

  // The rows between the perf-budget markers, as budget.json's `routes`; "–" is no budget yet.
  function parseTable(doc: string): Record<string, Record<string, number>> {
    const block = doc.match(/<!-- perf-budget:start -->\n([\s\S]*?)<!-- perf-budget:end -->/)?.[1];
    if (!block) throw new Error("no perf-budget markers");
    const rows = block.trim().split("\n").slice(2);
    return Object.fromEntries(
      rows.map((row) => {
        const [route, ...cells] = row.split("|").slice(1, -1).map((c) => c.trim());
        const id = route.match(/^`([^`]+)`/)?.[1] ?? route;
        const values = cells.map((c) => (c === "–" ? undefined : Number(c.replace(/,/g, ""))));
        return [id, Object.fromEntries(COLUMNS.flatMap((k, i) => (values[i] === undefined ? [] : [[k, values[i]]])))];
      }),
    );
  }

  const keysMatchRoutes = (budget: Budget) =>
    expect(Object.keys(budget.routes).sort()).toEqual(ROUTES.map((r) => r.id).sort());

  it("has one budget per route id, no more and no fewer", () => {
    keysMatchRoutes(BUDGET_JSON);
    expect(() => keysMatchRoutes({ ...BUDGET_JSON, routes: { ...BUDGET_JSON.routes, rankings: {} } })).toThrow();
    const noTeams = Object.fromEntries(Object.entries(BUDGET_JSON.routes).filter(([id]) => id !== "teams"));
    expect(() => keysMatchRoutes({ ...BUDGET_JSON, routes: noTeams })).toThrow();
  });

  it("matches the perf-budget table in docs/02-architecture.md", () => {
    expect(parseTable(DOC)).toEqual(BUDGET_JSON.routes);
  });

  it("catches a table that has drifted from budget.json", () => {
    const table = budgetTable({ login: { docBytes: 13_000, jsBytes: 121_000, requests: 18, a11y: 100 }, teams: {} });
    const doc = `<!-- perf-budget:start -->\n${table}\n<!-- perf-budget:end -->`;
    expect(parseTable(doc)).toEqual({ login: { docBytes: 13_000, jsBytes: 121_000, requests: 18, a11y: 100 }, teams: {} });
    expect(parseTable(doc.replace("121,000", "122,000"))).not.toEqual(parseTable(doc));
  });

  it("names the Lighthouse and Chrome versions the budgets were measured with beside the table", () => {
    const after = DOC.slice(DOC.indexOf("<!-- perf-budget:end -->")).split(/\n## /)[0];
    if (!BUDGET_JSON.measured) {
      expect(Object.values(BUDGET_JSON.routes).every((b) => Object.keys(b).length === 0)).toBe(true);
      return;
    }
    expect(after).toContain(`Lighthouse ${BUDGET_JSON.measured.lighthouse}`);
    expect(after).toContain(`Chrome ${BUDGET_JSON.measured.chrome}`);
  });
});
