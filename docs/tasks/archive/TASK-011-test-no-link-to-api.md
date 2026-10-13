---
id: TASK-011
title: Add the test that forbids <Link> to /api/
status: Done
depends_on: []
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: e02e2dc
---

# TASK-011 — Add the test that forbids <Link> to /api/

## Goal

A test fails whenever web source renders a Next.js `<Link>` to anything under `/api/`, so the rule in `.claude/rules/web.md` is enforced, not only stated.

## Context

- *From #18 (TASK-007):* `.claude/rules/web.md` says "Never use `<Link>` to anything under `/api/`, because prefetch runs the handler. Use a plain `<a>`; a test enforces this", but no such test exists. `ledger` has one to borrow from: `no-prefetched-handlers.test.ts`.
- Rules: `.claude/rules/web.md`.
- Existing tests: Vitest files beside the code in `web/lib/*.test.ts`.
- Today no web source imports `next/link`, so the scan of the tree passes from the start; the matcher's own cases are what prove it catches an offender.

## Acceptance criteria

- [x] AC-1: `web/lib/no-prefetched-handlers.test.ts` scans every `.ts` and `.tsx` file under `web/app/`, `web/lib/` and `web/components/` (when it exists), skipping `*.test.*` files, and fails with `<file>:<line>` for each `next/link` element whose `href` points under `/api/`. The element is matched by the name `next/link`'s default import is bound to in that file (`Link`, `NextLink`, …).
- [x] AC-2: The matcher is tested on inline sources. It flags `href="/api/x"`, `href={"/api/x"}`, `` href={`/api/${id}`} ``, `href={{ pathname: "/api/x" }}`, an `href` on a later line of a multi-line tag, and `<NextLink href="/api/x">` when `next/link` is imported as `NextLink`. It doesn't flag `<a href="/api/x">`, `<Link href="/teams">`, `<Link href="/apiary">`, `<LinkButton href="/api/x">`, or `<Link href="/api/x">` in a file that doesn't import `next/link`.
- [x] AC-3: The suite passes on the current tree, and the `<Link>` line in `.claude/rules/web.md` names the test file.

## Out of scope

- Changing any existing link or route.
- A wrapper component that renders `next/link` with a caller's `href` (none exists; the rule applies when one is written).

## Files likely touched

- `web/lib/no-prefetched-handlers.test.ts` — the new test
- `.claude/rules/web.md` — name the test

## Verification

- Automated: `pnpm --dir web exec vitest run lib/no-prefetched-handlers.test.ts`.
- Manual: on the branch, a throwaway `<Link href="/api/py/health">` (with `import Link from "next/link"`) in `web/app/teams/page.tsx` makes the test fail naming `app/teams/page.tsx:<line>`; reverting it makes it pass. The throwaway never reaches the PR's final diff.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- The matcher doesn't flag an `href` built from a variable (`href={url}`), a named `{ default as X }` import of `next/link`, or `React.createElement(Link, …)`; none occurs in the codebase and the AC doesn't require them → not tracked: stated in the test's header comment; the rule in `.claude/rules/web.md` still applies to them

## Plan

Approved 2026-10-13 at `e02e2dc`.

1. Test first: write the AC-2 cases against a stub `apiLinks()` that returns `[]`, and watch the flagging cases fail.
2. `web/lib/no-prefetched-handlers.test.ts`: parse each file with the TypeScript compiler API (`typescript` is already a web devDependency): `ts.createSourceFile(file, text, Latest, true, TSX)`.
   - `linkNames(sf)`: the default-import names of every `ImportDeclaration` whose module is `"next/link"`. None means no findings.
   - `apiLinks(file, text)`: walk the tree for `JsxOpeningElement` / `JsxSelfClosingElement` whose tag name is one of those names. Read the `href` attribute's initializer: a `StringLiteral`; a `JsxExpression` holding a `StringLiteral`, `NoSubstitutionTemplateLiteral` or `TemplateExpression` (its head text); or an `ObjectLiteralExpression` whose `pathname` is one of those. Flag the element when the text starts with `/api/`. Return `<file>:<line>` from `getLineAndCharacterOfPosition`.
   - `describe("matcher (AC-2)")`: one `it` per inline case above.
   - `describe("web source (AC-1)")`: walk `app/`, `lib/` and `components/` from the web root (`fileURLToPath(new URL("..", import.meta.url))`). Skip `*.test.*` and missing folders, then `expect(offenders).toEqual([])`.
3. `.claude/rules/web.md`: "a test enforces this" becomes "`web/lib/no-prefetched-handlers.test.ts` enforces this".
4. Manual check from Verification on the branch; paste the failing output in the PR.

Files: `web/lib/no-prefetched-handlers.test.ts` (new), `.claude/rules/web.md`.

Tests: AC-1 by the tree scan, plus the throwaway `<Link>` (Manual) showing it fails on an offender in real source. AC-2 by the inline cases (they fail against the stub). AC-3 by the suite passing on the branch and a read of the rule line.

Risks / open questions:
- The TypeScript parser over a regex like `ledger`'s: a regex stops at the first `>` (e.g. `onClick={() => …}` before `href`) and can't see import aliases. It costs ~40 lines.
- An `href` built from a variable (`href={url}`) can't be resolved statically and isn't flagged. The rule still applies; say so in a comment.

Size check: S. One new test file and one rule line; no runtime code.

## Review log

_Filled by /implement-task. One line per round._

Verify R1 PASS | Audit R1 PASS | Spec R1 APPROVE | Manual: throwaway `<Link href="/api/py/health">` in `app/teams/page.tsx` failed with `app/teams/page.tsx:20`, passed after revert

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 1
- First-pass AC FAILs: 0
- Plan revisions after approval: 0
