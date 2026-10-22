import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { needsBrowserAndBuild } from "../../scripts/lib/ci-scope.mjs";

// CI skips the browser install, the e2e suite and the build on a PR that only touches docs/config
// (scripts/lib/ci-scope.mjs, .github/workflows/ci.yml). The job itself always runs.
const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const SCRIPT = join(ROOT, "scripts/ci-scope.mjs");
const CI = readFileSync(join(ROOT, ".github/workflows/ci.yml"), "utf8");

describe("needsBrowserAndBuild", () => {
  it("skips a PR that changes only docs, .claude, backups and root markdown", () => {
    expect(needsBrowserAndBuild(["docs/04-model.md", "docs/tasks/TASK-026.md"])).toBe(false);
    expect(needsBrowserAndBuild([".claude/rules/git.md", ".claude/kit.json"])).toBe(false);
    expect(needsBrowserAndBuild(["backups/2026-10-22.dump"])).toBe(false);
    expect(needsBrowserAndBuild(["README.md", "CLAUDE.md", "Notes.MD"])).toBe(false);
    expect(needsBrowserAndBuild(["README.md", "docs/decisions.md", ".claude/rules/web.md"])).toBe(false);
  });

  it("runs when the file list is empty: nothing proves the PR is docs-only", () => {
    expect(needsBrowserAndBuild([])).toBe(true);
  });

  it("runs for app code, the engine, migrations, seeds and the lockfiles", () => {
    for (const file of [
      "web/app/teams/page.tsx",
      "web/e2e/teams.spec.ts",
      "python/api/src/api/main.py",
      "python/db/migrations/versions/0004_x.py",
      "python/db/seeds/fixture/week6.json",
      "pnpm-lock.yaml",
      "python/uv.lock",
      "package.json",
      "vercel.json",
      "scripts/ci-scope.mjs",
    ]) {
      expect(needsBrowserAndBuild([file]), file).toBe(true);
    }
  });

  it("runs for .github/, so a changed workflow (ci.yml included) runs itself", () => {
    expect(needsBrowserAndBuild([".github/workflows/ci.yml"])).toBe(true);
    expect(needsBrowserAndBuild([".github/actions/start-postgres/action.yml"])).toBe(true);
    expect(needsBrowserAndBuild(["docs/a.md", ".github/dependabot.yml"])).toBe(true);
  });

  it("runs for design/, which the fixture seed cites, and for markdown inside app code", () => {
    expect(needsBrowserAndBuild(["design/sample-data.md"])).toBe(true);
    expect(needsBrowserAndBuild(["web/app/README.md"])).toBe(true);
    expect(needsBrowserAndBuild(["python/db/views/README.md"])).toBe(true);
  });

  it("runs when one app file hides among docs", () => {
    expect(needsBrowserAndBuild(["docs/a.md", "docs/b.md", "web/lib/x.ts"])).toBe(true);
  });

  it("doesn't skip a look-alike: docs-old/, .claudeX/, a root file that merely contains .md", () => {
    expect(needsBrowserAndBuild(["docs-old/a.md"])).toBe(true);
    expect(needsBrowserAndBuild([".claudeX/a.md"])).toBe(true);
    expect(needsBrowserAndBuild(["notes.md.ts"])).toBe(true);
  });

  it("reads Windows separators and a leading ./ like their forward-slash forms", () => {
    expect(needsBrowserAndBuild(["docs\\a.md", "./README.md"])).toBe(false);
    expect(needsBrowserAndBuild(["web\\app\\page.tsx"])).toBe(true);
  });
});

