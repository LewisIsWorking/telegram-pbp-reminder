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

Entries from before that date show in the queue without a link - the
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

## Manual queue management - `/markdone`

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
📋 GM Queue #42 - Unreplied: 90 | ✅ 34 cleared today
C06:23 C09:17 C00:7 ...
Age: 🟢<6h 🟡1d 🟠2d 🔴3d 🟣5d 🔵7d 🟤14d ⚫30d+
━━ 📌 🦠 C06: Kibwe (23) ━━ @PathWars ⚡Caelum (~0h)
01 🟣 6d 12h. Link: Kieran will do slime lore... 🔗 https://t.me/...
02 🟣 6d 12h. Link: He has a +15... 🔗 https://t.me/...
```

- **GM Queue #N** - increments every post
- **Position numbers** - 01–99 across all campaigns; Kibwe always starts at 01
- **Campaign emoji** - matches the Telegram chat emoji
- **15-word previews** - enough context to recognise the message
- **Pinned** - latest queue post is always pinned in the bot topic

## Viewing the queue

`/queue` - posts the full queue sorted by:
1. Priority campaigns first, by rank (see [Campaign exclusions](#campaign-exclusions)).
   `queue_priority` is a number, lower first; `true` is a legacy alias for rank 1
2. Oldest unreplied message first within each campaign

Each entry shows:
- Age icon (see legend below)
- Time since posted
- Player name and message preview
- Direct Telegram link to the message (where available)

The queue reminder is **pinned** to the bot topic automatically -
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

As of v4.46.0, both counters also include `/markdone` clears (not just Telegram-reply clears). Before this fix the today figure could lag the all-time figure when most clearing happened via the slash command.

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
messages but counts as one batch - all of its messages are evicted
together when the batch falls off the end.

The retention applies only to the bot's GM Queue topic. Per-topic
pinned queues (in PBP campaign threads) are unaffected - they always
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

This is intentional - the queue represents messages that genuinely need
a GM response, not just topics where the GM has been recently active.

### When a clear becomes visible

Clearing is not instant. An entry disappears only after the next workflow run
processes the Telegram update containing your reply, so a queue post can show
entries you have already replied to.

The workflow declares `cron: '13 * * * *'` and `cron: '43 * * * *'` (moved off
`:00`/`:30` on 2026-08-31), but GitHub gives **no timing guarantee** for
scheduled runs and drops them under load. Observed gaps on this repo have run to
2 to 4.5 hours even with the hourly cron. The `:43` queue-only pass exists to
give a second chance each hour; it is not a promise of 30-minute cadence.

### A changed queue is re-checked about 10 minutes later

Lewis, 2026-09-13: *"if the queue changes, refire in 10 minutes or less... if
unchanged go back to 30"*. A change means someone is posting or the GM is
replying right now, which is exactly when waiting half an hour hurts most.

- **What counts as a change:** the queue's fingerprint moved during the run: a
  new unreplied post, a cleared reply, a silent campaign coming or going, or the
  queue emptying. An in-place refresh or the daily repost does **not** count.
- **How:** the run writes `refire=true` to its step output, and after the state
  push starts `queue-refire.yml`. That workflow waits about 7 minutes **outside**
  the `pbp-checker` lock (waiting inside it would stall the scheduled runs), then
  dispatches a normal run with `refire=true`.
- **When it stops:** a re-check that finds nothing changed asks for nothing, so
  the cadence falls back to the schedule by itself. A chain of **6** re-checks in
  a row is the cap (`MAX_CHAIN`, counted in `queue_refire_chain`), so a busy
  evening cannot dispatch a run every 10 minutes indefinitely.

Code: `scripts/scheduled/queue_refire.py`, called from `checker.main`, which
compares the fingerprint before and after the checks. Tests:
`scripts/test_queue_refire.py`, including the workflow wiring, where a typo in a
step id or output name would otherwise switch the feature off silently.

**Before concluding a reply was lost, check the timestamps.** Compare the run
time (`gh run list --workflow "PBP Inactivity Reminder"`) against when you
replied - the committed state in `data/state/queues/*.json` is only as fresh as
the last run that pushed it. `reply_log` in that file records every reply the
bot *has* accepted, so a recent entry there proves the mechanism is working.

---

## Scheduled reminders

The bot posts the full queue automatically at the hours set in
`queue_daily_hours` (default `[9, 21]` = 9am and 9pm UTC).

It also posts immediately whenever the queue changes (new unreplied
messages arrive), so the GM always has an up-to-date view.

⛔ **Until 2026-09-13 it reposted every hour instead, whether or not anything
changed.** The change fingerprint included the silent-campaign lines, and each
line carries an age ("no posts for 13d 20h") that ticks hourly. Measured from
committed state history, **12 of 13 consecutive reposts were only an age
ticking**; one was a real change.

The fingerprint now uses which campaigns are silent, not their rendered lines
(`queue_silence.silent_ids`). A campaign going silent or waking up is a change.

The caught-up section had already been kept out of the fingerprint for exactly
this reason. The silent section was not, which is how it got missed.

### An unchanged queue is refreshed in place

⚠️ **Fixing that removed the only visible sign the bot was alive.** The hourly
repost had doubled as a heartbeat, so a healthy quiet queue became
indistinguishable from a dead one. Lewis reported "the queue isn't updating"
the same day; state history showed it was updating on every real change.

So on a run where the queue has **not** changed, the pinned queue is **edited**
rather than left alone (`scheduled/queue_refresh.py`):

- Its first message carries **"🕒 Checked HH:MM BST"**, updated every run.
- Under it, **"⏭ Next check ~HH:MM BST"**: the next `:13` or `:43` cron.
  Lewis asked for a live countdown (2026-09-15); a Telegram message cannot
  tick, so it shows the time instead. The `~` is honest: GitHub delivers these
  crons late or not at all, and the heartbeat's dispatched runs land at their
  own minute. `CHECK_MINUTES` in `queue_refresh.py` restates the crons, and
  `test_queue_next_check.py` fails if the two drift apart.
- **Ages are current** again, instead of frozen until the next real change.
- **Nothing is posted and nobody is notified**, because Telegram edits don't
  notify. It stays quiet.

It **reposts instead** whenever it cannot edit cleanly, and never needs to know
exactly why:

| Situation | Why it reposts |
|---|---|
| Telegram refuses an edit | Its edit time limit isn't reliably documented (48h per some sources, unlimited for admins per another). A repost makes a fresh message. |
| The message count changed | `post_batch` records a chunk's id only if it sent, so an earlier failure leaves the ids shifted. Editing by position would put text in the wrong message. |
| There's no batch to edit | Nothing was recorded yet. |

**Unchanged messages are skipped, not re-sent.** Only the first message has the
Checked time; the others are often identical between runs, and Telegram rejects
an identical edit as "message is not modified". What each message last said is
kept in `gm_queue_texts`, which **must stay declared in `state_schema.py`**: an
undeclared key is discarded on every save, and the queue would repost every run.

A refresh keeps the current **"GM Queue #N"**. Only a real repost increments it.

---

## Queue nudge

A separate gentler per-player nudge is sent when a specific player's
message has been waiting unusually long. This is posted to the bot topic
with a personalised message and reply link.

---

## "All caught up!" notification

When the queue clears, the bot replaces it with a caught-up message that also
reports how long each campaign has been quiet, **longest idle first**:

```
━━━━━━━━━━━━━━━━
📋 All caught up! No unreplied messages.

━━ 🕒 Time since last post ━━
  💀 🤖 C09: Metal City - no posts for 22d 11h 🔗 ...
  🟡 🦠 C06: Kibwe - last post 3d 7h ago 🔗 ...
```

Notes:
- Campaigns past the silence threshold read "no posts for X"; the rest read
  "last post X ago", matching the wording used inside the queue itself.
- A campaign with unreplied entries never appears here, since it is already
  listed in the queue body.
- A campaign the bot has never seen a post in is skipped entirely, because it
  has no last-post time to report.
- Built by `queue_silence.campaign_age_lines`, rendered by
  `queue_caught_up.post_caught_up`.

---

## Campaign exclusions

Set `queue_exclude: true` in a campaign's topic_pair to skip it entirely.

**C08 Theria (pid `107151`) is excluded because Tyler Link runs it, not the
global GM.** Its topic_pair sets `gm_user_ids: [7863964681]`, which *replaces*
the global GM list for that campaign - see
[Per-campaign GMs](configuration.md#per-campaign-gms). Its queue file still
contains ~180 historical `unreplied` entries from before it was excluded; they
are inert and nothing reports them, so that number is not a backlog.

Set `queue_priority` to pin a campaign above the rest of the queue list.
The value is a **rank, lower wins**. `true` is accepted as a legacy alias
for rank 1.

| Rank | Campaigns |
|------|-----------|
| `1`  | C10 The Junction |
| `2`  | C06 Kibwe, C01 Doomsday Funtime |
| `99` | everything else (`NO_PRIORITY`, implicit) |

Equal ranks are broken by age, so C06 and C01 do not outrank each other.

> ⚠️ **Do not assign a rank of `99` or higher.** `NO_PRIORITY` in
> `commands/queue_format.py` is the implicit rank for unprioritised campaigns;
> a campaign at or above it would sort level with, or below, campaigns having
> no priority at all. This sentinel was `2` until 2026-07-30, which is why only
> one priority level was usable before then.

---

## "Reply to this next" follow-up

After the queue itself, the bot posts a short follow-up naming the single
campaign most in need of a reply:

```
━━━━━━━━━━━━━━━━
🎯 Reply to this next: 📆 C01: Doomsday Funtime
📌 Prioritised campaign, so it jumps the age queue.
⏳ Oldest message waiting 6d 16h (9 unreplied in this campaign).
↗ Horia Constantinescu: "Yes I am grateful for their aid."
🔗 https://t.me/Path_Wars/25059/168196
```

Selection rule (`scheduled/queue_focus.py`):

1. Normally the winner is the campaign whose **oldest** unreplied message has
   been waiting longest.
2. If **any** campaign flagged `queue_priority` has unreplied entries, the
   choice is made among those only. A prioritised campaign is never passed
   over because another campaign has an older message - C01 with a 2-hour-old
   message beats C07 with a 19-day-old one.
3. Between prioritised campaigns, lower rank number wins first, then age.
   So C10 (rank 1) beats C01/C06 (rank 2) whenever C10 is waiting, and when
   C10 is caught up the rank-2 pair take over.

The follow-up is appended to the queue's own message batch, so it is deleted
together with that queue on the next post. That is deliberate: a focus message
outliving its queue would keep pointing at a message already answered.

### Also sent to the GM as a DM, when the target changes

Since 2026-09-13 the same message is DMed to `gm_user_id`, the way the
escalation already is (`scheduled/queue_focus_dm.py`).

⚠️ **Only when the target moves, not on every queue post.** Most reposts do
not change what should be replied to next: a new message in another campaign,
a campaign going quiet, a daily slot. So it is sent when "Reply to this next"
starts pointing at a **different message**, and stays quiet otherwise.

- The target is the **message**, not the campaign. Answering the oldest message
  in a campaign moves the focus to that campaign's next oldest, and that is
  announced even though the campaign is unchanged.
- It is **not deleted** when superseded, unlike the group copy. It cannot
  mislead the same way: answering the target moves the focus, which sends a
  newer DM. The DMs read as a timeline, the newest always current.
- A DM Telegram refuses is **not** recorded as sent, so it is retried on the
  next post.
- Only the focus message is DMed, never the quiet-campaign fallback that
  replaces it when nothing is owed a reply.
- No DM is sent if the group queue post itself failed.

---

## Queue stats

`/queuestats` - Shows reply streaks, average response time, and
cleared-per-day stats for the GM.

---

## Transcript scanner vs live queue

The queue is built from two sources:

1. **Live queue** (`state["gm_queue"]`) - populated in real time as
   messages arrive. Cleared immediately when the GM replies.

2. **Transcript scanner** (`queue_scan.py`) - scans recent markdown
   transcript files as a backup, catching any messages the live queue
   might have missed (e.g. during bot downtime). Only uses
   `gm_queue_replied` state to filter - does NOT clear on GM activity.

Both sources are merged and deduplicated by the `/queue` command and
the scheduled reminder.
