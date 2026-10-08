"""CFBD client. Every call is counted against the monthly budget before it's made
(Patreon tier 1: 5,000 calls a month; warn at 80%)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from engine.clock import now

BASE_URL = "https://api.collegefootballdata.com"
MONTHLY_LIMIT = 5000
WARN_FRACTION = 0.8


class BudgetExceededError(RuntimeError):
    pass


class CallBudget:
    """Calls per calendar month (UTC), kept in a small JSON file next to the lake."""

    def __init__(self, path: Path, limit: int = MONTHLY_LIMIT) -> None:
        self.path = path
        self.limit = limit

    def _load(self) -> dict[str, int]:
        if not self.path.is_file():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def used(self) -> int:
        return self._load().get(now().strftime("%Y-%m"), 0)

    def spend(self) -> int:
        counts = self._load()
        month = now().strftime("%Y-%m")
        used = counts.get(month, 0)
        if used >= self.limit:
            raise BudgetExceededError(f"CFBD budget spent: {used}/{self.limit} calls in {month}.")
        counts[month] = used + 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(counts, indent=2), encoding="utf-8")
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
