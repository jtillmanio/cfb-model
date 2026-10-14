---
paths:
  - "web/**"
---

# Web (Next.js 16) rules

- **Read the version-matched docs in `node_modules/next/dist/docs/` before writing Next-specific code.** APIs have changed since training data:
  - `middleware.ts` is now `proxy.ts`, exporting `proxy`, and it runs on Node.
  - `cookies()`, `params` and `searchParams` are async only.
  - `next build` uses Turbopack; `experimental.ppr` is gone.
  - `next-env.d.ts` stays untracked.
- Keep `agentRules: false` in `next.config.ts`.
- UI matches the Claude Design handoff in `design/handoff/` (see "Design source" and "Design decisions" in `docs/05-ui-design-brief.md`). Use design-system tokens and shared components only; if something is missing, extend the system rather than adding a one-off style. All number display goes through the shared formatting module.
- Styling: Tailwind v4 utilities mapped to tokens in the `@theme` block of `web/app/globals.css` (colors, `text-caption`/`text-body`/…, radii). `web/app/tokens.css` is a byte copy of the handoff tokens.
- The browser never calls the FastAPI service. Server components call it with the signed JWT, through `web/lib/api.ts` (`server-only`). **One API call per page.** Response types and pure helpers live in `web/lib/*.ts` with Vitest tests beside them (`*.test.ts`).
- Never use `<Link>` to anything under `/api/`, because prefetch runs the handler. Use a plain `<a>`; `web/lib/no-prefetched-handlers.test.ts` enforces this.
- Every data route ships with a `loading.tsx` whose skeleton is drawn at the loaded size (`web/app/teams/loading.tsx`), with the pulse off under `prefers-reduced-motion`. Use route groups when a list and its `[id]` page need different skeletons. A route that only waits and then redirects (e.g. `/login/continue`, D-104) shows no API data, so it gets no `loading.tsx`: one would draw on the fast path, which must stay blank.
- A stale or invalid session redirects to `/login`; it never throws a 500.
- Vitest tests that spawn a shell get a 30 s timeout.
- E2E specs live in `web/e2e/` and run at phone and desktop widths.
- Dependabot majors (Next.js, TypeScript ≥ 7) are hand upgrades, not merges.
