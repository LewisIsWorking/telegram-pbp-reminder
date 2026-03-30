# Changelog

All notable changes to the PBP Reminder Bot are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/).

- **MAJOR** (x.0.0): Breaking config changes, workflow restructuring.
- **MINOR** (0.x.0): New commands, new features, new bot behaviours.
- **PATCH** (0.0.x): Bug fixes, test additions, refactors, documentation.

---

## [4.27.0] - 2026-03-30

### Fixed — Queue scanner flooding with 29-day-old entries

After the v4.26.0 queue clearing fix (GM messages no longer wipe pending
entries), all previously-suppressed transcript entries flooded back into
the queue. Entries going back 29 days appeared because the transcript
scanner had no knowledge of which ones had genuinely been replied to
before reply-to tracking was introduced.

**Fix:** `queue_scan_floor` state key — the scanner ignores any transcript
entry older than this date. Set to `2026-03-30` on deployment, giving a
clean slate. Future sessions build a clean `gm_queue_replied` record.

### Fixed — Missing links in queue nudge warnings

The `⚠️ @PathWars — X's message is Nh old!` warnings posted to the
bot topic now include a direct 🔗 link to the oldest message from that
player when available.

### Changed — Age icon scale: 9 tiers (added ⚫ 30d+)

| Icon | Age |
|---|---|
| 🟢 | < 6 h |
| ⚪ | 6–24 h |
| 🟡 | 1–2 d |
| 🟠 | 2–3 d |
| 🔴 | 3–5 d |
| 🟣 | 5–7 d |
| 🔵 | 7–14 d |
| 🟤 | 14–30 d |
| ⚫ | 30 d + |

`test_queue_format.py` updated for 9-tier scale (456 tests).

---
## [4.26.0] - 2026-03-30

### Fixed — GM Queue Clearing Bug

**The GM queue was clearing all entries whenever the GM sent any message
in a topic, not just when they replied to a specific message.**

Root cause: `queue_scan.py` reset `pending = []` on any GM transcript
entry. Fixed to `pass` — the scanner now only filters entries via
`gm_queue_replied` state, which is populated exclusively by direct
Telegram reply-to events.

### Added — POTW History

Every Player of the Week event is now permanently recorded in
`state["potw_history"]` with: week, campaign, winner ID/name, post count,
average gap, all 4 boons offered, and chosen boon (backfilled by
`_store_boon` on pick). 9 historical records backfilled from `player_boons`.

### Added — POTW Streaks

`scheduled/potw_streaks.py` — campaign and community consecutive-week
win streaks with milestone announcements:
- Campaign: 2 / 3 / 5 / 10 weeks → posted in campaign chat topic
- Community: 2 / 3 / 5 weeks → posted in bot topic

### Added — Week Welcome Post

`scheduled/week_welcome.py` — "🗳️ Welcome to Week X/YYYY!" posted to bot
topic each Sunday at `poll_post_hour` UTC alongside the session polls.

### Added — Swimming Poll

`scheduled/swimming_poll.py` — weekly poll in the Dark Pockets group
main chat (topic 1). Sunday start, pinned, daily pings, Mon–Sun options
with multiple choice. 7 swimmers; IDs auto-captured on first vote.

### Changed — Queue Reminder Doubled

`queue_daily_hours: [9, 21]` — queue reminder now posts at 9am **and**
9pm UTC daily (was 9am only). Tracking upgraded from date string to
slot-based (`last_queue_daily_slots`) so both daily slots fire reliably.

### Refactored — `boons/display.py`

`build_boons` and `build_boons_all` extracted from `boons/handler.py`
into new `boons/display.py` to keep handler under 200 lines.

### Fixed — `@BotName` suffix in command arguments

`/chooseboon`, `/scene`, `/pause`, `/kick`, `/addplayer` all used
fixed-length slices on `raw_text`, which included the `@BotName` suffix
that Telegram appends in groups (e.g. `/chooseboon@PathWarsNudgeBot 1`).
Fixed with `_arg(raw_text, n)` helper in `cmd_gm.py` and equivalent
regex strip in `cmd_player.py`.

### Added — Documentation

Four new docs files:
- `docs/behaviour.md` — intended behaviour for all major features
- `docs/gm-queue.md` — queue mechanics, clearing rules, reminders
- `docs/polls.md` — session polls, swimming poll, cross-notifications
- `docs/potw.md` — POTW selection, boons, streaks, history

102 production files, 454 tests passing.

---
## [4.25.0] - 2026-03-29

### Fixed — Poll notification phrasing

Vote notifications now read `"voted X in C01"` instead of
`"voted X (C01)"` — the campaign is part of the verb phrase,
making it unambiguous which poll the voter participated in.

Before: `🗳️ @DragonFox2000 (C01) voted Friday`
After:  `🗳️ @DragonFox2000 voted Friday in C01`

### Added — C11 Weekly Day Poll (manual trigger)

Utility path established for posting a dated day-of-week poll
directly via the Telegram API when the weekly result shows a
clear winner (e.g. "Weekday") and a follow-up specific-day
poll is needed mid-week without waiting for Sunday.

First use: C11 Week 13/52 — Mon 30 March to Sun 5 April,
posted and pinned to the Dark Pockets chat manually after
the Weekday option won the weekly session poll.

---
## [4.24.0] - 2026-03-29

### Added — Auto-Capture Unknown Poll Voter IDs

When a `poll_answer` arrives from a Telegram user ID that is not in a
campaign's `poll_user_ids` list (e.g. a player with a placeholder ID),
the real ID is now stored in `state["poll_unknown_voters"][code]`.

After each Sunday vote session, running:
```
python3 scripts/promote_poll_voters.py [--commit]
```
prints the captured IDs alongside their vote patterns and remaining
placeholders. Where there's a 1:1 match it auto-promotes. `--commit`
writes the result to `config.json` and clears the capture buffer.

This resolved Jack (`6452663252`) and Natasha (`8018921976`) automatically
after this week's C11 poll — no manual ID lookup required.

### Changed — Poll Notifications: @mention + Campaign Code

Vote notifications now show `@username (CODE)` instead of just first name:
```
🗳️ @Nemesiux (C01) voted Saturday
C01: Saturday: 2, Either: 2
C11: Weekday: 1
```
Username resolved from: player registry → `poll_user_names` config → first name.

### Changed — C11 Poll: Monday–Sunday

C11 (Dark Pockets) poll options updated from Fri/Sat/Sun/Weekday/Can't
to the full week: Mon / Tue / Wed / Thu / Fri / Sat / Sun / Can't make it.

### Fixed — Raw UID in Ping ("8030796908" instead of "@Sparkleslayer")

Added `poll_user_names: {uid: username}` config field. When a player is
in `poll_user_ids` but not in the PBP player registry, their username is
looked up from this map instead of falling back to the raw numeric ID.

### Added — `promote_poll_voters.py`

One-shot utility script (96 lines) to promote unknown voter IDs from
state into config after a vote session.

---
## [4.23.0] - 2026-03-29

### Fixed — Test Suite Contamination (22 failing tests in combined run)

Running `pytest scripts/` collected 454 tests but only 432 passed.
22 tests in `test_checker.py` failed when preceded by the campaign_table
test files, while passing in isolation.

**Root cause:** `test_campaign_table.py` imports `scheduled.campaign_table`
which does `import telegram as tg` at module level. When pytest collected
test files alphabetically, `campaign_table` ran first and bound `tg` to the
real `telegram` module. `test_checker.py` installed its own mock via
`sys.modules["telegram"] = _mock_tg` — a *different* object. Subsequent
calls from checker tests that passed through `campaign_table`'s `tg` binding
hit the real (unconfigured) module, raising `Invalid URL` errors that were
swallowed by try/except, silently zeroing the sent-message count.

**Fix:** `conftest.py` (new) — pytest loads this before collecting any test
module. It installs the complete mock telegram (9 functions: `send_message`,
`send_poll`, `pin_message`, `message_link`, etc.) into `sys.modules` once,
as the single authoritative mock. All modules that `import telegram` at any
point get the same mock object.

`test_checker.py` updated to import `_sent_messages` and `_mock_tg` from
`conftest` rather than reinstalling its own copy.

Suite: 432 → 454 passing (all 454 pass in combined and isolated runs).

---
## [4.22.0] - 2026-03-29

### Changed — Poll Overhaul: Sunday Start, Pinned, Daily Links, New Options

**Both C01 and C11 polls now:**
- Start early Sunday (7am UTC) and run all week (Mon–Sun)
- Poll message is **pinned** to the chat topic immediately after posting
- Daily ping includes a **direct link** to the pinned poll message
- Tally uses option-index-based vote storage (flexible, supports any options)

**C01 new options** (single-choice):
`Friday / Saturday / Both / Neither / Can't make it this week`

**C11 options** (multiple-choice, any day):
`Friday / Saturday / Sunday / Weekday / Can't make it`

**New in `telegram.py`:**
- `pin_message(chat_id, message_id)` — pins via `pinChatMessage`
- `message_link(group_id, topic_id, message_id, group_username)` — builds
  `t.me/Username/topic/msg` for public groups or `t.me/c/digits/msg` for private

**Vote storage** changed from `{"friday": [], "saturday": [], "cant": []}` to
`{"0": [], "1": [], "2": []}` (option index → uid list). Supports any poll
shape without code changes. Old state auto-migrates.

**`poll_result.py`** — finds winner by max votes across any-length option list;
all-time history tracked by option index.

