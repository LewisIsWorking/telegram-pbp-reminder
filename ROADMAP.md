# Roadmap

Planned features and improvements for the PBP Reminder Bot.
Status: ✅ Done | 🔧 In Progress | 📋 Planned | 💡 Idea

Dates shown as `[YYYY-MM-DD]` next to status icons indicate when work was completed or the item was logged.

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

## v4.0.0 — Codebase Modularization (✅ Complete)

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

### ✅ Chunk 11 — Last two overages (v4.51.7)
- Extracted `boons/resolution.py` (101 lines) from `boons/handler.py` (214 → 138):
  boon result formatting, campaign-name resolution, storage, `_resolve_boon`.
- Extracted `scheduled/potw_links.py` (57 lines) from `scheduled/potw.py` (205 → 169):
  transcript post-link lookup (`_find_player_post_links`, `_ENTRY_RE`, `_LOGS_DIR`).
- Both originals re-export the moved names, so `boons.handler.*` / `scheduled.potw.*`
  imports, `compat` aliases, and test patch targets resolve unchanged. The three
  `_LOGS_DIR`-redirect test patches were repointed to `scheduled.potw_links`.
- **✅ v4.0.0 modularization complete: every production module is ≤200 lines.**


---

## Future Ideas (unscheduled)

### ✅ Data Migration — Gist → Structured Repo JSON

Completed in v4.18.0. State is now stored in four partition files under
`data/state/` and committed to the repo every hourly run. The gist is
retained as an emergency dual-write backup. See CHANGELOG for details.


### ✅ C11 Dark Pockets — Multi-Group Campaign Support

Completed in v4.21.0–v4.25.0. C11 runs in a separate Telegram group
(`-1003496373617`). Full PBP tracking, weekly session poll (Mon–Sun,
multiple choice, Sunday start, pinned, daily link with @mentions), and
cross-campaign live vote notifications with C01. Both polls start Sunday
7am UTC. See CHANGELOG v4.21.0–v4.25.0 for full details.

**C11 player roster:** 8 players. Real Telegram IDs confirmed for
Sparkleslayer, Jack, Natasha, Craig. Remaining 4 (Malia, Safrah, Rino,
Elicia) auto-capture on next vote via `promote_poll_voters.py`.

---

### 💡 [2026-04-08] C11 Remaining Player IDs

IDs still pending for 4 C11 players (placeholders in config):
`@molluggg` (Molly Gibb), `@Brookm126` (Brook),
`@Luke_Skillen` (Luke Skillen), `@EliciaRoseT` (Elicia Rose Taylor).
Patrick Coxx (`@Thefununlce`, placeholder `9100000006`) also pending.
IDs auto-captured when they vote. Run `promote_poll_voters.py --commit` after.
Note: `9100000xxx` range now detected — fixed 2026-04-08.


- Optional AI-generated "story so far" recap using Anthropic API
- Posts to chat topic on a configurable schedule
- Requires ANTHROPIC_API_KEY secret (see removed pbp_summary_feature.py
  for prior implementation)

### 💡 Timezone-aware scheduling
- Allow per-campaign timezone config
- Schedule posts for reasonable local times instead of UTC cron
- Display "last post" times in local timezone

---

## Bug Log

Dated log of discovered bugs — open and resolved.

