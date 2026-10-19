"""CFBD client. Every call is counted against the monthly budget before it's made
(Patreon tier 1: 5,000 calls a month; warn at 80%)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx

from engine.clock import now
from engine.ingest.lake import LEDGER_KEY

if TYPE_CHECKING:
    from engine.ingest.lake import Lake

BASE_URL = "https://api.collegefootballdata.com"
MONTHLY_LIMIT = 5000
WARN_FRACTION = 0.8


class BudgetExceededError(RuntimeError):
    pass


class CallBudget:
    """Calls per calendar month (UTC), kept in `cfbd_calls.json` at the lake root, so the ledger
    lives wherever the lake does: a local file, or an object in R2 that every scheduled run
    shares (D-112)."""

    def __init__(self, lake: Lake, limit: int = MONTHLY_LIMIT) -> None:
        self.lake = lake
        self.limit = limit

    def _load(self) -> dict[str, int]:
        text = self.lake.read_text(LEDGER_KEY)
        return json.loads(text) if text else {}

    def used(self) -> int:
        return self._load().get(now().strftime("%Y-%m"), 0)

    def spend(self) -> int:
        counts = self._load()
        month = now().strftime("%Y-%m")
        used = counts.get(month, 0)
        if used >= self.limit:
            raise BudgetExceededError(f"CFBD budget spent: {used}/{self.limit} calls in {month}.")
        counts[month] = used + 1
        self.lake.write_text(LEDGER_KEY, json.dumps(counts, indent=2))
        if counts[month] >= self.limit * WARN_FRACTION:
            print(f"Warning: CFBD calls this month {counts[month]}/{self.limit}.")
        return counts[month]


class CfbdClient:
    def __init__(self, api_key: str, budget: CallBudget, http: httpx.Client | None = None):
        if not api_key:
            raise RuntimeError("CFBD_API_KEY is not set.")
        self.budget = budget
        self.http = http or httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=30,
        )

    def get(self, endpoint: str, params: dict[str, Any]) -> Any:
        self.budget.spend()
        response = self.http.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
