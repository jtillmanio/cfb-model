import { execFile } from "node:child_process";
import { mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { decode, encode } from "next-auth/jwt";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  devSecrets,
  devSessionCookie,
  loopbackOrigin,
  main,
  SESSION_COOKIE,
} from "../e2e/dev-session.mjs";

// The ui-verifier's dev sign-in (02 › Testing strategy › Test-only sign-in and clock; TASK-010):
// a mint that works only on loopback, only with .env.local's dev secret, and never in web/ source.

const WEB = fileURLToPath(new URL("..", import.meta.url));
const SCRIPT = join(WEB, "e2e", "dev-session.mjs");
const SECRET = "dev-only-secret-for-the-dev-session-test-0001";
const GITHUB_ID = "4242";

const tempDirs: string[] = [];
function envFile(text: string): string {
  const dir = mkdtempSync(join(tmpdir(), "dev-session-"));
  tempDirs.push(dir);
  const path = join(dir, ".env.local");
  writeFileSync(path, text);
  return path;
}

function streams() {
  const out = { stdout: "", stderr: "" };
  return {
    out,
    io: {
      stdout: { write: (s: string) => ((out.stdout += s), true) },
      stderr: { write: (s: string) => ((out.stderr += s), true) },
    },
  };
}

afterEach(() => {
  vi.unstubAllEnvs();
  for (const dir of tempDirs.splice(0)) rmSync(dir, { recursive: true, force: true });
});

describe("loopbackOrigin", () => {
  it.each(["http://localhost:3210", "http://127.0.0.1:3210/teams", "http://[::1]:3210"])("accepts %s", (url) => {
    expect(loopbackOrigin(url)).toBe(new URL(url).origin);
  });

  it.each([
    ["https://127.0.0.1:3210", /http:/],
    ["https://cfb-model.vercel.app", /http:/],
    ["http://example.com", /loopback/],
    ["http://10.0.0.5:3000", /loopback/],
    ["http://localhost.example.com", /loopback/],
    ["not a url", /not a URL/],
  ])("refuses %s", (url, reason) => {
    expect(() => loopbackOrigin(url)).toThrow(reason);
  });
});

describe("devSecrets", () => {
  it("reads both variables", () => {
    const text = `# dev\nDATABASE_URL=postgres://x\nAUTH_SECRET="${SECRET}"\nAUTH_ALLOWED_GITHUB_ID=${GITHUB_ID}\n`;
    expect(devSecrets(text)).toEqual({ secret: SECRET, githubId: GITHUB_ID });
  });

  it.each([
    ["AUTH_SECRET", `AUTH_ALLOWED_GITHUB_ID=${GITHUB_ID}\n`],
    ["AUTH_ALLOWED_GITHUB_ID", `AUTH_SECRET=${SECRET}\n`],
    ["AUTH_SECRET", `AUTH_SECRET=\nAUTH_ALLOWED_GITHUB_ID=${GITHUB_ID}\n`],
  ])("refuses without %s, naming it but not printing the other value", (missing, text) => {
    let message = "";
    try {
      devSecrets(text);
    } catch (e) {
      message = (e as Error).message;
    }
    expect(message).toContain(missing);
    expect(message).not.toContain(SECRET);
  });
});

describe("devSessionCookie", () => {
  it("is the Playwright cookie Auth.js would set, valid for 1 hour", async () => {
    const now = 1_800_000_000_000;
    const cookie = await devSessionCookie({ url: "http://127.0.0.1:3210", secret: SECRET, githubId: GITHUB_ID, encode, now });
    expect(cookie).toEqual({
      name: SESSION_COOKIE,
      value: expect.any(String),
      url: "http://127.0.0.1:3210",
      httpOnly: true,
      sameSite: "Lax",
      expires: now / 1000 + 3600,
    });
    expect(SESSION_COOKIE).toBe("authjs.session-token");
  });

  it("decodes with the secret it was minted with and no other (D-012)", async () => {
    const cookie = await devSessionCookie({ url: "http://127.0.0.1:3210", secret: SECRET, githubId: GITHUB_ID, encode });
    const token = await decode({ token: cookie.value, secret: SECRET, salt: SESSION_COOKIE });
    expect(token?.sub).toBe(GITHUB_ID);
    expect((token?.exp ?? 0) - (token?.iat ?? 0)).toBe(3600);
    await expect(
      decode({ token: cookie.value, secret: "the-preview-or-production-secret-0001", salt: SESSION_COOKIE }),
    ).rejects.toThrow();
  });
});

