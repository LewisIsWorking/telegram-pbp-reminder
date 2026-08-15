# Changelog

All notable changes to the PBP Reminder Bot are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/).

- **MAJOR** (x.0.0): Breaking config changes, workflow restructuring.
- **MINOR** (0.x.0): New commands, new features, new bot behaviours.
- **PATCH** (0.0.x): Bug fixes, test additions, refactors, documentation.

---

## [4.57.1] - 2026-08-15

### Changed

**C10 The Junction excluded from recruitment.**

It sits at 0/6 and won the recruit focus post every day, which is the same failure
the C08 Theria exclusion already existed to prevent. Added
`"disabled_features": ["recruitment"]` to its topic_pair, matching how C08 is handled.

C08 was already excluded and needed no change.

The winner is now **C09 Metal City** (2/6, 4 seats open), and the "N campaigns
currently short" count correctly drops from 6 to 5.

Note this also silences `check_recruitment_needs` for C10, since both features read
the same flag. That is the intended meaning of the flag rather than a side effect.

---

## [4.57.0] - 2026-08-15

### Added

**"Recruit for this next" — a daily post naming the campaign most in need of players.**

Requested as a sibling to the queue focus message. Where that one names the campaign
most in need of a *reply*, this names the one most in need of *new players*, in the
same shape:

    ━━━━━━━━━━━━━━━━
    🧭 Recruit for this next: 🚦 C10: The Junction
    ⏳ 6 seats open (0/6 players).
    ↗ Biggest gap of 6 campaigns currently short.
    🔗 https://t.me/Path_Wars/146645

Posted to the GM queue topic, **once per 24 hours, deleting its predecessor.** The
queue focus rides the queue's own message batch and dies with it; this one has no
batch, so it manages its own lifecycle the same way `schedule_post` does.

Selection: largest shortfall against the campaign's own `roster_target` wins, ties
broken on the lower fill ratio so a 1-of-2 outranks a 5-of-6 with the same gap.

**Campaigns with `recruitment` in `disabled_features` are excluded.** This is the
part that matters: C08 Theria sits at 0/4 and would otherwise win every single day,
which is precisely the campaign Lewis has switched recruitment off for. Mutation-proven
— deleting the flag check fails two tests by name.

Config: `recruit_focus_enabled` (default true) to switch it off.

### Notes

Two state keys were registered in both places a bot-sent id has to exist —
`state.PARTITIONS` and `posting/bot_sent_state_scan` — which are the exact two
omissions that duplicated the schedule post for two days in 4.54.1/4.54.2. Both
guards from that fix pass.

The schedule-post completeness guard added in 4.55.0 caught this feature mid-build:
registering "Recruit focus" in `checker._run_checks` and nowhere else failed
`test_schedule_is_complete` immediately, which is what that guard exists to do. It is
now listed as an interval job and appears in the schedule post.

2114 tests passing.

---

## [4.56.0] - 2026-08-14

### Fixed

**`/rosterplayers` did nothing, and said nothing.**

Reported from the group: tapped from the Telegram command menu, no reply at
all - indistinguishable from the bot being down.

It was registered in three of the five places a command needs to exist:

| place | had it? |
|---|---|
| `set_commands.py` (the Telegram menu) | yes - so it was tappable |
| `dispatch/cmd_info.py` (the handler) | yes |
| `router._READ_CMDS` | **no** |
| `bot_topic.no_campaign` | **no** |
| `help_text` | no (nor does `/roster`) |

Two silent consequences, both now fixed, for `/rostercampaigns`,
`/rosterplayers` and `/rosterall`:

- **From the bot topic** they fell through to `return  # Non-read commands not
  allowed` and did nothing.
- **From a campaign topic** they worked, but replied into the in-character pbp
  thread instead of the chat topic, because `is_read` is computed from
  `_READ_CMDS`.

Their sibling `/roster` was registered everywhere and behaved correctly, which
is what made this look like one broken command rather than a missing
registration. All three are cross-campaign by construction -
`build_roster_players` and friends take `(config, state)` and no pid - so they
belong in `no_campaign` beside `/roster`.

Not a `@BotName` problem: the suffix is stripped in four places already
(`parsing/message.py`, `dispatch/bot_topic.py`, `dispatch/cmd_gm.py`), and
`/rosterplayers@PathWarsNudgeBot` behaved identically to the bare form
throughout. Verified before changing anything.

### Added

**An advertised command never answers with silence.**

41 of the 79 commands in the Telegram menu produced no reply from the bot
topic. Most are write commands that genuinely need campaign context, and
refusing them there is correct - but refusing them *silently* is not. A
command in the menu can be tapped, and a tap that does nothing reads as a
broken bot.

They now answer: *"/scene needs to know which campaign, so use it in that
campaign's topic."* Deliberately not "changes campaign data" - `/hp`,
`/available` and `/pick` are reads that simply need to know which campaign.

Only for commands this bot advertises. `_MENU_COMMANDS` is derived from
`set_commands` rather than relisted, so the menu and the branch cannot
disagree. An unrecognised `/command` stays silent, because other bots share
this group and answering `/deploy@SomeOtherBot` would interrupt every one.

`test_no_advertised_command_is_silent.py` asserts the **outcome**, not the
registration: send every menu command and require a reply. A registry
cross-check ("every menu command is in `_READ_CMDS`") would be wrong, because
write commands legitimately are not read commands - and that read/write mapping
is the thing that was wrong in the first place.

2091 tests passing. Mutation-proven: un-registering the three roster shapes
fails 6 tests naming both original symptoms.

---

## [4.55.0] - 2026-08-13

### Added

**The schedule post has its own topic key, and moves to the GM queue topic.**

`post_schedule` read `bot_topic_id`, while its own docstring had said "for the
GM queue topic" since it was written. New `schedule_topic_id`, set to 146780,
falling back to `bot_topic_id` when absent.

Its own key rather than reusing `gm_queue_topic_id`: `leaderboard_topic_id` is
shared by four unrelated posts, so moving the leaderboard on 2026-08-12 also
moved the weekly digest, message milestones and the hero-point picker. One key
per destination means moving one post moves one post.

No migration needed. `tg.delete_message` is scoped to the chat and takes no
topic, so the first run in the new topic also removes the predecessor sitting
in the old one.

### Fixed

**The schedule post listed 11 of the 18 scheduled jobs.**

Everything it said was true - every hour, weekday and interval matched its real
gate. It just left seven jobs out entirely:

| Missing | Gate |
|---|---|
| Pin digest | daily at `pin_digest_hour` (08:00 UTC, same hour as the diagnostic) |
| Recruitment check | 14 days, per campaign |
| Weekly digest | 7 days |
| Campaign table | 6.5 days |
| Pace-drop alerts | 7 days |
| Daily tip | 22 hours |
| State backup | 1 day |

The pin digest is the visible one: it fires at the same hour as the diagnostic,
so the post showed one job at 09:00 BST when two were due.

Every existing guard was *per row* - given a row, does it quote the right
constant. A missing row has no constant to disagree with, so a job that was
never added is indistinguishable from a job that does not exist.

`test_schedule_is_complete.py` anchors to `checker._run_checks`, the one
authoritative registry of what the bot runs, and requires every label there to
be claimed by a fixed-clock row, an interval row, or an explicit event-driven
entry with a stated firing condition. Read by AST rather than by importing
`checker`, which would pull in the whole bot.

**"Roster summary - due now" was stuck, and had been for weeks.**

`last_roster` and `last_pace` are `{pid: iso}`, and the line took the earliest
value across every key. State accumulates campaign ids indefinitely; `1242` had
been removed from config and its 2026-07-06 timestamp was still there. Its job
iterates config, never reaches it, so never restamps it - the earliest value
could only move further into the past and the line was pinned to "due now"
permanently. A status line that cannot change reads as information and carries
none.

Now filtered to configured campaigns, and per-campaign jobs report how many are
due: `Roster summary - due now (1 of 9 campaigns)`. That count immediately
surfaced the real straggler - C08 Theria has no players recorded, so its roster
job skips at the `if not players and not counts` guard without stamping, and
has not run since 2026-06-07.

### Changed

- `_INTERVAL_JOBS` extracted from `schedule_post.py` to
  `scheduled/schedule_intervals.py`; the additions would have taken the file
  past 200 lines. Split by gate shape: `schedule_table` is fixed-clock,
  `schedule_intervals` is "days since last run".
- `_interval_lines(state, now)` renamed to `interval_lines(config, state, now)`.
  Renamed rather than defaulted so every call site had to be revisited.
- `TestLocalTimeRendering` moved to `test_schedule_local_time.py`;
  `test_schedule_post.py` had reached 211 lines.

1995 tests passing. The completeness guard is mutation-proven: dropping the pin
digest row fails it by name.

---

## [4.54.2] - 2026-08-11

### Fixed

**Nine state keys were written on every run and silently discarded.**

`state.py` documents the trap in one line near the top:

    # Keys not listed here (e.g. _config_cache) are transient and not persisted.

`_save_to_files` writes `{k: state[k] for k in keys if k in state}` per
partition, so **a key absent from `PARTITIONS` is dropped on every save.**
Nothing errors, nothing warns, the value is simply gone next run.

This is the actual cause of the duplicate schedule posts. 4.54.1 fixed the
bot-sent registry, which was a real and necessary bug, but not the one doing
the damage: `schedule_post_msg_id` was never persisted, so `prev` was always
`None` and there was never an ID to delete.

Four were mine, three of them idempotency guards that would have re-fired on
every 30-minute tick:

| key | consequence |
|---|---|
| `potw_week` | POTW re-awarded all Monday |
| `last_potw_roundup` | roundup reposted all Monday |
| `last_potw_countdown` | standings reposted all Thursday |
| `schedule_post_msg_id` | schedule post duplicated indefinitely |

Five were pre-existing, found by the new guard:

| key | consequence |
|---|---|
| `last_pin_digest` | identical shape — daily pin digest reposted every tick |
| `last_pin_alert_ts` | non-bot pin alerts re-fired |
| `poll_identified_voters` | voter identification lost |
| `availability` | **`/available` player data silently lost** |
| `timeline_events` | **`/timeline` GM entries silently lost** |

The last two are worse than a duplicate post: user-entered data was being
discarded every run.

### Added

- **`scripts/test_state_keys_are_declared.py`** — scans production source for
  keys **written** to `state` and fails if any is missing from `PARTITIONS`.
  Writes only: a key that is merely *read* needs no entry, which is why the
  legacy migration reads (`gm_queue`, `gm_reply_log`, `paused`, …) are
  correctly not flagged. Includes a save/load round-trip, because declaring a
  key is not the same as it surviving the partition filter.

  The existing `test_state_schema.py` guards *files*, not keys, and
  `pytest.skip`s when `data/state/` is absent — so an undeclared key was never
  in its scope. This one is key-level and cannot skip.

Mutation-proven: un-registering `schedule_post_msg_id` fails three tests
including the round-trip.

---

## [4.54.1] - 2026-08-11

### Fixed

**The schedule post stopped replacing itself and duplicated every 30 minutes.**

Root cause is mine, and it is the second instance of the same class as the
2026-08-10 topic-queue orphan: **a bot-sent message ID the registry does not
know about cannot be deleted.**

`post_schedule` stores `state["schedule_post_msg_id"]`, but I never added that
field to `posting/bot_sent_state_scan.py` — despite that module's docstring
stating the contract outright:

> When new fields are added to `live.json` ... that store a bot-sent message
> ID, that field should be picked up here so the registry's backfill stays
> accurate.

Every Actions run is a fresh checkout, so `bot_sent_ids.json` does not survive
and the registry rebuilds from `backfill_from_state`. An unknown ID is absent
from the registry, so `perform_guarded_delete` **refuses** it — behaving
exactly as designed — and the previous post is never removed.

The failure is quiet in the worst way: the guard was right, the refusal was
correct, and the only visible symptom was duplicate posts hours later.

- `schedule_post_msg_id` added to `extract_ids_from_live`.
- **`test_bot_sent_scan_covers_state.py`** — a guard so the next `_msg_id`
  field cannot slip the same gap. It scans production source for state keys
  ending in `_msg_id` / `_message_id` and fails if any is unknown to the scan
  module, with an allowlist for player/GM ids the bot must *never* delete.
  Includes a round-trip test, because knowing the key name is not the same as
  the rebuild actually authorising the delete.

