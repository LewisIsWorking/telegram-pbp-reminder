# Roadmap

Planned features and improvements for the PBP Reminder Bot.
Status: ✅ Done | 🔧 In Progress | 📋 Planned | 💡 Idea

---

## v1.1.0 — Player Self-Service & Awareness

### ✅ `/mystats` command
Players type `/mystats` in any PBP topic to see their own stats:
total posts, posting sessions, average gap, last post, current streak,
and weekly activity. No waiting for roster day.

### ✅ `/whosturn` command
Anyone can check combat status on demand: current round, whose phase it is,
who has acted, who hasn't. Works outside the ping timer schedule.

### ✅ Daily tips
The bot posts a random tip about one of its features once per day to a
randomly chosen PBP chat topic. Helps players discover commands without
needing to read GitHub or the issues topic. Tips rotate through all
features so each one gets explained eventually.

---

## v1.2.0 — Streaks & Celebrations

### ✅ Posting streaks
Track consecutive days each player posts. Display in `/mystats` and roster.
Milestone celebrations at 7, 14, 30, 60, 90 days ("🔥 Alice is on a 30-day
streak!"). Could feed into POTW weighting or be a standalone shout-out.

### ✅ Streak leaderboard
Add a "longest active streak" section to the weekly leaderboard. Show top 5
across all campaigns. Encourage consistent engagement over burst posting.

---

## v1.3.0 — Cross-Campaign Intelligence

### ✅ Weekly digest
A compact newsletter posted to the leaderboard topic once per week.
One-line summary per campaign: name, post count, trend, top contributor,
notable events (new player joined, combat started, anniversary). Designed
to be scannable in 10 seconds.

### ✅ Campaign health scoring
Assign each campaign a simple health score (traffic light)
based on weekly post volume.
Show in digest. Helps the GM spot campaigns that need
attention without reading every stat.

---

## v1.4.0 — Archive & History

### ✅ PBP transcript archive
Every message in every PBP topic is logged to persistent markdown files
in the repo. Monthly files per campaign at `data/pbp_logs/`. Media is
tagged with type markers. Auto-generated README index. A complete
disaster-recovery backup of every campaign's story.

### ✅ GitHub Pages dashboard v2
- Player-level drill-down (click a campaign to see individual stats)
- Summary cards, week filter, sortable columns
- Health indicator dots (green/yellow/orange/red)
- Trend arrows (week-over-week change)
- Mobile-responsive layout

### ✅ Personal history
`/myhistory` shows a player's posting pattern over time: weekly post
counts for the last 8 weeks as a text sparkline chart.

---

## v1.5.0 — History Import & Per-Campaign GMs

### ✅ Historical transcript backfill
`scripts/import_history.py` imports past PBP messages from Telegram Desktop
JSON exports into `data/pbp_logs/`. Idempotent, supports `--dry-run`.

### ✅ Per-campaign GM overrides
Optional `gm_user_ids` on individual topic_pairs replaces the global list
for that campaign. Allows different GMs per campaign (e.g. Theria).

### ✅ `/pause` and `/resume`
Temporarily disable inactivity tracking for planned breaks, holidays,
or between arcs. Pause reason displayed in `/status` and `/campaign`.

---

## v1.6.0 — GM Roster Management

### ✅ `/kick @player`
Manually remove a player from tracking without waiting for the 4-week
auto-removal.

### ✅ `/addplayer @username Name`
Manually register a player who hasn't posted yet so they appear in
the roster and get tracked.

---

## v1.9.0 — Character Awareness

### ✅ Character name mapping
Optional `characters` field per campaign maps user IDs to character names.
Names appear in rosters, `/mystats`, transcripts, and the new `/party` command.

### ✅ `/party` command
Shows the in-fiction party composition: character names, players, activity.

---

## v1.8.0 — Message Milestones

### ✅ Campaign milestones (every 500 messages)
Celebrates in the campaign's chat topic with escalating icons.

### ✅ Global milestones (every 5,000 messages)
Celebrates across all campaigns in the leaderboard topic.

---

## v1.7.0 — Player Catch-Up

### ✅ `/catchup`
Shows what happened since you last posted: message counts by person,
time since last post, and combat state. Essential for returning PBP players.

---

## v2.0.0 — Dashboard v2 & Smart Alerts

### ✅ Dashboard v2
Summary cards, week filter, sortable columns, player drill-down,
health indicators, trend arrows, mobile-responsive. Powered by
`player_breakdown` data in the weekly archive.

### ✅ Smart alerts
Pace drop detection (>40% week-over-week) and conversation dying
warning (48h+ total silence). Both gated behind `smart_alerts` feature
flag (enabled by default). Use `/pause` to silence during planned breaks.

---

## v2.1.0 — Scene Markers & GM Notes

### ✅ Scene markers
`/scene <n>` marks a narrative scene boundary in the campaign's
transcript file. Creates a styled divider with timestamp. Scene name
displayed in `/status` and `/campaign` output.

### ✅ GM notes
`/note <text>` adds persistent notes per campaign (max 20). View
with `/notes`, delete with `/delnote <N>`. Latest notes shown in
`/campaign` output. All players can view, only GMs can add/remove.

---

## v2.2.0 — Activity Insights

### ✅ Activity tracking
Every message records hour-of-day and day-of-week counters.
Permanent lightweight data (24 + 7 buckets per user per campaign).

### ✅ `/activity` command
Campaign-level posting patterns: busiest days, peak time blocks,
peak hour, and top posters. Available to everyone.

### ✅ `/profile` command
Cross-campaign player lookup. Shows every campaign a player is in
with post counts, character names, last activity, and streaks.
Matches by username, first name, or full name.

---

## v2.4.0 — Absence Tracking & Recap

### ✅ `/away` and `/back`
Players declare absences with duration or indefinitely. Away players
are skipped in inactivity warnings and combat pings. Auto-clears on
post or timer expiry.

### ✅ `/recap [N]`
Show the last N transcript entries from the campaign's archive.
Quick catch-up for returning players using the persistent log files.

---

## v2.5.0 — Dice Roller

### ✅ `/roll`
Roll dice inline with Pathfinder-standard notation. Supports modifiers,
keep-highest/lowest, multiple dice groups, and labels. Uses character
name when configured.

---

## v2.6.0 — Quest Tracker & GM Dashboard

### ✅ Quest tracking
`/quest`, `/quests`, `/done`, `/delquest`. Track active objectives per
campaign so players never lose track of what they're doing.

### ✅ `/gm` dashboard
Compact all-campaign overview: health icons, weekly posts, player counts,
combat/pause/away/quest flags. One command to check everything.

---

## v2.7.0 — DC Lookup, Pins & Loot

### ✅ `/dc`
PF2e DC lookup by level and difficulty. Proficiency DCs. Short aliases.

### ✅ Pins
`/pin`, `/pins`, `/delpin`. Bookmark key story moments, clues, reveals.

### ✅ Loot tracker
`/loot`, `/lootlist`, `/delloot`. Track party treasure and equipment.

---

## v2.8.0 — NPC & Condition Trackers

### ✅ NPC tracker
`/npc`, `/npcs`, `/delnpc`. Track named NPCs with descriptions.

### ✅ Condition tracker
`/condition`, `/conditions`, `/endcondition`, `/clearconditions`.
Track buffs, debuffs, and persistent effects during combat and RP.

---

## v2.9.0 — HP Tracker & Progress Clocks

### ✅ HP Tracker
`/hp set`, `/hp d`, `/hp h`, `/hp remove`, `/hp clear`, `/hp` view.
Visual HP bars with colour-coded status icons. Combat enemy management.

### ✅ Progress Clocks
`/clock`, `/tick`, `/untick`, `/delclock`, `/clocks`.
Blades-in-the-Dark style progress clocks for investigations, rituals, countdowns.

### ✅ Status integration
HP tracker, conditions, and clocks now shown in `/status` and `/summary`.

---

## v3.0.0 — Combat System Rebuild

### ✅ Foundry-compatible combat tracking
Rebuilt for async PBP alongside Foundry VTT. `/combat` to start, `/next` to
advance phases, auto-notify GM when all players have acted, combat log with
`/clog`, enemy roster with `/enemies`, summary on `/endcombat`.

---

## v4.0.0 — Codebase Modularization (In Progress)

Refactor all Python files to a **200-line hard maximum**. No code removal,
no compression, no comment removal. Pure extraction, OOP, and SOLID
principles. Incremental commits, each chunk tested and deployed.

### 🔧 Chunk 1 — Scaffold & Boons
- Create package directories (boons, combat, commands, transcript,
  scheduled, dispatch, parsing, players, helpers_pkg)
- Extract `boons/handler.py` (94 lines)

### 🔧 Chunk 2 — Combat & Parsing
- Extract `combat/display.py` (111 lines): whosturn, combatlog, format_elapsed
- Extract `combat/tracker.py` (159 lines): combat message routing, all-acted check
- Extract `combat/commands.py` (131 lines): start, next, end, enemies
- Extract `parsing/message.py` (81 lines): Telegram message parser

### 🔧 Chunk 3 — Commands (status/info)
- Extract `commands/status.py` (194 lines): build_status, build_overview
- Extract `commands/campaign.py` (168 lines): build_campaign_report, roster_user_stats, roster_block
- Extract `commands/player.py` (130 lines): build_mystats, build_myhistory, sparkline
- Moved `calc_streak` + `health_icon` to helpers.py (shared utilities)
- Remaining: gm_dashboard, summary, party, profile, catchup, activity, recap → chunk 4

### 🔧 Chunk 4 — Commands (trackers, mechanics, summary, dashboard, profile, catchup, recap)
- Extract `commands/trackers.py` (124 lines): notes, quests, pins, loot, npcs, conditions
- Extract `commands/mechanics.py` (113 lines): vote, timer, hp_tracker, clocks
- Extract `commands/summary.py` (175 lines): summary, party
- Extract `commands/dashboard.py` (160 lines): gm_dashboard, activity
- Extract `commands/profile.py` (83 lines): cross-campaign profile
- Extract `commands/catchup.py` (167 lines): catchup + transcript post reader
- Extract `commands/recap.py` (136 lines): rich transcript recap
- checker.py: 4744 → 3431 lines (−1313)

### 🔧 Chunk 5 — Transcript
- Extract `transcript/formatting.py` (94 lines): log entry + content formatting
- Extract `transcript/logger.py` (154 lines): append_to_transcript, write_scene_marker, cache
- Extract `transcript/finalize.py` (179 lines): month finalization + index generation
- checker.py: 3431 → 3055 lines (−376)

### 🔧 Chunk 6 — Scheduled Tasks
- Extract `scheduled/tips_data.py` (164 lines): _TIPS constant
- Extract `scheduled/tips.py` (49 lines): post_daily_tip
- Extract `scheduled/alerts.py` (146 lines): check_and_alert, check_player_activity
- Extract `scheduled/reports.py` (140 lines): post_roster_summary, post_pace_report
- Extract `scheduled/potw.py` (109 lines): _gather_potw_candidates, player_of_the_week
- Extract `scheduled/milestones.py` (157 lines): streak + anniversary milestones
- Extract `scheduled/message_milestones.py` (69 lines): check_message_milestones
- Extract `scheduled/leaderboard_data.py` (120 lines): _gather_leaderboard_stats
- Extract `scheduled/leaderboard.py` (135 lines): _format_leaderboard, post_campaign_leaderboard
- Extract `scheduled/maintenance.py` (180 lines): archive, cleanup, recruitment
- Extract `scheduled/smart_alerts.py` (136 lines): pace_drop, conversation_dying
- Extract `scheduled/digest.py` (87 lines): weekly digest
- Extract `scheduled/combat_ping.py` (102 lines): combat turns, expired timers
- checker.py: 3055 → 1632 lines (−1423)

### 🔧 Chunk 7 — Dispatch & Players
- Extract `dispatch/router.py` (116 lines): process_updates main loop
- Extract `dispatch/cmd_info.py` (168 lines): 28 read-only info commands
- Extract `dispatch/cmd_gm.py` (81 lines): pause, resume, kick, addplayer, scene
- Extract `dispatch/cmd_trackers.py` (122 lines): note, quest CRUD
- Extract `dispatch/cmd_trackers_items.py` (144 lines): pin, loot, NPC CRUD
- Extract `dispatch/cmd_conditions_hp.py` (199 lines): condition + HP tracker writes
- Extract `dispatch/cmd_clocks.py` (127 lines): clock, tick, untick, delclock
- Extract `dispatch/cmd_votes_timers.py` (155 lines): vote, pick, endvote, timer
- Extract `dispatch/cmd_player.py` (112 lines): away, back, chooseboon, roll
- Extract `dispatch/tracking.py` (125 lines): post-message state tracking
- Extract `dispatch/help_text.py` (94 lines): _HELP_TEXT constant
- Extract `players/management.py` (109 lines): handle_kick, handle_addplayer
- checker.py: 1632 → 277 lines (−1355)

### 🔧 Chunk 8 — Split helpers.py
- Extract `helpers_pkg/constants.py` (60 lines): all config constants
- Extract `helpers_pkg/config.py` (180 lines): load, validate, settings, GM helpers
- Extract `helpers_pkg/formatting.py` (146 lines): display_name, rank_icon, fmt_*, html_escape, etc.
- Extract `helpers_pkg/time_utils.py` (128 lines): intervals, timestamps, gaps, away
- Extract `helpers_pkg/topic_maps.py` (92 lines): TopicMaps class, build_topic_maps
- Extract `helpers_pkg/dice.py` (101 lines): roll_dice
- Extract `helpers_pkg/dc_lookup.py` (127 lines): DC tables and lookup
- Extract `helpers_pkg/mechanics.py` (124 lines): timer, HP, clock, streak, health
- `helpers.py` → thin 49-line re-export facade (zero external import changes needed)
- Extract `helpers_pkg/character.py` (character names, away tracking)
- Extract `helpers_pkg/trackers.py` (hp_bar, clock_display, timers)

### 🔧 Chunk 9 — Test Files (deferred)
- test_checker.py (5053 lines) uses backward-compat aliases in checker.py
- Splitting would require a test framework or shared runner — deferred to future session
- test_helpers.py (385 lines) and test_import_history.py (334 lines) are test-only, not production code

### 🔧 Chunk 10 — Final Cleanup
- Rewrote checker.py as clean orchestrator (201 lines: orchestration + backward-compat test aliases)
- Verified all production files ≤200 lines (43 modules)
- Remaining minor overages: post_changelog.py (207), import_history.py (312) — standalone utilities, not core bot


---

## Future Ideas (unscheduled)

### 💡 AI summaries (revisited)
- Optional AI-generated "story so far" recap using Anthropic API
- Posts to chat topic on a configurable schedule
- Requires ANTHROPIC_API_KEY secret (see removed pbp_summary_feature.py
  for prior implementation)

### 💡 Timezone-aware scheduling
- Allow per-campaign timezone config
- Schedule posts for reasonable local times instead of UTC cron
- Display "last post" times in local timezone

---

## Contributing

Ideas and feedback welcome in the
[Foundry & GitHub topic](https://t.me/Path_Wars/71537) or via GitHub issues.
