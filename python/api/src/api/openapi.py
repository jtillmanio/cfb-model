"""Dump the API's OpenAPI schema without a server or a token (TASK-052).

`pnpm api:types` runs `python -m api.openapi` and generates web/lib/api-types.ts from what it
prints. The schema route itself sits behind the JWT, so the dump reads `app.openapi()` in
process; no database connection opens, because `engine()` is lazy.
"""

from __future__ import annotations

import json
import sys

from .main import app


def schema_json() -> str:
    """The schema as sorted, indented ASCII JSON, so two dumps of one API are byte-equal."""
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    sys.stdout.write(schema_json())
