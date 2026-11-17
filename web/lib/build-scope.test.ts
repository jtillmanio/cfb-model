import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { needsPreviewBuild } from "../../scripts/lib/build-scope.mjs";

// Vercel's Ignored Build Step skips a preview whose changes can't reach the build (D-173,
// scripts/lib/build-scope.mjs, scripts/vercel-ignore.mjs). Production always builds.
const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const SCRIPT = join(ROOT, "scripts/vercel-ignore.mjs");

describe("needsPreviewBuild", () => {
  it("skips docs, .claude, backups and root markdown, as CI's scope step does", () => {
    expect(needsPreviewBuild(["docs/decisions.md", ".claude/kit.json", "backups/x.dump", "README.md"])).toBe(false);
  });

  it("skips CI files, the dev and CI scripts, the dispatcher, the root lint config and Python's tests", () => {
    for (const file of [
      ".github/workflows/lighthouse.yml",
      ".github/dependabot.yml",
      "scripts/perf/measure.mjs",
      "scripts/vercel-ignore.mjs",
      "infra/dispatcher/src/index.ts",
      ".vscode/settings.json",
      "eslint.config.mjs",
      "python/conftest.py",
      "python/api/tests/test_health.py",
      "python/db/tests/test_release.py",
      "python/engine/tests/fixtures/x.json",
    ]) {
      expect(needsPreviewBuild([file]), file).toBe(false);
    }
  });

  it("builds for anything the build reads: web/ (tests too, next build type-checks them), the API, migrations, configs, lockfiles", () => {
    for (const file of [
      "web/app/page.tsx",
      "web/lib/logos.test.ts",
      "web/e2e/teams.spec.ts",
      "web/playwright.config.ts",
      "web/public/robots.txt",
      "python/api/src/api/main.py",
      "python/db/migrations/versions/0007_x.py",
      "python/db/views/x.sql",
      "python/pyproject.toml",
      "python/uv.lock",
      "pnpm-lock.yaml",
      "package.json",
      "vercel.json",
      "design/sample-data.md",
    ]) {
      expect(needsPreviewBuild([file]), file).toBe(true);
    }
  });

  it("builds when the list is empty, when one app file hides among skippable ones, and for look-alikes", () => {
    expect(needsPreviewBuild([])).toBe(true);
    expect(needsPreviewBuild(["docs/a.md", ".github/x.yml", "web/lib/x.ts"])).toBe(true);
    for (const file of ["scripts-old/a.mjs", ".githubx/a.yml", "python/tests.py", "python/api/src/tests_util.py", "web/eslint.config.mjs"]) {
      expect(needsPreviewBuild([file]), file).toBe(true);
    }
  });

  it("reads Windows separators and a leading ./ like their forward-slash forms", () => {
    expect(needsPreviewBuild([".github\\workflows\\ci.yml", "./scripts/a.mjs"])).toBe(false);
    expect(needsPreviewBuild(["web\\app\\page.tsx"])).toBe(true);
  });
});

describe("scripts/vercel-ignore.mjs", () => {
  let dir: string;
  let base: string;
  const git = (...args: string[]) => {
    const run = spawnSync("git", args, { cwd: dir, encoding: "utf8" });
    expect(run.status, `git ${args.join(" ")}: ${run.stderr}`).toBe(0);
    return run.stdout.trim();
  };
  const write = (file: string, text = "x\n") => {
    mkdirSync(dirname(join(dir, file)), { recursive: true });
    writeFileSync(join(dir, file), text);
  };
  const ignore = (env: Record<string, string | undefined>) =>
    spawnSync(process.execPath, [SCRIPT], {
      cwd: dir,
      encoding: "utf8",
      env: { ...process.env, VERCEL_ENV: undefined, VERCEL_GIT_PREVIOUS_SHA: undefined, ...env },
    });
  /** Branch off the base commit, commit the given files, return the script's result as a preview. */
  const branch = (name: string, change: () => void) => {
    git("switch", "-q", "-c", name, base);
    change();
    git("add", "-A");
    git("commit", "-q", "-m", name);
    return ignore({ VERCEL_ENV: "preview", VERCEL_GIT_PREVIOUS_SHA: base });
  };

  beforeAll(() => {
    dir = mkdtempSync(join(tmpdir(), "vercel-ignore-"));
    git("init", "-q", "-b", "main");
    git("config", "user.email", "ci@example.com");
    git("config", "user.name", "ci");
    git("config", "commit.gpgsign", "false");
    write("web/app/page.tsx");
    write("docs/a.md");
    git("add", "-A");
    git("commit", "-q", "-m", "base");
    base = git("rev-parse", "HEAD");
  });
  afterAll(() => rmSync(dir, { recursive: true, force: true }));

  it("skips (exit 0) a preview push that touches only docs, CI and Python tests", () => {
    const run = branch("docs-ci", () => {
      write("docs/b.md");
      write(".github/workflows/lighthouse.yml");
      write("python/api/tests/test_x.py");
    });
    expect(run.stdout).toMatch(/^skip: 3 changed file\(s\)/);
    expect(run.status).toBe(0);
  }, 30_000);

  it("builds (exit 1) a preview push that touches app code too", () => {
    const run = branch("app", () => {
      write("docs/c.md");
      write("web/app/page.tsx", "changed\n");
    });
    expect(run.stdout).toMatch(/^build: web\/app\/page\.tsx can change the app/);
    expect(run.status).toBe(1);
  }, 30_000);

  it("builds when app code is renamed into docs: both sides of a rename count", () => {
    const run = branch("rename", () => git("mv", "web/app/page.tsx", "docs/page.md"));
    expect(run.stdout).toMatch(/^build: web\/app\/page\.tsx/);
    expect(run.status).toBe(1);
  }, 30_000);

  it("always builds production, and a preview it can't prove skippable", () => {
    git("switch", "-q", "docs-ci");
    const cases: [Record<string, string>, RegExp][] = [
      [{ VERCEL_ENV: "production", VERCEL_GIT_PREVIOUS_SHA: base }, /^build: production is not a preview/],
      [{}, /^build: no VERCEL_ENV is not a preview/],
      [{ VERCEL_ENV: "preview" }, /^build: no previous deployment/],
      [{ VERCEL_ENV: "preview", VERCEL_GIT_PREVIOUS_SHA: "0".repeat(40) }, /^build: 0{40} is not in this clone/],
      [{ VERCEL_ENV: "preview", VERCEL_GIT_PREVIOUS_SHA: git("rev-parse", "HEAD") }, /^build: no changed files/],
    ];
    for (const [env, why] of cases) {
      const run = ignore(env);
      expect(run.stdout, JSON.stringify(env)).toMatch(why);
      expect(run.status, JSON.stringify(env)).toBe(1);
    }
  }, 30_000);
});
