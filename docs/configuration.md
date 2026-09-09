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
| `group_username`    | —       | Public @username for t.me message links        |
| `poll_post_hour`    | 7       | UTC hour on Sunday to post the weekly poll     |
| `queue_daily_hours` | [9, 21] | UTC hours to post the GM queue reminder daily  |
| `diagnostic_hour`   | 8       | UTC hour to run the daily bot health diagnostic |

### Per-campaign topic_pair fields

Fields set inside each entry in `topic_pairs`:

| Field                    | Description |
|--------------------------|-------------|
| `hybrid_live`            | `true` — campaign has live sessions; enables the session poll |
| `group_id`               | Override Telegram group ID (for campaigns in a separate group, e.g. C11) |
| `group_username`         | Override `@username` for message links in this group |
| `linked_polls`           | List of campaign codes whose polls are cross-notified with this one |
| `poll_options`           | Custom poll answer labels (default: dynamic Fri/Sat/Can't dates) |
| `allows_multiple_answers`| `true` — players can pick more than one option (e.g. C11) |
| `poll_any_day`           | `true` — daily ping runs every day of the week (default: Mon–Sun anyway) |
| `poll_user_ids`          | Explicit list of Telegram user IDs to ping (overrides PBP roster) |
| `poll_user_names`        | `{uid: username}` map — fallback @mention for players not in PBP registry |
| `emoji`                  | Campaign emoji shown in queue section headers (e.g. `🦠`) |
| `queue_priority`         | Queue rank, **lower wins**. `true` is a legacy alias for rank 1. Unset means rank 99. See [GM queue ranks](gm-queue.md#campaign-exclusions) |
| `queue_exclude`          | `true` — campaign is excluded from the GM reply queue entirely |
| `gm_user_ids`            | **Replaces** the global GM list for this campaign only — see [Per-campaign GMs](#per-campaign-gms) |
| `disabled_features`      | Feature names switched off for this campaign (e.g. `["warnings", "recruitment"]`) |
| `roster_target`          | Target player count; overrides the default used by `/roster` and the roster nudge |
| `nudge_topic_id`         | Topic to send session-poll nudges to (defaults to the poll topic) |
| `poll_roster_filter`     | `true` — opt in to poll-roster filtering (see `commands/roster.py`) |
| `created`                | Campaign start date `YYYY-MM-DD`, used by `/campaign` and the timeline |
| `recruit_tier`           | Which recruitment queue this campaign draws from. See [Recruitment tiers](#recruitment-tiers) |

### Recruitment tiers

`recruit_tier` decides **which campaigns the recruitment advert offers**, and it
is a queue rather than a switch. Lewis, 2026-08-15: *a tier only becomes eligible
once every campaign in every lower tier is full*. That lets a table wait its turn
instead of being excluded outright.

| Tier | Meaning | Currently |
|------|---------|-----------|
| `0` | The normal queue. Implicit for any campaign that does not say otherwise. | Everything not listed below |
| `1` | Offered only once every tier-0 campaign is full. | C10 The Junction |
| `2` | Offered only once tiers 0 and 1 are full. | C08 Theria |
| `None` | Never recruited. | Any campaign with `recruitment` in `disabled_features` and no explicit tier |

⚠️ **Precedence matters, and it is the opposite of what reading the config
suggests.** An explicit `recruit_tier` is read **before** `disabled_features`, so
a campaign can carry `"recruitment"` in its disabled list and still be recruited
for when its tier comes up. C10 and C08 are both in exactly that state: hard
excluded on 2026-08-15, tiered since. Reading the disabled flag first would make
an explicit tier unreachable.

⚠️ A tier is **not** a reply-queue rank. `queue_priority` orders the GM reply
queue; `recruit_tier` orders who gets offered new players. A campaign can be
top of one and absent from the other, and C08 Theria is: `queue_exclude: true`
keeps it out of the reply queue entirely while tier 2 still recruits for it.

The rule lives in `scheduled/recruit_focus.py:recruit_tier`, and the "lowest tier
with a shortfall" selection in `_eligible_pairs` beside it.

### Per-campaign GMs

Most campaigns are run by the GM in the **global** `gm_user_ids`. A campaign run
by somebody else sets its own `gm_user_ids` inside its `topic_pair`.

> ⚠️ **The per-campaign list REPLACES the global one, it does not merge.**
> `helpers_pkg/config.py::gm_ids_for_campaign` returns the pair's list as-is
> whenever the key is present. Anyone not named in it — *including the global
> GM* — counts as a **player** in that campaign: their posts get queued as
> needing a reply, and their reply-tos do not clear entries.

Campaigns with a non-default GM:

| Campaign | GM | Notes |
|----------|----|-------|
| C08 Theria (pid `107151`) | **Tyler Link** (`7863964681`) | Not run by the global GM. Also sets `queue_exclude: true`, so C08 never appears in the GM reply queue, and disables `warnings` + `recruitment`. |

C08's queue file (`data/state/queues/107151.json`) still holds ~180 historical
`unreplied` entries dated 2026-03-24 to 2026-05-24, from before these settings
were added. They are **inert** — `queue_exclude` means nothing reads or reports
them. Do not mistake that count for a live backlog.

### Example: C11 Dark Pockets (separate group, linked poll)

```json
{
  "name": "Dark Pockets",
  "code": "C11",
  "group_id": -1003496373617,
  "chat_topic_id": 1068,
  "pbp_topic_ids": [1242],
  "hybrid_live": true,
  "poll_any_day": true,
  "allows_multiple_answers": true,
  "poll_options": ["Friday", "Saturday", "Sunday", "Weekday", "Can't make it"],
  "linked_polls": ["C01"],
  "created": "2026-03-29"
}
```

---