| Date | Status | Description | Fix |
|------|--------|-------------|-----|
| 2026-08-10 | ✅ Fixed 2026-08-10 | **C05 orphan: old "Unreplied:" posts never deleted.** Queue entries carry Telegram's raw **int** `message_thread_id`, but `topic_queues` is JSON so its keys are always **str** — `setdefault(51357, …)` missed the on-disk `"51357"` slot, so `existing.is_empty` was True and the previous batch was never deleted. The save then wrote a second, int-keyed slot, overwriting the real one and stranding those IDs beyond the L28 retry sweep. Missed by the suite because every test passed `thread_id` as a str, the one type production never sends. | `_threads_from_scanned` stringifies at the boundary; new `normalise_queue_keys` heals already-corrupted state and parks stranded IDs in `pending_delete`; `test_topic_queue_key_type.py` (7 tests). Deletion safety untouched — the bot-sent registry guard is still the only `deleteMessage` gate. |
| 2026-03-27 | ✅ Fixed 2026-03-27 | Unknown voter UIDs displayed as raw numbers in poll pings | Added `"Unknown (uid)"` fallback; added DragonFox2000 to C01 config |
| 2026-03-27 | ✅ Fixed 2026-03-27 | `None.items()` crash in `session_poll.py` when `poll_user_names` is `null` | Guard added |
| 2026-03-27 | ✅ Fixed 2026-03-27 | Missing `build_hp_tracker` import in `cmd_conditions_hp.py` (would NameError in production) | Import added |
| 2026-04-06 | ✅ Fixed 2026-04-06 | C11 queue links broken — private group requires `t.me/c/…` not `t.me/Path_Wars/…` | `_build_link()` added to `queue_scan.py` using per-campaign `group_username` |
| 2026-04-06 | ✅ Fixed 2026-04-06 | "Send failed ×7" — `unpin_message` logs 400 errors when Telegram already auto-unpinned expired polls | `suppress_errors` param added to `_post`; unpin and delete silently ignore "message not found" |
| 2026-04-08 | ✅ Fixed 2026-04-08 | Poll week number wrong — Sunday W14 poll labelled "W14/52" instead of "W15/52" | Use Monday's ISO week number when posting on Sunday |
| 2026-04-08 | ✅ Fixed 2026-04-08 | Vote notification dates drift mid-week — Monday shown as Apr 14 instead of Apr 6 | Poll options stored in state at creation; all notifications use stored options |
| 2026-04-08 | ✅ Fixed 2026-04-08 | `promote_poll_voters.py` missed `9100000xxx` placeholder range (Patrick Coxx) | Expanded `_is_placeholder` to cover `9100000xxx` |
| 2026-04-08 | ✅ Fixed 2026-04-08 | Telegram rate-limit warnings from per-topic queue bursts | 1s sleep between campaign posts in `topic_queue_poster.py` |
| 2026-04-08 | ✅ Fixed 2026-04-08 | Diagnostic showed `Worker ID: {...}` as rate-limit context — GitHub Actions infra lines not filtered correctly | Fixed filter to run on timestamp-stripped line; expanded infra prefix list |
| 2026-04-09 | ✅ Fixed 2026-04-09 | Per-topic queue posted to wrong thread in multi-topic campaigns (C06 Kibwe combat entries posted to PBP thread) | Added `thread_id` to scan entries; poster groups by thread and posts to each separately |
| 2026-04-13 | ✅ Fixed 2026-04-13 | Diagnostic showing git credential file paths as rate-limit context | Added path-based filter for `/home/runner` and `git-credentials-` lines; preview bumped to 200 chars |
| 2026-04-15 | ✅ Closed 2026-04-15 | C09 Metal City CHAT topic `104202` — decision on whether to track | Won't track. OOC/general discussion channel, not RP content. Queue, inactivity, and milestones don't apply. |
| 2026-06-15 | ✅ Fixed 2026-06-15 | Bot unpinned posts it didn't own — GM pins vanished when a thread's queue first posted | `_post_thread_queue` empty-slot branch called `unpin_all_messages` (Telegram `unpinAllChatMessages`, which ignores `message_thread_id` and clears pins group-wide). Removed the call; bot now only ever unpins a specific message id it pinned itself |
| 2026-04-15 | ✅ Closed 2026-04-15 | C11 unknown poll UIDs `7754924188`, `6464119705`, `6234551152` | No action needed — `promote_poll_voters.py` auto-captures real UIDs on next Sunday vote. |

---

## Contributing

Ideas and feedback welcome in the
[Foundry & GitHub topic](https://t.me/Path_Wars/71537) or via GitHub issues.

### Testing requirements

All code must maintain **100% test coverage**. See [`docs/testing.md`](docs/testing.md)
for the full testing guide, including the critical requirement to test
falsy/absent inputs for every fallback path.

**Key rule:** 100% coverage does not mean 100% correct. For any function
with a fallback (`entry.get("x", "")`, `if value: ... else: ...`), tests
must include cases where the primary value is `None`, missing, or empty —
not just the happy path. Untested fallback paths are how bugs ship despite
full coverage.
