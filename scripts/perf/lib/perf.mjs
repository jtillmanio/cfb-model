// The lighthouse workflow's decisions as pure functions (02 › Performance checks (Lighthouse),
// D-101, D-125): what a Lighthouse result says about a route, what fails the job, what the PR
// comment shows, what each event measures, which earlier run it is compared with, and how the job
// signs in and keeps secrets out of its reports. scripts/perf/*.mjs feed them the real inputs;
// web/lib/perf.test.ts feeds them fixtures. No imports, so report.mjs runs on bare Node.
//
// Two kinds of run (D-125). A `fixture` run measures a build served inside the job on the seeded
// test DB: the data never changes, so its numbers are gated. A `preview` run measures a Vercel
// preview on whatever data that database holds this week: reported, never gated.

/**
 * @typedef {"fixture" | "preview"} Mode
 * @typedef {{
 *   landedOn: string | null,
 *   ttfb: number | null, fcp: number | null, lcp: number | null, tbt: number | null,
 *   cls: number | null, a11y: number | null,
 *   docBytes: number, jsBytes: number, requests: number,
 *   forbidden: string[],
 * }} LoadSummary
 * @typedef {{ error: string }} LoadError
 * @typedef {{ path: string, loads: (LoadSummary | LoadError)[] }} MeasuredRoute
 * @typedef {{
 *   path: string, runs: number, errors: string[], landedOn: (string | null)[],
 *   first: LoadSummary | null, median: Record<string, number | null>, forbidden: string[],
 * }} RouteResult
 * @typedef {{ docBytes?: number, jsBytes?: number, requests?: number, a11y?: number }} RouteBudget
 * @typedef {{
 *   mode?: Mode, url: string, sha?: string | null, lighthouse?: string, chrome?: string, measuredAt: string,
 *   runs?: number, routes: Record<string, MeasuredRoute>,
 * }} Metrics
 * @typedef {{ name: string, value: string }} SessionCookie
 */

/** CLS at or over this fails the job. */
export const CLS_LIMIT = 0.1;

/** Where the fixture job serves the app (`next start`; the API sits behind it, as in e2e). */
export const FIXTURE_URL = "http://127.0.0.1:3100";

/** The fixture run finds its own PR comment by this and edits it in place. */
export const MARKER = "<!-- cfb-model-lighthouse -->";

/** Each kind of run keeps its own comment, so two runs finishing together never edit one. */
export const MARKERS = /** @type {const} */ ({ fixture: MARKER, preview: "<!-- cfb-model-lighthouse-preview -->" });

/** The event whose runs a kind of run is compared with: a hand run is never anyone's baseline. */
export const BASELINE_EVENT = /** @type {const} */ ({ fixture: "pull_request", preview: "deployment_status" });

/** What budget.json holds per route besides `a11y`, and how the comment names it. */
export const BUDGETED = /** @type {const} */ ([
  { key: "docBytes", label: "document + RSC", unit: "bytes" },
  { key: "jsBytes", label: "JS", unit: "bytes" },
  { key: "requests", label: "requests", unit: "count" },
]);

/** Reported against the baseline, never gated: a preview is cold or warm by chance, and a shared runner is no steadier. */
export const TIMINGS = /** @type {const} */ ([
  { key: "ttfb", label: "TTFB" },
  { key: "fcp", label: "FCP" },
  { key: "lcp", label: "LCP" },
  { key: "tbt", label: "TBT" },
]);

/** Shortest string treated as a secret, so an empty or one-letter value can't redact everything. */
const MIN_SECRET = 8;

/**
 * Vercel's preview extras (the toolbar and its feedback script). Previews inject them and
 * production never serves them, so they stay out of the counts.
 * @param {string} url
 */
export function isVercelExtra(url) {
  return /^https:\/\/vercel\.live\//.test(url) || /^https:\/\/[^/]+\/_next-live\//.test(url);
}

/**
 * The path of a request the browser must never make: anything under /api/py, the Python API
 * (hard rule 5). Null for any other URL.
 * @param {string} url
 * @returns {string | null}
 */
