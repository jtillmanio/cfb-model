"""The schema dump the web app's generated types come from (TASK-052, AC-1)."""

import json
import subprocess
import sys

from api.openapi import schema_json


def test_dump_lists_the_teams_and_health_routes_but_not_the_schema_route():
    paths = json.loads(schema_json())["paths"]
    assert "/api/py/teams" in paths
    assert "/api/py/health" in paths
    # The schema route is served only behind the JWT and is left out of the schema itself.
    assert "/api/py/openapi.json" not in paths


def test_two_dumps_are_equal():
    assert schema_json() == schema_json()


def test_running_the_module_prints_the_dump():
    # The web generator spawns exactly this, so the entry point itself is under test.
    result = subprocess.run(
        [sys.executable, "-m", "api.openapi"], capture_output=True, text=True, check=True
    )
    assert result.stdout == schema_json()
