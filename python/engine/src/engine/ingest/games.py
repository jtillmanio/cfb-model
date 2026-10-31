"""`engine ingest games`: CFBD /games for a week (or a season) pulled into the raw lake, then the
Parquet file read back and published to the dev DB (D-098, D-112).

A week whose saved response is all completed games is never fetched again (CLAUDE.md: never
re-fetch completed CFBD weeks); it's re-published from the saved file instead.
"""

from __future__ import annotations

from db.session import make_engine
from engine.ingest.cfbd import CfbdClient
from engine.ingest.endpoints import pull
from engine.ingest.lake import Lake, decode_raw, fetched_at_of, open_lake
from engine.publish.reference import publish_games_batch
from engine.sports.cfb.games import map_games


def ingest_games(
    season: int,
    week: int | None,
    season_type: str,
    db_url: str,
    lake: Lake | None = None,
    client: CfbdClient | None = None,
) -> None:
    lake = lake or open_lake()
    key = pull(lake, "games", season, week, season_type, client=client)
    batch = map_games(decode_raw(lake.read(key)), fetched_at_of(key))
    with make_engine(db_url).begin() as conn:
        count = publish_games_batch(conn, "cfb", "cfbd", batch)
    print(f"Upserted {count} games, {len(batch.teams)} teams, {len(batch.venues)} venues.")