export function forbiddenPath(url) {
  try {
    const { pathname } = new URL(url);
    return pathname === "/api/py" || pathname.startsWith("/api/py/") ? pathname : null;
  } catch {
    return null;
  }
}

/** @param {unknown} v */
const round = (v) => (typeof v === "number" && Number.isFinite(v) ? Math.round(v) : null);

/**
 * The numbers one Lighthouse result gives for its route; nothing of the page itself.
 * @param {any} lhr
 * @returns {LoadSummary}
 */
export function summariseLhr(lhr) {
  /** @type {{ url: string, resourceType?: string, transferSize?: number, mimeType?: string }[]} */
  const items = (lhr.audits?.["network-requests"]?.details?.items ?? []).filter(
    (/** @type {{ url: string }} */ q) => !isVercelExtra(q.url),
  );
  const metrics = lhr.audits?.metrics?.details?.items?.[0] ?? {};
  /** @param {string} key */
  const audit = (key) => lhr.audits?.[key]?.numericValue;
  /** @param {(q: (typeof items)[number]) => boolean} keep */
  const bytes = (keep) => items.filter(keep).reduce((sum, q) => sum + (q.transferSize ?? 0), 0);
  const a11y = lhr.categories?.accessibility?.score;
  let landedOn = null;
  try {
    landedOn = new URL(lhr.finalDisplayedUrl).pathname;
  } catch {
    /* no final URL: Lighthouse never loaded the page */
  }
  const cls = audit("cumulative-layout-shift");
  return {
    landedOn,
    ttfb: round(metrics.timeToFirstByte ?? metrics.observedTimeToFirstByte),
    fcp: round(audit("first-contentful-paint")),
    lcp: round(audit("largest-contentful-paint")),
    tbt: round(audit("total-blocking-time")),
    cls: typeof cls === "number" ? cls : null,
    a11y: typeof a11y === "number" ? Math.round(a11y * 100) : null,
    // The document carries the first RSC payload inline; prefetches fetch more.
    docBytes: bytes((q) => q.resourceType === "Document" || /text\/x-component/.test(q.mimeType ?? "")),
    jsBytes: bytes((q) => q.resourceType === "Script"),
    requests: items.length,
    forbidden: /** @type {string[]} */ (items.map((q) => forbiddenPath(q.url)).filter(Boolean)),
  };
}

/**
 * Median of the numbers given, ignoring missing ones; null when there are none.
 * @param {(number | null | undefined)[]} values
 * @returns {number | null}
 */
export function median(values) {
  const v = /** @type {number[]} */ (values.filter((x) => typeof x === "number" && Number.isFinite(x))).sort(
    (a, b) => a - b,
  );
  if (!v.length) return null;
  const mid = Math.floor(v.length / 2);
  return v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2;
}

/** @param {LoadSummary | LoadError} load @returns {load is LoadError} */
const failed = (load) => "error" in load;

/**
 * One route's runs, reduced: the first hit (the preview may be cold for it), the median of every
 * run that finished, and every forbidden request any run made.
 * @param {MeasuredRoute} measured
 * @returns {RouteResult}
 */
export function aggregateRoute(measured) {
  const loads = /** @type {LoadSummary[]} */ (measured.loads.filter((l) => !failed(l)));
  const keys = [...TIMINGS.map((t) => t.key), "cls", "a11y", ...BUDGETED.map((b) => b.key)];
  const med = Object.fromEntries(
    keys.map((k) => [k, median(loads.map((l) => /** @type {number | null} */ (l[/** @type {keyof LoadSummary} */ (k)])))]),
  );
  // The first hit is the first run, or nothing when that run failed: the second run is warm and
  // must not be reported as the first.
  const first = measured.loads[0] && !failed(measured.loads[0]) ? measured.loads[0] : null;
  return {
    path: measured.path,
    runs: loads.length,
    errors: measured.loads.filter(failed).map((l) => l.error),
    landedOn: [...new Set(loads.map((l) => l.landedOn))],
    first,
    median: med,
    forbidden: [...new Set(loads.flatMap((l) => l.forbidden))],
  };
}

/** @param {number} v @param {"bytes" | "count"} unit */
const amount = (v, unit) => (unit === "bytes" ? `${v.toLocaleString("en-US")} bytes` : String(Math.round(v)));

