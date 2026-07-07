# Delete safety — how the bot is prevented from deleting non-bot messages

This document is the single reference for the deletion safeguard added
after the **2026-05-08 incident**, in which the bot deleted around 200
player and GM messages from the Path Wars Telegram group.

If you are about to write code that deletes a Telegram message, read
this first. If you are reviewing a pull request that deletes a
Telegram message, read this first.

---

## The incident — cautionary tale

A maintenance script (`scripts/maintenance/purge_gm_queue_history.py`)
was written to clean up orphaned bot pin messages by sweeping a range
of message IDs and calling Telegram's `deleteMessage` for each one.
The script's body POSTed directly to the API:

```python
# THE BUG (now removed)
for mid in range(START, END + 1):
    requests.post(
        f"https://api.telegram.org/bot{token}/deleteMessage",
        json={"chat_id": GROUP_ID, "message_id": mid},
    )
```

The accompanying comment claimed *"Bot can only delete its own
messages — others silently fail"*. That comment was wrong. **A bot
with admin + delete permissions in a group can delete any message in
that group**, regardless of who posted it. There is no Telegram-side
flag or default that limits a bot to its own messages.

When the script ran with `START=151518, END=151741` (224 IDs), the
Telegram API obediently deleted everything in that range — the bot's
old pins, but also Tal'lysae's posts, Ji Yun's fulu request, Ryo
Yamakawa's questions, and the GM's replies. ~200 player and GM
messages, gone, in a single 11-second sweep. There is no recovery —
Telegram does not retain deleted message content.

The bot itself was working correctly throughout. The hourly scheduled
runs and the in-progress refactor commits did not contribute. The
script alone, run manually, caused the incident.

---

## The rule

**The bot may only delete messages it sent.**

There are no exceptions. There is no "force" flag. There is no
"trusted-script" mode. If you find yourself wanting one of those, you
have a different problem and should talk through the design.

The bot tracks every message ID it has sent in a registry persisted
to `data/state/bot_sent_ids.json`. Every delete call checks the
registry first and refuses if the ID isn't there.

---

## The mechanism

```
Caller                     telegram.delete_message
  ↓                                ↓
  tg.delete_message      →   posting.safe_delete.perform_guarded_delete
                                   ↓
                             posting.bot_sent_registry.is_bot_sent(mid)?
                                   ↓
                          ┌────────┴────────┐
                          ↓                 ↓
                       True               False
                          ↓                 ↓
                  HTTP delete call    return False, log refusal
                                      (no API call made)
```

Three production files compose the safeguard, all in
`scripts/posting/`:

* **`bot_sent_registry.py`** — owns the registry. Public API is
  `record_sent(mid)`, `is_bot_sent(mid)`, and `record_many(ids)`.
  Persists to `data/state/bot_sent_ids.json` (sorted JSON list of
  ints, append-only). On first read in a fresh process, calls
  `_backfill_locked` to seed the registry from `live.json` and
  `queues/*.json` (so the bot doesn't refuse to delete its own
  pre-registry pins).
* **`bot_sent_state_scan.py`** — pure helpers that pull bot-sent IDs
  out of the various state-file shapes (`gm_queue_history`,
  `topic_queues[*].msg_ids`, `caught_up_msg_id`, etc.). New state
  fields that store bot-sent IDs need to be picked up here.
* **`safe_delete.py`** — the guards. `perform_guarded_delete(chat_id,
  message_id, post_fn)` is the one place in the codebase that may
  pass `"deleteMessage"` as a method name, and `perform_guarded_unpin`
  is the one place that may pass `"unpinChatMessage"`. Each checks the
  registry, prints a diagnostic on refusal, and otherwise calls the
  post function.

`telegram.py` connects them: `delete_message` and `unpin_message` are
each a short delegate to the matching guard. The send functions
(`send_message_id`, `send_message_with_buttons`, `send_poll`) call
`record_sent` after every successful send so future deletes and unpins
work.

---

## Unpinning shares the same guard

The rule "the bot may only act on messages it sent" is not delete-only.
A bot with admin rights can **unpin any message in the group**, not just
its own — Telegram has no "own-messages-only" flag for `unpinChatMessage`
any more than it does for `deleteMessage`. A stale or crossed
`message_id` reaching the unpin call silently clears a GM's or player's
*manual* pin.

So `unpin_message` routes through `perform_guarded_unpin`, which applies
the identical `is_bot_sent` check before calling `unpinChatMessage`. The
callers only ever pass IDs the bot pinned itself (`poll_message_id`,
`last_queue_pin_id`, a batch/slot `pin_id`), and those IDs are recorded
at send time — so legitimate unpins pass, and only a non-bot ID is
refused. If you add a new place that unpins, do **not** reach for
`unpinAllChatMessages`/`unpinAllForumTopicMessages` (they clear pins the
bot never created); unpin a specific bot-sent ID through `unpin_message`.

---

## How to write code that deletes messages

### The right way

```python
import telegram as tg

# Send something:
mid = tg.send_message_id(chat_id, thread_id, "hello")
# tg.send_message_id has already called record_sent(mid).

# Later, delete it:
ok = tg.delete_message(chat_id, mid)
# tg.delete_message goes through the guard. ok is True if the
# message was deleted, False if either the registry refused or
# Telegram declined (already gone, no permission, etc).
```

