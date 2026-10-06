# cfb-model

A college football prediction model and web app: game predictions, picks against the spread, power rankings and an honest track record. Other sports later.

## Docs
| Doc | What's in it |
|---|---|
| [01 — Product](docs/01-product.md) | Vision, features, priorities, what "good" means |
| [02 — Architecture](docs/02-architecture.md) | System design, hosting ($0–5/mo), repo layout |
| [03 — Data model](docs/03-data-model.md) | Sources, data lake, Postgres schema, conventions |
| [04 — Model](docs/04-model.md) | Modeling approach + primer, validation, pick logic |
| [05 — UI design brief](docs/05-ui-design-brief.md) | Brief for Claude Design |
| [06 — Roadmap](docs/06-roadmap.md) | Phases, acceptance criteria, open questions |
| [07 — Claude Design playbook](docs/07-claude-design-playbook.md) | Prompts, review checks and handoff for the UI design |
| [07 — Claude Design playbook](docs/07-claude-design-playbook.md) | Prompts, review checks and handoff for the UI design |

## Stack
Python (uv, DuckDB, scikit-learn, FastAPI) · Next.js + Tailwind + shadcn/ui · Postgres (Neon) · Parquet on Cloudflare R2 · GitHub Actions · Vercel