/**
 * Everything that fails the job, each naming its route and the number or URL: only what holds
 * still between runs. Timings are never checked.
 * @param {Record<string, RouteResult>} routes
 * @param {Record<string, RouteBudget>} budget budget.json's `routes`
 * @param {string[]} [expected] every route id the job set out to measure
 * @returns {string[]}
 */
export function gateProblems(routes, budget, expected = []) {
  // Each route is measured by its own job; one that died wrote no metrics.
  const problems = expected
    .filter((id) => !routes[id])
    .map((id) => `${id}: never finished measuring (its job wrote no metrics)`);
  for (const [id, r] of Object.entries(routes)) {
    for (const path of r.forbidden) {
      problems.push(
        `${id}: requested ${path} during a page load or prefetch. The browser never calls the API ` +
          "(hard rule 5): link to it with a plain `<a>`, never `<Link>`, and fetch it from server code",
      );
    }
    if (!r.runs) {
      problems.push(`${id}: never finished measuring (${r.errors[0] ?? "no Lighthouse run finished"})`);
      continue;
    }
    const wrong = r.landedOn.filter((p) => p !== r.path);
    if (wrong.length) {
      problems.push(
        `${id}: loaded ${r.path} and ended on ${wrong.map((p) => p ?? "(nowhere)").join(", ")}` +
          (wrong.includes("/login")
            ? ": the session didn't take. The minted session's AUTH_SECRET and AUTH_ALLOWED_GITHUB_ID must " +
              "match the server's: web/e2e/test-env.ts's values for the fixture build, PREVIEW_AUTH_SECRET " +
              "and the allowlisted GitHub ID for a preview"
            : ""),
      );
      continue;
    }
    const b = budget[id] ?? {};
    for (const { key, label, unit } of BUDGETED) {
      const v = r.median[key];
      const limit = b[key];
      if (typeof limit === "number" && v != null && v > limit) {
        problems.push(`${id}: ${label} ${amount(v, unit)} is over the budget of ${amount(limit, unit)}`);
      }
    }
    const cls = r.median.cls;
    if (cls != null && cls >= CLS_LIMIT) problems.push(`${id}: CLS ${cls.toFixed(3)} is ${CLS_LIMIT} or more`);
    const a11y = r.median.a11y;
    if (typeof b.a11y === "number" && a11y != null && a11y < b.a11y) {
      problems.push(`${id}: accessibility ${a11y} is below the recorded ${b.a11y}`);
    }
  }
  return problems;
}

/**
 * What a run fails on, and what it only points out. A fixture run is gated by gateProblems. A
 * preview run fails on nothing: budgets are the fixture's, so its bytes are compared with none,
 * and anything else gateProblems would say (a forbidden request, CLS, a route that didn't measure
 * or landed elsewhere) is listed as noticed.
 * @param {{
 *   mode: Mode, routes: Record<string, RouteResult>, budget: Record<string, RouteBudget>, expected?: string[],
 * }} args
 * @returns {{ problems: string[], noticed: string[] }}
 */
export function checkRun({ mode, routes, budget, expected = [] }) {
  if (mode === "fixture") return { problems: gateProblems(routes, budget, expected), noticed: [] };
  return { problems: [], noticed: gateProblems(routes, {}, expected) };
}

/**
 * Routes missing a number budget.json should hold for them.
 * @param {Record<string, RouteResult>} routes
 * @param {Record<string, RouteBudget>} budget
 */
export function unbudgeted(routes, budget) {
  const keys = [...BUDGETED.map((b) => b.key), "a11y"];
  return Object.keys(routes).filter((id) =>
    keys.some((k) => typeof budget[id]?.[/** @type {keyof RouteBudget} */ (k)] !== "number"),
  );
}

/** Budgets sit this far above the run they were set from (02 › Performance checks › Budgets). */
const HEADROOM_TENTHS = 12;

/** Bytes that move this much between one route's runs are too noisy to gate on. */
const STEADY_SPREAD = 0.01;