**`session_poll_build.py`** — `sunday_week_key()` replaces Mon-based week key;
`option_tally()` and `build_history_str()` work with index-based votes.

---
## [4.21.0] - 2026-03-29

### Added — C11 Dark Pockets: Multi-Group Campaign Support

C11 (Dark Pockets) runs in a separate Telegram group. Full integration:

**1. PBP tracking** — C11's PBP topic (`1242`) is now a tracked campaign.
Post timestamps, activity, queue scan, transcripts all work the same as
every other campaign. Players are added to the roster as they post.

**2. Weekly session poll** — C11 gets its own native Telegram poll, posted
to its chat topic (`1068`) in the Dark Pockets group. Differences from C01:
- `poll_any_day: true` — poll posts and pings run any day of the week,
  not just Mon–Fri
- `allows_multiple_answers: true` — multiple choice
- Configurable options: Friday / Saturday / Sunday / Weekday / Can't make it

**3. Cross-campaign live vote notifications** — when anyone votes in
either C01 or C11's poll, both chat topics receive a tally update
immediately:
```
🗳️ Craig voted Friday
C01: 3 Fri / 1 Sat
C11: 2 Fri / 1 Sat
```
Both campaigns list both tallies. All four combinations notify both chats.

### Changed — Multi-Group Architecture

The bot now operates across multiple Telegram groups simultaneously:

- `helpers_pkg/groups.py` (new) — `group_id_for_campaign`,
  `linked_poll_codes`, `all_group_ids`, `pid_for_code`
- `helpers_pkg/topic_maps.py` — `TopicMaps` gains `to_group` dict
  (pid → group_id); `build_topic_maps` populates it from pair-level
  `group_id` overrides
- `parsing/message.py` — `parse_message(msg, maps)` replaces
  `parse_message(msg, group_id, maps)`; verifies group via `maps.to_group`
- `dispatch/router.py` — multi-group aware; routes `poll_answer` by
  `poll_id` (not by campaign assumption); passes correct `group_id`
  per-campaign to all downstream handlers
- `dispatch/poll_notify.py` (new) — `notify_vote` posts combined tally
  to own + all linked campaigns' chat topics on every vote
- `scheduled/session_poll.py` — fully rewritten; iterates all hybrid
  campaigns; per-code state slot; stores `poll_id` for answer matching
- `scheduled/session_poll_build.py` (new) — pure message builders
  extracted from `session_poll.py` (poll options, ping text, history)
- `scheduled/poll_result.py` — rewritten to iterate all hybrid campaigns
  and announce in each campaign's own group
- `telegram.py` — `send_poll` now returns `(message_id, poll_id)` tuple
- `state["session_poll"]` — migrated from flat dict to `{code: slot}` map;
  backwards-compat migration runs automatically on first load

### Updated — config.json

```json
C01: { "linked_polls": ["C11"] }
C11: {
  "group_id": -1003496373617,
  "chat_topic_id": 1068,
  "pbp_topic_ids": [1242],
  "hybrid_live": true,
  "poll_any_day": true,
  "allows_multiple_answers": true,
  "poll_options": ["Friday","Saturday","Sunday","Weekday","Can't make it"],
  "linked_polls": ["C01"]
}
```

Production files: 92 → 96. Suite: 436 passing.

---
## [4.20.0] - 2026-03-29

### Changed — Queue Entry Age Icons: 3 Tiers → 5 Tiers

The GM reply queue previously used only 3 icons. Long-overdue messages
all showed the same 🔴, making it impossible to tell a 2-day-old entry
from a 10-day-old one.

New scale:

| Icon | Age | Meaning |
|---|---|---|
| ⚪ | < 24 h | Fresh |
| 🟡 | 1–2 d | Getting old |
| 🟠 | 2–4 d | Overdue |
| 🔴 | 4–7 d | Stalled |
| 🟣 | 7 d + | Critically overdue |

Applies to both the `/queue` command and the daily queue reminder post.

### Refactored — `queue_format.py` Shared Helpers

Extracted `entry_age_icon`, `age_str`, and `short_preview` from
`commands/queue.py` and `scheduled/queue_reminder.py` (both had identical
copies) into a new `commands/queue_format.py` module. DRY, SOLID.

### Added — Queue Format Tests

42 new tests in `test_queue_format.py`: full parametrized coverage of all
8 icon tiers including boundary values, `age_str` formatting, and
`short_preview` truncation.

Suite: 394 → 436 tests.

### Updated — Docs

- `docs/architecture.md` — `queue_format.py` and `test_queue_format.py` added
- `ROADMAP.md` — C11 Dark Pockets multi-group feature spec added

---
## [4.19.0] - 2026-03-27

### Fixed — Silent Data Loss: 17 State Keys Missing from Partitions

The file-primary state introduced in v4.18.0 had a critical gap: 17 keys
written by active bot features were not mapped to any partition file, so
their values were never written and would be silently reset to `{}` on
the next load from files.

**Affected keys (would have been lost on first file-primary run):**

| Key | Written by |
|---|---|
| `characters` | `/setchar` — all character names |
| `away` | `/away`, `/back` |
| `paused_campaigns` | `/pause`, `/resume` |
| `current_scenes` | `/scene` |
| `clocks`, `conditions`, `hp_tracker` | In-game trackers |
| `loot`, `npcs`, `pins`, `quests` | In-game trackers |
| `reactions`, `timers`, `votes` | In-game trackers |
| `campaign_notes` | `/note` |
| `poll_history`, `poll_results` | DF session poll |

**Fix:** Added a `trackers` partition (11 keys). Moved `characters`, `away`,
`paused_campaigns`, `current_scenes`, `poll_history`, `poll_results` into
appropriate existing partitions. `_load_from_files` is tolerant of a
missing `trackers.json` for backwards compatibility with v4.18 checkouts.

### Added — State Tests (expanded)

`test_state.py` replaced by two files under 200 lines:
- `test_state_partitions.py` — 11 tests (partition contract, critical key placement)
- `test_state_io.py` — 11 tests (round-trip, missing files, public API, save guard)
- Regression test: `characters` survives file round-trip

Suite: 384 → 394 tests.

---
## [4.18.0] - 2026-03-27

### Changed — State Persistence: File-Primary with Gist Backup

The bot's state is now stored in versioned JSON files in the repository
instead of a single GitHub Gist blob. The Gist is still written on every
run as an emergency backup, but is no longer the primary source of truth.

**Why:** The Gist was a 121 KB single-point-of-failure. Files give full
git history, are diffable, and load faster with no API round-trip needed.

**New files (`data/state/`):**

| File | Keys | Size |
|---|---|---|
| `live.json` | offset, timestamps, combat, session | ~8 KB |
| `players.json` | players, registry, boons, MVP wins | ~17 KB |
| `queue.json` | gm_queue, queue_history, queue_archive | ~62 KB |
| `activity.json` | post_timestamps, message_counts, word counts | ~35 KB |

**Load order:** files → gist fallback → defaults. The bot refuses to save
if no source loaded successfully (existing data-protection behaviour
preserved).

### Added — State Tests

12 new tests in `test_state.py`: partition contract, file round-trip,
partial-file fallback, save guard, default backfill.

Suite: 372 → 384 tests.

### Added — Migration Script

`scripts/migrate_gist_to_files.py` — one-time script used to perform the
migration. Validates all gist keys are mapped, writes partition files,
and produces a `manifest.json` with metadata.

### Changed — Workflow

- `pip install pytest` added to dependencies (was running test files
  directly with `python`, now uses `pytest -q` consistently)
- All 7 test files enumerated explicitly in the test step
- Commit step message updated to reflect state files being committed

---
## [4.18.0] - 2026-03-27

### Changed — File-Primary State (Data Migration)

State is now stored in four JSON files in the repo (`data/state/`)
instead of a single flat GitHub Gist blob.

**Before:** every hourly run read and wrote a 121 KB JSON blob to the
gist. All 42 keys — hot operational data and cold history alike — in one
file with no git history.

**After:**

| File | Contents | Size |
|---|---|---|
| `data/state/live.json` | offset, timestamps, combat, session | 8 KB |
| `data/state/players.json` | player registry, boons, MVP wins | 17 KB |
| `data/state/queue.json` | GM reply queue, history, archive | 62 KB |
| `data/state/activity.json` | post timestamps, message counts, streaks | 35 KB |

The gist is still written every run as an emergency backup (dual-write).
If files are absent on load, the bot falls back to the gist automatically,
so the transition is zero-downtime.

Files are committed to the repo by the existing hourly workflow step
(`git add data/ && git commit`), giving every state change a full git
history — diffable, auditable, and recoverable.

### Added — Migration Script

`scripts/migrate_gist_to_files.py` — one-time script used to seed the
partition files from the live gist. Validates all keys are mapped and
prints a summary. Safe to re-run if needed.

### Added — State Tests

12 new tests in `test_state.py`:
- Partition contract (no key in two partitions, all DEFAULT_STATE keys mapped)
- File round-trip (save → load recovers all keys identically)
- Fallback behaviour (missing or partial files → None → gist fallback)
- Save guard (refuses to write if load never succeeded)

Suite: 372 → 384 tests.

### Changed — Workflow

- Added `pytest` to `pip install` in `pbp-reminder.yml`
- Replaced chained `python test_X.py &&` calls with a single
  `python -m pytest … -q` covering all 7 test files

---
## [4.17.0] - 2026-03-27

### Fixed — Campaign Table Alignment

The weekly Campaign Overview table was rendering as mangled,
misaligned text because it was sent without a parse mode, causing
Telegram to use a proportional font where spaces collapse.

