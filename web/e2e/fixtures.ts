import { test as base, type BrowserContext, type Cookie } from "@playwright/test";
import { encode } from "next-auth/jwt";

import { TEST_AUTH_SECRET, TEST_GITHUB_ID } from "./test-env";

// Test-only sign-in (02 › Testing strategy › Test-only sign-in and clock; D-090): mint the session
// cookie Auth.js would set after a GitHub sign-in. It lives here, never in web/ source, so
// production has no way in except GitHub.

// Auth.js's cookie on http (e2e runs on http://127.0.0.1); the name is also the key-derivation salt.
export const SESSION_COOKIE = "authjs.session-token";
const NINETY_DAYS = 90 * 24 * 60 * 60;

type NewCookie = Parameters<BrowserContext["addCookies"]>[0][number];

type MintOptions = {
  baseURL: string;
  secret?: string;
  githubId?: string;
  // Lifetime of the JWT inside the cookie; negative mints an already-expired token.
  tokenMaxAge?: number;
  // Lifetime of the browser cookie, so an expired token still reaches the server.
  cookieMaxAge?: number;
};

export async function mintSessionCookie({
  baseURL,
  secret = TEST_AUTH_SECRET,
  githubId = TEST_GITHUB_ID,
  tokenMaxAge = NINETY_DAYS,
  cookieMaxAge = tokenMaxAge > 0 ? tokenMaxAge : NINETY_DAYS,
}: MintOptions): Promise<NewCookie> {
  const value = await encode({
    token: { sub: githubId, name: "E2E Owner" },
    secret,
    salt: SESSION_COOKIE,
    maxAge: tokenMaxAge,
  });
  return {
    name: SESSION_COOKIE,
    value,
    url: baseURL,
    httpOnly: true,
    sameSite: "Lax",
    expires: Math.floor(Date.now() / 1000) + cookieMaxAge,
  };
}

export function findSessionCookie(cookies: Cookie[]): Cookie | undefined {
  return cookies.find((cookie) => cookie.name === SESSION_COOKIE);
}

// Signed in as the allowlisted test account.
export const test = base.extend({
  // Named `provide`, not `use`: the React hooks lint rule would read `use` as a hook.
  context: async ({ context, baseURL }, provide) => {
    await context.addCookies([await mintSessionCookie({ baseURL: baseURL! })]);
    await provide(context);
  },
});

export { expect } from "@playwright/test";