**`1 player posts` / `1 GM posts` in the weekly leaderboard.**

`posts_str` existed but only covers the bare word "post", so the qualified
counts were hand-rolled f-strings that never pluralised. Generalised into
`count_str(n, noun, plural=None)` in `helpers_pkg/formatting.py`; `posts_str`
now delegates to it.

### Changed

- **Weekly leaderboard moved to topic 146780** (`leaderboard_topic_id`
  137393 → 146780), as requested.
  ⚠️ `leaderboard_topic_id` is also read by `scheduled/digest.py`,
  `scheduled/message_milestones.py` and `boons/hero_point.py`, so the weekly
  digest, message milestones and the MVP hero-point claim move with it. The
  claim *must* follow its MVP post, and the others are the same weekly-summary
  family — but say the word if you want them split back out.

---

## [4.54.0] - 2026-08-10

### Added

**Tests for `/sessionplayed` and `/swimmingdone`, which had none — including
their GM authorisation check.**

`dispatch/gm_poll_cmds.py` was **78% `# pragma: no cover`** (63 lines). The
entire bodies of both commands were excluded line by line, *including*:

    gm_ids = set(str(g) for g in config.get("gm_user_ids", []))  # pragma: no cover
    if user_id not in gm_ids:                                    # pragma: no cover
        tg.send_message(group_id, bot_topic, "GMs only.")        # pragma: no cover

`grep -rn "sessionplayed\|swimmingdone" test_*.py` returned nothing. Zero
tests, zero coverage visibility, on an auth gate whose commands mutate
`session_happened` — the flag that silences poll pings for a whole week.
**An auth bypass there was invisible.**

Also untested and fully excluded: `handle_poll_closed` in
`dispatch/poll_router.py` (31 pragmas), which sets the same flag when a poll
closes, plus the vote-retraction and revoting branches of
`handle_poll_answer`.

- `scripts/test_gm_poll_cmds.py` — 19 tests. Auth tests assert on **both**
  halves: that the refusal is sent *and* that state was not mutated. Asserting
  only the message would still pass if the command fell through and wrote the
  state anyway.
- `scripts/test_poll_router_closed.py` — 26 tests. Built around matching the
  right poll: correct campaign, not a sibling, swimming kept independent,
  unknown ids touching nothing.
- Each negative has a positive counterpart (`test_gm_is_allowed`) proving the
  fixture can fire — the pattern from 4.53.2.

### Changed

- **94 `# pragma: no cover` removed** — all 63 from `gm_poll_cmds.py` and all
  31 from `poll_router.py`. Both files now measure **100% (131 statements,
  0 missed)** with no exclusions. Repo total: 503 → 409.

Verified by mutation: deleting both `if user_id not in gm_ids` checks fails
three tests, and the run log shows `Bot topic: /swimmingdone W14 by Mallory` —
the non-GM executing the command.

---

## [4.53.2] - 2026-08-10

### Fixed

**`tg_mock` covered 8 of 56 modules, so "did not post" assertions could
pass vacuously.**

The fixture hand-listed its patch targets. 56 modules do
`import telegram as tg`; it named 8. Any test using the fixture against
one of the other 48 asserted on a mock the code never touched, so

    assert not tg_mock.send_message.called

passed regardless of what the code did.

Demonstrated by deleting the POTW Monday gate outright — **the suite
stayed green.** A guard that cannot fail is not a guard.

The fixture now swaps the callables on the **shared `telegram` module
object** instead of patching modules one by one. Every module reaches
telegram through that single object, so one swap covers all of them,
including any added later — there is no list to keep in sync. It is also
O(1): patching all 56 individually was correct but tripled suite runtime.

- `test_tg_mock_coverage.py` — guards the guard. Checks discovery still
  finds the real modules, that the swap covers the actual senders, and —
  the part that matters — that calls made through several different
  modules genuinely land on the mock. Coverage alone would not be enough:
  a fixture that patched *nothing* would still satisfy every `not called`
  assertion in the suite, so the positive direction is asserted too.
- A guard forbidding `from telegram import <name>`, which would bind a
  function at import time and slip past the swap, silently restoring the
  exact vacuum this fixes.
- POTW and countdown fixtures given real campaigns and qualifying posts
  so they *can* fire, plus `test_monday_DOES_fire`,
  `test_countdown_DOES_post_on_thursday` and
  `test_roundup_DOES_post_when_there_are_winners` as counterweights —
  the earlier drafts used `topic_pairs: []`, so nothing could ever be
  sent and the negative assertions were true for the wrong reason.

Verified by mutation: removing the Monday gate now fails exactly the two
intended tests, and dropping `silent=True` fails the notification guard.

---

## [4.53.1] - 2026-08-10

### Changed

**The schedule post now renders in Belfast time, not UTC.**

`Europe/London`, so it is BST in summer and GMT in winter and the label
next to each time says which. 08:00 UTC reads as 09:00 BST in August and
08:00 GMT in December.

**Only the rendering changed.** Every gate, every cron trigger and every
stored timestamp is still UTC — a test pins the POTW row to
`POTW_WEEKDAY`/`POTW_POST_HOUR` so converting the display can never drag
a gate with it. Times are built as real datetimes and converted, rather
than having an hour added, so the DST changeover and any day rollover
are handled by the zone rather than by arithmetic that is wrong for half
the year.

- `scheduled/local_time.py` — conversion helper. Degrades to UTC with a
  log line if the zone cannot be loaded, rather than raising: this runs
  inside the scheduled-jobs loop and a tz lookup is not worth taking a
  whole run down for.
- `tzdata` added to all three workflow install steps. The Ubuntu runner
  has a system tz database but Windows does not, so without it `ZoneInfo`
  fails locally.
- **"Schedule post" added to `QUEUE_CHECKS`.** It advertises a :00/:30
  cadence and shows a countdown, but the half-past pass only ran
  `("Queue reminder", "Queue nudge")` — so its timer would have read as
  expired for half of every hour. Caught by the existing
  `test_queue_checks_are_real_labels` guard, which then required the spy
  registering too.

---

## [4.53.0] - 2026-08-10

### Added

**Self-replacing schedule + timer post in the GM queue topic.**

One message, rewritten every run: today's fixed-clock jobs with what has
already fired, weekday jobs coming up, interval jobs and when they are
next due, and the next cron tick.

Built as **one** message rather than a separate schedule and timer. An
accurate "next fire" timer has to refresh every run anyway (the cron
ticks at :00 and :30), and since the post deletes its predecessor,
refreshing costs no clutter — the topic always holds exactly one. That
also means one lifecycle and one thing to delete.

Delete-and-repost rather than `editMessageText`, deliberately: editing
would leave it drifting up the topic as other posts arrive, whereas
reposting keeps it at the bottom where a glance finds it.

- `scheduled/schedule_table.py` — the fixed-clock schedule as data,
  reading its hours from the same config keys and `helpers` constants the
  jobs read, so the post cannot advertise a time a job does not use.
- `scheduled/schedule_post.py` — renders and replaces the post.
- `telegram.send_message_id(..., silent=True)` — new opt-in parameter
  setting `disable_notification`. Defaults to False so every existing
  caller is unchanged. Without it this post would notify 48 times a day.
- Disable with `"schedule_post_enabled": false` in config.
- `test_schedule_post.py` — 19 tests.

### Fixed

**`tg_mock` only patched four modules, so some "did not post" assertions
passed vacuously.**

The fixture patched `topic_queue_poster`, `gm_queue_history`,
`posting.sender` and `posting.message_batch` — but not `scheduled.potw`.
Any test asserting `not tg_mock.send_message_id.called` against a POTW
path was therefore checking a mock the code never touched.

Proven by mutation: deleting the POTW Monday gate entirely left the suite
green. Two causes, both fixed — the fixture now also patches `potw`,
`potw_roundup`, `potw_countdown` and `schedule_post`, and the POTW
fixtures were given a real campaign and qualifying posts so they *can*
award. Re-running the same mutation now fails exactly the two intended
tests. `test_monday_DOES_fire` pins that capability so the negative cases
cannot silently go hollow again.

---

## [4.52.1] - 2026-08-10

### Fixed

**Silent and Caught up sections now read longest-idle first.**