**Changes:**
- Table is now wrapped in `<pre>…</pre>` and sent with
  `parse_mode="HTML"` so Telegram always uses its fixed-width font
- Header gets a 3-space prefix to compensate for emoji being
  2 display-cells wide in monospace, keeping "Campaign" visually
  aligned with the name column
- `<` in the legend is HTML-escaped to `&lt;` (required in HTML mode)
- Dropped the noisy "Total registered" column; the active-player
  count is more meaningful
- Extracted `_collect_rows`, `_count_week_posts`, and `_build_warning`
  into named helper functions (SOLID / single-responsibility)

### Added — Campaign Table Tests

33 new tests across two new files:
- `test_campaign_table.py` — integration tests (HTML structure,
  column alignment, queue indicator, warning banner)
- `test_campaign_table_unit.py` — unit tests for `_calc_age`,
  `_health_icon`, `_truncate`, `_count_week_posts`

Suite: 339 → 372 tests.

---
## [4.16.0] - 2026-03-27

### Added — Daily State Backup

Full gist state now backed up daily to `data/state_backup.json`.
Auto-committed to the repo by the existing workflow, creating a
git history of every state change. Protects against gist corruption.

### Added — Campaign Helpers Module

New `helpers_pkg/campaigns.py` centralizing all campaign config
lookups. Refactored 10 files from repeated for/if/break patterns
to single-line calls: `get_label`, `get_code`, `iter_campaigns`,
`is_excluded`, `is_hybrid`, `is_priority`.

### Fixed — Roster Label Bug

Variable shadowing caused `Party roster for #04: Bruce` instead
of the campaign name. Renamed player loop variable.

### Updated — README

Added 14 missing features to the table, 7 new commands,
data storage documentation, corrected file/test counts.

---
## [4.15.0] - 2026-03-26

### DF Session Poll — Full Feature

Native Telegram poll posted weekly in the DF chat topic.

**Poll lifecycle (Mon–Fri):**
- Monday: New poll + "New session poll is up!" ping
- Tue–Thu: Daily "Vote in the poll above!" ping
- Friday 15:00 UTC: Result announcement
- Only pings players who haven't voted yet
- Resets automatically each Monday

**Poll options:** Friday / Saturday / Can't make either

**Result announcement:**
```
🎲 Week 14/52 — Friday wins!
See you Friday night!
(1 can't make either)

All-time: Fridays 8/13, Saturdays 5/13
```

**Ping format:**
```
🗳️ Week 14/52 — Vote in the poll above!
1/4 voted.

Waiting on:
@Nemesiux
@DragonFox2000
```

**All-voted confirmation:**
```
✅ Week 14/52 — All 4 players have voted!
```

**Other poll features:**
- Historical win tracking (Fridays vs Saturdays all-time)
- GM included in roster (votes too)
- Vote change supported (native Telegram)
- Per-option vote tracking in state

### Refactored

Extracted `poll_result.py` for Friday announcement.

---
## [4.14.0] - 2026-03-26

### Added — DF Session Poll

Weekly poll in the Doomsday Funtime chat topic:
- Posts Monday, daily reminders through Friday
- Vote Friday or Saturday with inline buttons
- Shows live results: who voted for what, leading option
- Change your vote anytime by tapping the other button
- Only pings players who haven't voted yet
- Resets automatically each week

### Improved — Campaign Overview Table

- Renamed "Active" → "Players", added "Total" column (registered)
- Color legend at bottom: 🟢 <1d  🟡 1-3d  🟠 3-5d  🔴 5d+
- Footer: which campaign needs players most (excludes DF as hybrid)
- DF flagged `hybrid_live` in config — excluded from "needs players"

---
## [4.13.0] - 2026-03-26

### Added — Player Registry & Character Names

**Player Registry** (`commands/player_registry.py`):
- Every player gets a permanent campaign ID on first post
- GM is always Player 0. Players numbered sequentially
- `/registry` shows all players who have ever been in a campaign
- IDs persist even if a player leaves and returns

**Character Names** (`/setchar @username CharacterName`):
- Stored in state, shown on rosters and registry
- Backward compatible: checks state first, then config

**Roster overhaul**:
```
#01: Link
- @Linksanelf2006.
- Player 3.
- 20 posts total.
```
- `#01` = rank by activity (most posts first)
- `Player 3` = permanent campaign registry ID
- Campaign code in header: `Party roster for C05: Grand Explorers`
- Fixed: player count only counts players who have posted

### Added — Weekly Campaign Table

Posted weekly to bot topic, sorted by active players:
```
📊 Campaign Overview (W13)
Campaign           Code Active Week  Last
🔴 Doomsday Funtime  C01     1     3   3d
🟢 Kibwe             C06     7    36   0h
```

### Improved — Visual Separators

Every bot message starts with `━━━━━━━━━━━━━━━━` for clear
visual breaks between consecutive messages in Telegram.

### Fixed — Duplicate Nudges

Nudge now fires once per player per campaign, not per message.
Shows count: `⚠️ @PathWars — Dima's message in C07 is 48h old! (3 messages)`

### Improved — Comeback Alerts

Pings both GM and the returning player:
```
👀 Kaer'maga when? posted in Riddleport after 12d of silence!
@PathWars @Nemesiux
```

### Refactored

Extracted `dispatch/comeback.py` for comeback alert logic.

---
## [4.12.0] - 2026-03-22

### Queue — Maximum Value Update

**Header**: Per-campaign count summary for instant triage:
`📋 Unreplied: 11 | ✅ 6 cleared today`
`C06:2 C01:2 C00:3 C07:4`

**Player momentum**: Fastest responder per campaign in headers:
`━━ C06: Kibwe (2) ━━ @PathWars ⚡Link (~4h)`
Reply to them first to keep pace up.

**`/queuestats` upgraded**:
- Progress bar: `[████████░░] 15 vs 8 last week 📈`
- Peak player hours: `⏰ 14:00 (45), 18:00 (38)`
- Queue age heatmap: `🌡️ C09:5d 3h  C01:5d 2h`
- Cleared archive: last 5 items you replied to today

**Daily queue at 9am UTC**: Posts even if no changes, as a morning nudge.

**POTW post links**: Winner's posts linked in the award message.

**Kibwe pinned first** via `queue_priority` config flag.
**Theria excluded** from queue via `queue_exclude` flag.
**Campaign codes** fixed to C00, C01, C04, etc.

---
## [4.11.0] - 2026-03-20

### Queue Intelligence

- **Reply streak**: Queue header shows `✅ 3 cleared today` as motivation.
- **Estimated reply time**: `/waiting` shows "GM usually replies in ~12h"
  so players know what to expect.
- **`/queuestats`**: GM productivity dashboard — cleared today, this week,
  and average reply time per campaign.

### Queue Visibility

- **Queue in `/status`**: Unreplied count shows in campaign status output.
- **Thread context**: Current scene shown in queue campaign headers.
- **48h nudge**: Bot @mentions the GM when an entry crosses 48 hours.
- **Weekly queue report**: Clearance count added to the weekly leaderboard.

### Refactored

Extracted `cmd_info_ext.py` from `cmd_info.py` for newer commands
(search, reactions, timeline, waiting, session, health, queuestats).
All files under 200 lines.

---
## [4.10.0] - 2026-03-20

### Added — Player-Facing Queue (/waiting)

Players can see what the GM owes them:
- `/waiting` in a PBP topic: your unreplied messages in that campaign
- `/waiting` from the bot topic: cross-campaign summary

### Added — Session Counter (/session)

Auto-increments when the GM posts on a new calendar day.
- `/session` — shows current session number
- `/session set 272` — initialize or correct (GM only)

### Added — Campaign Health Dashboard (/health)

Color-coded overview of all campaigns at a glance:
```
🟢 C9: Metal City S45 — 22/wk, 6p, last 3h
🟡 C6: Kibwe S88 — 8/wk, 6p, last 1d 📋3
🔴 C1: Doomsday Funtime S272 — 3/wk, 5p, last 3d 📋2
```
Shows posts/week, player count, last post age, queue count.

### Added — Comeback Alert

When a player breaks a 5+ day silence, the bot topic gets:
```
👀 Ryo (Fierce Leopard) posted in Kibwe after 8d of silence!
```

### Quick Wins

- 🔗 link indicator in queue entries (entries without links have no icon)
- `/mystats` from bot topic shows cross-campaign stats summary
- Campaign codes in weekly leaderboard headers (C0, C1, etc.)

---
## [4.9.0] - 2026-03-20

### Overhauled — GM Reply Queue

Major upgrade to the queue system, now the bot's flagship feature.

**Transcript-powered scanning**: Queue reads directly from PBP
transcripts, catching all unreplied messages (not just since v4.6).

**Hybrid reply tracking**: When you reply to a message using
Telegram's reply feature, the bot records the original message's
timestamp. The scanner filters it out on the next run. Works for
old messages without message_ids too.

**Live updates**: Queue reposts to the bot topic whenever it changes
(new messages or replies). No more daily timer. Posts "All caught up!"
when you clear everything.

**Compact format**:
```
📋 Unreplied: 22
━━ C7: Hopeful End-Times (5) ━━ @PathWars
🔴 4d 5h. CzarChasm23: Lowda's gaze returns to normal...
🔴 4d 0h. Dima: Alita keeps her low ready... t.me/...
━━ C8: Theria (1) ━━ @Linksanelf2006
⚪ 15h. Cannon McMahon: "Ah! Yeah, quite so..."...
```

