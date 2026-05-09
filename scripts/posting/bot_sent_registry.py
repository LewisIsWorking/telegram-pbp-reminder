"""Registry of message IDs the bot has sent.

Single source of truth for "did the bot send this message?". Used by
``telegram.delete_message`` to refuse deletion of any message ID not
in the registry — preventing accidental deletion of player or other
non-bot messages by maintenance scripts, ID-range sweepers, race
conditions, or corrupted state.

State lives in ``data/state/bot_sent_ids.json`` as a JSON list of
ints. The list is append-only — once recorded, an ID stays in the
registry forever (a deletion does not remove the ID, since the
underlying Telegram message no longer exists anyway, and we don't
want to "forget" a previously-sent ID and then refuse to clean it up
later).

Backfill: on first read in a fresh process, ``backfill_from_state``
scans every existing bot state file (live.json, queues/*.json) for
message IDs the bot was already tracking pre-registry. Idempotent.

Why this is unconditional: Telegram bots with admin+delete permissions
can delete ANY message in the chat — including player messages — when
asked. The only safe rule is "the bot may only delete IDs it sent".
The registry enforces that rule at the lowest possible layer (the
Telegram wrapper), so all callers — scheduled posters, maintenance
scripts, future code — get the protection automatically.
"""

import json
import threading
from pathlib import Path
from typing import Iterable

from posting.bot_sent_state_scan import (
    extract_ids_from_live as _extract_ids_from_live,
    extract_ids_from_queue as _extract_ids_from_queue,
)

_LOCK = threading.Lock()
_LOADED = False
_IDS: set[int] = set()

# Path resolution: registry sits next to live.json. Tests can override
# by monkeypatching _STATE_PATH. The path is relative to this module so
# it works regardless of cwd.
_STATE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "state" / "bot_sent_ids.json"
)


def _load_locked() -> None:
    """Load the registry from disk into the in-memory set.

    Caller must hold ``_LOCK``. Idempotent — only loads on first call.
    Always runs ``backfill_from_state`` once after the on-disk file is
    read so older state-file IDs are picked up.
    """
    global _LOADED, _IDS
    if _LOADED:
        return
    if _STATE_PATH.exists():
        try:
            with open(_STATE_PATH, encoding="utf-8") as f:
                _IDS = set(int(x) for x in json.load(f))
        except (json.JSONDecodeError, ValueError, OSError) as e:
            print(f"[bot_sent_registry] Corrupt {_STATE_PATH} ({e}); "
                  f"starting empty")
            _IDS = set()
    else:
        _IDS = set()
    _backfill_locked()
    _LOADED = True


def _save_locked() -> None:
    """Persist the registry. Caller must hold ``_LOCK``."""
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STATE_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sorted(_IDS), f)
    tmp.replace(_STATE_PATH)


def record_sent(message_id: int | None) -> None:
    """Add a message ID to the registry. No-op if ``None``.

    Called from every successful send in ``telegram.py``. Persists
    immediately so a crash between send and registry-write doesn't
    leave an undeletable orphan. Multiple calls with the same ID are
    free (set semantics).
    """
    if message_id is None:
        return
    with _LOCK:
        _load_locked()
        if int(message_id) in _IDS:
            return
        _IDS.add(int(message_id))
        _save_locked()


def record_many(message_ids: Iterable[int]) -> None:
    """Record multiple IDs in one transaction (single disk write).

    Convenience for callers that have a list of IDs and want to record
    them all atomically rather than triggering N separate writes.
    """
    with _LOCK:
        _load_locked()
        before = len(_IDS)
        for mid in message_ids:
            if mid is not None:
                _IDS.add(int(mid))
        if len(_IDS) > before:
            _save_locked()


def is_bot_sent(message_id: int | None) -> bool:
    """Return True iff the bot has previously recorded sending this ID.

    The single check that ``telegram.delete_message`` uses to decide
    whether to call Telegram's deleteMessage API. Any negative answer
    short-circuits the delete, protecting non-bot messages from being
    removed regardless of who asked or why.
    """
    if message_id is None:
        return False
    with _LOCK:
        _load_locked()
        return int(message_id) in _IDS


def _backfill_locked() -> int:
    """Scan known state files; add bot-sent IDs to in-memory set.

    Caller holds ``_LOCK``. Walks ``live.json`` and every
    ``data/state/queues/*.json``, pulling out IDs from queue history,
    pin trackers, topic queue slots, and caught-up message references.
    Returns the number of IDs newly added (for diagnostics).

    Idempotent: only adds, never removes. Failed parses are ignored
    silently (a missing/corrupt state file should not crash the bot).
    """
    state_dir = _STATE_PATH.parent
    added = 0
    candidates: list = []

    live_path = state_dir / "live.json"
    if live_path.exists():
        try:
            with open(live_path, encoding="utf-8") as f:
                candidates.extend(_extract_ids_from_live(json.load(f)))
        except (json.JSONDecodeError, OSError):
            pass

    queues_dir = state_dir / "queues"
    if queues_dir.exists():
        for fp in queues_dir.glob("*.json"):
            try:
                with open(fp, encoding="utf-8") as f:
                    candidates.extend(_extract_ids_from_queue(json.load(f)))
            except (json.JSONDecodeError, OSError):
                pass

    for mid in candidates:
        if mid is None:
            continue
        try:
            mid_int = int(mid)
        except (TypeError, ValueError):
            continue
        if mid_int not in _IDS:
            _IDS.add(mid_int)
            added += 1

    if added:
        _save_locked()
    return added


def reset_for_test() -> None:
    """Reset in-memory state. Tests only — never call in production."""
    global _LOADED, _IDS
    with _LOCK:
        _LOADED = False
        _IDS = set()
