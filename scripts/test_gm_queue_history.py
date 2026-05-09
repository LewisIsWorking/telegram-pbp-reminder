"""Tests for scheduled/gm_queue_history.py — rolling 3-batch retention.

Internal implementation lives in ``posting`` (MessageBatch, QueueHistory,
post_batch). Tests patch the underlying telegram module references in
those packages, since that is where the real Telegram calls now happen.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import patch, MagicMock


class TestMigrateLegacy:
    def test_seeds_history_from_legacy_pin(self):
        from scheduled.gm_queue_history import migrate_legacy
        state = {"last_queue_pin_id": 12345}
        migrate_legacy(state)
        assert state["gm_queue_history"] == [
            {"msg_ids": [12345], "pin_id": 12345},
        ]

    def test_no_op_when_history_already_populated(self):
        from scheduled.gm_queue_history import migrate_legacy
        existing = [{"msg_ids": [1, 2], "pin_id": 1}]
        state = {"last_queue_pin_id": 99, "gm_queue_history": existing}
        migrate_legacy(state)
        assert state["gm_queue_history"] is existing  # unchanged identity

    def test_empty_history_when_no_legacy(self):
        from scheduled.gm_queue_history import migrate_legacy
        state = {"last_queue_pin_id": None}
        migrate_legacy(state)
        assert state["gm_queue_history"] == []


class TestAppendAndEvict:
    """Eviction calls are routed through posting.message_batch.tg.delete_message."""

    def test_first_append(self):
        from scheduled.gm_queue_history import append_and_evict
        state = {"gm_queue_history": []}
        with patch("posting.message_batch.tg") as mock_tg:
            append_and_evict(state, -100, [1001], 1001)
            mock_tg.delete_message.assert_not_called()
            assert state["gm_queue_history"] == [
                {"msg_ids": [1001], "pin_id": 1001},
            ]

    def test_keeps_three_no_eviction(self):
        from scheduled.gm_queue_history import append_and_evict
        state = {"gm_queue_history": []}
        with patch("posting.message_batch.tg") as mock_tg:
            append_and_evict(state, -100, [1], 1)
            append_and_evict(state, -100, [2], 2)
            append_and_evict(state, -100, [3], 3)
            mock_tg.delete_message.assert_not_called()
            assert len(state["gm_queue_history"]) == 3

    def test_fourth_append_evicts_oldest(self):
        from scheduled.gm_queue_history import append_and_evict
        state = {"gm_queue_history": []}
        with patch("posting.message_batch.tg") as mock_tg:
            mock_tg.delete_message.return_value = True
            for i in (1, 2, 3, 4):
                append_and_evict(state, -100, [i * 10], i * 10)
            # Oldest batch (msg_ids=[10]) should be evicted and deleted.
            mock_tg.delete_message.assert_called_once_with(-100, 10)
            assert len(state["gm_queue_history"]) == 3
            assert [b["pin_id"] for b in state["gm_queue_history"]] == [20, 30, 40]

    def test_eviction_deletes_every_id_in_evicted_batch(self):
        """Multi-message evicted batches must delete every message, not just the pin."""
        from scheduled.gm_queue_history import append_and_evict
        state = {"gm_queue_history": [
            {"msg_ids": [100, 101, 102], "pin_id": 100},
            {"msg_ids": [200], "pin_id": 200},
            {"msg_ids": [300], "pin_id": 300},
        ]}
        with patch("posting.message_batch.tg") as mock_tg:
            mock_tg.delete_message.return_value = True
            append_and_evict(state, -100, [400, 401], 400)
            # Every id in the evicted [100,101,102] batch must be deleted.
            assert mock_tg.delete_message.call_count == 3
            deleted = [c[0][1] for c in mock_tg.delete_message.call_args_list]
            assert deleted == [100, 101, 102]
            assert len(state["gm_queue_history"]) == 3

    def test_failed_delete_keeps_batch_for_retry(self):
        """When a delete fails, the batch is retained with the failed IDs."""
        from scheduled.gm_queue_history import append_and_evict
        state = {"gm_queue_history": [
            {"msg_ids": [100, 101], "pin_id": 100},
            {"msg_ids": [200], "pin_id": 200},
            {"msg_ids": [300], "pin_id": 300},
        ]}
        with patch("posting.message_batch.tg") as mock_tg:
            # 100 fails, 101 succeeds → batch retained with [100] only
            mock_tg.delete_message.side_effect = lambda gid, mid: mid != 100
            append_and_evict(state, -100, [400], 400)
            # Eviction was attempted on the oldest batch
            assert mock_tg.delete_message.call_count == 2
            # The retained batch sits at the front with only the failed ID
            assert state["gm_queue_history"][0]["msg_ids"] == [100]
            # And the rest are intact
            assert [b["pin_id"] for b in state["gm_queue_history"]] == [
                100, 200, 300, 400,
            ]

    def test_max_kept_constant_is_three(self):
        from scheduled.gm_queue_history import MAX_KEPT_BATCHES
        assert MAX_KEPT_BATCHES == 3


class TestPostAndPersist:
    """post_and_persist orchestrates send (via posting.sender) + unpin/pin
    (some via posting.sender, unpin-previous via scheduled.gm_queue_history)."""

    def test_sends_and_pins_first(self):
        from scheduled.gm_queue_history import post_and_persist
        state = {"gm_queue_history": [], "last_queue_pin_id": None}
        with patch("posting.sender.tg") as sender_tg, \
             patch("scheduled.gm_queue_history.tg") as gmh_tg:
            sender_tg.send_message_id.side_effect = [501, 502]
            sent, first = post_and_persist(state, -100, 999, ["chunk1", "chunk2"])
            assert sent is True
            assert first == 501
            sender_tg.pin_message.assert_called_once_with(
                -100, 501, disable_notification=False)
            assert state["last_queue_pin_id"] == 501
            assert state["gm_queue_history"] == [
                {"msg_ids": [501, 502], "pin_id": 501},
            ]

    def test_unpins_previous_pin(self):
        from scheduled.gm_queue_history import post_and_persist
        state = {"gm_queue_history": [], "last_queue_pin_id": 999}
        with patch("posting.sender.tg") as sender_tg, \
             patch("scheduled.gm_queue_history.tg") as gmh_tg:
            sender_tg.send_message_id.return_value = 700
            post_and_persist(state, -100, 1, ["only"])
            gmh_tg.unpin_message.assert_called_once_with(-100, 999)

    def test_returns_false_when_send_fails(self):
        from scheduled.gm_queue_history import post_and_persist
        state = {"gm_queue_history": [], "last_queue_pin_id": None}
        with patch("posting.sender.tg") as sender_tg:
            sender_tg.send_message_id.return_value = None
            sent, first = post_and_persist(state, -100, 1, ["chunk"])
            assert sent is False
            assert first is None
            sender_tg.pin_message.assert_not_called()
            assert state["gm_queue_history"] == []

    def test_partial_send_still_pins_first(self):
        """If chunk 2 fails but chunk 1 succeeded, batch is still recorded."""
        from scheduled.gm_queue_history import post_and_persist
        state = {"gm_queue_history": [], "last_queue_pin_id": None}
        with patch("posting.sender.tg") as sender_tg, \
             patch("scheduled.gm_queue_history.tg") as gmh_tg:
            sender_tg.send_message_id.side_effect = [501, None]
            sent, first = post_and_persist(state, -100, 1, ["a", "b"])
            assert sent is True
            assert first == 501
            assert state["gm_queue_history"][0]["msg_ids"] == [501]
