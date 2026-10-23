// Signs the lighthouse job in to what it measures (02 › Performance checks (Lighthouse) › Signing
// in, D-101, D-125). Sign-in is GitHub-only, which a script can't do, so this mints the session
// cookie Auth.js would set after the allowlisted account signed in, with the server's AUTH_SECRET:
// the preview's (safe only because previews and production have different AUTH_SECRETs, D-012, so
// the cookie can never open production), or e2e's test-only one for the fixture build the job
// serves itself. e2e mints its own in web/e2e/fixtures.ts; neither lives in web/.
//
//   TARGET_URL=https://… HEADERS_DIR=… AUTH_SECRET=… AUTH_ALLOWED_GITHUB_ID=… \
//     [VERCEL_AUTOMATION_BYPASS_SECRET=…] node scripts/perf/mint-session.mjs
//
// Prints ::add-mask:: for every secret before anything else, and for the cookie as soon as it
// exists; after that only statuses, never a value. Writes HEADERS_DIR/signed-in.json and
// signed-out.json (the headers Lighthouse is given) and nothing else. HEADERS_DIR must be outside
// the reports folder; the workflow deletes it when the job ends.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { encode } from "@auth/core/jwt";

import { mintSession, sessionHeaders } from "./lib/perf.mjs";

const {
  TARGET_URL,
  HEADERS_DIR,
  AUTH_SECRET,
  AUTH_ALLOWED_GITHUB_ID,
  VERCEL_AUTOMATION_BYPASS_SECRET: bypass,
} = process.env;

/** @param {string | undefined} value */
const mask = (value) => value && console.log(`::add-mask::${value}`);
mask(AUTH_SECRET);
mask(bypass);

/** @param {string} message */
function fail(message) {
  console.error(`mint-session: ${message}`);
  process.exit(1);
}

if (!TARGET_URL || !HEADERS_DIR) fail("TARGET_URL and HEADERS_DIR are required.");
let target;
try {
  target = new URL(/** @type {string} */ (TARGET_URL));
} catch {
  fail("TARGET_URL is not a URL.");
}

try {
  const cookie = await mintSession({ url: target.origin, secret: AUTH_SECRET, githubId: AUTH_ALLOWED_GITHUB_ID, encode });
  mask(cookie.value);
  const { signedIn, signedOut } = sessionHeaders({ cookie, bypass });
  const dir = /** @type {string} */ (HEADERS_DIR);
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  writeFileSync(join(dir, "signed-in.json"), JSON.stringify(signedIn), { mode: 0o600 });
  writeFileSync(join(dir, "signed-out.json"), JSON.stringify(signedOut), { mode: 0o600 });
  console.log(
    `mint-session: minted ${cookie.name} for ${target.host}, valid 1 hour` +
      (bypass ? ", with the Deployment Protection bypass" : ""),
  );
} catch (e) {
  fail(e instanceof Error ? e.message : String(e));
}