/**
 * The budgets a run sets, by 02's rule: the median + 20%, bytes rounded up to the next 1,000 and
 * requests to a whole one; accessibility is the measured score. Never invented: only a real
 * fixture run's metrics.json goes in (D-125); a preview's, or one that doesn't say, is refused.
 * Throws on a route that didn't measure or ended elsewhere, since its numbers aren't that page's.
 * @param {Metrics} metrics
 * @returns {{
 *   routes: Record<string, Required<RouteBudget>>,
 *   measured: { url: string, sha: string | null, lighthouse: string | null, chrome: string | null, at: string, runs: number | null, medians: Record<string, Required<RouteBudget>> },
 *   unsteady: string[],
 * }}
 */
export function budgetFrom(metrics) {
  if (metrics.mode !== "fixture") {
    throw new Error(
      `budgets come from a fixture run only (D-125); this metrics.json is ${metrics.mode ? `a ${metrics.mode} run's` : "from an older run that doesn't say"}`,
    );
  }
  /** @type {Record<string, Required<RouteBudget>>} */
  const routes = {};
  /** @type {Record<string, Required<RouteBudget>>} */
  const medians = {};
  /** @type {string[]} */
  const unsteady = [];
  for (const [id, measured] of Object.entries(metrics.routes)) {
    const r = aggregateRoute(measured);
    if (!r.runs) throw new Error(`${id}: no run finished (${r.errors[0] ?? "no loads"})`);
    const wrong = r.landedOn.filter((p) => p !== r.path);
    if (wrong.length) throw new Error(`${id}: ended on ${wrong.join(", ")}, not ${r.path}`);
    const m = /** @type {Required<RouteBudget>} */ (
      Object.fromEntries(["docBytes", "jsBytes", "requests", "a11y"].map((k) => [k, /** @type {number} */ (r.median[k])]))
    );
    medians[id] = m;
    // Integer arithmetic: 10,000 × 1.2 in floating point is 12,000.000000000002, which would round up a step.
    routes[id] = {
      docBytes: Math.ceil((m.docBytes * HEADROOM_TENTHS) / 10_000) * 1000,
      jsBytes: Math.ceil((m.jsBytes * HEADROOM_TENTHS) / 10_000) * 1000,
      requests: Math.ceil((m.requests * HEADROOM_TENTHS) / 10),
      a11y: Math.floor(m.a11y),
    };
    const loads = /** @type {LoadSummary[]} */ (measured.loads.filter((l) => !failed(l)));
    for (const { key, label, unit } of BUDGETED) {
      if (unit !== "bytes") continue;
      const v = loads.map((l) => l[key]);
      const lo = Math.min(...v);
      const hi = Math.max(...v);
      if (lo > 0 && (hi - lo) / lo >= STEADY_SPREAD) {
        unsteady.push(
          `${id}: ${label} moves ${(((hi - lo) / lo) * 100).toFixed(1)}% between runs ` +
            `(${lo.toLocaleString("en-US")}–${hi.toLocaleString("en-US")} bytes)`,
        );
      }
    }
  }
  return {
    routes,
    measured: {
      url: metrics.url,
      sha: metrics.sha ?? null,
      lighthouse: metrics.lighthouse ?? null,
      chrome: metrics.chrome ?? null,
      at: metrics.measuredAt,
      runs: metrics.runs ?? null,
      medians,
    },
    unsteady,
  };
}

/**
 * The perf-budget table in docs/02-architecture.md for budget.json's `routes`; "–" where a route
 * has no budget yet. web/lib/perf.test.ts checks the doc's table against budget.json.
 * @param {Record<string, RouteBudget>} routes
 */
export function budgetTable(routes) {
  /** @param {number | undefined} v */
  const cell = (v) => (typeof v === "number" ? v.toLocaleString("en-US") : "–");
  return [
    "| Route | Doc bytes | JS bytes | Requests | A11y |",
    "|---|---|---|---|---|",
    ...Object.entries(routes).map(
      ([id, b]) => `| \`${id}\` | ${cell(b.docBytes)} | ${cell(b.jsBytes)} | ${cell(b.requests)} | ${cell(b.a11y)} |`,
    ),
  ].join("\n");
}

