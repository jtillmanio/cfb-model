// Measures one deployment (02 › Performance checks (Lighthouse), D-101, D-125): Lighthouse, three
// runs per route, on the profile 02 fixes (mobile, devtools throttling: Slow 4G, 4× CPU;
// performance and accessibility). Run after mint-session.mjs, which wrote the headers this hands
// Lighthouse.
//
//   TARGET_URL=https://… HEADERS_DIR=… OUT_DIR=… CHROME_PATH=… AUTH_SECRET=… PERF_MODE=fixture|preview \
//     [VERCEL_AUTOMATION_BYPASS_SECRET=…] [SHA=…] [RUNS=3] [PERF_ROUTES=login,teams] \
//     node scripts/perf/measure.mjs
//
// A preview is measured one route per job (PERF_ROUTES = the matrix's route); the fixture build
// the job serves itself, every route in one job. PERF_MODE goes into metrics.json, so a budget is
// only ever set from a fixture run's numbers (budgetFrom). Writes
// OUT_DIR/reports/<route>-<n>.json and .html (scrubbed of every header and secret; the HTML is
// rebuilt from the scrubbed JSON) and OUT_DIR/metrics.json (numbers only: what report.mjs gates
// and compares). Lighthouse's raw output carries the headers it was given, so it is written under
// HEADERS_DIR, never the reports folder, and deleted as soon as it is read. A run that fails is
// recorded, not thrown: report.mjs fails the route.
import { spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { ReportGenerator } from "lighthouse/report/generator/report-generator.js";

import { chromeVersion, headerSecrets, scrubLhr, scrubText, summariseLhr } from "./lib/perf.mjs";
import { ROUTES } from "./routes.mjs";

const env = process.env;
for (const k of ["TARGET_URL", "HEADERS_DIR", "OUT_DIR", "CHROME_PATH", "PERF_MODE"]) {
  if (!env[k]) {
    console.error(`measure: ${k} is required`);
    process.exit(1);
  }
}
const base = new URL(/** @type {string} */ (env.TARGET_URL)).origin;
const headersDir = /** @type {string} */ (env.HEADERS_DIR);
const outDir = /** @type {string} */ (env.OUT_DIR);
const RUNS = Number(env.RUNS ?? 3);
const only = env.PERF_ROUTES?.split(",");
const routes = ROUTES.filter((r) => !only || only.includes(r.id));
if (!routes.length) {
  console.error(`measure: no route in routes.mjs matches PERF_ROUTES=${env.PERF_ROUTES}`);
  process.exit(1);
}

/** @param {boolean} signedIn */
const headerFile = (signedIn) => join(headersDir, signedIn ? "signed-in.json" : "signed-out.json");
const secrets = [
  env.AUTH_SECRET,
  env.VERCEL_AUTOMATION_BYPASS_SECRET,
  ...headerSecrets(JSON.parse(readFileSync(headerFile(true), "utf8"))),
];
// mint-session.mjs masked these in its own step; each step's log needs its own mask.
for (const secret of secrets) if (secret) console.log(`::add-mask::${secret}`);

const reports = join(outDir, "reports");
const raw = join(headersDir, "raw");
mkdirSync(reports, { recursive: true });
mkdirSync(raw, { recursive: true, mode: 0o700 });

// Actions' Ubuntu image restricts the user namespaces Chrome's sandbox needs. Chrome here only
// ever opens this app's own preview.
const chromeFlags = ["--headless=new", ...(env.CI === "true" ? ["--no-sandbox"] : [])];
const lighthouseCli = fileURLToPath(new URL("./node_modules/lighthouse/cli/index.js", import.meta.url));
const lighthouseVersion = JSON.parse(
  readFileSync(new URL("./node_modules/lighthouse/package.json", import.meta.url), "utf8"),
).version;
// Chrome's user agent is reduced to the major version (154.0.0.0), so ask the binary first; the
// user agent is the fallback where `--version` prints nothing (Windows).
/** @type {string | null} */
let chrome =
  spawnSync(/** @type {string} */ (env.CHROME_PATH), ["--version"], { encoding: "utf8", timeout: 30_000 })
    .stdout?.match(/\d+(?:\.\d+){3}/)?.[0] ?? null;

/**
 * One Lighthouse load of one route.
 * @param {import("./routes.mjs").PerfRoute} route
 * @param {number} n
 */
function lighthouse(route, n) {
  const name = `${route.id}-${n}`;
  const rawPath = join(raw, `${name}.json`);
  const r = spawnSync(
    process.execPath,
    [
      lighthouseCli,
      base + route.path,
      "--form-factor=mobile",
      "--throttling-method=devtools",
      "--only-categories=performance,accessibility",
      `--extra-headers=${headerFile(route.signedIn)}`,
      "--output=json",
      `--output-path=${rawPath}`,
      "--disable-full-page-screenshot",
      "--quiet",
      `--chrome-flags=${chromeFlags.join(" ")}`,
    ],
    { encoding: "utf8", env, timeout: 5 * 60_000 },
  );
  if (r.status !== 0) {
    rmSync(rawPath, { force: true });
    const why = (r.stderr || r.error?.message || "").trim().split("\n").slice(-1)[0];
    return { error: scrubText(`Lighthouse exited ${r.status ?? r.signal}: ${why}`, secrets).slice(0, 300) };
  }
  const lhr = scrubLhr(JSON.parse(readFileSync(rawPath, "utf8")), secrets);
  rmSync(rawPath);
  writeFileSync(join(reports, `${name}.json`), JSON.stringify(lhr));
  writeFileSync(join(reports, `${name}.html`), ReportGenerator.generateReportHtml(lhr));
  chrome ??= chromeVersion(lhr);
  if (lhr.runtimeError) return { error: `Lighthouse: ${lhr.runtimeError.code}` };
  return summariseLhr(lhr);
}

/** @type {import("./lib/perf.mjs").Metrics} */
const metrics = {
  mode: env.PERF_MODE === "fixture" ? "fixture" : "preview",
  url: base,
  sha: env.SHA ?? null,
  lighthouse: lighthouseVersion,
  measuredAt: new Date().toISOString(),
  runs: RUNS,
  routes: {},
};
try {
  for (const route of routes) {
    const loads = [];
    for (let n = 1; n <= RUNS; n++) loads.push(lighthouse(route, n));
    metrics.routes[route.id] = { path: route.path, loads };
    const ok = loads.filter((l) => !("error" in l)).length;
    console.log(`measure: ${route.id} ${route.path}: ${ok}/${RUNS} loads finished`);
  }
} finally {
  rmSync(raw, { recursive: true, force: true });
}
metrics.chrome = chrome ?? undefined;
writeFileSync(join(outDir, "metrics.json"), JSON.stringify(metrics, null, 2));
console.log(`measure: Lighthouse ${lighthouseVersion}, Chrome ${chrome ?? "unknown"}`);
