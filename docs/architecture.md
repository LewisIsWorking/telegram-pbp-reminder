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
  telegram.py             # Telegram Bot API wrapper
  state.py                # Gist-based state persistence
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
  helpers_pkg/            # Shared utilities (re-exported via helpers.py)
    constants.py          #   Paths, tunable defaults
    config.py             #   Config loading, validation, GM helpers
    formatting.py         #   Display names, dates, HTML escaping
    time_utils.py         #   Intervals, timestamps, away tracking
    topic_maps.py         #   Campaign↔topic lookups
    dice.py               #   /roll dice parser
    dc_lookup.py          #   PF2e DC tables
    mechanics.py          #   HP bars, clocks, streaks, timers
  parsing/                # Message parsing
    message.py            #   Telegram message → structured data
  players/                # Player management
    management.py         #   /kick, /addplayer
  scheduled/              # All hourly cron tasks
    alerts.py             #   Inactivity alerts, player warnings
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
  transcript/             # PBP transcript system
    finalize.py           #   Month finalization + index generation
    formatting.py         #   Log entry formatting
    logger.py             #   Append to transcript, scene markers
  test_checker.py         # 286 tests
  test_helpers.py         # 37 tests
  test_import_history.py  # 18 tests
  test_new_features.py    # 16 tests (v4.4-4.8 features)
config.json               # Your configuration
config.example.json       # Template configuration
boons.json                # Flavour boons for POTW (optional)
boons.example.json        # Sample boons file
docs/
  index.html              # Archive dashboard (Chart.js)
data/
  weekly_archive.json     # Auto-committed weekly stats archive
  pbp_logs/               # PBP transcript archive (monthly .md per campaign)
    README.md             # Auto-generated index of all transcripts
VERSION                   # Current semver version
CHANGELOG.md              # Release notes
ROADMAP.md                # Feature roadmap and modularization log
```

---