/**
 * The Chrome version Lighthouse ran, from the user agent it records; null when it has none.
 * @param {any} lhr
 * @returns {string | null}
 */
export function chromeVersion(lhr) {
  const ua = lhr?.environment?.hostUserAgent;
  return (typeof ua === "string" && ua.match(/Chrome\/([\d.]+)/)?.[1]) || null;
}

/** @param {number | null | undefined} v @param {"bytes" | "count" | "ms"} unit */
function fmt(v, unit) {
  if (v == null) return "–";
  if (unit === "bytes") return `${(v / 1024).toFixed(1)} KB`;
  if (unit === "ms") return v >= 1000 ? `${(v / 1000).toFixed(2)} s` : `${Math.round(v)} ms`;
  return String(Math.round(v));
}

/**
 * A run's PR comment (also the job summary): the fixture run's, gated against the budgets, or the
 * preview's, reported only and compared with no budget. Each starts with its own marker.
 * @param {{
 *   mode?: Mode,
 *   current: { url: string, sha?: string | null, lighthouse?: string, runs?: number, routes: Record<string, RouteResult> },
 *   baseline: { pr: number | string, at: string, routes: Record<string, { median?: Record<string, number | null> }> } | null,
 *   budget: Record<string, RouteBudget>,
 *   problems: string[],
 *   noticed?: string[],
 *   missingBudget?: string[],
 * }} args
 */
export function renderComment({ mode = "fixture", current, baseline, budget, problems, noticed = [], missingBudget = [] }) {
  const gated = mode === "fixture";
  /** @param {number | null | undefined} v */
  const ms = (v) => fmt(v, "ms");
  /** @param {string} id @param {string} key */
  const vsBase = (id, key) => {
    if (!baseline) return "";
    const v = baseline.routes[id]?.median?.[key];
    return v == null ? " (no baseline)" : ` (base ${ms(v)})`;
  };
  const n = problems.length;
  const lines = [
    MARKERS[mode],
    gated
      ? `### Lighthouse (fixture build): ${n ? `❌ ${n} problem${n > 1 ? "s" : ""}` : "✅ within budget"}`
      : "### Lighthouse (preview): reported only, never gated",
    "",
    (gated ? "This PR built and served inside the job on the seeded fixture DB" : "This PR's Vercel preview, on its own data") +
      ` (D-125): \`${current.url}\` at \`${(current.sha ?? "").slice(0, 7)}\` · Lighthouse ${current.lighthouse ?? "?"} mobile, ` +
      `devtools throttling (Slow 4G, 4× CPU) · median of ${current.runs ?? 3} runs per route`,
    "",
  ];
  if (n) lines.push("**Fails the job:**", "", ...problems.map((p) => `- ${p}`), "");
  if (noticed.length) lines.push("**Noticed** (worth a look; the preview never fails):", "", ...noticed.map((p) => `- ${p}`), "");
  if (gated && missingBudget.length) {
    lines.push(
      `**No budget recorded** for ${missingBudget.map((id) => `\`${id}\``).join(", ")}: add it to ` +
        "scripts/perf/budget.json and the budget table in docs/02-architecture.md › Performance checks.",
      "",
    );
  }
  lines.push(
    gated ? "**Gated** (median / budget)" : "**Measured** (median)",
    "",
    "| Route | Document + RSC | JS | Requests | CLS | Accessibility |",
    "|---|---|---|---|---|---|",
  );
  for (const [id, r] of Object.entries(current.routes)) {
    const b = budget[id] ?? {};
    /** @param {"docBytes" | "jsBytes" | "requests" | "a11y"} key @param {"bytes" | "count"} unit */
    const cell = (key, unit) => (gated ? `${fmt(r.median[key], unit)} / ${fmt(b[key], unit)}` : fmt(r.median[key], unit));
    const cls = r.median.cls;
    lines.push(
      `| \`${r.path}\` | ${cell("docBytes", "bytes")} | ${cell("jsBytes", "bytes")} | ${cell("requests", "count")} | ` +
        `${cls == null ? "–" : cls.toFixed(3)} | ${cell("a11y", "count")} |`,
    );
  }
  lines.push(
    "",
    "**Reported, never gated** (first hit / median)",
    "",
    `| Route | ${TIMINGS.map((t) => t.label).join(" | ")} |`,
    `|---|${TIMINGS.map(() => "---|").join("")}`,
  );
  for (const [id, r] of Object.entries(current.routes)) {
    const cells = TIMINGS.map(({ key }) => `${ms(r.first?.[key])} / ${ms(r.median[key])}${vsBase(id, key)}`);
    lines.push(`| \`${r.path}\` | ${cells.join(" | ")} |`);
  }
  const unfinished = Object.entries(current.routes).flatMap(([id, r]) =>
    [...new Set(r.errors)].map((e) => `- ${id}: ${e}`),
  );
  if (unfinished.length) lines.push("", "**Runs that didn't finish** (left out of the medians):", "", ...unfinished);
  lines.push(
    "",
    baseline
      ? `Timings compared with the last merged PR's run: PR #${baseline.pr}'s ${gated ? "fixture run" : "preview"}, ${String(baseline.at).slice(0, 10)}.`
      : "No baseline: no run of the kind from a recent merged PR is still kept (artifacts last 14 days).",
    (gated
      ? "Bytes, requests, CLS and accessibility hold still on the fixture's data, so they are gated; timings on a shared runner don't, so they are reported only. "
      : "A preview's bytes follow its database's data and its timings a cold or warm start, so nothing here is gated; the fixture run is. ") +
      "Reports are this run's artifacts.",
  );
  return lines.join("\n");
}

