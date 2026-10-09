# spec-reviewer: cfb-model

Project section for `.claude/agents/spec-reviewer.md`. The kit never ships or overwrites this file.

## Project-specific checks

Run these on added or changed lines only (existing code is the baseline). Each hit is a rule violation citing the CLAUDE.md hard rule number.

1. **Derived values stored (rule 1):** a new column, table or write that stores a result, record, rank, CLV, current pick or current contest line. These belong in `python/db/views/*.sql`.
2. **Model outputs mutated (rule 2):** `UPDATE`/`DELETE` SQL, or SQLAlchemy `update()`/`delete()`/attribute assignment followed by flush, against ratings, predictions or picks tables.
3. **Point-in-time (rule 4):** a new feature table, feature function or backtest path without an assertion that the max source timestamp is before `as_of`; any season-aggregate stat used in a backtest.
4. **API boundary (rule 5):** `python/api` importing pandas, polars, duckdb, scikit-learn, lightgbm or any `engine` module outside the light core; a client component (`"use client"`) or browser code calling the API or importing `web/lib/api.ts`; a page making more than one API call; `<Link>` to an `/api/` path.
5. **Protected paths (rule 6):** any change to a path matching `protectedPaths` in `.claude/kit.json`, or to a migration in `python/db/migrations/versions/` that exists on the base branch.
6. **Design tokens (rule 7):** in `web/**/*.{ts,tsx,css}`, a new hard-coded color (hex, `rgb()`, `hsl()`, `oklch()` literals; Tailwind palette classes like `text-red-500`; arbitrary values like `bg-[#0c0f12]`), px font size (`text-[13px]`, `fontSize: 13`), or spacing value (`p-[7px]`, `gap-[10px]`, `mt-[18px]`, inline `style` margins/padding/gaps). Use the token utilities from the `@theme` block in `web/app/globals.css`. Exempt: token definitions in `web/app/tokens.css` and that `@theme` block, and colors that come from data (team brand colors from the API set via `style`).

