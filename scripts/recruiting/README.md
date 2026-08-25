# `recruiting/`: getting adverts in front of new players

Lewis, 2026-08-20: *"instead of just repeating the same thing of always posting
on the Pathfinder 2e discord... a recruitment workflow of various places to put
the ad... then over time build out more and more places."*

## What the numbers said when this was built

**Measured 2026-08-20.** Re-measure before quoting; every figure here is a
snapshot, not a property.

| | |
|---|---|
| seats filled across campaigns | 41 |
| **distinct humans** | **20** |
| posted at all in the previous 7 days | **9** |
| seats held by the top 5 people | 22 of 41 (**54%**) |

### ⚠️ Corrected 2026-08-25: the leak is narrower than this first said

The original wording here warned that *"some of each new player refills a leak"*.
Re-measuring against `player_history` says that is true of the **total**, and
misleading about **joiners**:

| measured 2026-08-25 | |
|---|---|
| recorded joins since 2026-04 | 15 |
| of those, still seated | **12** |
| of those, since left | 3 (lasting 28, 28 and 41 days) |
| leaves with no join inside the window | **39** |

So leaves do outnumber joins 42 to 15, but 39 of those 42 are the **pre-April
cohort** draining out. People recruited since the log began have overwhelmingly
stayed. Recruiting is not pouring water into a bucket with a hole in it; it is
replacing an older intake that is ending naturally.

What is real, and unchanged: **20 humans hold 41 seats and the top five hold
22.** That is a concentration risk, not a churn one. One person leaving costs up
to six seats at once, and that is the failure this package cannot help with.

## The two halves

**`catalogue.py`** is the venue list: URLs, cooldowns, the exact format each
venue demands, and why rejected venues were rejected. Hand-edited, lives at
`data/recruitment_venues.json`.

**`log.py`** is what we did: which venues we posted to and when, and which
players came from where. Lives in `state` under `recruitment_log`, deliberately
apart from the catalogue so hand-editing can never race the bot's writes.

`rotation.py` joins them to answer "where can I post today".

**`readiness.py`** answers a question the other three cannot: *is the table we
are about to advertise actually alive?*

## ⭐ The biggest gap and the deadest table are usually the same campaign

`recruit_focus` picks whichever campaign is shortest of players. For the in-group
advert that is right, because everyone reading already knows the table. For an external
advert it is dangerous on its own, because seats are empty **because** nobody is
posting, and nobody is posting **because** seats are empty.

Found live on 2026-08-25: C04 Magni Guard was surfaced as the biggest gap at
"3/6 players", while its three seats had been silent 21, 24 and **56** days and
the whole campaign had produced **two** player posts that month.

A stranger who joins that gets one GM reply and leaves inside a month, and
`recruitment_log` records it as **the venue failing**. That is how a good venue
gets dropped for a table problem, with what looks like evidence.

So `/recruitads` now prints a warning above the venue list when the target
campaign has had no player post in `QUIET_DAYS` (14). It **warns, it does not
block**: a table can be quiet because everyone agreed to pause, and the GM knows
that and the bot does not.

⚠️ Readiness reads `last_post_time` directly and must **not** be routed through
`roster_members._active_players`. That function counts a permanent player
regardless of when they last posted, which is correct for "who is enrolled" (see
the L20 note there) and wrong for "is anyone posting". C04's 56-day seat is
permanent, which is exactly why it read as 3/6.

## ⭐ Attribution is the part that makes this converge

A longer venue list only spreads the same effort thinner. What turns it into an
answer is knowing that the Paizo board yielded four players from three posts
while a big general board yielded none from eight, because then the effort
moves. Without it you can add venues forever and never learn anything.

That needs one human habit: **when someone joins, say where they came from.**
Nothing can infer it, and a week later nobody remembers.

`unknown` is a real, recorded value. A venue credited by guesswork is worse than
one credited to nobody, because it survives review looking like evidence.

## ⚠️ An assumed cooldown is not a rule

The failure mode here is not running out of venues. It is getting muted in the
one venue that actually works, for reposting too soon or missing a flair.

So every cooldown carries `cooldown_source`:

- `rule` means the venue states it. Only **r/lfg** does so far: one post per 24
  hours, plus a title code system and a required flair.