**Other queue changes**:
- Campaign codes in headers (C0, C1, etc.)
- GM shown as @PathWars (your campaigns) or @username (others)
- Time before name: "🔴 3d 10h. Ryo:" not "🔴 Ryo (3d 10h):"
- 5-word previews, links inline, no paragraph gaps
- message_ids.json lookup for backfilled links
- msg# tags in transcripts for future link building
- Campaigns sorted by oldest unreplied message

---
## [4.8.1] - 2026-03-20

### Added — Tests for v4.4-4.8 Features

New test suite `test_new_features.py` covering 16 tests:
queue (build, entries), reactions (add, remove, display), timeline
(creation dates, add event, empty), boon reminders (24h, 7d auto-pick),
campaign resolution (exact, prefix, not found), queue reminder (skip empty).

CI workflow now runs 4 test suites (357 total: 286 + 37 + 18 + 16).

### Updated — README

Documented all features added in v4.4-4.8: `/search`, `/queue`,
`/reactions`, `/timeline`, `/event`, `/available`, `bot_topic_id` config,
daily queue reminder. Updated features table (23 entries), file structure
(76 production files), command list (35 player / 69 admin), and test count.

---
## [4.8.0] - 2026-03-20

### Added — Cross-Campaign Timeline

`/timeline` shows a chronological feed of events across all campaigns.
Works from both PBP topics and the bot channel.

Pulls from: manual GM events, POTW awards, player removals, and
campaign creation dates.

GMs can log story beats with `/event`:

```
/event The party enters the Temple of Pharasma
📜 Event logged for Doomsday Funtime: The party enters the Temple of Pharasma

/timeline
📅 Cross-Campaign Timeline:

📜 Mar 20 — [Doomsday Funtime] The party enters the Temple of Pharasma
🏅 Mar 18 — [Metal City] POTW: Metal City (W12)
🏅 Mar 18 — [Theria] POTW: Theria (W12)
👋 Mar 17 — [Kibwe] Anthony removed
🏅 Mar 11 — [Kibwe] POTW: Kibwe (W11)
🎬 Oct 06 — [Theria] Campaign started
```

---
## [4.7.1] - 2026-03-19

### Added — Daily Queue Reminder With Message Links

The bot posts a daily reminder to the bot topic showing all unreplied
player messages with direct links to each message:

```
📋 Unreplied messages:
Total: 5

━━ Kibwe (2) ━━
🔴 Ryo (2d): Fierce Leopard steps... https://t.me/Path_Wars/40585/12345
🟡 Bruce (1d): Cho Kobo examines... https://t.me/Path_Wars/40585/12350

━━ Riddleport (3) ━━
⚪ Lunnes (5h): Necrila checks... https://t.me/Path_Wars/66154/67890
```

Tap any link to jump straight to the message and reply.

---
## [4.7.0] - 2026-03-19

### Added — Reaction Tracking

The bot now tracks emoji reactions on PBP messages. View stats with
`/reactions` (or `/reactions kibwe` from the bot channel):

```
Top reactors:
  Link: 12 reactions
  Ryo: 8 reactions

Popular: x15  x8  x5
```

### Added — Player Availability

Players can mark which days they're available to post:

```
/available mon wed fri
/available         (show everyone's)
/available clear   (remove yours)
```

Helps the GM and other players know when to expect responses.

---
## [4.6.0] - 2026-03-19

### Added — GM Reply Queue

`/queue` shows all player messages the GM hasn't replied to, across
all campaigns. Messages are only cleared when the GM uses Telegram's
reply feature on that specific message — general narrative posts
don't clear anything.

```
📋 GM Reply Queue:
Total: 7 unreplied

━━ Kibwe (3) ━━
🔴 Ryo (2d ago): Fierce Leopard draws his blade and...
🟡 Bruce (1d ago): Cho Kobo steps forward cautiously
⚪ Awnii (3h ago): Leilani looks at Tal'lysae

━━ Riddleport (4) ━━
🔴 Lunnes (3d ago): Necrila checks the door for traps
...
```

Color coding: 🔴 48h+, 🟡 24h+, ⚪ recent.
GM-only. Works from bot topic and PBP topics.

---
## [4.5.2] - 2026-03-19

### Changed — Boon Auto-Select Extended to 7 Days

Auto-selection was at 48 hours, now 7 days. Reminder timeline:

- **24h** — gentle reminder
- **3 days** — second nudge
- **6 days** — last chance
- **7 days** — auto-selects boon #1

---
## [4.5.1] - 2026-03-19

### Added — Boon Reminders and Confirmations

Unclaimed POTW boons now get reminders at 12h and 24h:

```
🎁 @Player — you have an unclaimed boon for Kibwe!
⚠️ @Player — pick your boon for Kibwe! Auto-selects in 24h.
```

At 48h, auto-pick fires with a notification:

```
⏰ @Player's boon in Kibwe was auto-selected (boon #1) after 48h.
```

Boon confirmations now post to the bot topic with campaign name:

```
✅ Link chose boon #2 for Theria: The crystal hums...
```

### Fixed — Per-Update Error Isolation

One crashed command can no longer take down the entire bot. The
update processing loop now wraps each message in try/except — a
bad command gets logged, skipped, and the offset advances. Previously
a single TypeError blocked all processing for 5 hours.

---
## [4.5.0] - 2026-03-18

### Changed — All Bot Output Moved to Bot Topic

Every scheduled bot post now goes to the Bot Tips & Commands topic
instead of campaign chat topics. Campaign chats are now purely
player and GM conversation with zero bot noise.

**Moved:** rosters, pace reports, inactivity alerts, player warnings,
auto-removals, combat pings, POTW awards, recruitment notices,
streak milestones, message milestones, and smart alerts.

Falls back to campaign chat topics if `bot_topic_id` is not configured.

---
## [4.4.4] - 2026-03-18

### Fixed — /roll and /dc Now Work From Bot Channel

These commands don't need campaign context but were being ignored
when sent from the Bot Tips & Commands topic. Now both work directly:

```
/roll 1d20+5 Perception
/dc 5 hard
```

---
## [4.4.3] - 2026-03-18

### Fixed — /roll Broken With @botname Suffix

Telegram appends `@PathWarsNudgeBot` to commands selected from the menu.
The roll handler was stripping a hardcoded 5 characters (`/roll`) from
the raw text, so `/roll@PathWarsNudgeBot 1d20-5 Will save` became
`@PathWarsNudgeBot 1d20-5 Will save` which failed to parse as dice.

Now uses a regex to strip `/roll` and any `@botname` suffix before
parsing the dice expression. All roll formats work:

```
/roll 1d20-5 Will save
/roll@PathWarsNudgeBot 1d20-5 Will save
/roll 4d6kh3
```

---
## [4.4.2] - 2026-03-17

### Added — MVP Win Tracking

The weekly leaderboard now tracks how many times each player has won
MVP of the Week. Repeat winners show their total:

```
🏆 MVP of the Week: Link! (MVP x3)
```

Historical wins backfilled from the weekly archive (W07-W12).

---
## [4.4.1] - 2026-03-17

### Fixed — /search Now Blocks Creatures and Hazards

Players could look up monster stat blocks and spoil encounters.
Creatures and hazards are now excluded at both the Elasticsearch query
level and client-side as a safety net.

### Fixed — Auto-Removal Always Notifies

The GM bottleneck suppression (v4.2.0) was incorrectly skipping 4-week
auto-removals. Now:
- **4-week removal: always fires**, even when the GM hasn't posted
- **1/2/3 week warnings: suppressed** when GM is the bottleneck

The group always needs to know when a player drops off the roster.

---
## [4.4.0] - 2026-03-16

### Added — Bot Channel Commands

All read-only commands now work from the Bot Tips & Commands topic.
Specify a campaign name as an argument:

```
/mystats kibwe
/campaign riddleport
/status metal city
```

Commands that don't need a campaign (`/gm`, `/overview`, `/help`,
`/profile`, `/boonsall`) work without an argument. If you forget
the campaign name, the bot lists all available campaigns.

Write commands (combat, notes, HP, etc.) still only work from PBP topics.

### Added — Archives of Nethys Search

`/search [query]` searches AoN's Elasticsearch API and returns up to
5 results with name, level, rarity, summary, and link. Works from
any topic.

```
/search fireball
/search +1 striking
/search beastmaster dedication
```

---
## [4.3.0] - 2026-03-16

### Changed — Tips Post to Dedicated Bot Topic

Tips and command hints now post to the new Bot Tips & Commands topic
instead of randomly pinging PBP game chats. Changelog posts also go
here now. Configure via `bot_topic_id` in config.json.

### Changed — Once Per Day Alert Maximum

Topic silence alerts now fire at most once every 24 hours per campaign
(previously every 12 hours). Less noise, same information.

### Changed — Alert Threshold Raised to 24h

`alert_after_hours` bumped from 12 to 24. A campaign needs a full day
of silence before the first alert fires, not half a day.

---
## [4.2.0] - 2026-03-13

### Added — GM Bottleneck Suppression

If the GM hasn't posted in a campaign for 3+ days, the bot stops nagging
players about inactivity. No warnings, no auto-removals — nothing until
the GM posts again. Players can't do anything if the GM is the bottleneck.

Topic silence alerts still fire (useful for the GM to see), with the
existing "GM hasn't posted in Xd Yh" note appended.

### Added — GM Inactivity Note on Alerts

All inactivity alerts and player warnings now append a note when the GM
isn't the last poster:

```
GM hasn't posted in 5d 2h.
```

Appears on topic silence alerts, 1/2/3 week player warnings, and
4-week auto-removal messages. Skipped when the GM was the last to post.

### Fixed — Pace Report Counting Raw Messages Instead of Sessions

The weekly pace report was counting every individual Telegram message,
not posting sessions. A single PBP scene posted line-by-line (50 messages
in 2 hours) showed as "50 posts" instead of "~5 sessions."

`pace_split()` now uses `deduplicate_posts()` to collapse messages within
10 minutes into a single session, matching how rosters already count.

### Added — Kibwe PBP 2/2 Topic

Topic 137075 added to Kibwe's tracked PBP topics. Posts from both topics
merge under the canonical ID for stats, rosters, POTW, and transcripts.

### Changed — 200-Line Limit Enforced on All Files

Extracted `compat.py` (test aliases) from `checker.py` and
`import_formatting.py` from `import_history.py`. All 69 production
files now at or under 200 lines with zero exceptions.

---
## [4.1.1] - 2026-03-06

### Fixed — CRITICAL: State Wipe on Failed Gist Load

On March 5 at ~12:00 UTC, all bot state was wiped — 43 players and 952
messages across 8 campaigns lost. Root cause: `state.py` `load()` returned
empty `DEFAULT_STATE` on a transient gist API failure, then `save()` wrote
that empty state back, overwriting everything.

Two concurrent workflow runs (schedule + dynamic trigger) likely caused the
gist read to fail or race.

**Fix 1 — Fail-safe state loading (`state.py`):**
- `load()` now aborts the run (`SystemExit(1)`) if the gist can't be read,
  instead of silently returning empty state
- `save()` refuses to write unless a `_loaded_from_gist` flag confirms data
  was actually loaded from the gist
- A transient error now safely kills the run instead of nuking all data

**Fix 2 — Concurrency control (`pbp-reminder.yml`):**
- Added `concurrency: group: pbp-checker` so two workflow runs can never
  touch the gist simultaneously — the second run queues until the first finishes

**State restored** from last good gist revision (Mar 5 11:14, 43 players,
952 messages) via the gist API, with the current offset preserved.

---
## [4.1.0] - 2026-03-05

### Added — Telegram Command Menu

Registered a `/` command autocomplete menu via `setMyCommands`. Two scopes:
- **All group members** (31 commands): read-only player commands
- **Group admins** (63 commands): full set including GM tools

Run `scripts/set_commands.py` after adding new commands to update the menu.

### Fixed — POTW Boon Buttons

Boon inline keyboard buttons silently failed because Telegram requires
`answerCallbackQuery` within ~10 seconds, but the bot runs hourly via cron.

- Removed `answer_callback` calls (always timed out)
- Button clicks now send a visible confirmation message instead
- Added `remove_keyboard=True` to `edit_message` to strip buttons after selection
- POTW announcement now includes "/chooseboon N" fallback instructions
- Auto-expiry at 48h also strips the keyboard

### Fixed — Per-Campaign GM Appearing Twice in Roster

Link (`@Linksanelf2006`) showed as both "GM" and "Link" in the Theria roster.
`post_roster_summary` iterated all players without filtering GMs, then added
GM entries separately. Added `if uid in gm_ids: continue` to the player loop.

### Updated — README

Rewrote to reflect modular codebase: 9-package architecture diagram,
full 69-file structure with descriptions, 18-entry feature table,
live dashboard URL, 11 previously missing commands documented.

---
## [4.0.0] - 2026-03-04

### Refactored — Complete Codebase Modularization

Refactored `checker.py` from a single 5,155-line file into 69 production
files across 9 packages. Every file held to a strict 200-line maximum.
341 tests passing throughout (286 + 37 + 18).

**10-chunk extraction, executed incrementally with live deployment after each:**

| Chunk | What | Lines moved |
|-------|------|-------------|
| 1 | Boons package + scaffold all directories | 60 |
| 2 | Combat (3 modules) + message parsing | 482 |
| 3 | Status, campaign, player command builders | 492 |
| 4 | 17 more command builders → 7 modules | 958 |
| 5 | Transcript system → 3 modules | 427 |
| 6 | 23 scheduled tasks → 13 modules | 1,625 |
| 7 | Command router → dispatch system (11 modules) + players | 1,355 |
| 8 | helpers.py (864 lines) → 8 submodules | 864 |
| 9-10 | Final cleanup, compat aliases, 200-line enforcement | — |

**Result:** `checker.py` went from 5,155 lines to 126 (orchestrator only).
`helpers.py` went from 864 lines to 49 (re-export facade).

```
scripts/
  checker.py        126 lines  (orchestrator)
  helpers.py         49 lines  (re-export facade)
  boons/              2 files  (POTW boon system)
  combat/             4 files  (combat tracker)
  commands/          10 files  (all /command builders)
  dispatch/          12 files  (command routing + tracking)
  helpers_pkg/        9 files  (config, formatting, dice, DC, mechanics)
  parsing/            2 files  (message parser)
  players/            2 files  (kick, addplayer)
  scheduled/         14 files  (all cron tasks)
  transcript/         4 files  (PBP logging)
```

### Fixed — GM Excluded From Player Counts

The GM was counted as a player everywhere, inflating party sizes by 1.
Fixed in 7 locations: every `player_count = len(players)` now filters GMs.

### Fixed — Per-Campaign GM Support

Added `gm_user_ids` per topic_pair in config, replacing the global GM list
for that campaign only. Link (`@Linksanelf2006`, user ID `7863964681`)
configured as Theria's GM.

### Added — Boon Storage System

- `/chooseboon N` text fallback for broken inline buttons
- `/boons` shows your boons in the current campaign
- `/boonsall` shows all boons across campaigns
- Boons stored in state with date, campaign, week number

### Added — Anniversary Next-Up Countdown

Anniversary messages now include "Next up: Campaign X (Nd away)" showing
which campaign's anniversary is coming next.

### Fixed — Slash Command Parsing

Commands with `@botname` suffix (e.g. `/status@PathWarsNudgeBot`) now
strip the suffix correctly. Fixed `/lootlist` and other commands that
weren't responding in group chats.

---
## [3.1.2] - 2026-02-28

### Improved — Weekly Leaderboard

- **Week number**: Header now shows ISO week number (e.g. "Week 9")
- **Weekly totals**: Summary line with total posts (player/GM split) across all active campaigns
- **MVP of the Week**: Top poster by volume gets a 🏆 callout and earns 1 Hero Point in a campaign of their choice

---
## [3.1.1] - 2026-02-28

### Improved — Transcript Readability

- **Day separators**: `### 📅 Wednesday, Feb 26` inserted when the date changes within a week
- **Silence gap markers**: `*— 18h of silence —*` shown for 12+ hour gaps (48h+ shown in days)
- **Quote formatting**: PBP `>` and `>> -` syntax rendered as proper markdown blockquotes
- **Mechanical content styling**: Dice rolls, DCs, and hit results styled in italics
- **Monthly stats footer**: Completed months get a `📊 Month Summary` with message counts, active days, word count, and most active posters
- **Improved caching**: Unified `_transcript_cache` tracks week, date, and timestamp per campaign/month

### Tests

- 6 new transcript tests (day headers, silence gaps, multi-day silence, quote formatting, mechanical styling, monthly stats)
- **341 total**

---
## [3.1.0] - 2026-02-28

### Improved — Reading Experience

#### /recap overhaul
- **Character names**: Shows character names (e.g. `Cardigan`) instead of player names
- **GM tags**: GM posts marked with 🎲 for instant recognition
- **Scene boundaries**: Scene markers (━━━ 🎭 The Dark Cave ━━━) appear inline
- **Time gaps**: Shows `⋯ 12h later ⋯` between posts separated by 4+ hours
- **Better truncation**: 200 chars at word boundaries instead of hard-cut at 120
- **Newline markers**: Multi-line posts show ↩ for line breaks
- **HTML formatting**: Bold poster headers for cleaner visual hierarchy

#### /catchup overhaul
- **Actual content**: Now shows the last 8 posts since your last message, not just counts
- **Combat awareness**: Tells you if you've already acted or still need to post
- **Recap hint**: Suggests `/recap N` when there are more posts than shown
- **Better time formatting**: Uses "3h", "1d 6h" instead of raw hours

### Other
- 4 new tests (316 total)
- Updated daily tips for /recap and /catchup

---
## [3.0.1] - 2026-02-28

### Improved
- Pace report now shows ISO week numbers (e.g. "This week W09", "Last week W08")
- PBP transcript logs now insert `## Week N (Mon DD–Mon DD)` headers when the ISO week changes
- Week headers make it easy to find specific weeks when scrolling through monthly logs

---
## [3.0.0] - 2026-02-28

### Changed — Combat System Rebuild (Foundry-compatible)

Rebuilt the combat tracker to complement Foundry VTT rather than replace it.
Foundry handles mechanics; the bot handles async turn coordination.