Reported from queue #1327, whose Caught up section read `21h, 0h, 2h, 5h,
4d 2h, 1h` — that is `config["topic_pairs"]` order, not age order.
`silent_campaigns` and `caught_up_campaigns` built their lists by
appending in iteration order and never sorted, while `campaign_age_lines`
ten lines below them in the same module already did
`rows.sort(key=lambda r: r[0], reverse=True)`.

The data was always there: `_idle_campaigns` yields `days` as a float, so
sub-day ages (0h vs 21h) discriminate correctly.

This cost more than tidiness. In that same queue **C06 at 4d 2h was the
oldest caught-up campaign but sat fourth in the list**, which is why it
read as though C01 at 21h were the worst.

### Added

**"Oldest campaign" callout on an empty queue.**

A populated queue ends with the "Reply to this next" focus message, built
from unreplied entries — so an empty queue pointed nowhere. When there is
nothing to reply to, the caught-up notification now names the single
campaign that has gone longest without any post.

Ranking is just "longest since last post", so a silent campaign outranks
a caught-up one without a special rule: 9d beats 21h because it is a
bigger number, not because of which section it is in.

`test_queue_silence_ordering.py` — 10 tests, fixtured with the exact
campaign ages from the reported queue.

### Not a bug (investigated)

Silent campaigns **do** already count GM posts. `dispatch/tracking.py`
writes `state["topics"][pid]["last_message_time"]` for every non-bot
message, GM included — local state shows C09's entry stamped with
`last_user=Path`, the GM account. The one genuine gap is that posts in a
campaign's **chat** topic are not counted, because chat topics are not in
`pbp_topic_ids` and `parse_message` rejects them. That is arguably
correct: the silence clock measures story activity.
## [4.52.0] - 2026-08-10

### Changed

**Player of the Week now fires on Mondays, once per calendar week,
instead of drifting.**

Reported as "it doesn't really know when to post it and it seems to fire
semi-randomly whenever anyone makes a post". Both halves of that were
real, from one gate:
`interval_elapsed(state["last_potw"][pid], 7, now)`.

- **It crept.** The award fired on the first cron tick *at or after* the
  7-day mark. The cron ticks at :00 and :30, so the post time drifted
  later every week and eventually wandered onto a different weekday.
- **It fired on player activity.** A week with fewer than
  `POTW_MIN_POSTS` qualifying posts hit `continue` **without stamping**
  `last_potw`. The gate stayed open, so the award went off on the first
  tick after someone posted enough to qualify — exactly the reported
  symptom.
- **Every campaign drifted separately**, since `last_potw` is per-pid, so
  awards scattered across all seven days.

Replaced with a calendar weekday gate plus an ISO week key, the same
shape `scheduled.week_welcome` already used. A skipped week is now simply
a skipped week: the no-candidate branch stamps too, so it cannot fire
late.

### Added

- **Weekly roundup** (`scheduled/potw_roundup.py`) — one summary of every
  campaign's winner to the bot topic, ranked by average gap. Additive
  rather than a replacement: the per-campaign messages must stay because
  `boons/handler.py` edits each one in place when its winner claims, keyed
  by pid in `pending_potw_boons`.
- **Midweek standings** (`scheduled/potw_countdown.py`) — Thursday post
  showing the current leader and the closest chaser per campaign, with
  the gap between them. Reuses `potw._gather_potw_candidates` and the same
  `min(avg_gap_hours)` selection as the award, so Thursday can never name
  a leader that Monday then contradicts.
- `scheduled/potw_schedule.py` — shared week key and weekday gate, so the
  award and its countdown cannot disagree about what "this week" means.
- New tunables, overridable from the config settings block:
  `potw_weekday` (0 = Monday), `potw_countdown_weekday` (3 = Thursday),
  `potw_post_hour` (9 UTC).
- `test_potw_monday_schedule.py` — 18 tests.

`POTW_INTERVAL_DAYS` is retained but no longer decides when the award
fires; older state and config settings blocks still reference it.
## [4.51.13] - 2026-08-10

### Fixed

**Old "Unreplied:" posts stopped being deleted — a type mismatch, not a
logic error.**

C05 Grand Explorers accumulated three live queue posts (04/08, 06/08,
09/08) where each should have replaced the last.

`parse_message` returns Telegram's raw `message_thread_id`, which is an
**int**, and that int is stored verbatim on every queue entry. The
per-topic poster used it as the key into `cq["topic_queues"]` — but that
dict is persisted as JSON, and **JSON object keys are always strings**.
So `queues.setdefault(51357, ...)` never matched the on-disk `"51357"`
slot. A fresh empty slot was handed to the poster, `existing.is_empty`
was True, and the previous batch was never deleted.

The save then wrote the int key back out as a *second* string key,
overwriting the real slot — which is why the L28 `pending_delete` retry
sweep could not rescue it either. The stranded IDs were gone from state
entirely, so nothing ever tried to delete them again.

Invisible to the suite because every existing test passes `thread_id` as
a string (see `test_topic_queue_retry.py`) — the one type production
never supplies.

- `_threads_from_scanned` now stringifies at the boundary.
- New `topic_queue_state.normalise_queue_keys` repairs state already
  corrupted by the buggy runs. Where both an int and a string key exist
  for one thread, the int-keyed slot is the newer one and stays live; the
  stranded string-keyed IDs are parked in `pending_delete` so the
  existing retry sweep removes them rather than dropping them.
- `test_topic_queue_key_type.py` — 7 tests, including an end-to-end
  reproduction of the orphan and the duplicate-key merge.

**No change to deletion safety.** The bot still deletes only IDs in the
bot-sent registry: `perform_guarded_delete` remains the single
`deleteMessage` call site and the only gate. This fix changes *which slot
is found*, never *what may be deleted*. The 30 registry/guard/bypass
tests pass unchanged, and `unpinAllChatMessages` is still never called
(it is group-wide and would wipe GM pins).

---

## [4.51.12] - 2026-07-15

### Added

**Pin activity is now visible: a daily digest + a real-time non-bot alert.**

Telegram shows nothing in the chat when a message is unpinned, so the
bot's pin activity was invisible unless you read the `pin_audit_log.json`
file directly. Two new scheduled tasks (in `scheduled/pin_report.py`,
dispatched from `checker.py`) surface it in your bot topic:

- **Daily digest** — once a day (at `pin_digest_hour`, default
  `diagnostic_hour` = 8), a standalone "📌 Pin activity — last 24h"
  message: how many messages the bot pinned, unpinned, and deleted, and
  whether any touched a message the bot didn't make.
- **Real-time non-bot alert** — every run, if the bot pinned/unpinned/
  deleted a message it did **not** send, it immediately posts a "🚨 PIN
  GUARD ALERT" naming the message id, action, and call site. In normal
  operation the bot only ever touches its own pins, so this should never
  fire — if it does, it's the vanishing-pin bug caught in the act.

To power the alert, audit entries now carry a `bot_owned` flag
(`is_bot_sent` at action time; unpins/deletes already knew it from the
guard, and the unguarded pin path now checks explicitly — so a bot
pinning a message it never sent is caught). New state keys:
`last_pin_digest`, `last_pin_alert_ts`.

---

## [4.51.11] - 2026-07-14

### Added

**Pin-audit trail now also logs deletes, closing the auto-unpin blind spot.**

The forensic `pin_audit_log.json` (added in 4.51.10) logged pins and
unpins, and its first live run confirmed the bot only ever unpins its
own prior pins. But a pin can vanish a second way the log couldn't see:
Telegram **auto-unpins a message when it's deleted**, so if a GM/player
manually pinned a message the *bot* had sent, the bot deleting that
message during queue eviction removes the pin with no unpin call at all.
`perform_guarded_delete` now records every delete (success, failure, or
guard-refusal) to the same audit, so a vanished pin's id will always
show up — as an `unpin` or a `delete`. The cap rose 800 → 3000 rows
(deletes are higher-volume) to retain ~two weeks of activity, and
`record_action` is now best-effort (swallows its own exceptions) so a
logging failure can never break an actual pin/unpin/delete.

### Fixed

**Registered `pin_audit_log` in the state schema.** 4.51.10 shipped the
audit writer but omitted the `state_store/schema.py` entry; once the bot
created the file on disk, `test_state_schema` (which asserts every state
file is documented) began failing. Added the `AUX_FILES` entry.

---

## [4.51.10] - 2026-07-07

### Added

**Forensic pin/unpin audit trail (`data/state/pin_audit_log.json`).**

A GM/player manual pin was reported as still disappearing despite the
registry unpin guard, and only the bot has pin rights in that group.
An exhaustive trace of every pin/unpin path found they all operate on
bot-owned ids and the guard has never once fired (no `refusal_log.json`
ever created) — so the code, as written, cannot unpin a non-bot
message. To get ground truth instead of another speculative fix, the
bot now records **every** pin and unpin it performs — success, failure,
or guard-refusal — with the resolved originating call site
(`file:line`), to a bounded, committed `pin_audit_log.json`. Previously
only *refused* unpins were logged; successful ones left no trace, which
was exactly the blind spot. Next time a pin vanishes we can check the
log and say definitively whether the bot touched that id and from
where. `telegram.pin_message` now delegates to
`posting.safe_delete.perform_pin` (keeping `telegram.py` under the
200-line cap); pinning itself stays unguarded (it removes no content)
but is logged so a pinned-then-vanished non-bot id is traceable to its
source.

---

## [4.51.9] - 2026-07-07

### Removed

**Retired the C11 "Dark Pockets" campaign from tracking.**

The bot was removed from the Dark Pockets Telegram group, so it can no
longer see posts there (its last ingested message was 2026-06-29). C11
was the only campaign running in a separate group (`group_id`
`-1003496373617`); its `topic_pair` has been deleted from `config.json`
and the `C01 ↔ C11` `linked_polls` link severed so C01's vote
notifications no longer render a stale C11 tally block. No code change
was needed — the ingestion/queue/poll logic is all config-driven, so
dropping the pair fully untracks the campaign (no more queue entries,
polls, roster, warnings, or recruitment attempts against an
unreachable group). Orphaned C11 state under `data/state` is inert once
the pair is gone and is left untouched.

---

## [4.51.8] - 2026-07-07

### Fixed

**The bot no longer unpins messages it didn't send.**

`unpin_message` used to POST `unpinChatMessage` for whatever message ID
a caller handed it. Because a bot with admin rights can unpin **any**
message in a group (Telegram has no "only my own messages" restriction —
the same reality behind the 2026-05-08 delete incident), a stale or
crossed ID silently cleared a GM's or player's *manual* pin.

`unpin_message` now delegates to `posting.safe_delete.perform_guarded_unpin`,
which applies the same bot-sent-registry check that already guards
deletion: an ID the bot never recorded sending is refused before any
HTTP request, with a diagnostic line and a refusal-log entry. Legitimate
unpins are unaffected — the callers only pass IDs the bot pinned itself
(`poll_message_id`, `last_queue_pin_id`, batch/slot `pin_id`), all of
which are recorded at send time.

Adds the `perform_guarded_unpin` guard, a regression test that a non-bot
ID is refused with no API call, a parallel guard test suite, and a
`docs/dev/delete-safety.md` section documenting that unpin shares the
guard. PATCH bump (4.51.8).

---

## [4.51.7] - 2026-06-16

### Changed

**Completed the v4.0.0 modularization: every production module is now ≤200 lines.**

The last two files over the project's 200-line limit were split by pure
extraction (no behaviour change):

- `boons/handler.py` (214 → 138) — boon-resolution logic (result
  formatting, campaign-name resolution, storage, `_resolve_boon`) moved
  to new `boons/resolution.py` (101).
- `scheduled/potw.py` (205 → 169) — transcript post-link lookup
  (`_find_player_post_links`, `_ENTRY_RE`, `_LOGS_DIR`) moved to new
  `scheduled/potw_links.py` (57).

Both originals re-export the moved names, so `boons.handler.*` /
`scheduled.potw.*` imports, `compat` aliases, and test patch targets
keep resolving unchanged. The three tests that redirect the transcript
root were repointed from `scheduled.potw._LOGS_DIR` to
`scheduled.potw_links._LOGS_DIR` (the module where the moved function
reads it). Full suite green (1753 passed).

### Changed

**MVP prize message now advertises the `/heropoint` typed fallback.**

The weekly MVP announcement is followed by a Hero Point picker with
inline buttons, but those buttons depend on a callback that can lag
behind the hourly cron. The prize line now reads "Claim it with the
buttons below — or type `/heropoint <campaign>` if they don't respond,"
making the already-shipped typed command (4.51.x) discoverable at the
moment the user needs it. Covered by `test_checker_roster_b.py`.

### Fixed

**Text file I/O now always uses `encoding="utf-8"`.**

`open()`, `Path.read_text()` and `Path.write_text()` without an
explicit `encoding=` use the *platform default* — utf-8 on the Linux
CI runner, but cp1252 on a Windows dev box. The bot writes UTF-8
transcripts (em-dashes, accented player names, emoji), so on Windows
the round-trip mangled those characters: ~7 tests failed locally
(`UnicodeDecodeError` / em-dash mismatch) while passing on CI, and any
non-utf-8 host running the bot would have corrupted real transcript
and state files.

Added an explicit `encoding="utf-8"` to all 98 text-mode file
operations across production and tests (binary `"rb"`/`"wb"` opens are
correctly left untouched). The full suite now passes on Windows, not
just Linux.

### Added

**`test_encoding_hygiene.py` — regression guard.**

An AST-based test that walks the source tree and fails if any
text-mode `open`/`read_text`/`write_text` omits `encoding=`. Prevents
the platform-default-encoding bug class from creeping back in.

---

## [4.51.4] - 2026-06-15

### Removed

**Deleted the `telegram.unpin_all_messages` footgun.**

Follow-up hardening to 4.51.3. The helper wrapped Telegram's group-wide
`unpinAllChatMessages` behind a thread-scoped-looking signature, which
is what caused the GM-pin wipe. Now that no production code calls it,
the function (and its `conftest.py` mock) are removed so it can't be
reintroduced by accident. A comment in `telegram.py` records why, and
points future callers at `unpin_message` (specific id) or, if a real
per-topic clear is ever needed, `unpinAllForumTopicMessages`.

---

## [4.51.3] - 2026-06-15

### Fixed

**Bot unpinned posts it didn't own.**

Lewis reported the nudge bot was unpinning messages that weren't its
own — GM-pinned posts disappeared from PBP topics.

Root cause: `_post_thread_queue` (in `scheduled/topic_queue_poster.py`)
took an empty-slot branch — hit the *first* time a thread's queue is
posted, or any run after a clear reset the slot — that called
`tg.unpin_all_messages(group_id, thread_id)`. That helper invokes
Telegram's `unpinAllChatMessages`, which **unpins every pinned message
in the entire group** and silently ignores the `message_thread_id`
argument (thread scoping belongs to a *different* method,
`unpinAllForumTopicMessages`). So on every fresh thread the bot wiped
the GMs' own pins along with any stale bot pin.

The fix removes that call entirely. The bot now only ever unpins a
specific message id it pinned itself (the `unpin_message` path used
when refreshing a tracked queue). When a slot has no tracked ids there
is nothing of the bot's own to unpin, so it skips straight to posting.

`telegram.unpin_all_messages` is left in place but is now unused by
production code; it should not be called per-thread (it is group-wide).

Regression tests added in `test_topic_queue.py`:
`test_empty_slot_never_unpins_others_pins` and
`test_update_unpins_only_own_pin`.

---

## [4.51.2] - 2026-05-28

### Fixed

**Per-topic queue orphan: failed deletes are now retried, not abandoned.**
**(Supersedes 4.51.1, whose diagnosis was wrong.)**

Lewis reported that a `📋 Unreplied: 5` message in C01 stayed visible
after `📋 Unreplied: 8` replaced it — the old queue wasn't deleted even
though new messages had arrived and a new queue had posted.

4.51.1 misdiagnosed this as Telegram's 48h delete window (the message
"aging out" after sitting unchanged) and added a 36h forced-refresh.
That was wrong: the queue *was* actively reposting, so it wasn't
sitting static — the delete itself was failing and being abandoned.

Real cause: `_post_thread_queue` called `existing.delete_all()`, and
on any failure it logged the failed ID and then overwrote the slot
with only the freshly-posted message. The failed ID was dropped, so
no later run ever retried it — one failed delete became a permanent
orphan, with new queues stacking on top. `_clear_thread_queue` had
the same flaw. `MessageBatch.delete_all` was explicitly designed to
return failed IDs *for retry*, but the callers never honoured it.

The fix parks failed-delete IDs in a new slot field `pending_delete`
and re-attempts them at the top of every post/clear run until they
succeed. The bot is a group admin, so its own messages have no 48h
delete limit — a retry always eventually wins. A failure that was a
bot-sent-registry refusal also self-heals: the registry backfill now
reads `pending_delete`, so the ID is registered and the next retry
passes the guard.

### Reverted from 4.51.1

* The 36h staleness gate (`can_skip_repost`, `_msg_age_hours`,
  `_REFRESH_AFTER_HOURS`) is removed. It solved a problem that wasn't
  occurring and added a daily re-post of stuck queues.

### Code changes

* `scripts/scheduled/topic_queue_state.py` — replaced the staleness
  helpers with `queue_pending_deletes(slot, ids)` (dedup-append failed
  IDs) and `retry_pending_deletes(slot, group_id)` (re-attempt parked
  IDs, keep only those still failing).
* `scripts/scheduled/topic_queue_poster.py` — `_post_thread_queue` and
  `_clear_thread_queue` now call `retry_pending_deletes` first (sweeps
  orphans every run, even when content is unchanged) and carry any
  failed delete forward via `queue_pending_deletes` instead of
  abandoning it. The update path also unpins the old pinned message
  before deleting, so a failed delete can't leave two pinned messages.
  The inactive-thread loop now also processes threads that have only
  parked orphans (no current batch). The central-registry migration
  registration was extracted to `topic_queue_migration.py` to keep the
  poster under the 200-line cap.
* `scripts/posting/bot_sent_state_scan.py` — registry backfill now
  reads `pending_delete` so a registry-refused delete can recover.
* `scripts/scheduled/topic_queue_migration.py` (new) — holds the
  migration registration extracted from the poster.

### Tests

1740 passing (was 1726). New: `test_topic_queue_retry.py` (7 tests —
failed delete parked not abandoned, success leaves no pending, pending
retried on the unchanged/skip path, orphan clears on a later run,
clear-path carry-forward, clear preserves existing pending, inactive
thread with only orphans gets swept); pending-delete helper tests in
`test_topic_queue_state.py`; a backfill test in `test_bot_sent_registry.py`.
The 4.51.1 staleness tests were removed.

The existing C01 orphan (156513) is Lewis's manual cleanup — the bot
never auto-deletes orphans. This stops new ones and lets already-
tracked failures self-clear.

Version: PATCH. See L28 in `docs/dev/REFACTOR_PROGRESS.md` for the
full post-mortem, including why the first (48h) diagnosis was wrong.

---

## [4.51.1] - 2026-05-28

### Fixed

**Per-topic queue orphaned when it sat unchanged past 48h.**

Lewis reported a `📋 Unreplied: 5` message in C01 that never got
deleted when `📋 Unreplied: 8` replaced it. Root cause: Telegram
refuses to let a bot delete a message older than 48 hours, and the
per-topic pinned queue only re-posts when its content changes. A
queue that sat unchanged for ~2d20h (no new posts, no replies →
identical fingerprint → the poster's "no change, skip" branch
fired every cron tick) aged its tracked message past the 48h
window. When activity finally resumed and the queue re-posted,
the delete of the now-too-old message was refused by Telegram, so
the old message orphaned in the channel.

The bot-topic GM Queue never hit this because it force-reposts on
its `queue_daily_hours` schedule (every 12h here), keeping its
tracked message comfortably under 48h. The per-topic queue had no
equivalent forced-refresh cadence.

The fix adds a staleness gate: the per-topic poster now re-posts an
*unchanged* queue once its tracked message crosses 36h old (well
under 48h), deleting the still-young old message and resetting the
age clock. The tracked message can therefore never reach 48h, so
deletes always succeed and the orphan window is closed.

Code changes:

* `scripts/scheduled/topic_queue_state.py` — new
  `can_skip_repost(slot, fingerprint, existing, now)` helper and a
  private `_msg_age_hours`. Skip is allowed only when the queue is
  unchanged AND the tracked message is younger than
  `_REFRESH_AFTER_HOURS` (36). Unknown age (legacy slot, missing or
  unparseable `last_posted_at`) → never skip, force a refresh.
* `scripts/scheduled/topic_queue_poster.py` — `_post_thread_queue`
  swaps its inline `fingerprint == … and not is_empty` skip check
  for `can_skip_repost(...)`. File stays at the 200-line cap (the
  import extends an existing line; the condition is a 1-for-1 swap).

Behaviour deltas:

* A genuinely stuck per-topic queue (GM hasn't replied, players
  haven't posted) now re-posts its pinned message roughly once a
  day instead of sitting silently. This is mild extra noise but
  only happens for stale queues — exactly when surfacing the
  pending state is useful — and it's the mechanism that keeps the
  message deletable.
* Legacy slots (pre-`last_posted_at` schema) re-post once on first
  encounter to acquire a timestamp, then age-check normally.

Tests: 1734 passing (was 1726; +8 new in `test_topic_queue_state.py`
covering the staleness gate — unchanged+fresh skips, fingerprint
change forces repost, empty batch, stale-past-threshold, just-under
threshold, missing/unparseable/naive timestamps). Two existing
`TestPostThreadQueue` skip tests updated: one gains a fresh
`last_posted_at`; the legacy-slot one now asserts the
migrating-repost behaviour.

The pre-existing orphaned message in C01 (156513) is Lewis's manual
cleanup — the bot does not auto-delete orphans (hard rule). This
fix stops new ones from forming.

Version: PATCH — a bug fix. The periodic re-post of stuck queues is
a side effect of the correctness fix, not a new feature.

See L28 in `docs/dev/REFACTOR_PROGRESS.md` for the 48h-window
analysis and why a forced-refresh cadence is the right shape.

---

## [4.51.0] - 2026-05-19

### Changed

**Per-topic pinned queue: slim format + roster nudge on caught-up.**

Cannon (player in C05/MW) flagged on 2026-05-19 that the pinned
per-topic queue messages in the RP channels were a "brick of meta
information" — immersion-breaking, dominated by the age-icon
legend and the quote/preview snippets. The visible body of every
pinned queue was:

```
━━━━━━━━━━━━━━━━
📋 Unreplied: 2
Age: 🆕<1h 🌱6h 🌿12h 🌳1d 🟢2d 🟩3d 🟡4d 🟨5d 🟠6d 🟧7d ... ☀24d
01 [153422] 🌳 14h. Ryo Yamakawa: "And who is this master?
   The one who stole us from wherever we were? Away...
   🔗 https://t.me/Path_Wars/51357/153422