/**
 * One metrics file from the per-route jobs' parts, routes in the route list's order.
 * @param {Metrics[]} parts
 * @param {string[]} order
 * @returns {Metrics}
 */
export function mergeMetrics(parts, order) {
  if (!parts.length) throw new Error("no route was measured: every measuring job failed before writing its metrics");
  /** @type {Record<string, MeasuredRoute>} */
  const routes = Object.assign({}, ...parts.map((p) => p.routes));
  const sorted = Object.fromEntries([
    ...order.filter((id) => routes[id]).map((id) => [id, routes[id]]),
    ...Object.entries(routes).filter(([id]) => !order.includes(id)),
  ]);
  const [first] = [...parts].sort((a, b) => (a.measuredAt < b.measuredAt ? -1 : 1));
  return { ...first, routes: sorted };
}

/**
 * The measuring jobs' metrics.json files among a download folder's files. download-artifact puts
 * each artifact in its own folder, except when the pattern matches only one (the fixture job's):
 * then its metrics.json lands straight in the folder, where merge writes its result. merge runs
 * once, so that file is always a part, never an earlier merge.
 * @param {string[]} files
 * @returns {string[]}
 */
export function metricsParts(files) {
  return files.filter((f) => /(^|[\\/])metrics\.json$/.test(f));
}

/**
 * The comment a kind of run posted before, found by its marker (the fixture run's by default).
 * @template {{ body?: string }} T
 * @param {T[]} comments
 * @param {string} [marker]
 * @returns {T | undefined}
 */
export function findComment(comments, marker = MARKER) {
  return comments.find((c) => typeof c.body === "string" && c.body.startsWith(marker));
}

/**
 * What to measure, or why not (D-125). A pull request, or a hand run naming no URL, is measured as
 * the fixture build the job serves itself. A deployment event is a preview, measured only when it
 * succeeded on the Preview environment. A hand run naming a URL is a preview too: any https URL
 * except production's, unless allow_production is ticked. Production's host is refused either way
 * without it.
 * @param {{
 *   eventName: string, environment?: string, state?: string, deploymentUrl?: string,
 *   inputUrl?: string, productionUrl?: string, allowProduction?: boolean,
 * }} args
 * @returns {{ mode: Mode, url: string } | { skip: string } | { problem: string }}
 */
