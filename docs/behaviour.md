# Intended Behaviour

How the bot is designed to work, and why.

---

## GM Reply Queue

### What it tracks
Every non-command player message in a PBP topic is added to the GM reply queue.
The queue is visible via `/queue` and is also posted as a scheduled reminder.

### What clears an entry
**Only a direct Telegram reply** (using Telegram's reply-to feature) from the GM
clears a specific message. The bot detects the `reply_to_message_id` field on
incoming GM messages and marks that specific entry as replied.

### What does NOT clear entries
- The GM posting a general (non-reply) message in the topic.
- The GM posting commands.
- Time passing.
- Any player activity.

This was a known bug before v4.26.0: the transcript scanner treated any GM
message as clearing all accumulated player messages. Fixed — the scanner now
relies solely on reply-to tracking.

### Queue reminder schedule
Posted at the hours configured in `queue_daily_hours` (default: `[9, 21]`
= 9am and 9pm UTC), **plus** immediately whenever the queue fingerprint changes
(new unreplied messages arrive between scheduled posts).

---

## Session Polls (C01 Doomsday Funtime & C11 Dark Pockets)

### Poll lifecycle
1. **Sunday at `poll_post_hour` UTC (default 07:00)** — poll is posted and pinned
   to the campaign's chat topic.
2. **Each day (Mon–Sun)** — players who haven't voted receive a daily ping with a
   direct link to the pinned poll.
3. **Once everyone has voted** — "All X players have voted!" confirmation posted once.
4. **Friday at 15:00 UTC** — result announced in each campaign's chat topic.

### Vote notifications (cross-campaign)
C01 and C11 are linked (`linked_polls` config). When any player votes in either
poll, both chat topics immediately receive a tally update:
```
🗳️ @Nemesiux voted Friday in C01
C01: Friday: 3, Saturday: 1
C11: Weekday: 2
```

### Poll options
- **C01:** Friday / Saturday / Either Friday or Saturday / Both / Can't make it this week (single choice)
- **C11:** Monday–Sunday / Can't make it (multiple choice, any combination)

### Voter ID capture
When a player with a placeholder ID votes, their real Telegram ID is captured
automatically in `state["poll_unknown_voters"]`. Run
`python3 scripts/promote_poll_voters.py --commit` after a vote session to
promote captured IDs into `config.json`.

---

## Player of the Week (POTW)

### Selection
Each campaign independently runs POTW on a configurable interval
(`potw_interval_days`, default 7). The winner is the non-GM player with the
most consistent posting — lowest average gap between posts — with a minimum
post count (`potw_min_posts`, default 5).

### Boon offer
The winner is offered 4 boons (3 random flavour + 1 mechanical). They choose
via inline buttons or `/chooseboon N` in the PBP topic.

The boon choice is permanent once selected. Unchosen boons are logged as
`null` in `potw_history`.

### History
Every POTW event is recorded in `state["potw_history"]` with:
- Week, year, date, campaign, PID
- Winner's user ID, name, username
- Post count and average gap for that week
- All 4 boons offered
- The chosen boon (or `null` if not yet chosen)

### Streaks
- **Campaign streak:** same player wins POTW in consecutive weeks for a single
  campaign. Announced at 2, 3, 5, 10 weeks.
- **Community streak:** same player wins POTW in consecutive weeks across any
  combination of campaigns. Announced at 2, 3, 5 weeks.

---

## Inactivity Alerts

The bot monitors the time since the last message in each PBP topic.

| Threshold | Action |
|---|---|
| `alert_after_hours` (default 24h) | Alert posted to the campaign topic |
| 1 week of player inactivity | First warning to the player |
| 2 weeks | Second warning |
| 3 weeks | Third warning |
| 4 weeks (`player_remove_weeks`) | Player removed from tracking |

Campaigns can be paused with `/pause [reason]` — all inactivity tracking
suspended until `/resume`.

---

## GM Queue Nudge

A separate gentler nudge (distinct from the full queue reminder) is sent
when a specific player's message has been waiting longer than a threshold.
The nudge is personalised per player and includes a direct reply link.

---

## Transcript Archiving

Every non-command message in every PBP topic is appended to a monthly
markdown transcript file at `data/pbp_logs/<Campaign_Name>/YYYY-MM.md`.

The transcript uses this format:
```
**Player Name** (Character) (2026-03-29 14:32:00) msg#140375:
Message content here
```

The `msg#` tag enables the queue scanner to build direct Telegram links
to specific messages.

---

## Weekly Welcome

On Sunday at `poll_post_hour` UTC, the bot posts a "Welcome to Week X"
message in the bot topic. Fires once per Sunday-anchored week alongside
the session poll.

---

## Swimming Poll (Dark Pockets group)

A separate social poll posted Sunday at `poll_post_hour` UTC in the
Dark Pockets group main chat (topic 1). Covers Monday–Sunday with
multiple choice, pinging 7 players daily until they vote.

Voter IDs for new swimmers are captured the same way as C11 session poll IDs.
