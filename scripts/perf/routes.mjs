// The one list of what every PR preview measures (02 › Performance checks (Lighthouse), D-101).
// The lighthouse workflow measures these and nothing else, one job per route, and
// scripts/perf/budget.json holds one budget per id.
//
// A PR that adds a top-level screen adds its route here, and its budget, in the same PR:
// web/lib/perf.test.ts fails on a top-level page under web/app/ with no route. Data-heavy detail
// pages (Game Detail, Team) get a small and a large instance, each its own entry.
//
//   id        stable name: the key in budget.json, the matrix job and the PR comment
//   path      what Lighthouse loads
//   signedIn  false for a page measured signed out (/login)

/** @typedef {{ id: string, path: string, signedIn: boolean }} PerfRoute */

/** @type {PerfRoute[]} */
export const ROUTES = [
  { id: "login", path: "/login", signedIn: false },
  { id: "teams", path: "/teams", signedIn: true },
];