export function measurable({ eventName, environment, state, deploymentUrl, inputUrl, productionUrl, allowProduction }) {
  if (eventName === "pull_request" || (eventName === "workflow_dispatch" && !inputUrl)) {
    return { mode: "fixture", url: FIXTURE_URL };
  }
  if (eventName === "deployment_status") {
    if (state !== "success") return { skip: `deployment is ${state}, not success` };
    if (environment !== "Preview") return { skip: `${environment} is not a preview` };
  } else if (eventName !== "workflow_dispatch") {
    return { skip: `${eventName} is not a trigger this job measures` };
  }
  const url = eventName === "workflow_dispatch" ? inputUrl : deploymentUrl;
  let parsed;
  try {
    parsed = new URL(url ?? "");
  } catch {
    return { problem: `not a URL: ${url || "(none)"}` };
  }
  if (parsed.protocol !== "https:") return { problem: `${url} is not https` };
  let prodHost = null;
  try {
    prodHost = productionUrl ? new URL(productionUrl).host : null;
  } catch {
    /* an unset or bad PRODUCTION_URL names no host */
  }
  if (prodHost && parsed.host === prodHost && !allowProduction) {
    return { problem: `${url} is production (PRODUCTION_URL); tick allow_production to measure it` };
  }
  return { mode: "preview", url: parsed.origin };
}

/**
 * measurable's inputs from the event that started the job (the payload at GITHUB_EVENT_PATH).
 * Vercel puts the deployment's own URL in environment_url; target_url is its dashboard page.
 * @param {string} eventName
 * @param {any} event
 * @param {string} [productionUrl]
 * @returns {Parameters<typeof measurable>[0]}
 */
export function eventInputs(eventName, event, productionUrl) {
  if (eventName === "deployment_status") {
    const status = event?.deployment_status ?? {};
    return {
      eventName,
      state: status.state,
      environment: status.environment ?? event?.deployment?.environment,
      deploymentUrl: status.environment_url,
      productionUrl,
    };
  }
  if (eventName === "workflow_dispatch") {
    const allow = event?.inputs?.allow_production;
    return { eventName, inputUrl: event?.inputs?.url, allowProduction: allow === true || allow === "true", productionUrl };
  }
  return { eventName, productionUrl };
}

/**
 * The name of Auth.js's session cookie at this URL. It is also the salt the token is encrypted
 * with, so a cookie minted under the wrong name never decodes.
 * @param {string} url
 */
export function sessionCookieName(url) {
  return new URL(url).protocol === "https:" ? "__Secure-authjs.session-token" : "authjs.session-token";
}

/**
 * The session cookie Auth.js would set after the allowlisted account signed in with GitHub, minted
 * with the preview's AUTH_SECRET (which differs from production's, D-012). `encode` is Auth.js's
 * own (`@auth/core/jwt`), passed in so this file needs no dependency.
 * @param {{
 *   url: string, secret: string | undefined, githubId: string | undefined,
 *   encode: (params: { token: { sub: string, name: string }, secret: string, salt: string, maxAge: number }) => Promise<string>,
 *   maxAge?: number,
 * }} args
 * @returns {Promise<SessionCookie>}
 */
export async function mintSession({ url, secret, githubId, encode, maxAge = 60 * 60 }) {
  if (!secret) {
    throw new Error(
      "AUTH_SECRET is not set: pass the server's AUTH_SECRET (PREVIEW_AUTH_SECRET for a preview, web/e2e/test-env.ts's for the fixture build)",
    );
  }
  if (!githubId) throw new Error("AUTH_ALLOWED_GITHUB_ID is not set: pass the GitHub ID the server allows");
  const name = sessionCookieName(url);
  const value = await encode({ token: { sub: String(githubId), name: "Lighthouse" }, secret, salt: name, maxAge });
  return { name, value };
}

/**
 * The headers Lighthouse is given. Both keep the Vercel toolbar out and carry the Deployment
 * Protection bypass when there is one; only the signed-in set carries the session.
 * @param {{ cookie: SessionCookie, bypass?: string }} args
 * @returns {{ signedIn: Record<string, string>, signedOut: Record<string, string> }}
 */
export function sessionHeaders({ cookie, bypass }) {
  /** @type {Record<string, string>} */
  const signedOut = { "x-vercel-skip-toolbar": "1" };
  if (bypass) signedOut["x-vercel-protection-bypass"] = bypass;
  return { signedIn: { ...signedOut, Cookie: `${cookie.name}=${cookie.value}` }, signedOut };
}

