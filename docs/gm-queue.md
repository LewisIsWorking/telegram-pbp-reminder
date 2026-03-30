# GM Reply Queue

## What it is

The GM reply queue tracks every player message that hasn't received a
direct GM reply yet. It gives the GM a prioritised list of what needs
a response across all campaigns.

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

## Viewing the queue

`/queue` — posts the full queue sorted by:
1. Priority campaigns first (configured with `queue_priority: true`)
2. Oldest unreplied message first within each campaign

Each entry shows:
- Age icon (⚪🟡🟠🔴🟣🔵🟤 — see below)
- Time since posted
- Player name and message preview
- Direct Telegram link to the message

### Age icon scale

| Icon | Age | Meaning |
|---|---|---|
| ⚪ | < 6 h | Fresh |
| 🟡 | 6–24 h | Same day |
| 🟠 | 1–2 d | Getting old |
| 🔴 | 2–3 d | Overdue |
| 🟣 | 3–5 d | Stalled |
| 🔵 | 5–7 d | Alarming |
| 🟤 | 7 d + | Abandoned |

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