#### New workflow
1. `/combat Ogre, 2 Skeletons` — starts combat with named enemy roster
2. Players post their actions naturally (bot tracks who's posted)
3. **Auto-notify**: GM gets pinged when all players have acted
4. `/next` — advance phase (players→enemies→next round). No more `/round N phase`
5. `/clog The ogre crits Cardigan!` — log key combat moments
6. `/endcombat` — end combat with a log summary

#### New commands
- `/combat [enemies]` (GM): start combat with optional enemy list
- `/next` (GM): advance to next phase/round automatically
- `/enemies [list]` (GM): view or update enemy roster mid-combat
- `/clog <event>` (GM): add combat log entry
- `/combatlog` (everyone): view combat log
- `/round N phase` still works for manual overrides

#### Improvements
- **Auto-GM-ping**: When every non-away player has posted actions, bot notifies GM
- **Per-player timestamps**: `/whosturn` now shows how long each player has been waiting
- **Enemy roster**: visible in `/whosturn` and stored in combat state
- **Combat log**: narrative record of key moments, shown in `/endcombat` summary
- **Elapsed time formatting**: "30m", "3h", "1d 6h" instead of raw hours
- `players_acted` changed from list to dict (auto-migrates old format)

#### Breaking changes
- Combat state format changed (auto-migrates old list format)
- `_handle_combat_message()` signature changed (added raw_text, user_name)

### Other
- 11 new tests (312 total)
- Updated daily tips for new combat workflow

---
## [2.9.0] - 2026-02-28

### Added — HP Tracker, Progress Clocks & Status Integration

#### HP Tracker (combat management)
- `/hp set [name] <current>/<max>` (GM): set up enemy HP with visual bars
- `/hp d [name] <amount>` (GM): deal damage, shows 💀 DOWN! at 0 HP
- `/hp h [name] <amount>` (GM): heal (capped at max)
- `/hp remove [name]` (GM): remove a single entry
- `/hp clear` (GM): wipe all HP entries after combat
- `/hp` (everyone): view HP tracker with colour-coded bars ████░░
- Max 20 HP entries per campaign

#### Progress Clocks (investigations, rituals, countdowns)
- `/clock [name] <segments>` (GM): create a 2–12 segment clock ◉◉◉○○○
- `/tick [name] [N]` (GM): advance a clock (default 1 segment)
- `/untick [name] [N]` (GM): reverse a clock
- `/delclock [name]` (GM): remove a clock
- `/clocks` (everyone): view all clocks, ✅ shown when complete
- Max 15 clocks per campaign

#### Status integration
- `/status` now shows HP tracker (alive/total), conditions, clocks
- `/summary` shows full HP bars and clock progress

### Fixed
- Timer expiry notification crash (was trying to unpack chat_topic_id as tuple)

#### Other
- 2 new daily tips (HP tracker, progress clocks)
- 22 new tests (301 total)

---
## [2.8.0] - 2026-02-28

### Added — NPC Tracker & Condition Tracker

#### NPC tracker
- `/npc [name] — <desc>` (GM): add NPC with name and description
- `/npcs`: view all tracked NPCs — a living dramatis personae
- `/delnpc <N>` (GM): remove an NPC
- Supports em-dash, double-hyphen, or single-hyphen separators
- Max 40 NPCs per campaign

#### Condition tracker
- `/condition <target> — <effect> [| duration]` (GM): track buffs/debuffs
- `/conditions`: view all active conditions with targets and durations
- `/endcondition <N>` (GM): remove a specific condition
- `/clearconditions` (GM): wipe all conditions (e.g. after combat ends)
- Duration is optional free-text (e.g. "1 round", "until end of next turn")

#### Other
- 2 new daily tips (NPCs, conditions)
- 11 new tests (258 total)

---
## [2.7.0] - 2026-02-28

### Added — DC Lookup, Pins & Loot Tracker

#### `/dc` command (everyone)
- PF2e DC lookup: `/dc 5` shows all DCs for level 5, `/dc 5 hard` for specific
- Proficiency DCs: `/dc trained`, `/dc master`, `/dc legendary`
- Short aliases: `e`, `h`, `vh`, `ih`, `t`, `ex`, `m`, `l`
- Covers levels 0–20, all 7 difficulty adjustments, 5 proficiency tiers

#### Pin system (story bookmarks)
- `/pin <text>` (GM): bookmark a key story moment, clue, or revelation
- `/pins`: view all bookmarks with dates and author
- `/delpin <N>` (GM): remove a pin
- Max 30 pins per campaign

#### Loot tracker
- `/loot <item>` (GM): add item to party loot
- `/lootlist`: view all party loot
- `/delloot <N>` (GM): remove claimed/sold item
- Max 50 items per campaign

#### Other
- 3 new daily tips (DC, pins, loot)
- 16 new tests (247 total)

---
## [2.6.0] - 2026-02-27

### Added — Quest Tracker & GM Dashboard

#### Quest tracking
- `/quest <text>` (GM): add active quest/objective
- `/quests`: view all quests (active + completed) with numbered list
- `/done <N>` (GM): mark quest as completed with timestamp
- `/delquest <N>` (GM): remove quest entirely
- Max 20 quests per campaign; active shown first, completed with date

#### GM dashboard
- `/gm` (GM only): compact all-campaign overview in one message
- Shows: health icon (🟢🟡🟠🔴), weekly posts, player count, last post age
- Flags: ⏸️ paused, ⚔️ combat active, ✈️ away count, ⚠️ at-risk count, 📋 quest count
- Cross-campaign totals at bottom

#### Other
- 2 new daily tips (quests, GM dashboard)
- 9 new tests (231 total)

---
## [2.5.0] - 2026-02-27

### Added — Dice Roller
- `/roll <dice> [label]`: roll dice with Pathfinder-standard notation
  - `1d20+5 Stealth` — attack/skill rolls with labels
  - `2d6+3` — damage rolls with modifiers
  - `4d6kh3` — keep highest (ability scores)
  - `2d20kl1` — keep lowest (disadvantage)
  - Multiple dice groups: `1d20+5 2d6+3`
- Uses character name when configured (e.g. "🎲 Cardigan — Stealth:")
- Strikethrough on dropped dice in keep-highest/lowest rolls
- 1 new daily tip, 12 new tests (222 total)

---
## [2.4.0] - 2026-02-27

### Added — Absence Tracking & Recap

#### `/away` command
- Players declare absences: `/away 3 days vacation`, `/away 2 weeks`,
  `/away busy with work` (indefinite)
- Supports duration parsing: N days, N weeks, or freeform text
- Away players are **skipped** in inactivity warnings and combat pings
- Away status shown in `/status` (✈️ Away line) and `/party` output
- Auto-clears when the player posts a non-command message
- Timed absences auto-expire when their `until` date passes

#### `/back` command
- Manually clear away status before the timer expires
- Sends a welcome-back message with character name if configured

#### `/recap [N]` command
- Shows the last N transcript entries (default 10, max 25)
- Reads from `data/pbp_logs/` archive files — works with historical imports
- Compact format: `[date time] Name: message snippet`
- Spans multiple month files if needed

#### Integration
- 2 new daily tips (away and recap features)
- `helpers.is_away()` centralises away checking with auto-expiry
- `helpers.parse_away_duration()` handles duration parsing
- 17 new tests covering all commands, integrations, and edge cases

---
## [2.3.0] - 2026-02-27

### Added — Word Count Tracking
- Every PBP message now tracks word count per-user per-campaign
- `/mystats` shows total words written and average words per post
- `/profile` shows word counts per-campaign and total across all campaigns
- Weekly archive includes per-player word counts and campaign totals
- New daily tip explaining the word count feature
- 3 new tests (word count accumulation, mystats output, profile output)

---
## [2.2.1] - 2026-02-27

### Changed — Dashboard v2
- Rebuilt GitHub Pages dashboard with summary cards (campaigns, posts, players, avg gap)
- Week selector filter to view any archived week
- Sortable campaign table with column headers
- Click-to-expand player drill-down rows showing per-player posts, sessions, avg gap
- Campaign health indicators (colour-coded dots)
- Week-over-week trend percentages with colour coding
- Mobile-responsive layout (2-column summary on small screens)

### Changed — Cleaner alerts
- Removed `/pause` suggestion from silence alerts and pace drop alerts (less noise)

---
## [2.2.0] - 2026-02-26

### Summary
Activity insights. Track posting patterns and view cross-campaign player
profiles. Know when your campaigns are most active.

### Added — Activity tracking
- Every message now records hour-of-day and day-of-week counters in
  `activity_hours` and `activity_days` state fields. Lightweight
  permanent counters (24 hour buckets + 7 day buckets per user per
  campaign) that never need pruning.

### Added — `/activity` command
- Shows campaign-level posting patterns: busiest days (bar chart),
  busiest time blocks, peak hour, and top 3 most active posters.
- Available to all players and GMs.

### Added — `/profile` command
- Cross-campaign player lookup: `/profile @alice` or `/profile Alice`.
- Shows every campaign the player is in: post counts, character names,
  last activity, and active streaks.
- Matches by username, first name, or full name (case-insensitive).
- Works for any player in any monitored campaign.

### Added
- 2 new daily tips (activity patterns, player profiles).

### Tests
- 8 new tests: activity tracking counters, activity command, activity
  empty, activity via message, profile command, profile not found,
  profile no target, profile cross-campaign.
- Total: 208 tests (37 helpers + 153 checker + 18 import).

---
## [2.1.0] - 2026-02-26

### Summary
Scene markers and GM notes. GMs can now mark narrative scene boundaries
in transcripts and maintain persistent notes per campaign.

### Added — Scene markers
- **`/scene <name>`** (GM only): marks a scene boundary in the campaign's
  transcript file with a styled divider. Scene name stored in state and
  displayed in `/status` and `/campaign` output.
- Transcript entries: `### 🎭 Scene: <name>` with timestamp, surrounded
  by horizontal rules for clear visual separation.

### Added — GM notes
- **`/note <text>`** (GM only): adds a persistent note to the campaign.
  Max 20 notes per campaign. Timestamped on creation.
- **`/notes`** (everyone): view all GM notes for the current campaign,
  numbered with creation dates.
- **`/delnote <N>`** (GM only): delete a note by its number.
- Latest 3 notes shown in `/campaign` output with "see all" hint.

### Added
- 2 new daily tips (scene markers, GM notes).
- New state fields: `current_scenes`, `campaign_notes`.

### Tests
- 14 new tests: scene command, scene no-name, scene non-GM, scene in
  status, scene in campaign, note command, note no-text, note max limit,
  notes command, notes empty, delnote, delnote invalid, notes in campaign,
  write_scene_marker transcript.
- Total: 200 tests (37 helpers + 145 checker + 18 import).

---
## [2.0.0] - 2026-02-26

### Summary
Dashboard v2 and smart alerts. The GitHub Pages dashboard now has summary
cards, week filtering, sortable columns, and click-to-expand player
drill-downs. Smart alerts detect pace drops (>40% week-over-week) and
total silence (48h+ from everyone including GM).

### Added — Dashboard v2
- **Summary cards**: campaigns, weekly posts, active players, avg response gap.
- **Week filter**: dropdown to view any archived week's data.
- **Sortable columns**: click any table header to sort asc/desc.
- **Player drill-down**: click a campaign row to see per-player stats
  (posts, sessions, avg gap) for that week.
- **Health indicators**: colour-coded dots (green/yellow/orange/red) by
  weekly post volume.
- **Trend arrows**: week-over-week change shown with colour-coded percentages.
- **Mobile-responsive**: works on phone screens with adapted grid layout.

### Added — Player breakdown in archive
- `player_breakdown` field in `weekly_archive.json` stores per-player
  stats for each week: posts, sessions (unique days), and avg gap.
- Powers the dashboard drill-down feature.

### Added — Smart alerts
- **Pace drop detection**: if a campaign's posts drop >40% vs the
  previous week (minimum 5 posts/week baseline), a gentle alert is sent
  to the chat topic. Weekly cadence, won't spam.
- **Conversation dying**: if ALL participants (including GM) go silent
  for 48h+, a one-time alert fires. Resets automatically when anyone
  posts. Skips paused campaigns. Use `/pause` to silence during breaks.
- Both gated behind `smart_alerts` feature flag (enabled by default,
  disable per-campaign via `disabled_features`).

### Added — New daily tips
- Tip explaining smart alerts and how to silence them with `/pause`.
- Tip explaining the `/overview` command for cross-campaign monitoring.

---
## [1.9.0] - 2026-02-26

### Summary
Character awareness. Campaigns can now map player IDs to character names.
Characters appear in rosters, `/mystats`, `/party`, and transcripts.

### Added — `/party` command
- Shows the in-fiction party: character names, who plays them, activity status.
- Active vs inactive breakdown.
- Requires `characters` config on the campaign's topic_pair.

### Added — Character names throughout
- **Roster summaries**: player lines show "Alice (Cardigan)" when configured.
- **`/mystats`**: header shows "playing Cardigan" when configured.
- **Transcripts**: log entries show "**Alice** (Cardigan)" for player messages.
- Config field: `"characters": {"user_id": "Character Name"}` per campaign.

### Added
- `helpers.get_characters()` and `helpers.character_name()` lookup functions.
- New daily tip for `/party`.

### Tests
- 6 new tests: character_name helper, get_characters, party with/without
  characters, mystats with character, transcript with character.
- Total: 178 tests (37 helpers + 123 checker + 18 import).

---
## [1.8.0] - 2026-02-26

### Summary
Message milestone celebrations. The bot now celebrates every 500th PBP
message per campaign and every 5,000th message across all campaigns.

### Added — Message milestones
- Campaign milestones: every 500 messages (500, 1000, 1500, ...) posted
  to the campaign's chat topic with a unique icon per tier.
- Global milestones: every 5,000 messages across all campaigns, posted
  to the leaderboard topic.
- Tracked in `state["celebrated_milestones"]` to prevent duplicate posts.
- Icons progress: 🎯 → 🏅 → ⚡ → 🔥 → ⭐ → 💎 → 🌟 → 👑 → 🏆 → 🎆

### Added
- New daily tip for message milestones.
- Added to `_run_checks` scheduler.

### Note
Milestones are based on the bot's live message count (messages tracked
since the bot was deployed). Historical imports populate transcripts
but don't retroactively update the live counts. Milestones will fire
naturally as campaigns continue posting.

