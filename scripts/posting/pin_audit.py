"""Persistent audit trail of every pin/unpin/delete the bot performs.

Complements ``refusal_log`` (which records only *blocked* mutations).
This log records every pin, unpin, and delete the bot actually
attempts — success or failure, plus the resolved originating call site
— so that when a pinned message disappears we can answer definitively:
did the bot touch it, and from which code path?

Deletes are logged too because of a second, subtler way a pin can
vanish: Telegram **auto-unpins a message when it is deleted**. If a GM
or player manually pinned a message the *bot* had sent, and the bot
later deletes that message during queue eviction, the pin disappears
with no unpin call ever happening — so an unpin-only log would show
nothing. Logging deletes closes that blind spot: the vanished message
id will appear here as a ``delete`` entry instead.

Entries append to ``data/state/pin_audit_log.json``. Each is a dict:
    timestamp   ISO-8601 UTC
    action      "pin" | "unpin" | "delete"
    chat_id     Telegram chat the action targeted
    message_id  the message pinned/unpinned/deleted
    ok          bool — did Telegram accept the call?
    refused     bool — True for a mutation the registry guard blocked
    site        "file:line" of the originating caller (wrapper frames
                in telegram.py / safe_delete.py / this file are skipped)

Why an on-disk trail: only this bot has pin rights in the affected
group, yet human pins have gone missing — so we need ground truth on
what the bot pins, unpins, and deletes, surviving the process exit and
landing in the next CI commit for review.

The log is bounded to the most recent ``_MAX_ENTRIES`` rows. Deletes
are higher-volume than pins/unpins (a multi-chunk queue eviction
deletes several ids per run), so the cap is set to retain roughly two
weeks of combined activity — enough to still hold the relevant rows
when a disappearance is reported days later. Recording is best-effort:
a logging failure must never break the actual pin/unpin/delete, so
``record_action`` swallows its own exceptions.
"""

import threading
import traceback
from datetime import datetime, timezone

from state_store import StateStore

_LOCK = threading.Lock()
_LOG_NAME = "pin_audit_log"
_MAX_ENTRIES = 3000
_store = StateStore()

# Frames in these files are wrappers, not the true caller — skip them
# when resolving the originating call site.
_WRAPPER_FILES = ("pin_audit.py", "safe_delete.py", "telegram.py")


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _caller_site() -> str:
    """Return 'file:line' of the first stack frame outside the wrappers.

    Walks newest-to-oldest so the immediate business caller (e.g.
    ``topic_queue_poster.py``) is reported rather than the telegram/
    safe_delete delegation layer it passed through.
    """
    for frame in reversed(traceback.extract_stack()[:-1]):
        name = frame.filename.replace("\\", "/").rsplit("/", 1)[-1]
        if name not in _WRAPPER_FILES:
            return f"{name}:{frame.lineno}"
    return "?"  # pragma: no cover


def record_action(action: str, chat_id: int, message_id: int, ok: bool,
                  *, refused: bool = False, timestamp: str | None = None,
                  site: str | None = None) -> None:
    """Append a pin/unpin/delete audit entry (bounded to the most recent rows).

    Best-effort: this is a diagnostic trail, so a failure to log (disk
    error, unwritable state dir, etc.) must never propagate and break
    the actual pin/unpin/delete the caller just performed. Any exception
    is caught and printed, not raised.
    """
    try:
        entry = {
            "timestamp": timestamp or _now_iso(),
            "action": action,
            "chat_id": chat_id,
            "message_id": message_id,
            "ok": bool(ok),
            "refused": bool(refused),
            "site": site or _caller_site(),
        }
        with _LOCK:
            existing = _store.load_aux(_LOG_NAME, default=[])
            if not isinstance(existing, list):
                existing = []
            existing.append(entry)
            if len(existing) > _MAX_ENTRIES:
                existing = existing[-_MAX_ENTRIES:]
            _store.save_aux(_LOG_NAME, existing)
    except Exception as e:  # pragma: no cover — diagnostic must never break ops
        print(f"[pin_audit] failed to record {action} "
              f"mid={message_id}: {e}")


def recent(limit: int = 50) -> list:
    """Return the most recent audit entries (oldest first, newest last)."""
    with _LOCK:
        entries = _store.load_aux(_LOG_NAME, default=[])
    if not isinstance(entries, list):
        return []  # pragma: no cover
    return entries[-limit:]


def reset_for_test() -> None:
    """Test helper — wipe the on-disk audit log.

    Tests should monkeypatch ``_store`` to a tmp-rooted StateStore
    before calling this, so production state is not touched.
    """
    with _LOCK:
        _store.delete_aux(_LOG_NAME)
