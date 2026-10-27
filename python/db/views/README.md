# Views

Derived data lives here, never in columns (CLAUDE.md hard rule 1). Each `*.sql` file is
re-applied in name order after every migration (`db:migrate`, the preview build and the
`release` workflow), and onto each nightly backup's restored copy, which then queries every view
(the `backup` workflow). Write each one as `CREATE OR REPLACE VIEW …`, and give each one a test.

| File | View | Test |
|---|---|---|
| `010_game_market.sql` | `game_market`: each game's opening, current and closing line (D-120) | `python/db/tests/test_game_market.py` |
| `020_latest_team_ratings.sql` | `latest_team_ratings`: each team's rating entering a week from its version's newest succeeded scheduled or ad-hoc run, with its FBS rank (D-136) | `python/db/tests/test_team_rankings.py` |
| `030_team_rankings.sql` | `team_rankings`: each FBS team's rank and its change since the week before (D-136) | `python/db/tests/test_team_rankings.py` |
| `040_team_schedule_strength.sql` | `team_schedule_strength`: SOS of the games played so far, adjusted for site, and its FBS rank (D-136) | `python/db/tests/test_team_schedule_strength.py` |

A view that reads another view sorts after it.
