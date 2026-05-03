# GM Reply Queue

## What it is

The GM reply queue tracks every player message that hasn't received a
direct GM reply yet. It gives the GM a prioritised list of what needs
a response across all campaigns.

---

## Why some entries have no link

Direct 🔗 links to messages require a `msg#12345` tag in the transcript.
These tags started being written on **20 March 2026 (v4.18.0)** when live
message ID tracking was introduced.

Entries from before that date show in the queue without a link — the
Telegram Bot API cannot retroactively fetch message IDs for historical
messages. This only affects pre-v4.18 entries and resolves naturally as
old 🟤 entries are replied to and cleared.

All new messages since 20 March have links.

---

## Reply audit log

Every GM reply is permanently recorded in `state["gm_reply_log"]`
(capped at 500 entries). Each record stores the timestamp, campaign PID,
message ID, player name, message preview, and how it was cleared
(`"reply"` for Telegram reply-to, `"markdone"` for manual clears).

This log survives state resets and provides a full history of GM
responses across all campaigns.

---

## Manual queue management — `/markdone`

If a message was replied to outside Telegram's reply feature, or before
the bot started tracking replies, use `/markdone` in the PBP topic:

| Command | Effect |
|---|---|
| `/markdone` | Clear the oldest unreplied entry |
| `/markdone 3` | Clear entry #3 from the queue list |
| `/markdone 140368` | Clear by Telegram message ID |
| `/markdone all` | Clear all entries for this campaign |

Each manual clear is written to `gm_reply_log` with `"via": "markdone"`.

---

## Queue format

Every queue post has this structure:
```
━━━━━━━━━━━━━━━━
📋 GM Queue #42 — Unreplied: 90 | ✅ 34 cleared today
C06:23 C09:17 C00:7 ...
Age: 🟢<6h 🟡1d 🟠2d 🔴3d 🟣5d 🔵7d 🟤14d ⚫30d+
━━ 📌 🦠 C06: Kibwe (23) ━━ @PathWars ⚡Caelum (~0h)
01 🟣 6d 12h. Link: Kieran will do slime lore... 🔗 https://t.me/...
02 🟣 6d 12h. Link: He has a +15... 🔗 https://t.me/...
```

- **GM Queue #N** — increments every post
- **Position numbers** — 01–99 across all campaigns; Kibwe always starts at 01
- **Campaign emoji** — matches the Telegram chat emoji
- **15-word previews** — enough context to recognise the message
- **Pinned** — latest queue post is always pinned in the bot topic

## Viewing the queue

`/queue` — posts the full queue sorted by:
1. Priority campaigns first (configured with `queue_priority: true`)
2. Oldest unreplied message first within each campaign

Each entry shows:
- Age icon (see legend below)
- Time since posted
- Player name and message preview
- Direct Telegram link to the message (where available)

The queue reminder is **pinned** to the bot topic automatically —
the previous pin is unpinned when a new one is posted.

### Age icon legend

Every queue post includes this in the header:
`Age: 🟢<6h 🟡1d 🟠2d 🔴3d 🟣5d 🔵7d 🟤14d ⚫30d+`

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

---

## Header counters

Every queue post header includes two clear counters:

- **today** -- count of GM-reply clears recorded since 00:00 UTC,
  read from `state.queue_history`.
- **all-time** -- count of every recorded clear across all campaigns,
  read from per-campaign `reply_log` files and filtered to
  `{reply, markdone, manual}` so migration markers are excluded.

Both counters are deduplicated at write time. `queue_io.mark_replied`
returns a bool and the audit-trail append is gated on that flag, so a
Telegram update being replayed (offset retry, edit, etc.) does not
inflate the figures.

## Rolling retention in the GM Queue topic

Only the **last 3 queue post batches** are kept in the GM Queue topic.
When a fourth batch is posted, every message in the oldest batch is
deleted from Telegram so the topic stays scannable.

A *batch* is the full set of messages produced by a single queue post.
A long queue (more than ~4000 chars) is sent as multiple Telegram
messages but counts as one batch — all of its messages are evicted
together when the batch falls off the end.

The retention applies only to the bot's GM Queue topic. Per-topic
pinned queues (in PBP campaign threads) are unaffected — they always
keep exactly one current pin per thread, with the previous pin's
messages deleted on each refresh.

Retention state lives in `state["gm_queue_history"]`, capped at 3
batches; the cap is defined as `MAX_KEPT_BATCHES` in
`scheduled/gm_queue_history.py`.

---

## How entries are cleared

**A queue entry is cleared when the GM uses Telegram's reply-to feature
on that specific message.** The bot detects `reply_to_message_id` and
marks that entry as replied.

**What does NOT clear entries:**
- The GM posting a general message in the topic without replying
- The GM posting commands
- Player messages
- Time passing

This is intentional — the queue represents messages that genuinely need
a GM response, not just topics where the GM has been recently active.

---

## Scheduled reminders

The bot posts the full queue automatically at the hours set in
`queue_daily_hours` (default `[9, 21]` = 9am and 9pm UTC).

It also posts immediately whenever the queue changes (new unreplied
messages arrive), so the GM always has an up-to-date view.

---

## Queue nudge

A separate gentler per-player nudge is sent when a specific player's
message has been waiting unusually long. This is posted to the bot topic
with a personalised message and reply link.

---

## Campaign exclusions

Set `queue_exclude: true` in a campaign's topic_pair to skip it entirely
(e.g. C08 Theria, which has a different GM).

Set `queue_priority: true` to always pin a campaign to the top of the
queue list (e.g. C06 Kibwe).

---

## Queue stats

`/queuestats` — Shows reply streaks, average response time, and
cleared-per-day stats for the GM.

---

## Transcript scanner vs live queue

The queue is built from two sources:

1. **Live queue** (`state["gm_queue"]`) — populated in real time as
   messages arrive. Cleared immediately when the GM replies.

2. **Transcript scanner** (`queue_scan.py`) — scans recent markdown
   transcript files as a backup, catching any messages the live queue
   might have missed (e.g. during bot downtime). Only uses
   `gm_queue_replied` state to filter — does NOT clear on GM activity.

Both sources are merged and deduplicated by the `/queue` command and
the scheduled reminder.