```

Lewis's defence of the QUOTE ("so I know I'm replying to the
correct message") was specifically about the bot-topic GM Queue
where he triages across many campaigns. In the per-topic case the
GM is already in that conversation; the quote is redundant.

The fix ships a two-tier display:

* **Bot-topic GM Queue** (Lewis's workspace) — unchanged. Verbose
  by design; the quote, the legend, the all-time counter all stay.
* **Per-topic pinned queue** (each PBP channel) — slimmed hard:

```
📋 Unreplied: 2
↗ Ryo · 🌳 14h · t.me/Path_Wars/51357/153422
↗ Bruce · 🌳 13h · t.me/Path_Wars/142887/153432
```

Dropped from the per-topic format: the separator line, the age
legend, the numbered prefix, the message-id brackets, the
quote/preview text, the 🔗 link emoji. Kept: count header, link
(Lewis hard requirement — every entry has its own jumpable link),
age icon (urgency hint at a glance), first name (channel context
means full names aren't needed).

**Caught-up message** also gains a roster-tagging behaviour
(Lewis's choice, Option A from the design discussion). When the
per-topic queue transitions from non-empty to empty:

```
📋 All caught up. Time for players to post!
@alice @bob @charlie @dave @ryo @anthony
```

All active-roster players (non-perm-recent + perm — the same set
``commands.roster._active_players`` returns) get an @-mention. This
fires Telegram notifications on every transition, which is
intentional: the bot's purpose is GM accountability AND nudging
players when the queue clears. Edge case (0 active players,
including ``state=None`` from tests): falls back to a bare
``📋 All caught up here.`` (no tag line, nobody to nudge).

### Code changes

* `scripts/commands/topic_queue_format.py` — rewrote
  ``format_topic_queue`` for the slim shape. New helper
  ``_format_topic_line`` builds the per-entry line. Dropped imports
  of ``format_queue_line`` and ``short_preview`` from
  ``queue_format`` (no longer needed). Dropped ``_AGE_LEGEND`` and
  ``_SEPARATOR`` constants.
* `scripts/scheduled/per_topic_caught_up.py` (new, 68 lines) —
  single source of truth for the caught-up message text. Exposes
  ``build_caught_up_text(pid, state, config)`` which handles both
  the bare and the tagged forms. Lazy-imports ``_active_players``
  from ``commands.roster`` to avoid circular import at module load.
* `scripts/scheduled/topic_queue_poster.py` — threaded ``state``
  through ``post_topic_queues`` (keyword-only, optional) and
  ``_clear_thread_queue`` (with ``pid`` and ``config`` siblings).
  Replaced the hardcoded ``"━━━\n✅ All caught up!"`` with a call
  to ``build_caught_up_text``. File stays at the 200-line cap by
  trimming previously-verbose docstrings.
* `scripts/scheduled/queue_reminder.py` — passes ``state=state``
  through to ``post_topic_queues``. Single-line touch.

### Tests

* `scripts/test_per_topic_slim_format.py` (new, 193 lines, 14 tests)
  covering the slim format (first-name only, age icon kept, bare
  link without 🔗, no quote, no numbered prefix, no legend, no
  separator, link-omission edge case) and the caught-up builder
  (state=None fallback, 0-active fallback, with-roster nudge,
  per-record perm flag inclusion, config-list perm inclusion,
  cross-campaign isolation).
* `scripts/test_topic_queue.py` — four assertions updated for the
  new format: ``test_entry_with_link`` (no 🔗), the renamed
  ``test_multiple_entries_no_numbered_prefix`` (no 01/02), the
  renamed ``test_age_legend_removed`` (legend absent), and
  ``test_splits_long_message`` (500 entries to overflow instead of
  60-with-quotes since per-line size dropped).
* `scripts/test_topic_queue_b.py` — four ``_clear_thread_queue``
  call sites updated to pass the new ``pid=, state=None, config={}``
  keyword arguments. The existing assertions (caught-up sent,
  prior caught-up deleted, slot cleared, msg_ids removed) still
  hold with the new builder since they assert presence of
  "caught up" substring rather than exact text.

1726 passing (was 1712; +14 new). Every changed file under the
200-line cap.

### Behaviour deltas

* In each PBP channel, the pinned queue message body is now ~3
  short lines plus the count header instead of ~25 lines of
  legend + quoted previews.
* When a per-topic queue clears (the transition that fires the
  caught-up message), the active roster gets @-mentioned. For
  campaigns with 4–6 active players this fires that many
  notifications per transition. Bots that respect mute settings
  will respect them here too — Telegram's normal mention rules
  apply, and players who don't want pings can mute the topic.
* Bot-topic GM Queue (``scheduled/queue_reminder.py``) and its
  caught-up notification (``scheduled/queue_caught_up.py``) are
  unchanged.

Not affected: state-schema, cron cadence, eviction lifecycle, the
rolling-history machinery from 4.49.1.

Version: MINOR bump because behaviour is user-visible (the shape
of the per-topic post and a new tagging side-effect on caught-up).
Backward-compatible: ``state=None`` in ``post_topic_queues``
falls back to the bare caught-up form so callers that haven't
updated keep working.

See L27 in `docs/dev/REFACTOR_PROGRESS.md` for the two-tier
display rationale (same data, different audience, different
shape) and the design trade-off on full-pings vs notification
noise.

---

## [4.50.0] - 2026-05-17

### Added

**Config-driven `permanent_user_ids` rule + Current/Perm section split.**

Lewis reported on 2026-05-17 (twice in close succession) that the
roster output wasn't accounting for Anthony, Horia, and Ryo as
permanent players, even though memory entry #17 captured the rule
"A/H/R are always perm in every campaign they're in." The previous
fix path — use `/setpermanent` in each PBP topic to flip the
per-record flag — was high-friction (one command per
user-per-campaign) and prone to drift when new enrolments arrived
with the default `permanent=False`.

This release encodes the rule directly as config:

```json
"permanent_user_ids": [6144366145, 5443237599, 138025700]
```

(Anthony @MrNegetZ, Horia @Nemesiux, Ryo @RyoYamakawa.) Any player
whose `user_id` matches an entry in this list is treated as
permanent in every campaign they're enrolled in, regardless of the
per-record flag. The per-record flag still works for per-campaign
exceptions; the new config list works alongside it as a logical OR.

The drill-down view (`/roster C00`) also gets a visual upgrade:
players are split into separate `Current:` and `Perm:` sections
instead of carrying an inline `[perm]` tag. Lewis spotted that 3
of 4 players in C00 were perm and the inline tag was easy to miss
when scanning. Two labelled sections make the split unambiguous.

### Code changes

* **New** `scripts/players/permanence.py` (53 lines) — single source
  of truth for `is_permanent(player, config)`. Returns True when
  EITHER `player["permanent"]` is True OR `player["user_id"]` is in
  `config["permanent_user_ids"]`. Tolerates int/str user_id
  mismatches, missing config keys, missing user_id fields.
* `scripts/commands/roster.py` — `_active_players` and
  `_split_active` now take a `config` parameter and delegate to
  `is_permanent`. `build_roster_campaign` renders Current/Perm as
  two separate sections, omitting either when empty. Inline
  `[perm]` tag removed.
* `scripts/commands/roster_players.py` — `_at_risk_status`,
  `_aggregate_by_user`, and `build_footer` all thread `config`
  through. The cross-campaign player table's `permanent: bool`
  flag now reads from `is_permanent` rather than the raw per-record
  field.
* `scripts/commands/roster_views.py` — the `/rosterall` aggregator
  passes `config` to `_aggregate_by_user` and `build_footer`.
* `scripts/scheduled/maintenance.py:check_recruitment_needs` —
  recruitment alert's perm-split now uses `is_permanent(p, config)`
  for both the count partition AND the inline `[perm]` tag in the
  roster listing.
* `scripts/scheduled/alerts.py:check_player_activity` — the
  auto-removal block (`if not player.get("permanent")...`) and the
  week-3 warning suppression both delegate to `is_permanent`. This
  means A/H/R are now never auto-removed and never receive the
  week-3 warning, even when their per-record flag is unset.
* `scripts/scheduled/roster_nudge.py` — both `_active_players`
  callers pass `config`.
* `config.json` — new `permanent_user_ids` key with three IDs.

### Tests

* **New** `scripts/test_permanence.py` (79 lines, 7 tests) covering:
  per-record flag True/False, user_id in config list, int vs str
  user_id matching, empty/missing user_id, missing config key,
  precedence semantics (logical OR).
* `scripts/test_roster_perm_display.py`:
  - `test_campaign_view_tags_perm_players_in_name_list` replaced
    with `test_campaign_view_splits_current_and_perm_sections`.
  - `test_split_active_partitions_correctly` updated for the new
    config-aware signature.
  - **New** `test_split_active_honours_config_perm_user_ids` covers
    the config-list partitioning path.
* `scripts/test_roster_views_a.py`:
  - `test_campaigns_view_tags_perm_players_inline` replaced with
    `test_campaigns_view_splits_current_and_perm_sections`.

1712 passing (was 1704). Every changed file under the 200-line
cap; `scheduled/maintenance.py` at exactly 200,
`scheduled/alerts.py` at 199.

### Behaviour deltas

* `/roster` overview — same X/Y +Z perm format; Z now includes A/H/R
  automatically. C00 (which currently shows 4/6 with no perm)
  will show 3/6 +1 perm or similar depending on which of A/H/R are
  enrolled.
* `/roster C00` drill-down — Current and Perm now appear as two
  separate labelled sections. Inline `[perm]` tag is gone.
* `/rostercampaigns`, `/rosterall` — same section split applies to
  every block.
* `/rosterplayers` — the `[perm]` tag in the cross-campaign player
  table still appears for visual consistency; the underlying perm
  classification now uses `is_permanent`.
* Recruitment alert (`📢 ... needs N more players!`) — same
  `Current roster (X/Y +Z perm):` format; perm count now folds in
  A/H/R automatically.
* Inactivity alerts (`scheduled/alerts.py`) — A/H/R now skip both
  the week-3 warning and the 4-week auto-removal, matching the
  rule from memory #17. Other (per-record-flagged) perm players
  unchanged.

Not affected: state-schema, hourly cron cadence, message lifecycle,
posting machinery. No migration; the new config key defaults to an
empty list if missing.

Version: MINOR bump because behaviour changes are user-visible (the
drill-down format) AND a new feature (`permanent_user_ids`) is
shipped. The change is additive and backward-compatible.

See L26 in `docs/dev/REFACTOR_PROGRESS.md` for the two lessons:
encapsulating a recurring dict-lookup behind a helper, and
recognising when an intent is better encoded as config than
repeatedly applied to state.

---

## [4.49.1] - 2026-05-12

### Fixed

**"All caught up!" now evicts the previous GM Queue.**

Lewis reported on 2026-05-12 that the bot topic had two messages
visible after queue #382's content was replied to:

  1. The GM Queue #382 message (3 unreplied, the old state)
  2. The "All caught up!" notification (no unreplied, the new state)

The first should have been deleted when the second went out, but
it wasn't. Root cause: pre-fix, the caught-up branches in
`scheduled/queue_reminder.py` sent the message via plain
`tg.send_message`, bypassing the rolling-history machinery in
`gm_queue_history.post_and_persist`. The previous GM Queue batch
stayed in `state["gm_queue_history"]` with no trigger to evict it
until a NEW real queue post arrived — and even then, only the
queue batch would be evicted, leaving the now-stale "All caught
up!" message orphaned in chat alongside the new queue.

The fix routes the caught-up case through the same batch
machinery, with a new `pin: bool = True` parameter on
`post_and_persist` so the caught-up message itself isn't pinned
(it's informational, not a sticky reference like the queue):

Code changes:

* `scripts/scheduled/gm_queue_history.py:post_and_persist` — new
  `pin: bool = True` keyword parameter forwarded to `post_batch`.
  When False, the returned batch has `pin_id=None`, and
  `state["last_queue_pin_id"]` is set to None accordingly. Previous
  pin (if any) is still unpinned so the bot topic doesn't
  accumulate stale notifications.
* `scripts/scheduled/queue_caught_up.py` (new, 37 lines) — sibling
  helper module exposing `post_caught_up(state, group_id, bot_topic)`
  and the `CAUGHT_UP_TEXT` constant. The helper exists only to dedupe
  the call from both empty-queue branches in `queue_reminder.py`,
  but lives in its own file so `queue_reminder.py` stays under the
  200-line cap.
* `scripts/scheduled/queue_reminder.py` — both "All caught up!"
  branches (line-68 production path and line-73 defensive path)
  now call `_post_caught_up(state, group_id, bot_topic)` (aliased
  from `queue_caught_up.post_caught_up`) instead of
  `tg.send_message`. Resulting flow: caught-up message goes out,
  previous batch evicts (its chat messages get deleted),
  caught-up message is registered in `gm_queue_history` so the
  NEXT real queue post evicts it in turn.

Tests:

* `scripts/test_queue_caught_up_helper.py` (new, 104 lines, 4 tests):
  - `post_caught_up` routes through `post_and_persist` with `pin=False`
    and the right text constant
  - `pin=False` makes `post_batch` skip pinning and clears
    `last_queue_pin_id`
  - `pin=False` still unpins the PREVIOUS pin so old pin notifications
    don't accumulate
  - `pin=True` (default) preserves pre-fix behaviour exactly
* `scripts/test_queue_reminder_caught_up_a.py` and `_b.py` — the two
  failing "message sent" tests updated to patch `_post_caught_up`
  directly (the deeper `post_and_persist` chain is covered by the
  helper module's tests, so duplicating that mock here would just
  add noise). 1704 passing (was 1700; +4 new helper tests, two
  existing tests updated to match the new mock target).

Per `tg.send_message_id` semantics, the new caught-up message
also gets registered in `bot_sent_registry` (because it goes
through `post_batch` → `tg.send_message_id`). That means future
eviction attempts on the caught-up message will pass the registry
safeguard, which is correct: the message is bot-sent and trackable.

Version: PATCH because the visible message text is unchanged and
the only behaviour change is "the previous queue actually
disappears now" — a bug fix, not a new feature.

See L25 in `docs/dev/REFACTOR_PROGRESS.md` for the lesson about
batch-machinery being the right abstraction for ANY bot-topic
message that should later be auto-evicted, not just queue posts.

---

## [4.49.0] - 2026-05-12

### Changed

**Recruitment alert respects the permanent flag.**

Lewis flagged on 2026-05-12 that the recruitment alert
(`📢 X needs N more players!` posted by
`scheduled/maintenance.py:check_recruitment_needs`) was lumping
permanent players in with non-perm when computing roster fullness.
A campaign at `5/6 +1 perm` was reading as `5/6` and asking for 1
more player; a campaign at `4/6 +2 perm` (perms padding to combined
6) was being skipped entirely as "full roster". Both were wrong:
perm players don't fill the X/Y target slots, so the alert should
fire whenever non-perm count is short of target.

Post-fix, the alert message reads like the roster overview from
4.48.1 onwards:

```
📢 Grand Explorers needs 2 more players!

