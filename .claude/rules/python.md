---
paths:
  - "python/**"
---

# Python rules

- Run everything through `uv run …` (on Windows, `py` rather than `python` outside uv). Scripts are engine CLI commands in Python, never PowerShell/bash pairs.
- Tests live in `python/<pkg>/tests/test_*.py`; DB tests use the `db_conn` fixture from `python/conftest.py` (test-DB guard, rolled back).
- `engine/core` must not import from `engine/sports/*`. Sport-specific code goes behind the `Sport` plugin.
- `python/api` depends only on the engine's **light core** (numpy, scipy, pydantic). Never add pandas, polars, duckdb, scikit-learn or lightgbm to the API: it runs as a Vercel function with a 250 MB bundle limit.
- Models are built from a `ModelSpec`. No hidden behavior outside the spec; same inputs + same spec give the same output.
- Every feature table and backtest path asserts the point-in-time rule (max source timestamp < `as_of`). Adding a feature without that assertion is a bug.
- Count CFBD calls through the ingest client's budget tracker. Never call the API directly from elsewhere.
- Destructive CLI commands (`--rebuild`, truncate, reload) check `LIVE` and refuse when it's true.
