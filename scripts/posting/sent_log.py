"""What the bot sent, so a later failure can name the message.

A message ID on its own cannot be triaged. ``mid=169479`` says nothing
about whether the thing still sitting in the group is a stale
``Unreplied: 2`` nobody will miss, or something that matters.

``bot_sent_registry`` deliberately does not hold this. It is the safety
structure — an append-only set that must stay small, cheap and boring,
because ``perform_guarded_delete`` consults it on every call and the
consequence of corrupting it is the bot deleting a player's message.
This is the descriptive record beside it: bounded, disposable, and free
to change shape without touching the guard.

Written by ``bot_sent_registry.record_sent``, which every successful send
in ``telegram.py`` already calls — so capture is automatic and no new
call site can forget it.

⚠️ Bounded to ``MAX_ENTRIES`` most recent. Losing the description of a
six-month-old message costs a line of context in a report; letting this
file grow forever costs a checkout on every CI run. The registry keeps
the ID for the safety check regardless — only the prose is evicted.
"""

import threading
from datetime import datetime, timezone

from state_store import StateStore

_LOCK = threading.Lock()
_AUX_NAME = "sent_messages"
_store = StateStore()

# Roughly a month of bot output at current volume. Reports that reach
# further back than this fall through to the transcript archive and then
# to an explicit "unknown", which is itself the useful answer.
MAX_ENTRIES = 1500

# Enough to recognise a message, short enough that the state file stays
# small and no alert accidentally reproduces a wall of GM prose.
PREVIEW_CHARS = 90


def _load() -> dict:
    data = _store.load_aux(_AUX_NAME, default={})
    return data if isinstance(data, dict) else {}


def record(message_id: int, text: str | None = None,
           thread_id: int | None = None, kind: str | None = None) -> None:
    """Note what a just-sent message was. Best-effort, never raises.

    Failure here must never propagate: this is diagnostic colour, and
    losing it is annoying whereas breaking a send is not. The caller has
    already sent the message by the time we are called.
    """
    try:
        preview = " ".join((text or "").split())[:PREVIEW_CHARS]
        with _LOCK:
            log = _load()
            log[str(message_id)] = {
                "at": datetime.now(timezone.utc).isoformat(),
                "thread_id": thread_id,
                "kind": kind,
                "preview": preview,
            }
            if len(log) > MAX_ENTRIES:
                # Evict oldest by send time. Keys are stringified ints and
                # Telegram IDs increase monotonically, but sorting on "at"
                # is honest about what we mean and survives a backfill
                # that inserts old IDs out of order.
                for key in sorted(log, key=lambda k: log[k].get("at") or "")[
                        :len(log) - MAX_ENTRIES]:
                    log.pop(key, None)
            _store.save_aux(_AUX_NAME, log)
    except Exception as exc:  # pragma: no cover - diagnostic only
        print(f"[sent_log] could not record mid={message_id}: {exc}")


def describe(message_id: int) -> dict | None:
    """Return what we recorded for this ID, or None if we never saw it."""
    return _load().get(str(message_id))


def reset_for_test() -> None:
    """Test helper — wipe the log. Monkeypatch ``_store`` first."""
    with _LOCK:
        _store.delete_aux(_AUX_NAME)
