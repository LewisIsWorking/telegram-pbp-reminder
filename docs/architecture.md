## Multi-topic campaigns

If a campaign uses multiple PBP threads (e.g. split scenes), list them all:
```json
{
    "name": "My Campaign",
    "chat_topic_id": 11111,
    "pbp_topic_ids": [22222, 33333, 44444]
}
```
The first ID becomes the canonical ID. All posts across the listed topics
are merged for stats, rosters, POTW, and leaderboards.

---

## File structure

```
.github/workflows/
  pbp-reminder.yml        # Hourly cron job (tests + checker)
  changelog-notify.yml    # Posts changelog to Telegram on push
scripts/
  checker.py              # Orchestrator: load → process → check → save
  helpers.py              # Re-export facade for helpers_pkg/
  telegram.py             # Telegram Bot API wrapper (send, poll, pin, message_link)
  state.py                # File-primary state persistence (gist backup)
  compat.py               # Backward-compat aliases for test suite
  set_commands.py         # Register Telegram / command menu
  post_changelog.py       # Changelog parser and Telegram poster
  import_history.py       # Historical transcript backfill
  import_formatting.py    # Message formatting for import
  boons/                  # POTW boon system
    handler.py            #   Boon callbacks, storage, expiry
    reminders.py          #   Boon reminders (24h, 3d, 6d, 7d auto-pick)
  combat/                 # Combat tracking
    commands.py           #   /combat, /next, /endcombat, /enemies
    display.py            #   /whosturn, /combatlog
    tracker.py            #   Message routing, all-acted detection
  commands/               # All /command output builders
    campaign.py           #   /campaign, roster blocks
    catchup.py            #   /catchup
    dashboard.py          #   /gm, /activity
    mechanics.py          #   /showvote, /showtimer, /hp, /clocks
    player.py             #   /mystats, /myhistory
    profile.py            #   /profile
    recap.py              #   /recap
    status.py             #   /status, /overview
    summary.py            #   /summary, /party
    trackers.py           #   /notes, /quests, /pins, /lootlist, /npcs, /conditions
    queue.py              #   /queue (GM reply queue)
    queue_format.py       #   Shared queue formatting (age icons, age_str, preview)
    queue_scan.py         #   Transcript scanning for unreplied messages
    reactions.py          #   /reactions (emoji tracking)
    timeline.py           #   /timeline, /event
  dispatch/               # Command routing and message processing
    router.py             #   Main update loop, context builder
    bot_topic.py          #   Bot topic command handler (campaign arg resolution)
    cmd_info.py           #   28 read-only info commands
    cmd_gm.py             #   GM control commands
    cmd_trackers.py       #   Note/quest CRUD
    cmd_trackers_items.py #   Pin/loot/NPC CRUD
    cmd_conditions_hp.py  #   Condition + HP writes
    cmd_clocks.py         #   Clock commands
    cmd_votes_timers.py   #   Vote + timer commands
    cmd_player.py         #   /away, /back, /roll, /chooseboon
    tracking.py           #   Post-message state tracking
    help_text.py          #   /help text constant
    cmd_search.py         #   /search (Archives of Nethys)
    poll_notify.py        #   Cross-campaign vote tally notifications
  helpers_pkg/            # Shared utilities (re-exported via helpers.py)
    constants.py          #   Paths, tunable defaults
    config.py             #   Config loading, validation, GM helpers
    formatting.py         #   Display names, dates, HTML escaping
    time_utils.py         #   Intervals, timestamps, away tracking
    topic_maps.py         #   Campaign↔topic lookups
    dice.py               #   /roll dice parser
    dc_lookup.py          #   PF2e DC tables
    mechanics.py          #   HP bars, clocks, streaks, timers
    groups.py             #   Multi-group helpers (group_id_for_campaign, linked_poll_codes)
  parsing/                # Message parsing
    message.py            #   Telegram message → structured data
  players/                # Player management
    management.py         #   /kick, /addplayer
  scheduled/              # All hourly cron tasks
    alerts.py             #   Inactivity alerts, player warnings
    campaign_table.py     #   Weekly campaign overview table (HTML <pre>)
    combat_ping.py        #   Combat turn pings, timer expiry
    digest.py             #   Weekly cross-campaign digest
    leaderboard.py        #   Leaderboard formatting + posting
    leaderboard_data.py   #   Stats gathering for leaderboard
    maintenance.py        #   Archive, cleanup, recruitment
    message_milestones.py #   500/5000 message celebrations
    milestones.py         #   Streak + anniversary milestones
    potw.py               #   Player of the Week selection
    reports.py            #   Roster + pace reports
    smart_alerts.py       #   Pace drop + silence detection
    tips.py               #   Daily tips
    tips_data.py          #   Tip text constants
    queue_reminder.py     #   Daily GM reply queue reminder with links
    session_poll.py       #   Weekly session poll (Sunday start, pin, daily link)
    session_poll_build.py #   Pure poll message builders (options, pings, history)
    poll_result.py        #   Friday result announcement (all hybrid campaigns)
  transcript/             # PBP transcript system
    finalize.py           #   Month finalization + index generation
    formatting.py         #   Log entry formatting
    logger.py             #   Append to transcript, scene markers
  test_checker.py         # 286 tests
  test_helpers.py         # 37 tests
  test_import_history.py  # 18 tests
  test_new_features.py    # 16 tests (v4.4-4.8 features)
  test_campaign_table.py  # 12 integration tests (campaign overview table)
  test_campaign_table_unit.py # 21 unit tests (age, health, post count, truncate)
  test_state_partitions.py # 11 tests (partition contract, critical key placement)
  test_state_io.py        # 11 tests (file round-trip, public API, save guard)
  test_queue_format.py    # 42 tests (8-tier age icons, age_str, preview)
  conftest.py             # Shared mock telegram — installed before all test imports
  migrate_gist_to_files.py # One-time migration script (gist → data/state/)
config.json               # Your configuration
config.example.json       # Template configuration
boons.json                # Flavour boons for POTW (optional)
boons.example.json        # Sample boons file
docs/
  index.html              # Archive dashboard (Chart.js)
  data/
  state/                  # Live bot state (committed every hourly run)
    live.json             #   offset, timestamps, combat, session (~8 KB)
    players.json          #   player registry, characters, boons (~17 KB)
    queue.json            #   GM reply queue, history, archive (~62 KB)
    activity.json         #   post timestamps, message counts (~35 KB)
    trackers.json         #   clocks, conditions, HP, loot, npcs, pins, quests
    manifest.json         #   migration metadata
  weekly_archive.json     # Auto-committed weekly stats archive
  state_backup.json       # Legacy full-state backup (kept for reference)
  pbp_logs/               # PBP transcript archive (monthly .md per campaign)
    README.md             # Auto-generated index of all transcripts
VERSION                   # Current semver version
CHANGELOG.md              # Release notes
ROADMAP.md                # Feature roadmap and modularization log
```

---

