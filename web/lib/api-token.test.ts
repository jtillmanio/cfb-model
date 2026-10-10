import { decodeProtectedHeader, jwtVerify } from "jose";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { API_TOKEN_AUDIENCE, API_TOKEN_ISSUER } from "./api-token";
import { getHealth, getTeams } from "./api";

// `server-only` throws outside React's server build; `@/auth` would load all of Auth.js. The
// session is whatever `auth()` resolves to in each test.
const { auth } = vi.hoisted(() => ({ auth: vi.fn() }));
vi.mock("server-only", () => ({}));
vi.mock("@/auth", () => ({ auth }));

const SECRET = "vitest-only-api-jwt-secret-0123456789abcdef";
const OWNER_ID = "4242";

const fetchMock = vi.fn<typeof fetch>();

function okResponse(): Response {
  return new Response(JSON.stringify({ teams: [] }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function bearerToken(call: number): string {
  const init = fetchMock.mock.calls[call][1];
  const header = new Headers(init?.headers).get("authorization");
  expect(header).toMatch(/^Bearer \S+$/);
  return header!.slice("Bearer ".length);
}

async function verified(token: string) {
  const { payload } = await jwtVerify(token, new TextEncoder().encode(SECRET), {
    issuer: API_TOKEN_ISSUER,
    audience: API_TOKEN_AUDIENCE,
    algorithms: ["HS256"],
  });
  return payload;
}

beforeEach(() => {
  vi.stubEnv("API_JWT_SECRET", SECRET);
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockImplementation(async () => okResponse());
  auth.mockResolvedValue({ user: { id: OWNER_ID }, expires: "2099-01-01T00:00:00.000Z" });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  auth.mockReset();
});

describe("signed API calls", () => {
  it("send an HS256 Bearer token for the session's GitHub user (AC-1)", async () => {
    await getTeams();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const token = bearerToken(0);
    expect(decodeProtectedHeader(token).alg).toBe("HS256");
    const payload = await verified(token);
    expect(payload.sub).toBe(OWNER_ID);
  });

  it("live at most 300 seconds (AC-2)", async () => {
    await getTeams();

    const { iat, exp } = await verified(bearerToken(0));
    expect(typeof iat).toBe("number");
    expect(typeof exp).toBe("number");
    expect(exp! - iat!).toBeGreaterThan(0);
    expect(exp! - iat!).toBeLessThanOrEqual(300);
  });

  it("mint a fresh token for every request (AC-2)", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-10T12:00:00Z"));
    await getTeams();
    vi.setSystemTime(new Date("2026-10-10T12:00:02Z"));
    await getTeams();

    const first = bearerToken(0);
    const second = bearerToken(1);
    expect(second).not.toBe(first);
    // Verified against the fake clock, so the 60 s lifetime hasn't run out.
    expect((await verified(first)).iat).toBe(Date.parse("2026-10-10T12:00:00Z") / 1000);
    expect((await verified(second)).iat).toBe(Date.parse("2026-10-10T12:00:02Z") / 1000);
  });
});

describe("refused before any request is sent (AC-3)", () => {
  it("throws without a session", async () => {
    auth.mockResolvedValue(null);

    const error = await getTeams().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(Error);
    expect((error as Error).message).not.toContain(SECRET);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("throws when the session has no GitHub user ID", async () => {
    auth.mockResolvedValue({ user: { id: "" }, expires: "2099-01-01T00:00:00.000Z" });

    await expect(getTeams()).rejects.toThrow();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    ["unset", undefined],
    ["empty", ""],
  ])("throws when API_JWT_SECRET is %s", async (_label, value) => {
    vi.stubEnv("API_JWT_SECRET", value);

    await expect(getTeams()).rejects.toThrow(/API_JWT_SECRET/);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("throws on a secret too short for HS256, without echoing it", async () => {
    const short = "short-secret-value";
    vi.stubEnv("API_JWT_SECRET", short);

    const error = await getTeams().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(Error);
    expect((error as Error).message).toMatch(/API_JWT_SECRET/);
    expect((error as Error).message).not.toContain(short);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("health", () => {
  it("stays unsigned: the one route open without a session (02 › Auth)", async () => {
    auth.mockResolvedValue(null);
    fetchMock.mockImplementation(
      async () => new Response(JSON.stringify({ commit: "x", db_reachable: true, migration_head: null })),
    );

    await getHealth();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).has("authorization")).toBe(false);
    expect(auth).not.toHaveBeenCalled();
  });
});
