"""Carry-forward-and-retry for per-topic queue deletes (L28, 2026-05-28).

The C01 orphan: a per-topic queue's old message wasn't deleted even
after new messages arrived and a new queue was posted. Root cause —
``_post_thread_queue`` logged a failed delete and then overwrote the
slot with only the new message, abandoning the failed ID forever. The
bot is a group admin (no 48h delete limit on its own messages), so a
retry always eventually wins; the fix parks failed IDs in
``pending_delete`` and re-attempts them every run until they clear.
"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

_NOW = datetime(2026, 5, 28, 13, 0, 0, tzinfo=timezone.utc)
_ENTRIES = [{"name": "Alice", "time": "2026-05-28 10:00:00",
             "preview": "hi", "link": "", "thread_id": "40585"}]
_CFG = {"group_id": -1001234567890,
        "topic_pairs": [{"name": "DF", "pbp_topic_ids": [40585],
                         "chat_topic_id": 200, "code": "C01"}]}


class TestPostThreadCarryForward:
    def test_failed_delete_parked_not_abandoned(self, tg_mock):
        """A failed delete of the previous message is parked in
        pending_delete, and the new queue is still posted/tracked."""
        from scheduled.topic_queue_poster import _post_thread_queue
        slot = {"msg_ids": [156513], "fingerprint": "stale"}
        tg_mock.send_message_id.return_value = 156550
        tg_mock.delete_message.return_value = False  # delete fails
        _post_thread_queue(-100, "40585", slot, _ENTRIES, _NOW)
        # Old ID carried forward for retry; new message tracked.
        assert slot["pending_delete"] == [156513]
        assert slot["msg_ids"] == [156550]

    def test_successful_delete_leaves_no_pending(self, tg_mock):
        from scheduled.topic_queue_poster import _post_thread_queue
        slot = {"msg_ids": [156513], "fingerprint": "stale"}
        tg_mock.send_message_id.return_value = 156550
        tg_mock.delete_message.return_value = True
        _post_thread_queue(-100, "40585", slot, _ENTRIES, _NOW)
        assert slot.get("pending_delete", []) == []
        assert slot["msg_ids"] == [156550]

    def test_pending_retried_even_when_content_unchanged(self, tg_mock):
        """Unchanged queue (skip path) still sweeps lingering orphans."""
        from scheduled.topic_queue_poster import _post_thread_queue
        # fingerprint matches the single entry's time → would skip the
        # repost, but a parked orphan must still be retried.
        slot = {"msg_ids": [156550], "fingerprint": "2026-05-28 10:00:00",
                "pending_delete": [156513]}
        tg_mock.delete_message.return_value = True
        _post_thread_queue(-100, "40585", slot, _ENTRIES, _NOW)
        # No re-post (unchanged) but the orphan got cleaned up.
        tg_mock.send_message_id.assert_not_called()
        assert slot["pending_delete"] == []

    def test_orphan_clears_on_a_later_run(self, tg_mock):
        """End-to-end: delete fails on run 1 (parked), succeeds on run 2."""
        from scheduled.topic_queue_poster import _post_thread_queue
        slot = {"msg_ids": [156513], "fingerprint": "stale"}
        # Run 1: repost, old delete fails → parked.
        tg_mock.send_message_id.return_value = 156550
        tg_mock.delete_message.return_value = False
        _post_thread_queue(-100, "40585", slot, _ENTRIES, _NOW)
        assert slot["pending_delete"] == [156513]
        # Run 2: content unchanged, delete now succeeds → orphan gone.
        tg_mock.delete_message.return_value = True
        _post_thread_queue(-100, "40585", slot, _ENTRIES, _NOW)
        assert slot["pending_delete"] == []


class TestClearThreadCarryForward:
    def test_failed_delete_parked_on_clear(self, tg_mock):
        from scheduled.topic_queue_poster import _clear_thread_queue
        slot = {"msg_ids": [156513], "fingerprint": "fp"}
        tg_mock.send_message_id.return_value = 8888  # caught-up msg
        tg_mock.delete_message.return_value = False  # queue delete fails
        _clear_thread_queue(-100, "40585", slot,
                            pid="40585", state=None, config={})
        assert slot["pending_delete"] == [156513]
        assert slot["msg_ids"] == []  # current batch cleared
        assert slot["caught_up_msg_id"] == 8888

    def test_clear_preserves_existing_pending(self, tg_mock):
        from scheduled.topic_queue_poster import _clear_thread_queue
        slot = {"msg_ids": [156550], "fingerprint": "fp",
                "pending_delete": [156513]}
        tg_mock.send_message_id.return_value = 8888
        # Old orphan deletes now; current batch delete also succeeds.
        tg_mock.delete_message.return_value = True
        _clear_thread_queue(-100, "40585", slot,
                            pid="40585", state=None, config={})
        assert slot["pending_delete"] == []


class TestPostTopicQueuesZombieSweep:
    def test_inactive_thread_with_only_pending_is_swept(self, tg_mock):
        """A thread with no active entries and no current batch, but a
        parked orphan, still gets processed so the orphan is retried."""
        from scheduled.topic_queue_poster import post_topic_queues
        cq = {"pid": "40585", "topic_msg_id": None, "topic_fingerprint": "",
              "topic_queues": {"40585": {"msg_ids": [], "fingerprint": "",
                                         "pending_delete": [156513]}}}
        from unittest.mock import patch
        with patch("scheduled.topic_queue_poster._all_pids", return_value=["40585"]), \
             patch("scheduled.topic_queue_poster._load", return_value=cq), \
             patch("scheduled.topic_queue_poster._save"):
            tg_mock.delete_message.return_value = True
            post_topic_queues(_CFG, {}, _NOW)
            tg_mock.delete_message.assert_any_call(-1001234567890, 156513)
            assert cq["topic_queues"]["40585"]["pending_delete"] == []