Current roster (4/6 +1 perm):
- Link (@Linksanelf2006)
- Ryo Yamakawa (@RyoYamakawa) [perm]
- Laetheron (@StorybookRhizome)
- Anthony NegetZ (@MrNegetZ)
- Cannon McMahon (@ArtyArtillery)

Know anyone who'd like to join? Send them to the recruitment topic!
```

The `[perm]` tag appears inline next to each permanent player's
mention, the header uses the `X/Y +Z perm` format from `/roster`,
and the `needs N more` calculation gates on non-perm count vs
target (so a campaign with 5 non-perm + 1 perm now correctly asks
for 1 more non-perm; a campaign with 6 non-perm + 1 perm no longer
fires the alert).

Code changes:

- `scripts/scheduled/maintenance.py:check_recruitment_needs`
  - Split `non_gm` players into `non_perm_players` and
    `perm_players` via the `permanent` flag (same shape as
    `commands/roster.py:_split_active`).
  - `needed = target - non_perm_count` (was `target - player_count`
    where player_count included perms).
  - Roster section header rewritten to `Current roster (X/Y +Z perm):`
    with the `+Z perm` suffix omitted when there are no perms (clean
    "X/Y" reads for campaigns without permanent players).
  - Each listed player gets a `[perm]` tag inline when `permanent=True`.
  - Print log line updated to include the perm suffix.

Tests:

- `scripts/test_recruitment_perm_display.py` (new, 104 lines, 4 tests):
  - 5 non-perm + 1 perm → `5/6 +1 perm` header, asks for 1 more, perm
    tag inline
  - 4 non-perm + 0 perm → clean `4/6` header, no `+0 perm` clutter
  - 6 non-perm + 1 perm → no alert (non-perm at target)
  - 3 non-perm + 3 perm → fires alert with `3/6 +3 perm` and asks
    for 3 more (the case where the old combined-count logic would
    have skipped the alert entirely because 3+3=6)

1700 passing (was 1696; +4 new). Every changed file under the
200-line cap.

Version: MINOR bump because user-visible behaviour changed (the
shape of the recruitment alert and the conditions under which it
fires). No state-schema changes; no migrations.

See L24 in `docs/dev/REFACTOR_PROGRESS.md` for the three-spot
sweep needed when the perm-split rule changes (overview, per-
campaign drill-down, recruitment alert — all read the same flag,
all need the same shape).

---

## [4.48.1] - 2026-05-12

### Fixed

**Roster warning icon now gates on non-perm count, not combined.**

Lewis flagged on 2026-05-12 that the `✅`/`⚠️` icon in
`/roster` should consider only non-permanent players against the
target, since permanent players don't fill the "out of 6" slots
the target is measuring. Pre-fix, the icon gated on
`(non_perm + perm) >= target`, which would show "5/6 +1 perm"
as ✅ even though the campaign has only 5 non-perm active.
Post-fix, the same case correctly shows ⚠️ because non-perm 5 < 6.

With today's data no displayed icons actually flip (no campaign
is currently in the "padded by perms to hit target" state), so
the immediate visible output is unchanged. The semantic is now
correct for any future case where a campaign IS padded by perms.

Code changes:

- `scripts/commands/roster.py`:
  - `build_roster_overview`: icon gate changed from
    `combined >= target` to `non_perm_n >= target`; sort key
    updated to use non-perm count for warning ordering and
    within-group ordering.
  - `build_roster_campaign`: same icon change applied to the
    per-campaign drill-down header.
  - Comments added explaining the three-role model for the
    permanent flag (membership / auto-removal-suppression /
    target-slots) and pointing at L23 in REFACTOR_PROGRESS.md.

Tests:

- `scripts/test_roster_perm_display.py`:
  `test_overview_icon_uses_combined_count` (which had asserted
  the old combined-count behaviour) replaced with
  `test_overview_icon_gates_on_non_perm_count` covering three
  cases: 4/6 +2 perm → ⚠️, 6/6 → ✅, 7/6 +1 perm → ✅.
  1696 passed.

Not a code issue but discovered during the same investigation:
Lewis's mental model of which players are perm-flagged didn't
fully match the actual state. State as of 2026-05-12 has Ryo
flagged perm in C05 only (Lewis: "in every campaign Ryo's in");
Moss flagged perm in C01 (Lewis didn't mention); Anthony and
Horia not flagged perm anywhere (Lewis: "perm in C01 only").
The `permanent` flag is per `{pid}:{user_id}` record, not
global. Fixing the data is on Lewis's plate and outside this
commit's scope.

Version: PATCH bump because the displayed icon for current data
doesn't change — the fix is semantic correctness for future
state. No state-schema changes, no migrations.

See L23 in `docs/dev/REFACTOR_PROGRESS.md` for the three-role
breakdown of the permanent flag and the process lesson about
verifying against actual state data before acting on numeric
discrepancies in UI counts.

---

## [4.48.0] - 2026-05-11

### Changed

**POTW boon selection moved to the website; `/chooseboon` removed.**

The Player-of-the-Week announcement no longer offers inline
buttons or a `/chooseboon N` text command for picking a boon.
Players now log in at
`https://comeonover.netlify.app/PathWars` to claim their boon.

