"""Persistent log of every delete refusal by ``safe_delete``.

Each refusal is appended to ``data/state/refusal_log.json`` as a JSON
object with ``timestamp`` (ISO-8601 UTC), ``chat_id``, and
``message_id``. The log is append-only and persistent across runs.

A separate "alerted" marker (``data/state/refusal_log_alerted.json``)
holds the most-recent timestamp that has been reported via Telegram
alert. ``get_unalerted_refusals`` returns entries newer than that
marker so the alert script can post them once.

Why an on-disk log rather than in-memory: a refusal in production is
either a bug ("we tried to delete our own message but the registry
forgot it") or a foiled incident ("something tried to delete a
non-bot message"). Both need an audit trail that survives the bot
process exiting and shows up in the next CI commit so an operator
can review.

Why a separate file rather than mixing into ``live.json``: refusals
should never disappear from the audit trail through routine state
mutation. Keeping them in a dedicated file means accidentally
clobbering ``live.json`` doesn't lose the safety record.
"""

import threading
from datetime import datetime, timezone

from state_store import StateStore

_LOCK = threading.Lock()

# Persistence routes through StateStore (slice 2 of P3/9). Two aux
# files: ``refusal_log`` (the entry list) and ``refusal_log_alerted``
# (the marker dict). Tests monkeypatch ``_store`` for isolation;
# see ``_test_state_isolation.py`` and the per-test fixtures.
_LOG_NAME = "refusal_log"
_ALERTED_NAME = "refusal_log_alerted"
_store = StateStore()


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def record_refusal(chat_id: int, message_id: int,
                   timestamp: str | None = None) -> None:
    """Append a refusal entry to the on-disk log.

    Called from ``safe_delete.perform_guarded_delete`` whenever the
    registry refuses a delete. ``timestamp`` defaults to "now (UTC)".
    """
    entry = {
        "timestamp": timestamp or _now_iso(),
        "chat_id": chat_id,
        "message_id": message_id,
    }
    with _LOCK:
        existing = _store.load_aux(_LOG_NAME, default=[])
        if not isinstance(existing, list):
            existing = []
        existing.append(entry)
        _store.save_aux(_LOG_NAME, existing)


def get_unalerted_refusals() -> list:
    """Return the refusal entries newer than the alerted marker.

    Used by ``scripts/refusal_alert.py`` to produce the body of a
    Telegram alert. Empty list means no new refusals since last
    alert was sent.
    """
    with _LOCK:
        all_entries = _store.load_aux(_LOG_NAME, default=[])
        if not isinstance(all_entries, list):
            all_entries = []
        marker_data = _store.load_aux(_ALERTED_NAME, default={})
        if not isinstance(marker_data, dict):
            marker_data = {}
        marker = marker_data.get("alerted_through", "")
    if not marker:
        return all_entries
    return [e for e in all_entries if e.get("timestamp", "") > marker]


def mark_alerted(through_timestamp: str | None = None) -> None:
    """Update the alerted marker to ``through_timestamp`` (or now).

    Called by the alert script after a Telegram alert is successfully
    posted. Future calls to ``get_unalerted_refusals`` will exclude
    entries with timestamps <= this marker.
    """
    ts = through_timestamp or _now_iso()
    with _LOCK:
        _store.save_aux(_ALERTED_NAME, {"alerted_through": ts})


def reset_for_test() -> None:
    """Test helper — wipe the on-disk log and marker.

    Tests that exercise refusal logging should monkeypatch ``_store``
    to a tmp-rooted StateStore before calling this, so production
    state is not touched.
    """
    with _LOCK:
        _store.delete_aux(_LOG_NAME)
        _store.delete_aux(_ALERTED_NAME)
