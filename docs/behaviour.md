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

### Every campaign appears somewhere

A campaign with no unreplied entries is not omitted, it is placed in one of
three states so nothing quietly vanishes from the queue:

| State | Condition | Reads |
|---|---|---|
| never posted | no `last_message_time` at all | `no posts yet` |
| silent | idle >= 5 days | `no posts for 12d` |
| caught up | posted within 5 days | `last post 1d ago` |

⛔ **Never posted was dropped entirely until 2026-08-30** (see `CHANGELOG`
4.62.1). C10 The Junction was configured on 2026-08-13 and appeared in no
section for 17 days, which is exactly backwards: no posts at all is the most
silent a campaign can be, not a fourth thing to skip. It now sorts above every
finite age via `days = inf`.

The never-posted line carries **no age on purpose**. `silent_campaigns` feeds
the fingerprint above, so an age ticking there would repost the whole queue
every hour forever.

`queue_exclude` (C08 Theria) is the switch for a campaign that should not be
listed at all, and it still suppresses every section.

The per-topic *"All caught up. Time for players to post!"* message posted inside
a campaign's own topic is a different thing: it marks the transition from having
unreplied entries to having none, so a campaign that has never had an entry does
not get one.

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

## Inactivity: warnings and removals are separate

Two feature flags, because nagging a player and sweeping a dead seat are
different acts with different audiences:

| `disabled_features` | effect |
|---|---|
| *(neither)* | warn at 1, 2, 3 weeks; remove at 4. The default. |
| `warnings` | **stay quiet, stay tidy.** No nudges to players, seats still swept at 4 weeks. What another GM's table wants. |
| `removals` | warn, but never act on it. |
| both | prefer `paused_campaigns`, which says *why*. |

Until 2026-08-30 one flag named `warnings` gated both, so C08 Theria,
which disables it because another GM runs that table, accumulated **five
seats silent 110 to 176 days**. Theria read up to five players larger
than it was in `/roster`, in the recruit advert and in the weekly
community roster.

Independent of both flags:

- **permanent players** are never removed (the L20 rule);
- **`/away`** players are never warned or removed while away;
- **`paused_campaigns`** stops both, and is the right switch for a hiatus;
- the **GM bottleneck** suppresses warnings when the GM has been quiet 3+
  days, but deliberately does **not** suppress removals. A seat silent
  for a month is dead whoever is at fault.

One roster post per campaign per sweep, not one per person: five removals
in a run used to mean five near-identical rosters in that campaign's
chat.

---

## Community Roster (weekly)

Every 7 days the bot posts the full community roster into the GM queue
topic (`community_roster_topic_id`, falling back to `gm_queue_topic_id`).
It **deletes nothing**: the run of these posts is the record of the
community over time, which is the reason to have it.

It shows the working rather than a headline number, because a headline
number is what went wrong on 2026-08-30 (see `CHANGELOG` 4.60.1):

- **people and seats separately.** One person can hold five seats, and
  which of the two you quote decides whether recruiting looks solved.
- **enrolled and active separately.** Active means posted within 30 days,
  matching `roster_members._ACTIVE_DAYS`, and the post says so in words.
- **every campaign with its players named**, plus a 💤 line for seats that
  are silent and how long they have been.
- **rows in no current campaign**, which is where retired campaigns leave
  ghost seats that inflate every enrolment total.

The 💤 list is the **complement** of the active list, derived by
subtracting it rather than by re-testing `last_post_time`. Permanent
players count as active through any amount of silence (the L20 rule), so
a second opinion would print the same person as both active and quiet in
a single post.

Sent silent: it @-mentions the whole community by design, and a weekly
notification each is how a topic gets muted.

Ad-hoc equivalent, any revision, nothing posted:

```bash
cd scripts && python -m recruiting.roster_basis
```

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

---

## Daily Diagnostic

At `diagnostic_hour` UTC (default 8am) the bot fetches the last 25
GitHub Actions run logs and scans for:

- Rate limit hits (HTTP 429)
- Fatal errors and save refusals
- Failed Telegram sends
- Unknown voter IDs captured
- State and backup warnings

A summary is posted to the bot topic. If everything is clean:
`✅ All clear across 22 hourly runs`. Issues are shown with an example
line from the log.

**Activity summary** also shown: poll votes recorded, POTW awards,
queue peak unreplied count.

---

## Rate Limiting

Telegram limits message bursts. The bot automatically retries once on
HTTP 429, waiting the `retry_after` duration specified in the response
before retrying. If the retry also fails, the message is dropped and
logged.

---

## Queue Nudge Key Format

`state["queue_nudged"]` tracks which players have already been nudged
using `pid:username` keys (e.g. `"40585:Anthony NegetZ"`). Once a player
is nudged, they won't be nudged again until the key expires or is manually
cleared. The key cap is 200 entries (oldest evicted first).

---

## Media Group Deduplication

Telegram sends each image in a multi-photo post as a separate message
update, each with the same `media_group_id`. Only the **first** message
of a group is added to the GM reply queue — subsequent images in the
same group are skipped. Replying to the first image clears the group.

---

## Forum Topic Reply Detection

In Telegram forum topics, every message has `reply_to_message` set to
the topic's root header (same message ID as the thread ID, contains
`forum_topic_created`). The bot ignores these — only genuine
reply-to-a-specific-message events clear queue entries.
