"""Persistent record of message IDs Telegram will not let the bot delete.

Added 2026-08-16 alongside the ``perform_guarded_delete`` fix. Before
that fix the bot could not tell "deleted" from "Telegram refused" —
``"message can't be deleted"`` was in ``_post``'s ``suppress_errors``
tuple, so a refusal came back as soft success. Result: **715 deletes in
the pin audit, 715 successes, zero failures, ever**, while an
``Unreplied: 2`` post from 2026-08-03 sat in the C06 topic the whole
time. See ``a-printed-fault-is-not-a-gate`` — detecting a fault and
recording it as fine is the same as not detecting it.

Removing the suppression makes a refused delete return ``False``, which
routes the ID into ``pending_delete`` and retries it every run. That is
right for a transient failure and wrong for a permanent one: a message
past Telegram's 48h window (or a service message) will never delete, so
the retry is a call the bot makes twice an hour forever and a
``pending_delete`` list that only grows.

This module is the third outcome. After ``MAX_ATTEMPTS`` failed tries an
ID is **hopeless**: the bot stops asking Telegram, drops it from
``pending_delete``, and files it here so a human can delete it by hand.
Filing routes through ``refusal_log`` as well, so the existing
``refusal_alert.py`` path reports it without a second alert channel.

Why a counter and not a reason string: the reason is Telegram's error
body, which varies by cause (48h window, service message, lost admin
rights) and by API version. **Attempts are the thing we can count
reliably**, and "tried four times across two hours and never once
succeeded" is the operational fact either way.
"""

import threading
from datetime import datetime, timezone

from posting.refusal_log import record_refusal
from state_store import StateStore

_LOCK = threading.Lock()

# Aux file name; StateStore keeps it beside refusal_log.json rather than
# in live.json, for the same reason refusal_log does — an audit record
# must not vanish through routine state mutation.
_LOG_NAME = "stuck_deletes"
_store = StateStore()

# Four attempts spans roughly two hours at the 30-minute run cadence.
# Long enough that a Telegram outage or a rate-limit burst recovers on
# its own; short enough that a genuinely undeletable message stops
# costing an API call twice an hour for the rest of the bot's life.
MAX_ATTEMPTS = 4


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    """Return the on-disk map, tolerating a missing or corrupt file."""
    data = _store.load_aux(_LOG_NAME, default={})
    return data if isinstance(data, dict) else {}


def note_failed_delete(chat_id: int, message_id: int) -> bool:
    """Count one failed delete for ``message_id``; True once it is hopeless.

    Called from ``safe_delete.perform_guarded_delete`` on every delete
    Telegram declines. Returns True on the attempt that reaches
    ``MAX_ATTEMPTS`` and on every attempt after it, so the caller can
    stop retrying and the sweep can drop the ID.

    The entry keeps ``first_seen`` and ``last_seen`` because "failing
    since 2026-08-03" and "started failing an hour ago" call for
    different responses, and the attempt count alone cannot tell them
    apart.
    """
    key = str(message_id)
    with _LOCK:
        log = _load()
        entry = log.get(key) or {"chat_id": chat_id, "attempts": 0,
                                 "first_seen": _now_iso()}
        entry["attempts"] = entry.get("attempts", 0) + 1
        entry["chat_id"] = chat_id
        entry["last_seen"] = _now_iso()
        hopeless = entry["attempts"] >= MAX_ATTEMPTS
        entry["hopeless"] = hopeless
        log[key] = entry
        _store.save_aux(_LOG_NAME, log)
    if hopeless and entry["attempts"] == MAX_ATTEMPTS:
        # Alert exactly once, on the attempt that crosses the line. Later
        # attempts are suppressed by is_hopeless before reaching here, but
        # the equality guard means a caller that ignores that still cannot
        # spam the alert channel.
        print(f"[delete_message] GIVING UP chat={chat_id} mid={message_id}: "
              f"Telegram declined {MAX_ATTEMPTS} times. The message is still "
              f"in the chat and must be deleted by hand.")
        record_refusal(chat_id, message_id)
    return hopeless


def is_hopeless(message_id: int) -> bool:
    """True when this ID has already exhausted its delete attempts.

    Checked before the HTTP call so a hopeless ID costs nothing. This
    is what bounds the retry loop that removing the error suppression
    would otherwise create.
    """
    entry = _load().get(str(message_id))
    return bool(entry and entry.get("hopeless"))


def hopeless_ids() -> list[int]:
    """Every message ID the bot has given up on, for reporting."""
    return [int(k) for k, v in _load().items() if v.get("hopeless")]


def clear_stuck(message_id: int) -> None:
    """Forget one ID — for when a human deletes the message manually.

    Also the escape hatch if the bot regains delete rights: without it a
    hopeless ID stays hopeless forever on a counter that no longer
    reflects reality.
    """
    key = str(message_id)
    with _LOCK:
        log = _load()
        if log.pop(key, None) is not None:
            _store.save_aux(_LOG_NAME, log)


def reset_for_test() -> None:
    """Test helper — wipe the log. Monkeypatch ``_store`` first."""
    with _LOCK:
        _store.delete_aux(_LOG_NAME)
