import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

// Vercel skips a build whose changes are all docs/config (scripts/vercel-ignore-build.mjs, D-126):
// exit 0 skips, exit 1 builds. Each case clones a local "origin" the way Vercel clones GitHub.
const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const SCRIPT = join(ROOT, "scripts/vercel-ignore-build.mjs");

describe("scripts/vercel-ignore-build.mjs", () => {
  let tmp: string;
  let origin: string;
  let cases = 0;

  const git = (cwd: string, ...args: string[]) => {
    const run = spawnSync("git", args, { cwd, encoding: "utf8" });
    expect(run.status, `git ${args.join(" ")}: ${run.stderr}`).toBe(0);
    return run.stdout.trim();
  };
  const write = (repo: string, file: string, text = "x\n") => {
    mkdirSync(dirname(join(repo, file)), { recursive: true });
    writeFileSync(join(repo, file), text);
  };
  const commit = (repo: string, files: string[], message: string) => {
    for (const file of files) write(repo, file, `${message}\n`);
    git(repo, "add", "-A");
    git(repo, "commit", "-q", "-m", message);
    return git(repo, "rev-parse", "HEAD");
  };
  /** A fresh clone of origin on a new branch, as Vercel checks out a pushed branch. */
  const clone = (branch = `b${++cases}`) => {
    const repo = join(tmp, `clone-${++cases}`);
    git(tmp, "clone", "-q", origin, repo);
    git(repo, "config", "user.email", "ci@example.com");
    git(repo, "config", "user.name", "ci");
    git(repo, "config", "commit.gpgsign", "false");
    if (branch !== "main") git(repo, "switch", "-q", "-c", branch);
    return repo;
  };
  const ignore = (repo: string, env: Record<string, string> = {}, cwd = repo) => {
    const clean = { ...process.env };
    for (const key of Object.keys(clean)) if (key.startsWith("VERCEL_")) delete clean[key];
    return spawnSync(process.execPath, [SCRIPT], { cwd, encoding: "utf8", env: { ...clean, ...env } });
  };

  beforeAll(() => {
    tmp = mkdtempSync(join(tmpdir(), "vercel-ignore-"));
    const seed = join(tmp, "seed");
    origin = join(tmp, "origin.git");
    git(tmp, "init", "-q", "-b", "main", seed);
    git(seed, "config", "user.email", "ci@example.com");
    git(seed, "config", "user.name", "ci");
    git(seed, "config", "commit.gpgsign", "false");
    commit(seed, ["web/app/page.tsx", "docs/a.md"], "base");
    git(tmp, "clone", "-q", "--bare", seed, origin);
  });
  afterAll(() => {
    rmSync(tmp, { recursive: true, force: true });
  });

  it("skips when everything since the branch's last deployment is docs/config", () => {
    const repo = clone();
    const deployed = commit(repo, ["web/app/page.tsx"], "code");
    commit(repo, ["docs/b.md", "README.md", ".claude/kit.json"], "docs");
    const run = ignore(repo, { VERCEL_GIT_PREVIOUS_SHA: deployed, VERCEL_GIT_COMMIT_REF: "b" });
    expect(run.stdout).toMatch(/^skip: 3 changed file\(s\) since the last deployment/);
    expect(run.status).toBe(0);
  }, 30_000);

  it("builds when app code changed since the last deployment", () => {
    const repo = clone();
    const deployed = commit(repo, ["docs/b.md"], "docs");
    commit(repo, ["docs/c.md", "python/api/src/api/main.py"], "code");
    const run = ignore(repo, { VERCEL_GIT_PREVIOUS_SHA: deployed });
    expect(run.stdout).toMatch(/^build: python\/api\/src\/api\/main\.py changed since/);
    expect(run.status).toBe(1);
  }, 30_000);

  it("builds for vercel.json, workflows and design/, which the shared rule never skips", () => {
    for (const file of ["vercel.json", ".github/workflows/ci.yml", "design/sample-data.md"]) {
      const repo = clone();
      const deployed = git(repo, "rev-parse", "HEAD");
      commit(repo, [file], file);
      expect(ignore(repo, { VERCEL_GIT_PREVIOUS_SHA: deployed }).status, file).toBe(1);
    }
  }, 30_000);

  it("on a branch's first build, skips a docs-only branch by its merge base with origin/main", () => {
    const repo = clone();
    commit(repo, ["docs/b.md"], "one");
    commit(repo, ["docs/c.md"], "two");
    const run = ignore(repo, { VERCEL_GIT_COMMIT_REF: "b" });
    expect(run.stdout).toMatch(/^skip: 2 changed file\(s\) since the merge base with origin\/main/);
    expect(run.status).toBe(0);
  }, 30_000);

  it("on a branch's first build, builds when any commit on the branch changed code", () => {
    const repo = clone();
    commit(repo, ["web/lib/x.ts"], "code");
    commit(repo, ["docs/b.md"], "docs");
    const run = ignore(repo, { VERCEL_GIT_COMMIT_REF: "b" });
    expect(run.stdout).toMatch(/^build: web\/lib\/x\.ts changed since the merge base/);
    expect(run.status).toBe(1);
  }, 30_000);

  it("builds main's first deployment: there is nothing to compare with", () => {
    const repo = clone("main");
    commit(repo, ["docs/b.md"], "docs");
    const run = ignore(repo, { VERCEL_GIT_COMMIT_REF: "main" });
    expect(run.stdout).toMatch(/^build: main has no earlier deployment/);
    expect(run.status).toBe(1);
  }, 30_000);

  it("builds when origin/main can't be fetched or the last deployment's commit is gone", () => {
    const repo = clone();
    commit(repo, ["docs/b.md"], "docs");
    git(repo, "remote", "remove", "origin");
    expect(ignore(repo, { VERCEL_GIT_COMMIT_REF: "b" }).stdout).toMatch(/^build: .*can't be fetched/);
    const gone = "0123456789abcdef0123456789abcdef01234567";
    const run = ignore(repo, { VERCEL_GIT_PREVIOUS_SHA: gone });
    expect(run.stdout).toMatch(/^build: the last deployment's commit 0123456 can't be fetched/);
    expect(run.status).toBe(1);
  }, 30_000);

  it("builds when the last deployment is this commit (a redeploy)", () => {
    const repo = clone();
    const head = commit(repo, ["docs/b.md"], "docs");
    expect(ignore(repo, { VERCEL_GIT_PREVIOUS_SHA: head }).status).toBe(1);
  }, 30_000);

  it("works from a service root below the repository root", () => {
    const repo = clone();
    const deployed = git(repo, "rev-parse", "HEAD");
    commit(repo, ["docs/b.md"], "docs");
    expect(ignore(repo, { VERCEL_GIT_PREVIOUS_SHA: deployed }, join(repo, "web")).status).toBe(0);
  }, 30_000);

  it("builds outside a git repository", () => {
    const bare = mkdtempSync(join(tmpdir(), "vercel-ignore-bare-"));
    try {
      const run = spawnSync(process.execPath, [SCRIPT], {
        cwd: bare,
        encoding: "utf8",
        env: { ...process.env, GIT_CEILING_DIRECTORIES: dirname(bare) },
      });
      expect(run.stdout).toMatch(/^build: not a git checkout/);
      expect(run.status).toBe(1);
    } finally {
      rmSync(bare, { recursive: true, force: true });
    }
  }, 30_000);
});

describe("vercel.json", () => {
  it("runs the script as every service's Ignored Build Step, from the repository root", () => {
    const config = JSON.parse(readFileSync(join(ROOT, "vercel.json"), "utf8"));
    // With `services`, a top-level ignoreCommand fails the deployment: it must sit on each service.
    // The same command on both, so the services always build or skip together.
    expect(config.ignoreCommand).toBeUndefined();
    const services = Object.keys(config.services);
    expect(services).toEqual(["web", "api"]);
    for (const name of services) {
      expect(config.services[name].ignoreCommand, name).toBe(
        'node "$(git rev-parse --show-toplevel)/scripts/vercel-ignore-build.mjs"',
      );
    }
  });
});