- `assumed` means nobody has checked, and the loader **refuses** anything under
  `MIN_ASSUMED_COOLDOWN_DAYS` (7). Read the venue's rules before shortening one.

## Two distinctions that decide the next action

**`None` vs `0`, twice, and both matter.**

`days_since` returns `None` for a venue never posted to. Returning `0.0` would
make it look freshly used and suppress it permanently, when an untried venue is
the only kind that can still teach us anything.

`yield_table`'s `per_post` is `None` when nothing was posted there. *"Tried eight
times, got nobody"* says stop; *"never tried"* says go. Rendering both as `0.00`
merges two opposite conclusions into one number.

## Commands

| command | who | what |
|---|---|---|
| `/recruitads` | anyone | which venues are due, and what each demands |
| `/recruityield` | anyone | which venues have actually produced players |
| `/recruitposted <venue-id>` | GM | record that the advert went up |
| `/recruitjoined <venue-id> <name>` | GM | credit a new player to a venue |

The writes are GM-only because they move the figures that decide where the next
hour of effort goes.

⚠️ A command must be registered in **four** places: `set_commands.py`,
`_READ_CMDS` in `dispatch/router.py`, `no_campaign` in `dispatch/bot_topic.py`,
and a handler. Missing any one fails **silently**, which happened to three of the
four roster commands on 2026-08-14. `test_every_command_is_reachable.py` now
fails if a command reaches some registries and not the rest.

⚠️ `recruitment_log` is listed in `state_schema.PARTITIONS`. It has to be:
`save()` builds each partition as `{k: state[k] for k in keys if k in state}`, so
an unlisted key is discarded on every save with no error. Both write commands
would answer "recorded" and the data would be gone by the next run.

## Posting is manual, on purpose

The bot says where and what. It does not post. Automating submissions into
Discords and Reddit is how accounts get banned, and a ban costs far more than the
few minutes saved.

## Widening it

Venues start as `candidate`, become `active` once they produce someone, and
become `rejected` with the reason recorded. Rejected entries **stay in the file**
so the reasoning is not rediscovered and re-litigated in three months.

The `r-pbp` and `giantitp-recruitment` entries are deliberately incomplete: they
are leads I could not verify, left visibly unfinished rather than filled in with
plausible guesses.

### ⚠️ Foundry was rejected for the wrong reason (corrected 2026-08-25)

The Roll20 rejection is sound: its rules require the game to run on Roll20 and
this one does not. The original note then generalised *"same reason rules out the
Foundry and Fantasy Grounds boards"*, and that was **wrong**, because these
campaigns **do** run on Foundry VTT. Foundry carries the mechanics, maps and
automation; Telegram carries the asynchronous posting.

Lewis caught it: *"Foundry could be fine, it's telegram+foundry, so...maybe?"*

`foundry-lfg` is now a `candidate`, and its audience is a genuine filter rather
than just a bigger crowd: someone already running Foundry needs no onboarding
into the half of the setup that is hardest to teach.

The general lesson is worth more than the venue: **a rejection reason copied from
one venue to another is a guess wearing a decision's clothes.** Each rejection
needs checking against what this game actually is.

One angle worth remembering when writing the advert: PF2e play-by-post **on
Telegram** is a narrow ask, and general LFG boards are mostly people wanting live
voice games. The play-by-post-specific venues are the better bet, and the pitch
needs to answer "why Telegram" up front.

The advert itself lives in **[`docs/recruitment-ad.md`](../../docs/recruitment-ad.md)**,
with the per-venue variations.

## Testing

```
cd scripts && python -m pytest test_recruiting_rotation.py test_recruiting_yield.py test_recruiting_readiness.py test_every_command_is_reachable.py -q
```

Proven by mutation, **twelve** of them, each asserted to have applied before the
run so that green can never mean "the probe never arrived".

Six for the catalogue and rotation: unlisting the state key, turning "never
posted" into `0.0`, collapsing `per_post` to `0.0`, removing the assumed-cooldown
floor, dropping a command from one of the four registries, and ignoring cooldowns
entirely.

Six for readiness: raising `QUIET_DAYS` so it never fires, treating "no player
has ever posted" as healthy, reading only the first `pbp_topic_id`, dropping the
clamp on future timestamps, taking the oldest seat instead of the newest, and
severing the warning from the message it is supposed to appear in.