User-facing changes:

- New POTW messages drop the `Tap a button below, or use
  /chooseboon N in the ... RP topic.` line and instead end with
  `Log in to claim your boon: 🔗 https://comeonover.netlify.app/PathWars`.
- The four `Boon #1` / `Boon #2` / ... inline buttons no longer
  appear on new POTW messages.
- The three escalating 24h / 3-day / 6-day boon reminders now
  point to the website rather than telling players to use
  `/chooseboon` in the PBP topic.
- The `/chooseboon` command is no longer registered with
  Telegram and is no longer listed in the in-chat help text.
- The `/help` / `/commands` reference text drops the
  `/chooseboon <N>` line.

Code changes:

- `scripts/scheduled/potw.py` — boon_text rewritten; inline
  buttons construction removed; send_message_with_buttons →
  send_message_id.
- `scripts/boons/reminders.py` — three reminder texts updated.
- `scripts/dispatch/cmd_player.py` — `/chooseboon` handler removed;
  module docstring updated; unused `choose_boon_by_text` import
  removed.
- `scripts/dispatch/bot_topic.py` — `/chooseboon` handler removed.
- `scripts/dispatch/router.py` — `/chooseboon` text-command branch
  removed; `process_boon_callback` dispatch in the callback_query
  handler removed (hero-point callbacks still handled); unused
  `process_boon_callback` import removed.
- `scripts/dispatch/help_text.py` — `/chooseboon <N>` line dropped.
- `scripts/parsing/message.py` — the `/chooseboon`-specific
  sentinel-pid special-case removed; main-chat messages with no
  thread_id now rejected uniformly.
- `scripts/set_commands.py` — `("chooseboon", "...")` entry removed.

Not touched: the `choose_boon_by_text` and `process_boon_callback`
functions in `scripts/boons/handler.py` remain in place and are
still exported from `boons/__init__.py`. They have no production
callers after this commit but their tests continue to pass, which
is why they stay — removing them would balloon the scope of this
change into a multi-file test cleanup. Future work can excise the
dead functions if desired.

Known UX gap (one-time, deliberate): players who tap one of the
inline buttons on a POTW message posted before this commit will
see no response — the bot now silently ignores `boon:` callbacks.
Old POTW messages will become inert relics in chat history. This
is acceptable because (a) future POTW messages don't have buttons,
(b) the website is the documented path going forward, and (c)
adding a "that command moved — use the website" reply would mean
keeping the entire callback-dispatch path alive just for the
degraded case.

Version: MINOR bump because user-visible behaviour changed (the
shape of the POTW announcement and the loss of `/chooseboon`).
No state-schema changes; no migrations needed.

Tests: 1696 passing (was 1698; two obsolete tests deleted with
explanatory comments — `test_process_updates_boon_callback` and
`test_chooseboon_executes`). Every file remains under the 200-line
cap. See L22 in `docs/dev/REFACTOR_PROGRESS.md` for the learning.

---

## [4.47.1] - 2026-05-03

### Refactored

**`scripts/test_core_coverage.py` split by subject-under-test**
(`test_core_queue.py`, `test_core_markdone.py`,
`test_core_state.py`, `test_core_scheduled.py` — all new)

The single 514-line `test_core_coverage.py` violated the 200-line
budget and grouped tests for six unrelated modules under one file.
The author had already drawn topic boundaries with section-divider
comments; the split honours those exact cut points:

- `test_core_queue.py` (126 lines) — `commands/queue.py`
- `test_core_markdone.py` (151 lines) — `commands/markdone.py`
- `test_core_state.py` (51 lines) — `state.py` file-I/O paths
- `test_core_scheduled.py` (194 lines) — `scheduled/{session_poll,queue_reminder,potw}.py` guard tests

No test bodies changed. Each new file's docstring describes its
scope. Full suite still 1509 passing; no behaviour change. Closes
the last per-file budget violation introduced by today's work.

---
## [4.47.0] - 2026-05-03

### Refactored

**Gist I/O extracted from state.py**
(`state_gist.py` [new], `state.py`)

The gist load/save code was a ~50-line block at the bottom of
`state.py` reading module-level `_GIST_API` and `_GIST_TOKEN`
singletons. With per-module dependencies and a strong line-count
budget, extracting it into `state_gist.py` was overdue.

The new module exposes two pure functions:
`gist_load(api, token, filename) -> dict | None` and
`gist_save(api, token, filename, state) -> None`. Credentials are
passed in rather than read from a singleton, so the module is
import-time pure and trivial to unit-test without monkey-patching.
`state.py` keeps the credential singletons and passes them through
to each call site, preserving the existing `state.init()` API.

`state.py` drops from 203 to 156 lines; `state_gist.py` is 68
lines. `import requests` is no longer needed in `state.py`.

### Tests

`scripts/test_state_gist.py` (new): 11 tests covering both pure
functions plus the internal `_headers` builder. Asserts:
- empty api or token returns None / no-ops
- successful load returns parsed state
- HTTP error and network error abort with `SystemExit` (protects
  against silently clobbering gist history with an empty save)
- save HTTP failure and network exception are caught and logged
- non-JSON-native types in state serialise via `default=str`

The 9 previously-existing gist tests in `test_core_coverage.py`
are removed (they tested module-private functions that no longer
exist). Two patch sites in `test_core_coverage.py` and two in
`test_state_io.py` updated to patch the new `gist_load`/`gist_save`
names. Full suite: 1509 passing (was 1500); 1 pre-existing flaky
failure unrelated to this change.

---

## [4.46.0] - 2026-05-03

### Fixed

**`/markdone` clears now appear in the daily counter**
(`commands/markdone_audit.py` [new], `commands/markdone.py`)

The queue header counters previously disagreed on what counts as a
clear: the all-time figure read `reply_log` (which includes both
Telegram-reply and `/markdone` clears) but the today figure read
`state.queue_history` (which only had Telegram-reply clears). A
session where most clears happened via `/markdone` would show a
small "today" against a much larger all-time, with no obvious
explanation.

`/markdone` now writes to both stores via the new `record_clear`
helper in `commands/markdone_audit.py`. The two existing audit-trail
write blocks in `markdone.py` (`_clear_entries` and `_clear_by_msg_id`)
collapse to single calls into the helper, removing duplication and
keeping `markdone.py` under the 200-line budget.

### Tests

`scripts/test_markdone_audit.py` (new): 5 tests covering reply_log
shape, preview truncation, the mirroring call into
`queue_stats.record_reply`, log preservation across clears, and the
end-to-end queue_history write that closes the parity gap. Full
suite: 1500 passing (was 1495), same 8 pre-existing
Windows-codec failures.

---

## [4.45.0] - 2026-05-03

### Fixed

**Reply tracking deduplication**
(`commands/queue_io.py`, `commands/markdone.py`,
`commands/queue_stats.py`, `dispatch/tracking.py`,
`dispatch/gm_reply.py` [new])

The bot was over-counting cleared queue entries when the same Telegram
update arrived more than once (offset replays, retries, edits). The
queue header showed "53 cleared today" against 29 actual unique
clears. `mark_replied` deduplicated `replied[]` but unconditionally
appended to `reply_log[]`, and `record_reply` had no dedup at all, so
`state.queue_history` and `state.queue_archive` accumulated duplicate
entries on every replayed update.

`mark_replied` now returns a `bool` and gates the `reply_log` append
on that flag. `record_reply` accepts an optional `msg_id` and is
defensively idempotent against the most-recent archive entry for the
same `(pid, msg_id)`. `markdone.py` applies the same gate to both of
its `reply_log` write paths. The reply-recording flow itself was
extracted to `dispatch/gm_reply.py` (`record_gm_reply`) so the side
effects (per-campaign queue + global state) are co-located, single
responsibility, and easy to test.

### Added

**All-time clears in the GM Queue header**
(`commands/queue_stats.py`, `scheduled/queue_reminder.py`)

The header now reads
`GM Queue #N - Unreplied: X | Y today | Z all-time`. The all-time
counter is sourced from per-campaign `reply_log` files (the uncapped
audit trail) and filters to `{reply, markdone, manual}` so migration
markers (`archive-pre-w11`, `dedup`) are excluded. New helper
`get_alltime_clears(filter_via=None)` in `commands/queue_stats.py`.

**Known limitation:** the "today" counter still reads
`state.queue_history`, which only records Telegram-reply clears, not
`/markdone` clears. The asymmetry pre-dates this release but is more
visible now that the all-time figure includes both. Aligning them
would need `markdone.py` to call `record_reply`; deferred for a
follow-up so the dedup landing remains scoped.

### Tests

`scripts/test_queue_dedup.py` (new): 14 tests covering idempotent
`mark_replied`, repeated `record_reply` no-op, both `markdone`
paths, `get_alltime_clears` filter behaviour, and the
`gm_reply.record_gm_reply` flow end-to-end. Full suite: 1495 passing
(8 pre-existing Windows-codec test failures unchanged).

---

## [4.44.0] - 2026-05-03

### Added

**Rolling 3-batch retention in the GM Queue topic**
(`scheduled/gm_queue_history.py`, `scheduled/queue_reminder.py`,
`state.py`, `docs/gm-queue.md`)

Only the last three queue post batches are kept in the GM Queue topic.
When a fourth batch is posted, every Telegram message in the oldest
batch is deleted so the topic stays scannable. A *batch* is the full
set of messages produced by a single queue post — long queues that
overflow Telegram's 4096-char limit count as one batch and evict
together. State lives in `state["gm_queue_history"]` (live partition);
`MAX_KEPT_BATCHES = 3`. The legacy `last_queue_pin_id` is kept and
seeded into history on first run via an idempotent migration.

