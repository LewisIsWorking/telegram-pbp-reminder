# `recruiting/`: getting adverts in front of new players

Lewis, 2026-08-20: *"instead of just repeating the same thing of always posting
on the Pathfinder 2e discord... a recruitment workflow of various places to put
the ad... then over time build out more and more places."*

## What the numbers said when this was built

| | |
|---|---|
| seats filled across campaigns | 41 |
| **distinct humans** | **20** |
| posted at all in the previous 7 days | **9** |
| seats held by the top 5 people | 22 of 41 (**54%**) |

Worth keeping in view: half the seats belong to five people, and eleven of the
twenty players were silent for a week. Recruiting is still right, but some of
each new player refills a leak, so the yield per advert will read worse than it
is. Retention is a separate piece of work and this package does not attempt it.

## The two halves

**`catalogue.py`** is the venue list: URLs, cooldowns, the exact format each
venue demands, and why rejected venues were rejected. Hand-edited, lives at
`data/recruitment_venues.json`.

**`log.py`** is what we did: which venues we posted to and when, and which
players came from where. Lives in `state` under `recruitment_log`, deliberately
apart from the catalogue so hand-editing can never race the bot's writes.

`rotation.py` joins them to answer "where can I post today".

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

One angle worth remembering when writing the advert: PF2e play-by-post **on
Telegram** is a narrow ask, and general LFG boards are mostly people wanting live
voice games. The play-by-post-specific venues are the better bet, and the pitch
probably needs to answer "why Telegram" up front.

## Testing

```
cd scripts && python -m pytest test_recruiting_rotation.py test_recruiting_yield.py test_every_command_is_reachable.py -q
```

Proven by mutation, six of them, each asserted to have applied first: unlisting
the state key, turning "never posted" into `0.0`, collapsing `per_post` to `0.0`,
removing the assumed-cooldown floor, dropping a command from one of the four
registries, and ignoring cooldowns entirely.