/**
 * Every secret string a signed-in header set holds: the bypass, the Cookie header and the cookie
 * value alone.
 * @param {Record<string, string>} headers
 * @returns {string[]}
 */
export function headerSecrets(headers) {
  const cookie = headers.Cookie;
  const value = cookie?.includes("=") ? cookie.slice(cookie.indexOf("=") + 1) : undefined;
  return /** @type {string[]} */ ([headers["x-vercel-protection-bypass"], cookie, value].filter(Boolean));
}

/** @param {(string | null | undefined)[]} secrets */
const live = (secrets) =>
  /** @type {string[]} */ (secrets.filter((s) => typeof s === "string" && s.length >= MIN_SECRET));

/**
 * Text with every secret replaced by [redacted]: for the HTML report and anything else written out.
 * @param {string} text
 * @param {(string | null | undefined)[]} secrets
 */
export function scrubText(text, secrets) {
  return live(secrets).reduce((s, secret) => s.split(secret).join("[redacted]"), text);
}

/**
 * A Lighthouse result with every secret blanked and the headers it was given dropped (Lighthouse
 * copies them into configSettings.extraHeaders). The input is left alone.
 * @template T
 * @param {T} lhr
 * @param {(string | null | undefined)[]} secrets
 * @returns {T}
 */
export function scrubLhr(lhr, secrets) {
  const keep = live(secrets);
  /** @param {unknown} v @returns {unknown} */
  const clean = (v) => {
    if (typeof v === "string") return scrubText(v, keep);
    if (Array.isArray(v)) return v.map(clean);
    if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, clean(x)]));
    return v;
  };
  const out = /** @type {any} */ (clean(lhr));
  if (out?.configSettings) out.configSettings.extraHeaders = null;
  return out;
}

/**
 * Null when no file holds a secret; otherwise the failure, naming the files and never a value.
 * @param {{ name: string, text: string }[]} files
 * @param {(string | null | undefined)[]} secrets
 * @returns {string | null}
 */
export function guardMessage(files, secrets) {
  const keep = live(secrets);
  const leaked = files.filter(({ text }) => keep.some((s) => text.includes(s))).map((f) => f.name);
  if (!leaked.length) return null;
  return `A secret reached ${leaked.length} report file${leaked.length > 1 ? "s" : ""}, so nothing is uploaded: ${leaked.join(", ")}`;
}

/**
 * The PRs a baseline may come from, newest merge first: merged, other than this one, at most
 * `limit`. PRs are squash-merged and main is never measured, so the last merged PR's run is the
 * nearest thing to main. A docs-only PR has no fixture run (paths-ignore), so report.mjs walks
 * this list until a PR has a run of the right kind.
 * @template {{ number: number, merged_at: string | null }} T
 * @param {T[]} pulls
 * @param {number[]} [currentPrs]
 * @param {number} [limit]
 * @returns {T[]}
 */
export function baselineCandidates(pulls, currentPrs = [], limit = 10) {
  return pulls
    .filter((p) => p.merged_at && !currentPrs.includes(p.number))
    .sort((a, b) => (/** @type {string} */ (a.merged_at) < /** @type {string} */ (b.merged_at) ? 1 : -1))
    .slice(0, limit);
}

/**
 * The newest merged pull request other than this one.
 * @template {{ number: number, merged_at: string | null }} T
 * @param {T[]} pulls
 * @param {number[]} [currentPrs]
 * @returns {T | null}
 */
export function baselinePr(pulls, currentPrs = []) {
  return baselineCandidates(pulls, currentPrs, 1)[0] ?? null;
}

/**
 * The newest green run of the workflow on that PR's head commit, of the given event when one is
 * named (BASELINE_EVENT: a fixture run is compared with pull_request runs, a preview with
 * deployment_status runs).
 * @template {{ status: string, conclusion: string | null, created_at: string, event?: string }} T
 * @param {T[]} runs
 * @param {string} [event]
 * @returns {T | null}
 */
export function baselineRun(runs, event) {
  return (
    runs
      .filter((r) => r.status === "completed" && r.conclusion === "success" && (!event || r.event === event))
      .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0] ?? null
  );
}