### Adding a new sender

If you add a new function to `telegram.py` that returns a message ID,
call `record_sent` after the API call succeeds. Use the existing
senders as a template:

```python
def send_my_new_thing(chat_id, ...):
    result = _post("sendThing", payload, "send_thing")
    if not result:
        return None
    mid = result["message_id"]
    from posting.bot_sent_registry import record_sent
    record_sent(mid)
    return mid
```

The lazy import inside the function is intentional — it avoids
circular imports between `telegram.py` and `posting/`.

### Adding a new state field that stores a bot-sent ID

If you add a new state field in `live.json` or `queues/{pid}.json`
that holds a bot-sent message ID, **also add it to**
`scripts/posting/bot_sent_state_scan.py` so the next process startup
picks it up via backfill. Without that, a process restart followed by
a delete attempt for the new field would refuse and log a refusal —
which is the correct fail-safe but probably not what you wanted.

### Maintenance scripts that delete messages

Route through `tg.delete_message`. Never call
`requests.post` to `deleteMessage` directly. The rewritten
`scripts/maintenance/purge_gm_queue_history.py` is the reference
template.

```python
import telegram as tg

tg.init(os.environ["TELEGRAM_BOT_TOKEN"])
for mid in range(START, END + 1):
    ok = tg.delete_message(GROUP_ID, mid)
    # The guard refuses non-bot IDs in the range, prints a
    # diagnostic, and returns False without calling the API.
```

---

## Escape hatch

If you have a known bot-sent message ID that isn't in the registry
(legitimate edge case: an external script posted via the bot token
without going through `telegram.py`), add it explicitly:

```python
from posting.bot_sent_registry import record_sent
record_sent(154321)  # known bot-sent ID
```

Now `tg.delete_message(chat_id, 154321)` will go through. Use this
sparingly and with intent — every manual `record_sent` is a place
where the registry might disagree with reality.

---

## What's enforced by tests

`scripts/test_no_direct_delete_bypass.py` runs in CI on every push
and asserts:

1. **No new file mentions `deleteMessage`** outside the explicit
   allow-list. Adding a new mention requires either routing through
   `tg.delete_message` (the right answer) or editing the allow-list
   with a justification (forces review).
2. **No file constructs an `api.telegram.org/.../deleteMessage`
   URL** — the exact pattern the original purge script used to
   bypass the guard.
3. **Only `posting/safe_delete.py` may call any function with
   `"deleteMessage"` as the first positional argument.** Catches
   copy-pasted call patterns that forgot to delegate.

Together these make it structurally impossible to re-introduce the
bypass without a deliberate code review.

`scripts/test_safe_delete.py` covers the guard's behaviour itself:
refusal of unknown IDs, pass-through of known IDs, propagation of
the suppress_errors tuple, and (importantly) that the function
signature has no `force` parameter.

`scripts/test_bot_sent_registry.py` covers the registry: round-trip
record/check, persistence, reload, set semantics on duplicates,
backfill from sample state files, and graceful handling of
missing/corrupt state files.

---

## Soft-success semantics in `_post` (added 2026-05-10)

The layer below `safe_delete` — `telegram._post` — distinguishes
*hard failures* (network errors, rate-limit-after-retry,
unrecognised error bodies; returns `None`) from *soft successes*
(Telegram says the desired end state is already achieved, e.g.
"message to delete not found"; returns `True`). Both
`safe_delete.perform_guarded_delete` and `telegram.unpin_message`
use `_post(...) is not None`, so they read soft success the same
as real success.

**This is correctness, not a safety relaxation.** The change lives
*downstream* of the registry check. The registry is still the
gatekeeper: any message ID not in `bot_sent_ids.json` is refused
at the `safe_delete` layer before any HTTP call is made. The
soft-success path only changes how the *result* is interpreted
for IDs the registry has already approved. If the `is_bot_sent`
guard refuses, `_post` is never reached.

The catalogue of recognised soft-success error bodies and the
full rationale lives in `scripts/telegram_post_notes.py`. White-
box tests in `scripts/test_telegram_03_suppress.py` lock the
behaviour and guard against regression.

Why this matters for the incident: the original purge script
wouldn't have benefited from soft-success semantics — it bypassed
`safe_delete` entirely by POSTing to the API directly. The
safeguard's first principle ("the registry gates every delete")
is what prevents a recurrence; the soft-success refinement is a
separate quality-of-life fix for evictions that previously got
stuck because Telegram's "already gone" response was being read
as "delete failed."

---

## Related

* `scripts/posting/bot_sent_registry.py` — the registry module
* `scripts/posting/safe_delete.py` — the guard module
* `scripts/posting/bot_sent_state_scan.py` — backfill helpers
* `scripts/maintenance/purge_gm_queue_history.py` — reference
  template for safe maintenance scripts that delete
* `docs/dev/ROADMAP.md` — entries P1/3, P1/4, P1/5 track the
  safeguard rollout
* `docs/dev/REFACTOR_PROGRESS.md` — post-incident addendum at end
