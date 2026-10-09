import type { Account, Profile, Session } from "next-auth";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authConfig, SESSION_MAX_AGE_SECONDS } from "@/auth.config";

const ALLOWED = "1234567";

const github = { provider: "github", type: "oauth", providerAccountId: ALLOWED } as Account;

// Only the fields the callbacks read; Auth.js passes more.
type Callbacks = NonNullable<typeof authConfig.callbacks>;
type ArgsOf<K extends keyof Callbacks> = Parameters<NonNullable<Callbacks[K]>>[0];
type SignInArgs = ArgsOf<"signIn">;
type AuthorizedArgs = ArgsOf<"authorized">;

// GitHub's profile carries a numeric id; Auth.js's Profile type says string.
function githubProfile(id: unknown): Profile {
  return { id } as unknown as Profile;
}

function signIn(profileId: unknown, account: Account | null = github) {
  const args = { user: {}, account, profile: githubProfile(profileId) } as SignInArgs;
  return authConfig.callbacks!.signIn!(args);
}

function authorized(userId: string | undefined) {
  const auth = userId === undefined ? null : ({ user: { id: userId }, expires: "" } as Session);
  return authConfig.callbacks!.authorized!({ auth } as AuthorizedArgs);
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("authConfig", () => {
  it("keeps a session for 90 days", () => {
    expect(SESSION_MAX_AGE_SECONDS).toBe(90 * 24 * 60 * 60);
    expect(authConfig.session?.maxAge).toBe(90 * 24 * 60 * 60);
    expect(authConfig.session?.strategy).toBe("jwt");
  });

  it("sends sign-in and sign-in errors to /login", () => {
    expect(authConfig.pages?.signIn).toBe("/login");
    expect(authConfig.pages?.error).toBe("/login");
  });
});

describe("signIn callback", () => {
  it("admits the allowlisted GitHub ID", async () => {
    vi.stubEnv("AUTH_ALLOWED_GITHUB_ID", ALLOWED);
    expect(await signIn(Number(ALLOWED))).toBe(true);
  });

  it("refuses any other GitHub ID, which Auth.js sends to pages.error as AccessDenied", async () => {
    vi.stubEnv("AUTH_ALLOWED_GITHUB_ID", ALLOWED);
    expect(await signIn(7654321)).toBe(false);
  });

  it("refuses everyone when the allowlist is unset or empty", async () => {
    vi.stubEnv("AUTH_ALLOWED_GITHUB_ID", undefined);
    expect(await signIn(Number(ALLOWED))).toBe(false);
    vi.stubEnv("AUTH_ALLOWED_GITHUB_ID", "");
    expect(await signIn(Number(ALLOWED))).toBe(false);
  });

  it("refuses a provider other than GitHub", async () => {
    vi.stubEnv("AUTH_ALLOWED_GITHUB_ID", ALLOWED);
    expect(await signIn(Number(ALLOWED), { ...github, provider: "google" })).toBe(false);
    expect(await signIn(Number(ALLOWED), null)).toBe(false);
  });
});

describe("jwt and session callbacks", () => {
  it("make the GitHub ID the session's user ID", async () => {
    const token = (await authConfig.callbacks!.jwt!({
      token: { sub: "random-uuid-from-auth-js" },
      user: { id: "random-uuid-from-auth-js" },
      account: github,
      profile: githubProfile(Number(ALLOWED)),
    } as ArgsOf<"jwt">)) as { sub?: string };
    expect(token.sub).toBe(ALLOWED);

    const session = (await authConfig.callbacks!.session!({
      session: { user: { name: "Owner" }, expires: "2027-01-07T00:00:00.000Z" },
      token,
    } as ArgsOf<"session">)) as Session;
    expect(session.user?.id).toBe(ALLOWED);
  });
});

describe("authorized callback (every request through proxy.ts)", () => {
  it("lets the allowlisted session through", async () => {
    vi.stubEnv("AUTH_ALLOWED_GITHUB_ID", ALLOWED);
    expect(await authorized(ALLOWED)).toBe(true);
  });

  it("turns away no session, another ID, and every session once the allowlist is emptied", async () => {
    vi.stubEnv("AUTH_ALLOWED_GITHUB_ID", ALLOWED);
    expect(await authorized(undefined)).toBe(false);
    expect(await authorized("7654321")).toBe(false);
    vi.stubEnv("AUTH_ALLOWED_GITHUB_ID", "");
    expect(await authorized(ALLOWED)).toBe(false);
  });
});