### Tests
- 4 new tests: campaign 500, not repeated, campaign 1000, global 5000.
- Total: 172 tests (37 helpers + 117 checker + 18 import).

---
## [1.7.0] - 2026-02-26

### Summary
New `/catchup` command shows players what happened since they last posted.
Perfect for PBP where you might come back after a few days to find 30+ new
messages across multiple people.

### Added — `/catchup` command
- Shows how many messages were posted since your last one and who posted them.
- Tells you if combat started while you were away (round, phase).
- Handles edge cases: no history, just posted, nobody posted since you.
- New daily tip for `/catchup`.
- Added to help text.

### Tests
- 5 new tests: no history, caught up, nobody posted, messages with counts,
  combat awareness.
- Total: 165 tests (37 helpers + 112 checker + 16 import).

---
## [1.6.0] - 2026-02-26

### Summary
GM roster management commands. GMs can now manually add and remove players
from campaign tracking without waiting for automatic processes.

### Added — `/kick` command (GM only)
- `/kick @username` or `/kick PlayerName` removes a player from this
  campaign's roster immediately.
- Player is moved to the removed list (same as auto-removal at 4 weeks).
- Kicked players can rejoin by posting in PBP again.
- Matches by username, first name, or full name (case-insensitive).

### Added — `/addplayer` command (GM only)
- `/addplayer @username Player Name` pre-registers a player on the roster
  before they've posted.
- Creates a placeholder entry that updates with full stats on first post.
- Prevents duplicates (checks existing roster).
- Clears any previous removal record for that player.

### Added
- 2 new daily tips for `/kick` and `/addplayer`.
- Help text updated with new commands.

### Tests
- 6 new tests: kick by username, kick by name, kick no match,
  addplayer, addplayer duplicate, addplayer clears removed.
- Total: 160 tests (37 helpers + 107 checker + 16 import).

---
## [1.5.0] - 2026-02-26

### Summary
Historical transcript backfill. A new import script reads Telegram Desktop
JSON exports and populates the transcript archive with all past PBP messages.
Also adds Theria (C08) to the tracked campaigns with per-campaign GM support.

### Added — History Import
- `scripts/import_history.py`: imports historical PBP messages from Telegram
  Desktop JSON exports into the same `data/pbp_logs/` format the live bot uses.
- Supports `--dry-run` to preview without writing files.
- Idempotent: tracks imported message IDs per campaign, safe to run repeatedly.
- Handles Telegram's mixed text/entity format, media detection, GM tagging.
- 16 tests for the import script.

