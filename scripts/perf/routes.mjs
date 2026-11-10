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
  { id: "this-week", path: "/", signedIn: true },
  { id: "teams", path: "/teams", signedIn: true },
  { id: "design-system", path: "/design-system", signedIn: true },
];

// The screen-to-screen taps the fixture run times (TASK-014, 02 › Performance checks (Lighthouse) ›
// Taps): client navigations, on Lighthouse's mobile profile, so the phone's nav. Reported, never
// gated on time; a forbidden request during a tap fails the run. web/lib/perf.test.ts fails on a
// tap whose `from` or `to` isn't a signed-in route above.
//
//   id       stable name: the key in metrics.json and the row in the PR comment
//   from     the route (id) the runner loads first
//   to       the route (id) the tap lands on
//   heading  `to`'s <h1>: the first clock stops when it shows (its loading.tsx draws it too)
//   via      a selector tapped first and not timed (opening the More sheet)
//   link     the selector the timed tap lands on

/** @typedef {{ id: string, from: string, to: string, heading: string, via?: string, link: string }} PerfTap */

/** @type {PerfTap[]} */
export const TAPS = [
  {
    id: "this-week→teams",
    from: "this-week",
    to: "teams",
    heading: "Teams",
    // Teams isn't one of the bottom tabs (MOBILE_TABS in web/lib/shell.ts): it is in the More sheet.
    via: 'nav[aria-label="Tabs"] button[popovertarget="shell-more"]',
    link: '#shell-more a[href="/teams"]',
  },
  {
    id: "teams→this-week",
    from: "teams",
    to: "this-week",
    heading: "This Week",
    link: 'nav[aria-label="Tabs"] a[href="/"]',
  },
];
