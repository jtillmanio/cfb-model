// The lighthouse workflow's steps that need thinking (02 › Performance checks (Lighthouse), D-101).
//   node scripts/perf/report.mjs plan       which URL to measure, or why not; the route list as JSON;
//                                           the PR whose older runs this one cancels
//   node scripts/perf/report.mjs guard DIR  fail if any file under DIR holds a secret; names files, never values
//   node scripts/perf/report.mjs merge DIR  the per-route jobs' metrics.json files under DIR, as one
//   node scripts/perf/report.mjs baseline   the newest merged PR's newest green run
//   node scripts/perf/report.mjs report     job summary, the one PR comment, then the gate
//   node scripts/perf/report.mjs budget FILE  budget.json and 02's perf-budget table from a run's
//                                           merged metrics.json (its lighthouse-metrics artifact)
//
// Uses only Node and the GitHub REST API: nothing from scripts/perf/package.json.
import { appendFileSync, existsSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import {
  aggregateRoute,
  baselinePr,
  baselineRun,
  budgetFrom,
  budgetTable,
  eventInputs,
  findComment,
  gateProblems,
  guardMessage,
  headerSecrets,
  measurable,
  mergeMetrics,
  renderComment,
  unbudgeted,
} from "./lib/perf.mjs";
import { ROUTES } from "./routes.mjs";

const env = process.env;
const WORKFLOW = "lighthouse.yml";
const BUDGET_FILE = new URL("./budget.json", import.meta.url);

/** @param {string} key @param {string} value */
const output = (key, value) => env.GITHUB_OUTPUT && appendFileSync(env.GITHUB_OUTPUT, `${key}=${value}\n`);

/** @param {string} file */
const readJson = (file) => JSON.parse(readFileSync(file, "utf8"));

/**
 * @param {string} path
 * @param {RequestInit & { method?: string }} [init]
 */
async function github(path, init = {}) {
  const res = await fetch(`https://api.github.com/repos/${env.GITHUB_REPOSITORY}/${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${env.GH_TOKEN}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) throw new Error(`GitHub ${init.method ?? "GET"} ${path}: ${res.status} ${await res.text()}`);
  return res.json();
}

/**
 * The open pull requests whose head is this commit.
 * @param {string | undefined} sha
 * @returns {Promise<{ number: number, state: string }[]>}
 */
async function pullsFor(sha) {
  if (!sha) return [];
  return (await github(`commits/${sha}/pulls`)).filter((/** @type {{ state: string }} */ p) => p.state === "open");
}

async function plan() {
  const eventName = env.GITHUB_EVENT_NAME ?? "";
  const event = env.GITHUB_EVENT_PATH ? readJson(env.GITHUB_EVENT_PATH) : {};
  const result = measurable(eventInputs(eventName, event, env.PRODUCTION_URL));
  if ("problem" in result) throw new Error(result.problem);
  if ("skip" in result) {
    console.log(`Not measuring: ${result.skip}.`);
    return;
  }
  // A newer push to the same PR cancels this run (the measuring jobs' concurrency group); a commit
  // with no PR, or a hand run, is a group of its own. Without a token (a local try) there's no lookup.
  const sha = event.deployment?.sha;
  const [pr] = eventName === "deployment_status" && env.GH_TOKEN ? await pullsFor(sha) : [];
  const group = pr ? `pr-${pr.number}` : `run-${env.GITHUB_RUN_ID ?? "local"}`;
  const routes = ROUTES.map((r) => r.id);
  console.log(JSON.stringify({ url: result.url, group, routes }));
  output("url", result.url);
  output("group", group);
  output("routes", JSON.stringify(routes));
}

/** @param {string} dir @returns {string[]} */
function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

/** @param {string} dir */
function merge(dir) {
  const out = join(dir, "metrics.json");
  const parts = walk(dir)
    .filter((f) => f.endsWith("metrics.json") && f !== out)
    .map(readJson);
  const merged = mergeMetrics(parts, ROUTES.map((r) => r.id));
  writeFileSync(out, JSON.stringify(merged, null, 2));
  console.log(`merge: ${Object.keys(merged.routes).join(", ")}`);
}

/** @param {string} dir */
function guard(dir) {
  let headers = {};
  try {
    headers = readJson(join(env.HEADERS_DIR ?? "", "signed-in.json"));
  } catch {
    /* no session was minted, so none can leak */
  }
  const secrets = [env.AUTH_SECRET, env.VERCEL_AUTOMATION_BYPASS_SECRET, ...headerSecrets(headers)];
  // Masked before anything else is printed (02 › Performance checks › Signing in).
  for (const secret of secrets) if (secret) console.log(`::add-mask::${secret}`);
  const files = walk(dir).map((p) => ({ name: p, text: readFileSync(p, "utf8") }));
  const problem = guardMessage(files, secrets);
  if (problem) throw new Error(problem);
  console.log(`guard: ${files.length} files, no secret in any`);
}

async function baseline() {
  const event = env.GITHUB_EVENT_PATH ? readJson(env.GITHUB_EVENT_PATH) : {};
  const current = (await pullsFor(event.deployment?.sha)).map((p) => p.number);
  const pulls = await github("pulls?state=closed&sort=updated&direction=desc&per_page=50");
  const pr = baselinePr(pulls, current);
  if (!pr) return console.log("baseline: no merged pull request");
  const { workflow_runs: runs } = await github(`actions/workflows/${WORKFLOW}/runs?head_sha=${pr.head.sha}&per_page=20`);
  const run = baselineRun(runs);
  if (!run) return console.log(`baseline: PR #${pr.number} has no green Lighthouse run`);
  console.log(`baseline: PR #${pr.number}, run ${run.id}`);
  output("run_id", String(run.id));
  output("pr", String(pr.number));
}

/**
 * A metrics.json (this run's or the baseline's) as per-route results.
 * @param {string} file
 */
function load(file) {
  /** @type {import("./lib/perf.mjs").Metrics} */
  const m = readJson(file);
  return { ...m, routes: Object.fromEntries(Object.entries(m.routes).map(([id, r]) => [id, aggregateRoute(r)])) };
}

async function report() {
  if (!env.METRICS) throw new Error("METRICS (the merged metrics.json) is required");
  const current = load(env.METRICS);
  // A route with an empty entry (no run has set its budget yet) is reported as unbudgeted, not gated.
  const budget = existsSync(BUDGET_FILE) ? JSON.parse(readFileSync(BUDGET_FILE, "utf8")).routes : {};
  const before = env.BASELINE_METRICS && existsSync(env.BASELINE_METRICS) ? load(env.BASELINE_METRICS) : null;
  const baseline = before ? { ...before, pr: env.BASELINE_PR ?? "?", at: before.measuredAt } : null;
  const problems = gateProblems(current.routes, budget, ROUTES.map((r) => r.id));
  const body = renderComment({ current, baseline, budget, problems, missingBudget: unbudgeted(current.routes, budget) });

  if (env.GITHUB_STEP_SUMMARY) appendFileSync(env.GITHUB_STEP_SUMMARY, `${body}\n`);
  else console.log(body);

  // A hand run has no pull request to answer; its summary is the report.
  if (env.GITHUB_EVENT_NAME === "deployment_status") {
    const event = env.GITHUB_EVENT_PATH ? readJson(env.GITHUB_EVENT_PATH) : {};
    for (const pr of await pullsFor(event.deployment?.sha)) {
      const comments = await github(`issues/${pr.number}/comments?per_page=100`);
      const mine = findComment(comments);
      const init = { body: JSON.stringify({ body }) };
      if (mine) await github(`issues/comments/${mine.id}`, { ...init, method: "PATCH" });
      else await github(`issues/${pr.number}/comments`, { ...init, method: "POST" });
      console.log(`report: ${mine ? "updated" : "posted"} the comment on #${pr.number}`);
    }
  }
  if (problems.length) {
    for (const p of problems) console.log(`::error::${p}`);
    process.exit(1);
  }
}

/**
 * Rewrites budget.json from a run's merged metrics.json and prints 02's table to paste between the
 * perf-budget markers. Refuses a run with a route missing; bytes that move 1% or more between runs
 * are printed for the PR to explain, since 02 asks that they be checked.
 * @param {string} file
 */
function budget(file) {
  /** @type {import("./lib/perf.mjs").Metrics} */
  const metrics = readJson(file);
  const missing = ROUTES.filter((r) => !metrics.routes[r.id]).map((r) => r.id);
  if (missing.length) throw new Error(`the run didn't measure ${missing.join(", ")}`);
  const { routes, measured, unsteady } = budgetFrom(metrics);
  const current = JSON.parse(readFileSync(BUDGET_FILE, "utf8"));
  writeFileSync(BUDGET_FILE, `${JSON.stringify({ ...current, measured, routes }, null, 2)}\n`);
  console.log(budgetTable(routes));
  console.log(`\nMeasured: Lighthouse ${measured.lighthouse}, Chrome ${measured.chrome}, ${measured.url} at ${measured.sha}`);
  for (const [id, m] of Object.entries(measured.medians)) console.log(`  ${id}: ${JSON.stringify(m)}`);
  for (const u of unsteady) console.log(`::warning::${u}`);
}

const command = process.argv[2];
const dirArg = () => {
  if (!process.argv[3]) throw new Error(`${command} needs a directory`);
  return process.argv[3];
};
/** @type {Record<string, () => unknown>} */
const commands = {
  plan,
  guard: () => guard(dirArg()),
  merge: () => merge(dirArg()),
  baseline,
  report,
  budget: () => budget(dirArg()),
};
const run = commands[command];
if (!run) {
  console.error("usage: node scripts/perf/report.mjs <plan | guard DIR | merge DIR | baseline | report | budget FILE>");
  process.exit(2);
}
try {
  await run();
} catch (e) {
  console.error(e instanceof Error ? e.message : String(e));
  process.exit(1);
}