describe("main", () => {
  const goodEnv = `AUTH_SECRET=${SECRET}\nAUTH_ALLOWED_GITHUB_ID=${GITHUB_ID}\n`;

  it("prints exactly one line, the cookie as JSON, and never the secret", async () => {
    const { out, io } = streams();
    const code = await main(envFile(goodEnv), { argv: ["http://localhost:3210"], ...io });
    expect(code).toBe(0);
    expect(out.stderr).toBe("");
    expect(out.stdout.endsWith("\n")).toBe(true);
    expect(out.stdout.trimEnd().split("\n")).toHaveLength(1);
    expect(out.stdout).not.toContain(SECRET);
    const cookie = JSON.parse(out.stdout);
    expect(cookie).toMatchObject({ name: SESSION_COOKIE, url: "http://localhost:3210", httpOnly: true, sameSite: "Lax" });
    expect((await decode({ token: cookie.value, secret: SECRET, salt: SESSION_COOKIE }))?.sub).toBe(GITHUB_ID);
  });

  it.each([
    ["a non-loopback URL", ["https://example.com"], goodEnv, /loopback|http:/],
    ["no URL", [], goodEnv, /usage/],
    ["a second argument, such as a file flag", ["http://localhost:3210", "--env-file=.env.live"], goodEnv, /usage/],
    ["no AUTH_SECRET in .env.local", ["http://localhost:3210"], `AUTH_ALLOWED_GITHUB_ID=${GITHUB_ID}\n`, /AUTH_SECRET/],
    ["no AUTH_ALLOWED_GITHUB_ID in .env.local", ["http://localhost:3210"], `AUTH_SECRET=${SECRET}\n`, /AUTH_ALLOWED_GITHUB_ID/],
  ])("refuses %s: exit 1, reason on stderr, nothing on stdout", async (_, argv, env, reason) => {
    const { out, io } = streams();
    const code = await main(envFile(env), { argv, ...io });
    expect(code).toBe(1);
    expect(out.stdout).toBe("");
    expect(out.stderr).toMatch(/^dev-session: /);
    expect(out.stderr).toMatch(reason);
    expect(out.stderr).not.toContain(SECRET);
  });

  it("refuses when .env.local is missing", async () => {
    const { out, io } = streams();
    const missing = join(mkdtempSync(join(tmpdir(), "dev-session-")), ".env.local");
    tempDirs.push(join(missing, ".."));
    expect(await main(missing, { argv: ["http://localhost:3210"], ...io })).toBe(1);
    expect(out.stdout).toBe("");
    expect(out.stderr).toMatch(/\.env\.local/);
  });

  it("never falls back to the process environment", async () => {
    vi.stubEnv("AUTH_SECRET", SECRET);
    vi.stubEnv("AUTH_ALLOWED_GITHUB_ID", GITHUB_ID);
    const { out, io } = streams();
    expect(await main(envFile("DATABASE_URL=postgres://x\n"), { argv: ["http://localhost:3210"], ...io })).toBe(1);
    expect(out.stdout).toBe("");
  });

  it("refuses a production URL when run as a script", async () => {
    const run = promisify(execFile)(process.execPath, [SCRIPT, "https://example.com"], { cwd: WEB });
    await expect(run).rejects.toMatchObject({ code: 1, stdout: "", stderr: expect.stringMatching(/^dev-session: .*http:/) });
  });
});

// The mint stays test tooling: no app source imports from e2e/ (TASK-010 AC-3).
const E2E_IMPORT = /(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s+|\brequire\s*\(\s*)["'][^"']*\be2e\//;
const APP_ROOTS = ["app", "lib"];
const APP_FILES = ["proxy.ts", "auth.ts", "auth.config.ts"];

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.(ts|tsx|mts|js|mjs)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : [];
  });
}

describe("app source never imports from e2e/", () => {
  it.each([
    `import { mintSessionCookie } from "../e2e/fixtures";`,
    `import { main } from "@/e2e/dev-session.mjs";`,
    `export { devSecrets } from '../../e2e/dev-session.mjs';`,
    `const m = await import("../e2e/dev-session.mjs");`,
    `import "../e2e/side-effect";`,
  ])("the scan catches %s", (line) => {
    expect(line).toMatch(E2E_IMPORT);
  });

  it.each([`import { encode } from "next-auth/jwt";`, `// see web/e2e/fixtures.ts`, `const e2e = "/e2e/";`])(
    "the scan ignores %s",
    (line) => {
      expect(line).not.toMatch(E2E_IMPORT);
    },
  );

  it("holds for web/app, web/lib, proxy.ts, auth.ts and auth.config.ts", () => {
    const files = [...APP_ROOTS.flatMap((root) => sourceFiles(join(WEB, root))), ...APP_FILES.map((f) => join(WEB, f))];
    expect(files.length).toBeGreaterThan(APP_FILES.length);
    const offenders = files.filter((file) => E2E_IMPORT.test(readFileSync(file, "utf8"))).map((f) => relative(WEB, f));
    expect(offenders).toEqual([]);
  });
});
