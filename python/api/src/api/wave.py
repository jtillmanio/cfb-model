"""A screen's queries, run concurrently in one wave within the budget (docs/02-architecture.md ›
Non-functional requirements: at most 6 queries per page, in one wave).

Each query gets its own connection: one connection runs one statement at a time, so a shared one
would serialize them. The engine keeps no pool (NullPool, db/session.py), so each opens and closes
a Neon pooled connection."""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlalchemy import Engine, Row, TextClause

QUERY_BUDGET = 6

Query = tuple[TextClause, Mapping[str, Any]]


class OverBudget(ValueError):
    pass


def _run(engine: Engine, sql: TextClause, params: Mapping[str, Any]) -> list[Row[Any]]:
    with engine.connect() as conn:
        return list(conn.execute(sql, dict(params)).all())


def run_wave(engine: Engine, queries: Mapping[str, Query]) -> dict[str, list[Row[Any]]]:
    """Every query at once; waits for all, then re-raises the first failure in `queries` order."""
    if len(queries) > QUERY_BUDGET:
        raise OverBudget(f"{len(queries)} queries in one wave; the budget is {QUERY_BUDGET}")
    with ThreadPoolExecutor(max_workers=max(len(queries), 1)) as pool:
        futures = {name: pool.submit(_run, engine, sql, params) for name, (sql, params) in
                   queries.items()}  # fmt: skip
    return {name: future.result() for name, future in futures.items()}
