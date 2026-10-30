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
| `050_current_picks.sql` | `current_picks`: the newest pick per game, version, market and line source; none when the newest row is a pass (D-140, D-142) | `python/db/tests/test_current_picks.py` |
| `060_pick_outcomes.sql` | `pick_outcomes`: every pick graded at its line (won, lost, push, pending, void), its units at its price and its CLV against the close (D-132, D-142) | `python/db/tests/test_pick_outcomes.py` |
| `070_model_record.sql` | `model_record`: the current picks' W-L-P, win %, units, ROI and avg CLV through each week, alone, to date, by tier and by edge bucket (D-142) | `python/db/tests/test_model_record.py` |

A view that reads another view sorts after it.