### Fixed

**Per-topic pinned queue: stale messages no longer orphaned on update**
(`scheduled/topic_queue_poster.py`, `scheduled/topic_queue_state.py`)

When a thread's pinned queue overflowed into multiple Telegram
messages, only the *first* message ID was tracked in
`topic_queues[thread_id]["msg_id"]`. On the next refresh the
non-first messages of the previous post were left behind in the
thread. The slot schema is now
`{msg_ids: list[int], fingerprint: str}` and every tracked id is
deleted before a new batch is posted. Legacy slots (`{msg_id: int}`)
are read transparently and rewritten to the new shape on first
update.

### Refactored

**Workflow** (`.github/workflows/pbp-reminder.yml`)

Removed a temporary one-off purge step that had been blocking
`checker.py` on every cron tick because the referenced script was
not on the remote.

---

## [4.43.0] - 2026-04-20

### Added

**Unknown voter alert improvements** (`dispatch/poll_notify.py`)

When an unrecognised UID votes, the alert now shows which options they voted for
and which placeholder usernames remain unresolved. When they later send any
message, the bot posts an identification alert and auto-promotes them on the
next workflow run.

**`/roster` command** (`commands/roster.py`, `dispatch/cmd_info.py`, `dispatch/bot_topic.py`)

Available to everyone from any topic including the bot topic.
- `/roster` — all campaigns ordered fewest to most active players (last 30d),
  shown as `4/6`, `8/6` etc with ✅ at target and ⚠️ below
- `/roster C04` or `/roster 04` — current active players + full join/leave history

**Player join/leave history** (`players/history.py`)

Permanent append-only log in `state["player_history"]`. Fires on `/addplayer`,
`/kick`, auto-removal, and rejoin. Updated roster automatically posts to the
campaign's chat topic on each event.

**`/kick` and `/addplayer` from any topic** (`dispatch/cmd_gm.py`)

Both commands now work from the PBP topic, COMBAT topic, or CHAT topic.
The bot resolves whichever topic you're in back to the canonical campaign.

**Hero Point campaign picker for MVP of the Week** (`boons/hero_point.py`)

After the leaderboard MVP is announced, the bot posts inline buttons — one per
campaign the winner is active in. Tapping one posts `✅ +1 Hero Point for
Magni Watch — Chase` to the bot topic.

**Silent campaign links** (`scheduled/queue_silence.py`)

Silent campaign entries in the GM queue now include the RP topic link and show
`Xd Yh` elapsed time. Threshold lowered from 10 days to 5 days.

**CI alert with failure details** (`scripts/ci_alert.py`)

Test failure alerts now include the specific FAILED test names and any coverage
gaps, so failures are diagnosable without opening GitHub Actions.

### Fixed

- `_voter_mention` now flags missing usernames visibly as
  `Christopher (⚠️ username unknown — uid 8787586972)` instead of silently
  using the display name as if it were a username
- Christopher (@Sestina_The_Banner_Witch) corrected in C01 `poll_user_names`
- C00 Riddleport COMBAT topic corrected (145053 → 133428)
- Workflow YAML repaired after inline Python f-string broke the parser
- C01 poll options merged: "Either Friday or Saturday" + "Both" → "Both/Either"
- Message IDs shown in queue entries now extracted from link when transcript
  lacks a `msg#` tag

---

## [4.42.0] - 2026-04-20

### Added

**`/roster` command** (`commands/roster.py`, `dispatch/cmd_info.py`)

Available to everyone. Two modes:

- `/roster` — all campaigns ordered fewest to most active players (last 30
  days), with ✅ at 6+ and ⚠️ + deficit count below target
- `/roster C04` or `/roster 04` — drill-down for one campaign: current
  active players plus full join/leave history with dates

**Player join/leave history log** (`players/history.py`)

New `state["player_history"]` list — a permanent append-only audit log of
every join and leave event, with timestamp, player name, username, and
campaign pid. Events recorded:

- **join** — when a player is added via `/addplayer`
- **join** — when a previously removed player posts again (rejoin)
- **leave** — when a player is kicked via `/kick`
- **leave** — when a player is auto-removed after 3 weeks of inactivity

History only starts accumulating from this release onward.

---

## [4.41.0] - 2026-04-18

### Added

**Message ID shown in GM queue entries** (`commands/queue_format.py`, `scheduled/queue_reminder.py`, `commands/topic_queue_format.py`)

Every entry in the GM queue now shows its Telegram message ID in brackets:

```
01 [1970] 🌱 1h. Jack Graham: *[gif]* 🔗 https://t.me/c/.../1970
02 [2062] 🌱 1h. THE FUN UNCLE: "Like me, did you die...
```

Use `/markdone 1970` to clear by ID — safe against renumbering regardless
of how many other entries are cleared beforehand. To clear multiple entries
atomically use `/markdone 1970 2062` (space-separated IDs or numbers).

The ID is also shown in pinned per-thread queue messages.

Logic extracted to `format_queue_line()` in `queue_format.py`.

---

## [4.40.0] - 2026-04-16

### Added

**Richer unknown poll voter alert** (`dispatch/poll_notify.py`, `dispatch/poll_router.py`)

When an unrecognised UID votes in a session poll, the bot topic alert now
includes which options they voted for and which placeholder usernames remain
unresolved in config. Example:

> ⚠️ Unknown voter in C11 poll: uid 6234551152
> Voted: Wednesday, Friday, Saturday, Sunday
> Unresolved roster slots: @molluggg, @Brookm126, @Luke_Skillen, @EliciaRoseT, @Thefununlce
> They will be identified when they next post.

**Auto-identification of unknown voters** (`dispatch/tracking.py`, `dispatch/poll_notify.py`)

When any message arrives from a UID that was previously captured as an unknown
poll voter, the bot now:
- Removes the UID from `poll_unknown_voters`
- Stores the UID → username mapping in `poll_identified_voters`
- Posts an identification alert to the bot topic immediately

**Auto-promotion via workflow** (`scripts/promote_poll_voters.py`, `.github/workflows/pbp-reminder.yml`)

`promote_poll_voters.py --commit` now runs every workflow cycle. It uses
`poll_identified_voters` to match real UIDs to placeholder config entries by
username, automatically updating `config.json` and committing it. Config is
now included in the workflow's `git add` step so promotions are persisted
without any manual intervention.

---

## [4.39.0] - 2026-04-15

### Added

**Silent campaign detection in GM queue** (`scheduled/queue_silence.py`, `scheduled/queue_reminder.py`)

When a campaign has zero unreplied entries AND its RP topic has had no messages
for 10 or more days, it now appears at the bottom of the GM queue:

```
━━ 💤 Silent campaigns ━━
  🟫 🦄 C08: Theria — no posts for 14d
```

Uses the same age icons as the queue. Campaigns with any unreplied entries are
never listed here (they're already visible in the queue). The silence threshold
is 10 days. Silent campaigns are included in the queue fingerprint so the bot
re-posts when a campaign first crosses the threshold.

**`/markdone` in GM Telegram command menu** (`set_commands.py`)

`/markdone` is now listed in the `/` popup for group admins, with description:
`Mark queue entry as replied: /markdone [N|msg_id|all]`

**PathWars boon link in POTW message** (`scheduled/potw.py`)

The Player of the Week boon selection message now includes a direct link to
`https://comeonover.netlify.app/PathWars` below the `/chooseboon` instruction.
Also corrected "PBP topic" → "RP topic" in the same line.

---

## [4.38.0] - 2026-04-14

### Added

**900 campaign-specific milestone messages** (`data/milestone_messages/`)

Every PBP thread now receives a unique, flavour-specific message when it
crosses a 500-post milestone, instead of the generic fallback. Messages
are written specifically for each campaign's setting, characters, lore,
and tone — 50 messages per thread, covering milestones 500 through 25,000.

Messages are stored in per-campaign JSON files under `data/milestone_messages/`:

| File | Threads |
|------|---------|
| `c00_riddleport.json` | PBP (66154), COMBAT (145053) |
| `c01_doomsday_funtime.json` | PBP (25059), COMBAT (22566) |
| `c04_magni_watch.json` | PBP (76799), COMBAT (144765) |
| `c05_grand_explorers.json` | PBP (51357), Dream (56842), COMBAT (145040) |
| `c06_kibwe.json` | PBP (40585), COMBAT (137075) |
| `c07_hopeful_end_times.json` | PBP (52083), COMBAT (145045) |
| `c08_theria.json` | PBP (107151) |
| `c09_metal_city.json` | PBP (107171), COMBAT (142887) |
| `c11_dark_pockets.json` | PBP (1242), COMBAT (1825) |

**Per-campaign milestone message directory loader** (`scheduled/message_milestones.py`)

`_MilestoneMessages._load()` now scans the `data/milestone_messages/`
directory and merges all `.json` files, rather than reading a single
`milestone_messages.json`. Non-JSON files are skipped. Corrupt or missing
files are caught and skipped gracefully. Cache behaviour is unchanged.

---

## [4.37.0] - 2026-04-13

### Added

**Poll link in vote notifications** (`dispatch/poll_notify.py`)

Each vote notification now includes a `🔗` link directly to that week's
pinned poll message, so players can tap through to vote immediately.

**Unknown voter alert** (`dispatch/poll_notify.py`)

When a completely unrecognised UID votes in a poll, the bot posts an
immediate warning to the bot topic: `⚠️ Unknown voter in C01 poll: uid
999888 — They voted but aren't on the roster.` The known-check now also
covers `poll_user_names` keys, so named-but-unrostered voters (PathWars,
Elinoa, Christopher) no longer trigger it.

**Permanent player flag** (`scheduled/alerts.py`, `dispatch/cmd_gm.py`)

Players with `permanent: true` in their player entry are never
auto-removed and skip the week-3 warning (which references auto-removal).
Week-1 and week-2 inactivity pings still fire normally.
GM commands: `/setpermanent @username` / `/unsetpermanent @username`.

Currently marked permanent: Anthony (@MrNegetZ), Horia (@Nemesiux)
across all their campaigns; Ryo (@RyoYamakawa) across all 5 PBP campaigns.

### Fixed

**Diagnostic: git credential paths shown as rate-limit context**

`/home/runner/…/git-credentials-*.config` lines were matching the
rate-limit pattern and appearing as context in the diagnostic report.
Added path-based filter (`/home/runner`, `/github/`, `git-credentials-`).
Preview truncation bumped from 120 → 200 characters.

**C01 poll roster** (`config.json`)

Added Elinoa Wigglero (uid `8740050892`) and Christopher (uid `8787586972`)
to C01 `poll_user_ids` and `poll_user_names`. PathWars (uid `1698524397`)
labelled in C11 `poll_user_names`. All three cleared from `poll_unknown_voters`.

---

## [4.36.0] - 2026-04-09

### Fixed — Per-topic queue posted to wrong thread in multi-topic campaigns

**Root cause:** `topic_queue_poster.py` used the canonical campaign pid as both
the state key and the Telegram destination thread. For campaigns with multiple
PBP topics (e.g. C06 Kibwe: `40585` PBP + `137075` COMBAT), all entries were
posted as a single queue to thread `40585`, regardless of which thread the
entries actually came from.

**Fix:** `queue_scan.py` now adds a `thread_id` field to each entry (the
resolved physical topic the message was posted in). `topic_queue_poster.py`
groups entries by `thread_id` before posting, sending a separate pinned queue
to each active thread.

**State schema change:** `topic_queues: {thread_id: {msg_id, fingerprint}}`
replaces the old top-level `topic_msg_id` / `topic_fingerprint` fields.
A one-time migration runs on first post: the old stale message is deleted
and the new per-thread structure takes over.

### Changed

Campaign overview (`scheduled/campaign_table.py`) now uses the same 22-tier
GM queue age scale (`entry_age_icon` from `commands/queue_format.py`) for
health icons, replacing the old 4-tier 🟢🟡🟠🔴 scale. Legend updated to match.

Diagnostic tool now shows up to 10 unique examples per issue type (was 1),
and truncates at 120 characters (was 90).

---

## [4.35.0] - 2026-04-08

### Fixed — Poll week number, date drift in vote notifications, per-campaign message links, rate limiting

**Poll week number on Sunday** (`scheduled/session_poll.py`)

Polls posted on Sunday (e.g. W14) were labelling themselves with the
current ISO week instead of the upcoming week. A poll posted Sunday W14
covers Mon–Sat of W15, so the title now correctly reads `W15/52`.
Fix: `(now + timedelta(days=1)).isocalendar()[1]` when `weekday == 6`.

**Vote notification date drift** (`scheduled/session_poll.py`, `dispatch/poll_notify.py`, `dispatch/poll_router.py`)

Vote notifications mid-week were recalculating option dates from the
current time (e.g. Tuesday) instead of from the poll-creation Sunday,
causing labels like "Monday 2026-04-13" instead of "Monday 2026-04-06".

Fix: poll options are now stored in `state["session_poll"][code]["options"]`
at creation time. `_options_for_code` reads stored options first and
only falls back to recalculation when absent. `handle_poll_answer` uses
stored options for the voter label too.

**Per-campaign message links for private groups** (`commands/queue_scan.py`)

C11 (Dark Pockets) lives in a separate private group. The queue scanner
was hardcoding `t.me/Path_Wars/…` for all campaigns. Added `_build_link`
which checks `pair.get("group_username")` — if absent, builds a
`t.me/c/{digits}/…` private-group link instead.

**Telegram rate limiting** (`scheduled/topic_queue_poster.py`)

Multiple per-topic queue posts in a single hourly run were triggering
rate-limit warnings. Added 1s sleep between each campaign post/clear.

**C09 combat topic** (`config.json`)

Topic `142887` (Metal City Stargazers COMBAT) added to C09
`pbp_topic_ids` — it's a PBP split topic, not a separate campaign.

**Per-topic queue preview length** (`commands/topic_queue_format.py`)

Bumped from 15 words to 80 words per entry. The longer entries give
enough context to know what the player wrote without opening the link.

**Poll username casing + placeholder detection** (`config.json`, `scripts/promote_poll_voters.py`)

`thefununlce` corrected to `Thefununlce` (Patrick Coxx). Placeholder
detection in `promote_poll_voters.py` now covers the `9100000xxx`
range used for Patrick's placeholder UID, in addition to `9000000xxx`.

---

## [4.34.0] - 2026-04-06

### Added — Per-topic pinned queue + telegram.delete_message

**Per-topic pinned queue** (`commands/topic_queue_format.py`, `scheduled/topic_queue_poster.py`)

Each PBP topic now gets its own pinned queue message showing only that
topic's unreplied entries. The message uses the same age-icon scale and
entry format as the bot-topic queue but omits the campaign header (you're
already in context). State is stored per campaign in the existing
`data/state/queues/{pid}.json` files as two new fields:
- `topic_msg_id` — message_id of the current pinned message
- `topic_fingerprint` — change-detection string; post is skipped if unchanged

Lifecycle per hourly run:
- Entries exist, no pin → post and pin (with notification)
- Entries exist, pin exists, fingerprint unchanged → skip
- Entries exist, fingerprint changed → delete old, post and pin new
- No entries, pin exists → send "✅ All caught up!", unpin and delete old pin

**`telegram.delete_message`**

New `delete_message(chat_id, message_id)` helper added to `telegram.py`
and registered in `conftest.py`'s mock.

**`/markdone` context-awareness** — no code change required. The existing
`pid`-scoped dispatch already scopes entry numbers to the current PBP
topic when the command is used there, and requires a campaign name arg
when used from the bot topic.

### Changed

`scheduled/queue_reminder.py` — calls `post_topic_queues(config, scanned, now)`
immediately after `scan_transcripts` on every hourly tick, before the
bot-topic fingerprint check. Per-topic queue maintenance is therefore
independent of whether the bot-topic queue changes.

---

## [4.33.0] - 2026-03-31

### Changed — 22-tier age icon scale

Completely redesigned queue age icons. Old 9-tier circle scale replaced
with a 22-tier system:

**Under 24h — growth sequence:**
| Icon | Age |
|---|---|
| 🆕 | < 1h |
| 🌱 | 1–6h |
| 🌿 | 6–12h |
| 🌳 | 12–24h |

**Days 1–16 — one icon per day (circle then square per colour):**
🟢 🟩 🟡 🟨 🟠 🟧 🔴 🟥 🟣 🟪 🔵 🟦 🟤 🟫 ⚫ ⬛

**Beyond day 16:**
| Icon | Age |
|---|---|
| 💀 | 17–21d |
| ☠️ | 21d+ |

Queue header legend and week welcome legend both updated.
`test_queue_format.py` fully rewritten: 23 tests → 479 total.

---

## [4.32.0] - 2026-03-31

### Fixed — Forum topic header false-positive in reply tracking

Every message in a Telegram forum topic technically has `reply_to_message`
set to the topic's root/header message (same ID as `message_thread_id`,
contains `forum_topic_created`). The bot was treating these as GM replies
to player messages, recording `msg=40585` (thread ID) for every GM post.