### Added — Theria (C08)
- New campaign: PBP topic 107151, Chat topic 107141, started 2025-10-06.
- Disabled features: warnings, recruitment (not Lewis's campaign).
- Per-campaign `gm_user_ids` override: when a campaign has its own `gm_user_ids`
  in config, it replaces the global list for that campaign only. All 8 functions
  that check GM status now use per-campaign resolution.
- 3 new helper tests for `gm_ids_for_campaign`.

### Tests
- 16 new import tests + 3 new helper tests.
- Total: 154 tests (37 helpers + 101 checker + 16 import).
- CI updated to run import tests.

---
## [1.4.0] - 2026-02-26

### Summary
PBP transcript archiving. Every message in every PBP topic is now logged to
persistent markdown files in the repo — a complete, readable backup of every
campaign's story. If Telegram dies, the campaigns live on.

### Added — PBP Transcript Archive
- Every non-command message in every PBP topic is now appended to a monthly
  markdown transcript file at `data/pbp_logs/{CampaignName}/{YYYY-MM}.md`.
- Transcripts include: timestamp, player/GM name, role tag, message text.
- Media is logged with type markers: `*[image]*`, `*[sticker 😂]*`, `*[gif]*`,
  `*[video]*`, `*[voice message]*`, `*[document:filename.pdf]*`. Captions are
  preserved alongside media markers.
- An auto-generated `data/pbp_logs/README.md` index lists all campaigns with
  message counts and links to monthly log files.
- Files are committed to the repo hourly via GitHub Actions alongside the
  existing weekly archive.
- Only PBP topic messages are logged. Chat topics and bot commands are excluded.

### How It Works
The transcript files are standard markdown, readable directly on GitHub or any
markdown viewer. Each monthly file has a header and chronological entries:

```
# Doomsday Funtime — 2026-02

*PBP transcript archived by PathWarsNudge bot.*

---

**Alice** (2026-02-26 14:30:05):
I attack the goblin with my longsword!

**Lewis** [GM] (2026-02-26 14:32:10):
The goblin shrieks as the blade connects. Roll damage.

**Bob** (2026-02-26 14:35:22):
*[image]* battle map update
```

### Changed
- `_parse_message` now extracts media type (photo, sticker, gif, video, voice,
  document) and caption from Telegram messages.
- GitHub Actions workflow commit step updated to include transcript data.

### Tests
- 7 new tests: _sanitize_dirname, _format_log_entry (text, GM, image, sticker),
  _append_to_transcript (write + append), _parse_message media capture.
- All test suites redirected to temp directory for transcript writes.
- Total: 135 tests (34 helpers + 101 checker).

---
## [1.3.0] - 2026-02-26

### Summary
GM tools and personal history. GMs can now pause/resume inactivity tracking
for breaks between arcs or holidays. Players can view their 8-week posting
history as a text sparkline chart.

### Added — New Commands
- **/myhistory**: Shows a text sparkline of your weekly post counts over
  the last 8 weeks. Includes total posts, peak week, current week, and
  trend direction. The sparkline uses Unicode block characters (▁▂▃▄▅▆▇█)
  for a compact visual at-a-glance view of posting patterns.
- **/pause [reason]** (GM only): Pauses inactivity tracking for the campaign.
  All topic alerts and player warnings are suppressed while paused. The
  pause reason is shown in `/status` and `/campaign`. Use for planned breaks,
  holidays, or between-arc downtime. Non-GMs cannot use this command.
- **/resume** (GM only): Resumes inactivity tracking after a pause. Confirms
  in chat when tracking is re-enabled.

### Changed
- `/status` and `/campaign` now show ⏸️ PAUSED with reason when a campaign
  is paused.
- `check_and_alert` and `check_player_activity` both skip paused campaigns.
- 2 new daily tips added (covering /myhistory and /pause).
- Help text updated with all new commands.

### Tests
- 13 new tests: sparkline (3), myhistory (3), /pause command (2),
  /resume command (1), pause blocking (2), pause display (2).
- Total: 128 tests (34 helpers + 94 checker).

---
## [1.2.0] - 2026-02-26

### Summary
Streaks, celebrations, and cross-campaign intelligence. The bot now celebrates
posting milestones, shows streaks in rosters and leaderboards, and posts a
compact weekly digest with health-scored campaign summaries.

### Added — Streak Milestones
- The bot automatically celebrates when a player crosses a streak milestone:
  7, 14, 30, 60, or 90 consecutive days of posting. Each milestone has a
  unique message (scaling from 🔥 to 👑). Milestones are tracked per player
  per campaign and never posted twice for the same milestone. The streak must
  be continuous — missing a single day resets it.

### Added — Streak in Roster & Leaderboard
- **Roster**: Each player's entry now shows their current streak with a 🔥
  emoji if 2+ days. Adds one line to roster blocks only when relevant.
- **Leaderboard**: New "🔥 Longest Active Streaks" section at the bottom of
  the weekly leaderboard. Shows top 5 players across all campaigns, with
  streak length and campaign name.

### Added — Weekly Digest
- A compact one-line-per-campaign newsletter posted to the leaderboard topic
  once per week. Each line shows: health icon (🟢🟡🟠🔴 based on post volume),
  campaign name, post count with trend arrow, party size, active combat flag,
  and the week's MVP (most active player). Includes a colour legend.
  Designed to be scannable in under 10 seconds.
- Health scoring: 🟢 = 20+ posts/week, 🟡 = 10-19, 🟠 = 5-9, 🔴 = under 5.

### Changed
- `_gather_leaderboard_stats` now returns a 3-tuple including streak data.
- `_format_leaderboard` accepts optional `streaks` parameter.
- `_roster_user_stats` return dict now includes `streak` field.
- `_roster_block` displays streak when ≥ 2 days.
- `_run_checks` now includes streak milestones (14 scheduled checks total).

### Tests
- 8 new tests: streak milestones (3), weekly digest (2), leaderboard streaks (1),
  roster streak display (2).
- Total: 115 tests (34 helpers + 81 checker).

---
## [1.1.0] - 2026-02-26

### Summary
Player self-service update. Three new commands let players check their own stats,
inspect combat status, and discover features through daily tips. Plus a roadmap,
versioning pipeline, and 20 new tests.

### Added — New Commands
- **/mystats** (alias: **/me**): Players type `/mystats` in any PBP topic to see
  their personal stats: total posts, posting sessions, average gap between posts,
  weekly activity count, last post time, and current posting streak. Works for both
  players and GMs. No need to wait for roster day — check any time.
- **/whosturn**: Anyone can check combat status on demand. Shows: current round,
  whose phase it is (players/enemies), who has already acted (✅), and who the party
  is waiting on (⏳). During enemy phase, shows "Waiting for GM." Works outside the
  ping timer schedule so players can check without waiting for the automatic ping.

### Added — Daily Tips
- The bot now posts one random tip per day to a randomly chosen PBP chat topic.
  Each tip explains a bot feature (commands, combat tracking, POTW, streaks, etc).
  Tips rotate through all 12 entries before repeating, so every feature gets explained.
  This helps players who don't read GitHub or the issues topic discover what the bot
  can do. Tips are posted with HTML formatting for readability.

### Added — Posting Streaks
- The bot now tracks consecutive days with posts and displays the streak in `/mystats`.
  A "streak" means posting at least once per day with no gaps. Posts yesterday count
  as maintaining the streak. Streak resets if you miss a day. Shows 🔥 emoji for
  streaks of 2+ days.

### Added — Infrastructure
- **ROADMAP.md**: Full feature roadmap through v1.4.0+ with planned features
  (streaks leaderboard, weekly digest, campaign health scoring, dashboard improvements,
  GM tools, smart alerts, character awareness, AI summaries) and status tracking.
- **Changelog notifications**: When CHANGELOG.md is pushed, the `changelog-notify.yml`
  workflow posts the latest entry (formatted as Telegram HTML) to the Foundry & GitHub
  topic (https://t.me/Path_Wars/71537). Uses `post_changelog.py` which parses markdown,
  converts bold/italic/code/headers to HTML tags, and splits messages if they exceed
  Telegram's 4096 char limit.
- **VERSION file**: Semver-based version tracking. MAJOR = breaking config changes,
  MINOR = new features/commands, PATCH = fixes/tests/docs.

### Changed
- `telegram.py`: `send_message()` now accepts optional `parse_mode` parameter for
  HTML-formatted messages (used by daily tips).
- Help text updated with `/mystats`, `/me`, `/whosturn`, and daily tips.

### Tests
- 20 new tests: _build_mystats (4), _calc_streak (5), _build_whosturn (4),
  /whosturn command (1), /mystats command (2), daily tips (4).
- Total: 107 tests (34 helpers + 73 checker).

---
## [1.0.0] - 2026-02-26

### Summary
First versioned release. Consolidates all prior refactoring work (sessions 1–4)
plus today's new features into a stable, tested baseline.

### Added — New Features
- **/campaign command**: Type `/campaign` in any PBP topic to get a full scoreboard:
  campaign age, party size, weekly pace with trend arrows, complete roster with
  per-player stats (total posts, sessions, weekly count, average gap, last post),
  at-risk player warnings, and active combat state. This replaces the need to wait
  for scheduled roster/pace reports — players can check on demand.
- **/status command**: Quick health snapshot — party size, last post time, posts
  this week, at-risk players, combat state.
- **/help command**: Lists all bot features and GM commands in-chat.
- **Per-campaign feature toggles**: Add `"disabled_features": ["potw", "recruitment"]`
  to any campaign in config to turn off specific features per campaign. Valid toggles:
  alerts, warnings, roster, potw, pace, recruitment, combat, anniversary.
- **Config validation on startup**: Bot checks config structure before running —
  catches bad group_id, duplicate topic IDs, unknown feature names, malformed dates.
  Errors prevent the run; warnings are logged but continue.
- **Archive dashboard** (docs/index.html): Interactive web dashboard for
  weekly_archive.json. Line charts for posts per week, GM vs player splits, response
  gap trends, and a sortable campaign comparison table. Dark RPG-themed design.
  Works on GitHub Pages or locally.
- **Changelog notifications**: Bot posts release notes to the Foundry & GitHub
  topic automatically after each push.
- **Versioning**: Semver-based VERSION file and CHANGELOG.md.

### Added — Code Quality
- **87 tests** (32 helpers, 55 checker) covering: message parsing, combat state
  machine, boon selection/expiry, player warnings and removal, leaderboard stats,
  anniversary detection, recruitment checks, feature toggles, config validation,
  pace calculations, roster formatting, and all helper utilities.
- **CI test gate**: Tests run before the checker in GitHub Actions. If tests fail,
  the checker doesn't execute.
- **Extracted `_parse_message`**: Message validation and field extraction pulled out
  of `process_updates`, reducing the main loop from 111 to 75 lines.
- **Extracted `pace_split` helper**: Deduplicated GM/player weekly post split logic
  used by both `/campaign` and pace reports.
- **Shared timestamps**: All 11 per-run features now receive identical `now` and
  `maps` objects, eliminating 13 redundant `datetime.now()` calls per run.

### Removed
- `pbp_summary_feature.py`: Unused 206-line AI summary prototype. The `/campaign`
  command now fills this role without requiring an API key.

### Architecture (for reference — pre-v1.0.0 refactoring)
The codebase was restructured across 4 sessions from a single 1,200-line file into:
- `checker.py` (1,468 lines, 27 functions): All bot features and orchestration.
- `helpers.py` (418 lines, 28 functions): Pure utilities, constants, config loading.
- `telegram.py` (105 lines, 7 functions): Telegram Bot API wrapper.
- `state.py` (103 lines, 3 functions): Gist-backed state persistence.
- `test_helpers.py` (314 lines, 32 tests): Helper function test suite.
- `test_checker.py` (1,069 lines, 55 tests): Checker integration and unit tests.
- `docs/index.html` (411 lines): Archive dashboard.

Every function has docstrings and return type hints. Max nesting: 4 levels.
All settings are configurable via `config.json` with sensible defaults.
