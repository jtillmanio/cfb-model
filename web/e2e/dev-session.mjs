// Signs the ui-verifier in to the local dev server (02 › Testing strategy › Test-only sign-in and
// clock; TASK-010). Sign-in is GitHub-only, which an agent can't do, so this mints the session
// cookie Auth.js would set after the allowlisted account signed in, with the dev AUTH_SECRET. That
// is safe only because each environment has its own AUTH_SECRET (D-012): the cookie can't open a
// preview or production. It lives beside e2e's mint (fixtures.ts), never in web/ source.
//
//   node web/e2e/dev-session.mjs http://127.0.0.1:3210
//
// Prints one line, the Playwright cookie as JSON, valid 1 hour. Reads AUTH_SECRET and
// AUTH_ALLOWED_GITHUB_ID from the repo root's .env.local and nowhere else: no file flag, no
// fallback to the process environment. Refuses any URL that isn't http: on a loopback host.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseEnv } from "node:util";

import { encode } from "next-auth/jwt";

// Auth.js's cookie on http; the name is also the key-derivation salt.
export const SESSION_COOKIE = "authjs.session-token";
const ONE_HOUR = 60 * 60;
const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]"]);
const ENV_LOCAL = fileURLToPath(new URL("../../.env.local", import.meta.url));

/**
 * The URL's origin, if it is http: on a loopback host.
 * @param {string} url
 * @returns {string}
 */
export function loopbackOrigin(url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error(`${url} is not a URL.`);
  }
  if (parsed.protocol !== "http:") throw new Error(`${parsed.origin} is not http:; the dev sign-in is for the local dev server only.`);
  if (!LOOPBACK.has(parsed.hostname)) throw new Error(`${parsed.host} is not a loopback host (localhost, 127.0.0.1, [::1]).`);
  return parsed.origin;
}

/**
 * The two variables the mint needs, from .env.local's text. Errors name a variable, never a value.
 * @param {string} envText
 * @returns {{ secret: string, githubId: string }}
 */
export function devSecrets(envText) {
  const env = parseEnv(envText);
  for (const name of ["AUTH_SECRET", "AUTH_ALLOWED_GITHUB_ID"]) {
    if (!env[name]) throw new Error(`.env.local has no ${name}.`);
  }
  return { secret: /** @type {string} */ (env.AUTH_SECRET), githubId: /** @type {string} */ (env.AUTH_ALLOWED_GITHUB_ID) };
}

/**
 * The session cookie for Playwright's addCookies, valid 1 hour.
 * @param {{ url: string, secret: string, githubId: string, encode: typeof import("next-auth/jwt").encode, now?: number }} args
 */
export async function devSessionCookie({ url, secret, githubId, encode, now = Date.now() }) {
  const value = await encode({ token: { sub: githubId, name: "Dev owner" }, secret, salt: SESSION_COOKIE, maxAge: ONE_HOUR });
  return {
    name: SESSION_COOKIE,
    value,
    url,
    httpOnly: true,
    sameSite: /** @type {const} */ ("Lax"),
    expires: Math.floor(now / 1000) + ONE_HOUR,
  };
}

/**
 * The script. Tests pass a temp .env.local; the command line always uses the repo root's.
 * @param {string} envPath
 * @param {{ argv: string[], stdout: { write(s: string): unknown }, stderr: { write(s: string): unknown } }} io
 * @returns {Promise<0 | 1>}
 */
export async function main(envPath, { argv, stdout, stderr }) {
  try {
    if (argv.length !== 1) throw new Error("usage: node web/e2e/dev-session.mjs <http://localhost:port>");
    const url = loopbackOrigin(argv[0]);
    let envText;
    try {
      envText = readFileSync(envPath, "utf8");
    } catch {
      throw new Error("cannot read .env.local at the repo root.");
    }
    const { secret, githubId } = devSecrets(envText);
    const cookie = await devSessionCookie({ url, secret, githubId, encode });
    stdout.write(`${JSON.stringify(cookie)}\n`);
    return 0;
  } catch (e) {
    stderr.write(`dev-session: ${e instanceof Error ? e.message : String(e)}\n`);
    return 1;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(ENV_LOCAL, { argv: process.argv.slice(2), stdout: process.stdout, stderr: process.stderr });
}
