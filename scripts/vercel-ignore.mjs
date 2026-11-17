// Vercel's Ignored Build Step (D-173; Vercel › Settings › Git › Ignored Build Step, command
// `node scripts/vercel-ignore.mjs`). Exit 0 tells Vercel to skip the build, exit 1 to build.
//
// Skips only a preview, and only when every file changed since the branch's last successful
// deployment (VERCEL_GIT_PREVIOUS_SHA) is on scripts/lib/build-scope.mjs' list. Production (main)
// always builds: release.yml promotes a main commit's own build. Anything it can't establish (not
// a preview, no previous deployment, a commit outside Vercel's shallow clone, a failed diff, no
// changed files) builds: skipping needs proof, building doesn't. A crash exits 1, which builds.
//
// Usage: node scripts/vercel-ignore.mjs   (reads VERCEL_ENV and VERCEL_GIT_PREVIOUS_SHA)
import { spawnSync } from "node:child_process";

import { isBuildIrrelevant, needsPreviewBuild } from "./lib/build-scope.mjs";

/** @returns {{ build: boolean, why: string }} */
function decide() {
  const { VERCEL_ENV: target, VERCEL_GIT_PREVIOUS_SHA: base } = process.env;
  if (target !== "preview") return { build: true, why: `${target || "no VERCEL_ENV"} is not a preview` };
  if (!base) return { build: true, why: "no previous deployment on this branch" };
  /** @param {string[]} args */
  const git = (...args) => spawnSync("git", args, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });

  if (git("rev-parse", "--verify", "--quiet", `${base}^{commit}`).status !== 0) {
    return { build: true, why: `${base} is not in this clone` };
  }
  // --no-renames lists both sides of a rename, so web/a.ts -> docs/a.md can't read as docs-only.
  const diff = git("diff", "--name-only", "--no-renames", base, "HEAD");
  if (diff.status !== 0) return { build: true, why: `git diff ${base} HEAD failed: ${(diff.stderr || "").trim()}` };

  const files = diff.stdout.split("\n").map((line) => line.trim()).filter(Boolean);
  if (files.length === 0) return { build: true, why: `no changed files since ${base}` };
  if (needsPreviewBuild(files)) {
    return { build: true, why: `${files.find((file) => !isBuildIrrelevant(file))} can change the app` };
  }
  return { build: false, why: `${files.length} changed file(s) since ${base}, none of them read by the build` };
}

const { build, why } = decide();
console.log(`${build ? "build" : "skip"}: ${why}`);
process.exit(build ? 1 : 0);
