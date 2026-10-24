"""What Vercel installs for the API (D-004, D-114, D-126). It installs the workspace root from
the lock with --no-dev, and every deployment stores its own copy, so a package joins only on
purpose: add it to API_PACKAGES in the same PR that needs it, and say why in the PR."""

import subprocess

from db.config import repo_root

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


def no_dev_install() -> set[str]:
    run = subprocess.run(
        ["uv", "export", "--frozen", "--no-dev", "--no-hashes", "--no-emit-workspace",
         "--no-header", "--no-annotate"],
        cwd=repo_root() / "python", capture_output=True, text=True, check=True,
    )
    lines = [line.strip() for line in run.stdout.splitlines()]
    return {line.split("==")[0].lower() for line in lines if line and not line.startswith("#")}


def test_the_api_install_is_exactly_the_approved_packages():
    installed = no_dev_install()
    assert installed - API_PACKAGES == set(), "new packages in the API's install: approve them"
    assert API_PACKAGES - installed == set(), "packages gone from the API's install: drop them"


def test_the_engine_and_its_ingest_stack_stay_out():
    installed = no_dev_install()
    for package in ("cfb-engine", "httpx", "pyarrow", "boto3", "duckdb", "numpy", "pandas"):
        assert package not in installed
