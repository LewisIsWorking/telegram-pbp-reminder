## Configuration reference

All settings go in the `settings` block of `config.json`.
Every setting has a sensible default, so the entire block is optional.

| Setting                     | Default   | Description                                      |
|-----------------------------|-----------|--------------------------------------------------|
| `roster_interval_days`      | 3         | Days between party roster posts                  |
| `potw_interval_days`        | 7         | Days between Player of the Week awards           |
| `potw_min_posts`            | 5         | Minimum posting sessions to qualify for POTW     |
| `pace_interval_days`        | 7         | Days between pace comparison reports             |
| `leaderboard_interval_days` | 3         | Days between cross-campaign leaderboard          |
| `combat_ping_hours`         | 4         | Hours before pinging players who haven't acted   |
| `recruitment_interval_days` | 14        | Days between recruitment notices                 |
| `required_players`          | 6         | Target party size (triggers recruitment notices) |
| `post_session_minutes`      | 10        | Posts within this window count as one session    |
| `player_warn_weeks`         | [1, 2, 3] | Weeks of inactivity before each warning          |
| `player_remove_weeks`       | 4         | Weeks of inactivity before auto-removal          |

Top-level settings:

| Setting             | Default | Description                                    |
|---------------------|---------|------------------------------------------------|
| `alert_after_hours` | 4       | Hours of topic silence before inactivity alert |

---

