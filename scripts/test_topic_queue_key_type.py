"""Thread-id key type must not orphan the previous queue post (2026-08-10).

The C05 Grand Explorers orphan: three "Unreplied:" posts (04/08, 06/08,
09/08) all survived in the topic instead of each replacing the last.

Root cause — a type mismatch, not a logic error:

``parsing.message.parse_message`` returns Telegram's raw
``message_thread_id``, which is an **int**. That int is stored verbatim
on every queue entry by ``dispatch.tracking``. ``_threads_from_scanned``
reads it back and uses it as the key into ``cq["topic_queues"]``.

But ``topic_queues`` is persisted as JSON, and **JSON object keys are
always strings**. So on the next run::

    queues == {"51357": {"msg_ids": [100], ...}}   # loaded from disk
    queues.setdefault(51357, empty_slot())         # int key -> MISS

The lookup misses, a fresh empty slot is handed to
``_post_thread_queue``, ``existing.is_empty`` is True, and the previous
batch is never deleted. Worse, the save then serialises the int key back
to ``"51357"``, overwriting the real slot and losing those message IDs
permanently — so ``pending_delete`` never sees them either and the retry
sweep (L28) cannot help.

This is invisible to the pre-existing suite because every test passes
``thread_id`` as a string (see test_topic_queue_retry.py), which is the
one type production never supplies.

Guard: entries carrying an int thread_id must resolve to the SAME slot
as the string-keyed state loaded from JSON.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

_NOW = datetime(2026, 8, 10, 13, 0, 0, tzinfo=timezone.utc)
_CFG = {"group_id": -1001234567890,
        "topic_pairs": [{"name": "GE", "pbp_topic_ids": [51357],
                         "chat_topic_id": 200, "code": "C05"}]}


def _entry(tid):
    return {"name": "Buffet", "time": "2026-08-09 18:40:00",
            "preview": "hi", "link": "", "thread_id": tid}


class TestThreadIdKeyNormalisation:
    """``_threads_from_scanned`` must emit string keys."""

    def test_int_thread_id_becomes_string_key(self):
        from scheduled.topic_queue_poster import _threads_from_scanned
        scanned = {"51357": {"entries": [_entry(51357)]}}
        result = _threads_from_scanned(scanned)
        assert list(result.keys()) == ["51357"], (
            "int thread_id must normalise to a str key, otherwise it can "
            "never match the JSON-loaded topic_queues slot")
        assert all(isinstance(k, str) for k in result)

    def test_int_and_str_thread_ids_collapse_to_one_slot(self):
        """A campaign whose entries mix int and str must not split."""
        from scheduled.topic_queue_poster import _threads_from_scanned
        scanned = {"51357": {"entries": [_entry(51357), _entry("51357")]}}
        result = _threads_from_scanned(scanned)
        assert len(result) == 1, "int and str thread_id must share a slot"
        assert len(result["51357"][1]) == 2, "both entries land in it"

    def test_missing_thread_id_still_falls_back_to_pid(self):
        from scheduled.topic_queue_poster import _threads_from_scanned
        scanned = {"51357": {"entries": [{"name": "A", "time": "t",
                                          "preview": "p", "link": ""}]}}
        result = _threads_from_scanned(scanned)
        assert list(result.keys()) == ["51357"]


class TestPreviousBatchIsDeleted:
    """The end-to-end symptom: the old post must actually be deleted."""

    def test_int_keyed_entry_deletes_the_previous_post(self, tg_mock):
        """Reproduces the C05 orphan.

        State on disk has the slot under the string key (as JSON forces).
        The incoming entry carries an int thread_id. The previous message
        MUST still be deleted.
        """
        from scheduled.topic_queue_poster import (_threads_from_scanned,
                                                  _post_thread_queue)
        queues = {"51357": {"msg_ids": [170098], "fingerprint": "stale"}}
        threads = _threads_from_scanned(
            {"51357": {"entries": [_entry(51357)]}})
        tid = next(iter(threads))
        slot = queues.setdefault(tid, {"msg_ids": [], "fingerprint": ""})

        tg_mock.send_message_id.return_value = 170500
        tg_mock.delete_message.return_value = True
        _post_thread_queue(-100, tid, slot, threads[tid][1], _NOW)

        deleted = [c.args[1] for c in tg_mock.delete_message.call_args_list]
        assert 170098 in deleted, (
            "the previous Unreplied post was orphaned — this is the C05 bug")
        assert slot["msg_ids"] == [170500]
        assert len(queues) == 1, "must not create a second, int-keyed slot"


class TestExistingCorruptedStateSelfHeals:
    """State already holding int keys (from the buggy runs) must recover."""

    def test_int_keyed_slot_is_migrated_to_str(self):
        from scheduled.topic_queue_poster import _normalise_queue_keys
        queues = {51357: {"msg_ids": [170098], "fingerprint": "a"}}
        _normalise_queue_keys(queues)
        assert list(queues.keys()) == ["51357"]
        assert queues["51357"]["msg_ids"] == [170098]

    def test_duplicate_int_and_str_keys_merge_without_losing_ids(self):
        """The buggy save produced BOTH keys. Neither batch may be lost."""
        from scheduled.topic_queue_poster import _normalise_queue_keys
        queues = {"51357": {"msg_ids": [170098], "fingerprint": "old"},
                  51357: {"msg_ids": [170500], "fingerprint": "new"}}
        _normalise_queue_keys(queues)
        assert list(queues.keys()) == ["51357"]
        slot = queues["51357"]
        # The newer (int-keyed) batch stays live; the stranded string-keyed
        # ids are parked for the retry sweep rather than forgotten.
        assert slot["msg_ids"] == [170500]
        assert 170098 in slot.get("pending_delete", []), (
            "the stranded batch must be queued for deletion, not dropped")

    def test_already_clean_state_is_untouched(self):
        from scheduled.topic_queue_poster import _normalise_queue_keys
        queues = {"51357": {"msg_ids": [1], "fingerprint": "f"}}
        before = {k: dict(v) for k, v in queues.items()}
        _normalise_queue_keys(queues)
        assert queues == before
