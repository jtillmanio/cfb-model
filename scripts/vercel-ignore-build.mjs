// Vercel's Ignored Build Step (vercel.json `ignoreCommand`, D-126): skips a build whose changes
// are all docs/config, by the same rule CI uses to skip its build (scripts/lib/ci-scope.mjs). Each
// deployment stores its own copy of the functions, which count against Function Storage.
//
// Vercel reads the exit code: 0 skips the build, 1 builds. The diff starts at the branch's last
// successful deployment (VERCEL_GIT_PREVIOUS_SHA); on a branch's first build there is none, so it
// tries the merge base with origin/main. Anything it can't establish builds: skipping needs proof.
// Usage: node scripts/vercel-ignore-build.mjs   (run from anywhere inside the clone)
import { spawnSync } from "node:child_process";

import { isSkippable, needsBrowserAndBuild } from "./lib/ci-scope.mjs";

const git = (...args) => spawnSync("git", args, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
const ok = (...args) => git(...args).status === 0;
const hasCommit = (sha) => ok("cat-file", "-e", `${sha}^{commit}`);

/** The commit to diff from, or why there isn't one. @returns {{ base?: string, why: string }} */
function findBase() {
  const previous = (process.env.VERCEL_GIT_PREVIOUS_SHA ?? "").trim();
  if (previous) {
    // Vercel's clone is shallow; the previous deployment's commit may be older than its depth.
    if (hasCommit(previous) || (ok("fetch", "--quiet", "--depth=1", "origin", previous) && hasCommit(previous))) {
      return { base: previous, why: `the last deployment of this branch (${previous.slice(0, 7)})` };
    }
    return { why: `the last deployment's commit ${previous.slice(0, 7)} can't be fetched` };
  }
  const branch = (process.env.VERCEL_GIT_COMMIT_REF ?? "").trim();
  if (branch === "main") return { why: "main has no earlier deployment to compare with" };
  if (!ok("fetch", "--quiet", "--depth=200", "origin", "+refs/heads/main:refs/remotes/origin/main")) {
    return { why: "the first build of this branch, and origin/main can't be fetched" };
  }
  const base = git("merge-base", "origin/main", "HEAD");
  if (base.status !== 0) return { why: "the first build of this branch, with no merge base in reach" };
  return { base: base.stdout.trim(), why: "the merge base with origin/main" };
}

/** @returns {{ build: boolean, why: string }} */
function decide() {
  if (!ok("rev-parse", "--is-inside-work-tree")) return { build: true, why: "not a git checkout" };
  const { base, why } = findBase();
  if (!base) return { build: true, why };

  // --no-renames lists both sides of a rename, so src/a.ts -> docs/a.md can't read as docs-only.
  const diff = git("diff", "--name-only", "--no-renames", base, "HEAD");
  if (diff.status !== 0) return { build: true, why: `git diff from ${why} failed` };
  const files = diff.stdout.split("\n").map((line) => line.trim()).filter(Boolean);
  if (files.length === 0) return { build: true, why: `no changed files since ${why}` };
  if (needsBrowserAndBuild(files)) {
    return { build: true, why: `${files.find((file) => !isSkippable(file))} changed since ${why}` };
  }
  return { build: false, why: `${files.length} changed file(s) since ${why}, all docs/config` };
}

const { build, why } = decide();
console.log(`${build ? "build" : "skip"}: ${why}`);
process.exit(build ? 1 : 0);
