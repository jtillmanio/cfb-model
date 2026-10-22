// CI's scope step (.github/workflows/ci.yml, id: scope): decides whether the browser install, the
// e2e suite and the build run. Prints `full: <why>` or `skip: <why>` and appends `full=true|false`
// to $GITHUB_OUTPUT. Anything it can't establish (no --base, a base that isn't in the clone, a
// failed diff) is `full`: skipping needs proof, running doesn't.
// Usage: node scripts/ci-scope.mjs [--base <ref>]
import { spawnSync } from "node:child_process";
import { appendFileSync } from "node:fs";

import { isSkippable, needsBrowserAndBuild } from "./lib/ci-scope.mjs";

/** @returns {{ full: boolean, why: string }} */
function decide(base) {
  if (!base) return { full: true, why: "no --base (a push, not a pull request)" };
  const git = (...args) => spawnSync("git", args, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });

  const known = git("rev-parse", "--verify", "--quiet", `${base}^{commit}`);
  if (known.status !== 0) return { full: true, why: `${base} is not in this clone` };

  // --no-renames lists both sides of a rename, so src/a.ts -> docs/a.md can't read as docs-only.
  const diff = git("diff", "--name-only", "--no-renames", `${base}...HEAD`);
  if (diff.status !== 0) {
    return { full: true, why: `git diff ${base}...HEAD failed: ${(diff.stderr || "").trim()}` };
  }

  const files = diff.stdout.split("\n").map((line) => line.trim()).filter(Boolean);
  if (files.length === 0) return { full: true, why: `no changed files against ${base}` };
  if (needsBrowserAndBuild(files)) {
    return { full: true, why: `${files.find((file) => !isSkippable(file))} is outside the skip list` };
  }
  return { full: false, why: `${files.length} changed file(s), all docs/config` };
}

const args = process.argv.slice(2);
const flag = args.indexOf("--base");
const base = flag === -1 ? "" : (args[flag + 1] ?? "");

const { full, why } = decide(base);
console.log(`${full ? "full" : "skip"}: ${why}`);
if (process.env.GITHUB_OUTPUT) appendFileSync(process.env.GITHUB_OUTPUT, `full=${full}\n`);
