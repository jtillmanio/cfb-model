"""What Vercel installs for the API (D-004, D-114, D-126). It installs the workspace root from
the lock with --no-dev, and every deployment stores its own copy, so a package joins only on
purpose: add it to API_PACKAGES in the same PR that needs it, and say why in the PR.

The engine's base install is in it (TASK-055): the API computes edges and cover probabilities with
`engine.core` (hard rule 5), and the engine's own dependencies are ones the API already has. Its
ingest, lake and training stack is the `train` extra, which stays out."""

import ast
import subprocess
import sys

from db.config import repo_root

API_SRC = repo_root() / "python" / "api" / "src" / "api"

API_PACKAGES = {
    # The API itself: FastAPI and its stack, and the JWT guard (D-107).
    "fastapi", "starlette", "pydantic", "pydantic-core", "annotated-doc", "annotated-types",
    "typing-extensions", "typing-inspection", "anyio", "idna", "pyjwt",
    # cfb-db: the models, the session and the URL guards. Alembic (with mako) is cfb-db's for
    # migrations; the API only reads alembic_version with SQL.
    "sqlalchemy", "psycopg", "psycopg-binary", "alembic", "mako", "markupsafe", "python-dotenv",
    # Pulled in by the above, not imported by the API itself.
    "opentelemetry-api", "tzdata",
}


def _export(*flags: str) -> list[str]:
    run = subprocess.run(
        ["uv", "export", "--frozen", "--no-dev", "--no-hashes", "--no-header", "--no-annotate",
         *flags],
        cwd=repo_root() / "python", capture_output=True, text=True, check=True,
    )
    lines = [line.strip() for line in run.stdout.splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def no_dev_install() -> set[str]:
    return {line.split("==")[0].lower() for line in _export("--no-emit-workspace")}


def test_the_api_install_is_exactly_the_approved_packages():
    installed = no_dev_install()
    assert installed - API_PACKAGES == set(), "new packages in the API's install: approve them"
    assert API_PACKAGES - installed == set(), "packages gone from the API's install: drop them"


def test_the_engine_joins_but_its_ingest_and_training_stack_stay_out():
    assert "-e ./engine" in _export()  # workspace members are listed by path
    installed = no_dev_install()
    for package in ("httpx", "pyarrow", "boto3", "duckdb", "numpy", "pandas"):
        assert package not in installed


def test_loading_the_api_loads_no_heavy_or_sport_module():
    """The dev environment has numpy and the rest, so only what `api.main` actually imports
    shows whether the API would start without them."""
    probe = "import sys, api.main; print(' '.join(sorted(sys.modules)))"
    run = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    loaded = run.stdout.split()
    assert "engine.core" in loaded  # the probe sees the engine the API does load
    heavy = ("numpy", "httpx", "pyarrow", "boto3", "duckdb", "pandas")
    assert [m for m in loaded if m.split(".")[0] in heavy or m.startswith("engine.sports")] == []


def test_the_api_imports_only_the_engines_light_core():
    """Hard rule 5: `engine.core` and nothing else of the engine."""
    outside: list[str] = []
    core: list[str] = []
    for path in API_SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text("utf-8"))):
            names = (
                [a.name for a in node.names] if isinstance(node, ast.Import)
                else [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0
                else []
            )
            outside += [
                f"{path.name}: {n}" for n in names
                if n.split(".")[0] == "engine" and not n.startswith("engine.core")
            ]
            core += [n for n in names if n.startswith("engine.core")]
    assert core, "the scan found no engine.core import, so it would miss one from elsewhere"
    assert outside == []
