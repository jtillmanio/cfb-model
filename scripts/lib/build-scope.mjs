// Which pushes Vercel can skip building as a preview (D-173): one whose every changed file is on
// the list below can't change what the preview serves. scripts/vercel-ignore.mjs feeds this the
// real diff; web/lib/build-scope.test.ts feeds it fixtures. No imports beyond ci-scope's list, so
// it runs on bare Node in Vercel's Ignored Build Step, before any install.
//
// A path belongs here only if nothing in the Vercel build reads it: not `next build` (which also
// type-checks every .ts under web/, tests and e2e specs included, so web/ is never on the list),
// not the migration step in vercel.json's buildCommand (python/db), not the API service
// (python/api). design/ is left off, as in ci-scope. The skip list is CI's (docs, .claude,
// backups, root markdown) plus CI files, the dev and CI scripts, the Cloudflare dispatcher, the
// root lint config, and Python's tests.

import { isSkippable } from "./ci-scope.mjs";

/** Prefixes beyond ci-scope's whose changes never reach a Vercel build. */
export const BUILD_SKIP_PREFIXES = [".github/", "scripts/", "infra/", ".vscode/"];

/** Root files the build never reads: the root lint config (web/ lints with its own). */
export const BUILD_SKIP_FILES = ["eslint.config.mjs"];

/** Python tests: a tests/ folder or conftest.py anywhere under python/. Never shipped or run. */
const PYTHON_TEST = /^python\/(?:.+\/)?(?:tests\/.+|conftest\.py)$/;

/** Whether a changed file can't change what a preview build serves. */
export function isBuildIrrelevant(file) {
  const path = file.replaceAll("\\", "/").replace(/^\.\//, "");
  return (
    isSkippable(path) ||
    BUILD_SKIP_PREFIXES.some((prefix) => path.startsWith(prefix)) ||
    BUILD_SKIP_FILES.includes(path) ||
    PYTHON_TEST.test(path)
  );
}

/**
 * True when the preview must build: the diff is empty (nothing proves it can be skipped) or any
 * changed file is outside the list.
 * @param {string[]} files repo-relative paths from `git diff --name-only`
 */
export function needsPreviewBuild(files) {
  return files.length === 0 || files.some((file) => !isBuildIrrelevant(file));
}
