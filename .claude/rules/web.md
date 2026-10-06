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
- UI matches the Claude Design exports in `design/exports/` (see `docs/07-claude-design-playbook.md`). Use design-system tokens and shared components only; if something is missing, extend the system rather than adding a one-off style. All number display goes through the shared formatting module.
- The browser never calls the FastAPI service. Server components call it with the signed JWT. **One API call per page.**
- Never use `<Link>` to anything under `/api/`, because prefetch runs the handler. Use a plain `<a>`; a test enforces this.
- Every data route ships with a `loading.tsx` whose skeleton is drawn at the loaded size, with the pulse off under `prefers-reduced-motion`. Use route groups when a list and its `[id]` page need different skeletons.
- A stale or invalid session redirects to `/login`; it never throws a 500.
- Vitest tests that spawn a shell get a 30 s timeout.
- Dependabot majors (Next.js, TypeScript ≥ 7) are hand upgrades, not merges.
