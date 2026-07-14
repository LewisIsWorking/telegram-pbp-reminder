"""Persistent audit trail of every pin/unpin the bot performs.

Complements ``refusal_log`` (which records only *blocked* unpins). This
log records every pin and every unpin the bot actually attempts —
success or failure, plus the resolved originating call site — so that
when a pinned message disappears we can answer definitively: did the
bot unpin it, and from which code path?

Entries append to ``data/state/pin_audit_log.json``. Each is a dict:
    timestamp   ISO-8601 UTC
    action      "pin" | "unpin"
    chat_id     Telegram chat the action targeted
    message_id  the message pinned/unpinned
    ok          bool — did Telegram accept the call?
    refused     bool — True for an unpin the registry guard blocked
    site        "file:line" of the originating caller (wrapper frames
                in telegram.py / safe_delete.py / this file are skipped)

Why an on-disk trail: only this bot has pin rights in the affected
group, yet human pins have gone missing — so we need ground truth on
what the bot pins and unpins, surviving the process exit and landing
in the next CI commit for review.

The log is bounded to the most recent ``_MAX_ENTRIES`` rows. Unlike
refusals (rare), pins/unpins happen on most runs, so an unbounded file
would grow without limit; the tail is what matters for diagnosing a
recent disappearance.
"""

import threading
import traceback
from datetime import datetime, timezone

from state_store import StateStore

_LOCK = threading.Lock()
_LOG_NAME = "pin_audit_log"
_MAX_ENTRIES = 800
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
    """Append a pin/unpin audit entry (bounded to the most recent rows)."""
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