describe("scripts/ci-scope.mjs", () => {
  let dir: string;
  let out: string; // GITHUB_OUTPUT files live outside the repo so `git add -A` can't commit them
  const git = (...args: string[]) => {
    const run = spawnSync("git", args, { cwd: dir, encoding: "utf8" });
    expect(run.status, `git ${args.join(" ")}: ${run.stderr}`).toBe(0);
  };
  const write = (file: string, text = "x\n") => {
    mkdirSync(dirname(join(dir, file)), { recursive: true });
    writeFileSync(join(dir, file), text);
  };
  const scope = (args: string[], output?: string) =>
    spawnSync(process.execPath, [SCRIPT, ...args], {
      cwd: dir,
      encoding: "utf8",
      env: { ...process.env, GITHUB_OUTPUT: output ?? "" },
    });
  /** Branch off main, commit the given files, return the script's result against main. */
  const branch = (name: string, change: () => void, output?: string) => {
    git("switch", "-q", "-c", name, "main");
    change();
    git("add", "-A");
    git("commit", "-q", "-m", name);
    return scope(["--base", "main"], output);
  };

  beforeAll(() => {
    dir = mkdtempSync(join(tmpdir(), "ci-scope-"));
    out = mkdtempSync(join(tmpdir(), "ci-scope-out-"));
    git("init", "-q", "-b", "main");
    git("config", "user.email", "ci@example.com");
    git("config", "user.name", "ci");
    git("config", "commit.gpgsign", "false");
    write("web/app/page.tsx");
    write("docs/a.md");
    git("add", "-A");
    git("commit", "-q", "-m", "base");
  });
  afterAll(() => {
    rmSync(dir, { recursive: true, force: true });
    rmSync(out, { recursive: true, force: true });
  });

  it("prints skip and writes full=false for a docs-only branch", () => {
    const output = join(out, "docs");
    const run = branch("docs-only", () => {
      write("docs/b.md");
      write("README.md");
    }, output);
    expect(run.status).toBe(0);
    expect(run.stdout).toMatch(/^skip: /);
    expect(readFileSync(output, "utf8")).toBe("full=false\n");
  }, 30_000);

  it("prints full and writes full=true when app code changed too", () => {
    const output = join(out, "app");
    const run = branch("app", () => {
      write("docs/c.md");
      write("web/app/page.tsx", "changed\n");
    }, output);
    expect(run.stdout).toMatch(/^full: web\/app\/page\.tsx/);
    expect(readFileSync(output, "utf8")).toBe("full=true\n");
  }, 30_000);

  it("is full when a workflow changed", () => {
    const run = branch("workflow", () => write(".github/workflows/ci.yml"));
    expect(run.stdout).toMatch(/^full: \.github\/workflows\/ci\.yml/);
  }, 30_000);

  it("is full when app code is renamed into docs: both sides of a rename count", () => {
    const run = branch("rename", () => {
      git("mv", "web/app/page.tsx", "docs/page.md");
    });
    expect(run.stdout).toMatch(/^full: web\/app\/page\.tsx/);
  }, 30_000);

  it("is full with no --base, with a base that isn't in the clone, and with no diff", () => {
    const output = join(out, "none");
    expect(scope([], output).stdout).toMatch(/^full: no --base/);
    expect(readFileSync(output, "utf8")).toBe("full=true\n");
    expect(scope(["--base"]).stdout).toMatch(/^full: /);
    expect(scope(["--base", "origin/nope"]).stdout).toMatch(/^full: origin\/nope is not in this clone/);
    git("switch", "-q", "main");
    expect(scope(["--base", "main"]).stdout).toMatch(/^full: no changed files/);
  }, 30_000);

  it("is full outside a git repository", () => {
    const bare = mkdtempSync(join(tmpdir(), "ci-scope-bare-"));
    try {
      const run = spawnSync(process.execPath, [SCRIPT, "--base", "origin/main"], {
        cwd: bare,
        encoding: "utf8",
        env: { ...process.env, GITHUB_OUTPUT: "", GIT_CEILING_DIRECTORIES: dirname(bare) },
      });
      expect(run.status).toBe(0);
      expect(run.stdout).toMatch(/^full: /);
    } finally {
      rmSync(bare, { recursive: true, force: true });
    }
  }, 30_000);
});

describe(".github/workflows/ci.yml", () => {
  /** The job's steps as text, one entry per `      - ` item. */
  const steps = CI.slice(CI.indexOf("\n    steps:\n") + "\n    steps:\n".length)
    .split("\n")
    .filter((line) => !line.trimStart().startsWith("#"))
    .join("\n")
    .split(/\n(?=      - )/)
    .map((step) => step.replace(/^\n+/, ""));
  const name = (step: string) => /^ {6}- (?:name: (.+)|uses: (\S+)|run: (.+))/.exec(step)?.slice(1).find(Boolean);
  const gated = steps.filter((s) => s.includes("steps.scope.outputs.full"));

  it("gates exactly the browser install, the build, the e2e run and the e2e artifact upload", () => {
    expect(gated.map(name)).toEqual([
      "Install the e2e browser",
      "Build",
      "End-to-end tests",
      "actions/upload-artifact@v7",
    ]);
    expect(gated[0]).toContain("playwright install");
    expect(gated[1]).toContain("run: pnpm build");
    expect(gated[2]).toContain("run: pnpm test:e2e");
    expect(gated[3]).toMatch(/if: failure\(\) && steps\.scope\.outputs\.full == 'true'/);
    for (const step of gated.slice(0, 3)) {
      expect(step).toMatch(/^ {8}if: steps\.scope\.outputs\.full == 'true'$/m);
    }
  });

  it("leaves every other step ungated, including the install, the checks and the task-file parse", () => {
    const rest = steps.filter((s) => !gated.includes(s)).map((s) => name(s) ?? s);
    expect(rest).toEqual(
      expect.arrayContaining([
        "actions/checkout@v7",
        "Task files parse cleanly",
        "Install",
        "Merged migrations unchanged",
        "Migrate the test DB",
        "Seed the fixture",
        "pnpm typecheck",
        "pnpm lint",
        "pnpm test",
      ]),
    );
    for (const step of steps.filter((s) => !gated.includes(s))) {
      expect(step, name(step)).not.toContain("steps.scope");
      expect(step, name(step)).not.toMatch(/^ {8}if:/m);
    }
    // Playwright's browser is the only thing taken out of Install.
    expect(steps.find((s) => name(s) === "Install")).not.toContain("playwright");
  });

  it("runs the scope step after checkout and Node setup, before anything it gates", () => {
    const order = steps.map(name);
    const scope = order.indexOf("Scope (do the browser and build steps run?)");
    expect(scope).toBeGreaterThan(order.indexOf("actions/checkout@v7"));
    expect(scope).toBeGreaterThan(order.indexOf("actions/setup-node@v7"));
    expect(scope).toBeLessThan(order.indexOf("Install the e2e browser"));
    expect(steps[scope]).toContain("id: scope");
    expect(steps[scope]).toContain(
      "node scripts/ci-scope.mjs ${{ github.event_name == 'pull_request' && '--base origin/main' || '' }}",
    );
  });

  it("fetches full history so origin/main exists for the diff", () => {
    expect(steps[0]).toContain("fetch-depth: 0");
  });

  it("keeps the job running on every PR: no paths filter, no job-level if", () => {
    expect(CI).not.toMatch(/^\s*paths(-ignore)?:/m);
    const job = CI.slice(CI.indexOf("  verify:\n"), CI.indexOf("\n    steps:\n"));
    expect(job).not.toMatch(/^ {4}if:/m);
    expect(job).toContain("name: verify");
  });
});
