"""The test-DB guard and the LIVE guard (docs/02-architecture.md › Environments & databases)."""

import pytest

from db.config import (
    UnsafeDatabaseError,
    app_database_url,
    preview_migration_url,
    refuse_if_live,
    resolve_test_database_url,
)

DEV_POOLED = "postgresql://u:p@ep-dev-1-pooler.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require"
DEV_DIRECT = "postgresql://u:p@ep-dev-1.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require"
TEST_DIRECT = "postgresql://u:p@ep-test-2.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require"


def test_refuses_when_test_url_is_unset():
    with pytest.raises(UnsafeDatabaseError, match="not set"):
        resolve_test_database_url({"DATABASE_URL": DEV_POOLED})


def test_refuses_when_test_url_is_blank():
    with pytest.raises(UnsafeDatabaseError, match="not set"):
        resolve_test_database_url({"TEST_DATABASE_URL": "  "})


def test_refuses_when_test_url_names_the_dev_database():
    env = {"TEST_DATABASE_URL": DEV_POOLED, "DATABASE_URL": DEV_POOLED}
    with pytest.raises(UnsafeDatabaseError, match="DATABASE_URL"):
        resolve_test_database_url(env)


def test_refuses_the_dev_database_through_its_other_neon_endpoint():
    # The pooled and direct hostnames of one Neon branch differ only by "-pooler".
    env = {"TEST_DATABASE_URL": DEV_DIRECT, "DATABASE_URL": DEV_POOLED}
    with pytest.raises(UnsafeDatabaseError, match="DATABASE_URL"):
        resolve_test_database_url(env)


def test_refuses_when_test_url_matches_the_unpooled_dev_url():
    env = {"TEST_DATABASE_URL": DEV_POOLED, "DATABASE_URL_UNPOOLED": DEV_DIRECT}
    with pytest.raises(UnsafeDatabaseError, match="DATABASE_URL_UNPOOLED"):
        resolve_test_database_url(env)


def test_same_server_with_a_different_database_is_allowed():
    env = {
        "TEST_DATABASE_URL": "postgresql://ci:ci@localhost:5432/app_test",
        "DATABASE_URL": "postgresql://ci:ci@localhost:5432/app_dev",
    }
    assert resolve_test_database_url(env).endswith("/app_test")


def test_returns_a_distinct_test_url():
    env = {"TEST_DATABASE_URL": TEST_DIRECT, "DATABASE_URL": DEV_POOLED}
    assert resolve_test_database_url(env) == TEST_DIRECT


def test_app_uses_the_guarded_test_url_only_when_app_env_is_test():
    env = {"APP_ENV": "test", "TEST_DATABASE_URL": TEST_DIRECT, "DATABASE_URL": DEV_POOLED}
    assert app_database_url(env) == TEST_DIRECT
    assert app_database_url({**env, "APP_ENV": "development"}) == DEV_POOLED


def test_app_in_test_mode_never_falls_back_to_the_dev_url():
    with pytest.raises(UnsafeDatabaseError):
        app_database_url({"APP_ENV": "test", "DATABASE_URL": DEV_POOLED})


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes"])
def test_live_guard_refuses(value):
    with pytest.raises(UnsafeDatabaseError, match="LIVE"):
        refuse_if_live("seed the fixture", {"LIVE": value})


def test_live_guard_allows_when_unset_or_false():
    refuse_if_live("seed the fixture", {})
    refuse_if_live("seed the fixture", {"LIVE": "false"})


# The preview build migrates its own Neon branch, and never production's (docs/02 › Guards).
PROD_HOST = "ep-prod-9.c-6.us-east-2.aws.neon.tech"
PREVIEW_DIRECT = "postgresql://u:p@ep-preview-3.c-6.us-east-2.aws.neon.tech/neondb"


def test_preview_migration_skips_outside_preview_builds():
    env = {"VERCEL_ENV": "production", "DATABASE_URL_UNPOOLED": PREVIEW_DIRECT}
    assert preview_migration_url(env) is None
    assert preview_migration_url({}) is None


def test_preview_migration_refuses_without_the_production_host():
    env = {"VERCEL_ENV": "preview", "DATABASE_URL_UNPOOLED": PREVIEW_DIRECT}
    with pytest.raises(UnsafeDatabaseError, match="PRODUCTION_DATABASE_HOST"):
        preview_migration_url(env)


def test_preview_migration_refuses_the_production_database():
    env = {
        "VERCEL_ENV": "preview",
        "DATABASE_URL_UNPOOLED": f"postgresql://u:p@{PROD_HOST}/neondb",
        "PRODUCTION_DATABASE_HOST": "ep-prod-9-pooler.c-6.us-east-2.aws.neon.tech",
    }
    with pytest.raises(UnsafeDatabaseError, match="production"):
        preview_migration_url(env)


def test_preview_migration_returns_the_preview_branch_url():
    env = {
        "VERCEL_ENV": "preview",
        "DATABASE_URL_UNPOOLED": PREVIEW_DIRECT,
        "PRODUCTION_DATABASE_HOST": PROD_HOST,
    }
    assert preview_migration_url(env) == PREVIEW_DIRECT
