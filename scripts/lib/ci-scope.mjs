// Which pull requests need CI's slow steps (the browser install, the e2e suite, the production
// build) and which don't: a PR that touches only the paths below can't change what they test.
// scripts/ci-scope.mjs feeds this the real diff; web/lib/ci-scope.test.ts feeds it fixtures. No
// imports, so it runs on bare Node before `pnpm install`.
//
// The list is deliberately short. A path belongs on it only if neither the e2e suite (web/e2e,
// the API and the seed it starts) nor `next build` reads it. design/ is left off: the fixture
// seed's JSON cites it, and nothing here needs it skipped. .github/ is never on it, so a changed
// workflow, including ci.yml itself, runs the full gate. The steps that DO read docs/, .claude/
// and the root markdown (the task-file parse, pnpm test, pytest) are not gated at all.

/** Path prefixes (repo-relative, forward slashes) whose changes never need the slow steps. */
export const SKIP_PREFIXES = ["backups/", "docs/", ".claude/"];

/** Root-level markdown (README.md, CLAUDE.md, ...): a file name with no directory. */
export const SKIP_ROOT_MARKDOWN = /^[^/]+\.md$/i;

/** Whether a changed file can't affect the browser tests or the build. */
export function isSkippable(file) {
  const path = file.replaceAll("\\", "/").replace(/^\.\//, "");
  return SKIP_PREFIXES.some((prefix) => path.startsWith(prefix)) || SKIP_ROOT_MARKDOWN.test(path);
}

/**
 * True when the browser install, the e2e suite and the build must run: the diff is empty (nothing
 * proves it is docs-only) or any changed file is outside the skip list.
 * @param {string[]} files repo-relative paths from `git diff --name-only`
 */
export function needsBrowserAndBuild(files) {
  return files.length === 0 || files.some((file) => !isSkippable(file));
}