`_real_reply_id()` helper in `parsing/message.py` now filters out:
- `reply_to_message` with `forum_topic_created` key
- `reply_to_message` where `message_id == message_thread_id`

Confirmed working: reply to Kibwe message 140732 correctly recorded.

### Fixed — `/chooseboon` and all commands silently dropped from chat topics

`chat_topic_id` was not included in `to_canonical` mapping in
`topic_maps.py`. Messages from chat topics (e.g. 21528 = Kibwe chat)
were dropped before reaching any command handler. Added chat topic ID
to the canonical map so commands work from either chat or PBP topics.

### Fixed — Media group deduplication in GM queue

Telegram sends each image in a multi-photo post as a separate update
with the same `media_group_id`. Only the first message of a group is
now queued — subsequent images are skipped. `media_group_id` stored
in queue entries. Cleaned 2 existing Kibwe duplicates (140503, 140504).

### Fixed — `/markdone` accepts full t.me URLs

`/markdone https://t.me/Path_Wars/40585/139231` now works — the trailing
message ID is extracted from the URL automatically.

### Added — GM Queue sequential position numbers

Each queue entry is now prefixed with its position across all campaigns:
```
01 🟣 6d 12h. Link: Kieran will do slime lore... 🔗 ...
02 🟣 6d 12h. Link: He has a +15... 🔗 ...
```
Kibwe (priority) always starts at 01. Resets on each post.

### Changed — Queue preview length: 5 → 15 words

Message previews in the GM queue now show 15 words instead of 5.

### Added — GM Queue #N counter

Queue header now shows `📋 GM Queue #N` where N increments on every post.
Stored in `state["queue_post_count"]`.

### Added — Campaign emojis in queue section headers

Each campaign section prefixed with its emoji matching the Telegram chat:
`C00 💰 C01 📆 C04 🔍 C05 🔭 C06 🦠 C07 ⭐️ C08 🦄 C09 🤖 C11 🌑`
Stored as `emoji` field in `config.json` `topic_pairs`.

### Added — Queue auto-pin / unpin

After each queue reminder post, the first message is pinned to the bot
topic and the previously pinned queue message is unpinned. Tracked in
`state["last_queue_pin_id"]`. New `telegram.send_message_id()` and
`telegram.unpin_message()`.

### Added — Age legend in every queue header

`Age: 🟢 <6h  🟡 1d  🟠 2d  🔴 3d  🟣 5d  🔵 7d  🟤 14d  ⚫ 30d+`

106 production files, 456 tests passing.

---

## [4.31.0] - 2026-03-31

### Added — Queue reminder auto-pins latest post, unpins previous

After each queue reminder is sent, the first message is pinned to the
bot topic and the previously pinned queue message is unpinned. Tracked
in `state["last_queue_pin_id"]`.

New `telegram.send_message_id()` — like `send_message` but returns the
message_id. New `telegram.unpin_message()`.

### Added — Age legend in every queue reminder header

Every queue post now opens with:
```
📋 Unreplied: 103 | ✅ 39 cleared today
C06:35 C09:17 ...
Age: 🟢<6h 🟡1d 🟠2d 🔴3d 🟣5d 🔵7d 🟤14d ⚫30d+
```

### Verified — Reply tracking working correctly

Tested with 6 manual replies to Grand Explorers entries — all captured
in `data/state/queues/51357.json` reply_log with `via=reply`. Pre-link-era
entries (player=?) record the message ID correctly even without a live
queue entry to resolve the player name from.

---

## [4.30.0] - 2026-03-30

### Refactored — Per-Campaign Queue Partitions

Each campaign now has its own queue file at `data/state/queues/{pid}.json`
instead of all campaigns sharing keys in `queue.json`.

**Before:** `state["gm_queue_replied"]["40585"]` — shared dict, capped at
2000 entries, cross-campaign eviction possible.

**After:** `data/state/queues/40585.json`:
```json
{
  "pid": "40585",
  "unreplied": [...],
  "replied":   [...],
  "reply_log": [...]
}
```

**Benefits:**
- `replied` has no cap — every reply is remembered forever
- `reply_log` is per-campaign — full searchable audit trail
- No cross-campaign contamination or eviction
- `queue.json` slimmed to: `queue_history`, `queue_archive`, `pending_potw_boons`

**Migration:** 8 campaigns migrated from `gm_queue_replied` on deploy.
`data/` commit in the hourly workflow already covers `data/state/queues/`.

**New module:** `commands/queue_io.py` — load/save/mark_replied/migrate
per-campaign queue files. All queue touches in `tracking.py`,
`queue_scan.py`, and `markdone.py` now route through this module.

106 production files, 456 tests passing.

---

## [4.29.0] - 2026-03-30

### Fixed — Queue showing too few entries (floor too aggressive)

`queue_scan_floor` was set to `2026-03-30` (today), suppressing all
messages before today including legitimate recent ones. Reset to
`2026-03-16` (2 weeks ago) — kills the ancient 29d backlog but restores
🔵🟣🔴 entries from the past fortnight.

The real fix is a proper reply audit trail (below) rather than a floor.

### Added — GM Reply Audit Log (`gm_reply_log`)

Every GM reply-to event is now permanently recorded in
`state["gm_reply_log"]` (queue partition, capped at 500):

```json
{"t": "2026-03-30T19:00:00+00:00", "pid": "40585",
 "msg_id": "140368", "player": "Anthony NegetZ",
 "preview": "That's not a bug...", "via": "reply"}
```

`"via"` is `"reply"` for Telegram reply-to events and `"markdone"` for
manual clears. Provides a searchable history of all GM responses.

### Added — `/markdone` GM Command

Manually clear queue entries the bot missed (e.g. pre-history replies,
or messages handled outside Telegram's reply-to feature):

| Usage | Effect |
|---|---|
| `/markdone` | Clear oldest unreplied entry in this campaign |
| `/markdone 3` | Clear entry #3 from the queue list |
| `/markdone 140368` | Clear by Telegram message ID |
| `/markdone all` | Clear all entries for this campaign |

Each clear is written to `gm_reply_log` for audit purposes.

105 production files, 456 tests passing.

---

## [4.28.0] - 2026-03-30

### Fixed — Queue nudges re-firing every hour

`queue_nudged` state had 73 stale `pid:timestamp` keys from an old format.
The current code uses `pid:username` keys — the formats never matched, so
every run treated all players as un-nudged and fired again. Fixed by
clearing stale keys and pre-marking the current backlog players.

### Fixed — Telegram rate limiting (HTTP 429)

Queue nudge fired 16 messages in rapid succession, hitting Telegram's
burst limit. `telegram._post` now retries once on 429, waiting the
`retry_after` duration from the response before retrying.

### Added — Daily Diagnostic

`scheduled/diagnostic.py` + `scheduled/diagnostic_analysis.py` — runs
at `diagnostic_hour` (default 8am UTC) daily. Fetches the last 25
GitHub Actions run logs, scans for rate limits, errors, warnings,
unknown voters, queue peaks, and posts a summary to the bot topic:

```
🔍 Daily Diagnostic — 2026-03-31
⚠️ 1 issue type(s) found across 22 hourly runs
  ⚠️ Rate limited ×3
Activity:
  🗳️ 5 poll vote(s) recorded
  📋 Queue: 207 unreplied at peak
```

104 production files, 456 tests passing.

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
