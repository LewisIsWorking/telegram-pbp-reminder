"""Tests for topic_queue_poster — _threads_from_scanned, _clear_thread_queue, post_topic_queues."""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from datetime import datetime, timezone
from unittest.mock import patch

_NOW = datetime(2026, 4, 6, 13, 0, 0, tzinfo=timezone.utc)
_CFG = {
    "group_id": -1001234567890,
    "topic_pairs": [
        {"name": "Riddleport", "pbp_topic_ids": [40585], "chat_topic_id": 200, "code": "C00"},
        {"name": "Kibwe", "pbp_topic_ids": [40585, 137075], "chat_topic_id": 201,
         "code": "C06", "group_id": -1001234567890},
    ],
}


class TestPostTopicQueuesIntegration:
    def test_posts_to_correct_threads(self, tg_mock):
        """Multi-topic campaign entries go to their own thread, not canonical pid."""
        from scheduled.topic_queue_poster import post_topic_queues
        e_pbp    = {"name": "A", "time": "2026-04-06 10:00:00", "preview": "p",
                    "link": "", "thread_id": "40585"}
        e_combat = {"name": "B", "time": "2026-04-06 11:00:00", "preview": "q",
                    "link": "", "thread_id": "137075"}
        scanned = {"40585": {"entries": [e_pbp, e_combat], "campaign": "Kibwe", "code": "C06"}}
        cq = {"pid": "40585", "topic_msg_id": None, "topic_fingerprint": "",
              "topic_queues": {}}

        with patch("scheduled.topic_queue_poster._all_pids", return_value=["40585"]), \
             patch("scheduled.topic_queue_poster._load", return_value=cq), \
             patch("scheduled.topic_queue_poster._save"):
            tg_mock.send_message_id.return_value = 9999
            post_topic_queues(_CFG, scanned, _NOW)
            # Should have sent to both threads
            assert tg_mock.send_message_id.call_count == 2
            sent_threads = {call[0][1] for call in tg_mock.send_message_id.call_args_list}
            assert 40585 in sent_threads
            assert 137075 in sent_threads

    def test_clears_inactive_threads(self, tg_mock):
        from scheduled.topic_queue_poster import post_topic_queues
        cq = {"pid": "40585", "topic_msg_id": None, "topic_fingerprint": "",
              "topic_queues": {"40585": {"msg_ids": [1111], "fingerprint": "old"}}}

        with patch("scheduled.topic_queue_poster._all_pids", return_value=["40585"]), \
             patch("scheduled.topic_queue_poster._load", return_value=cq), \
             patch("scheduled.topic_queue_poster._save"):
            post_topic_queues(_CFG, {}, _NOW)
            # Should send caught-up (via send_message_id, capturing the id) and delete old
            tg_mock.send_message_id.assert_called_once()
            assert "caught up" in tg_mock.send_message_id.call_args[0][2].lower()

    def test_clears_inactive_threads_legacy_slot(self, tg_mock):
        """Legacy slot with singular msg_id still triggers clear path."""
        from scheduled.topic_queue_poster import post_topic_queues
        cq = {"pid": "40585", "topic_msg_id": None, "topic_fingerprint": "",
              "topic_queues": {"40585": {"msg_id": 1111, "fingerprint": "old"}}}

        with patch("scheduled.topic_queue_poster._all_pids", return_value=["40585"]), \
             patch("scheduled.topic_queue_poster._load", return_value=cq), \
             patch("scheduled.topic_queue_poster._save"):
            post_topic_queues(_CFG, {}, _NOW)
            tg_mock.send_message_id.assert_called_once()
            tg_mock.delete_message.assert_called_once_with(-1001234567890, 1111)

    def test_no_op_when_no_pins_and_empty(self, tg_mock):
        from scheduled.topic_queue_poster import post_topic_queues
        cq = {"pid": "40585", "topic_msg_id": None, "topic_fingerprint": "",
              "topic_queues": {}}

        with patch("scheduled.topic_queue_poster._all_pids", return_value=["40585"]), \
             patch("scheduled.topic_queue_poster._load", return_value=cq), \
             patch("scheduled.topic_queue_poster._save") as mock_save:
            post_topic_queues(_CFG, {}, _NOW)
            tg_mock.send_message_id.assert_not_called()
            mock_save.assert_not_called()


class TestClearThreadQueue:
    def test_clears_with_msg(self, tg_mock):
        from scheduled.topic_queue_poster import _clear_thread_queue
        slot = {"msg_ids": [7777], "fingerprint": "fp"}
        tg_mock.send_message_id.return_value = 8888
        _clear_thread_queue(-100, "40585", slot)
        # Caught-up notice is sent via send_message_id so we can capture
        # its id for deletion on the next cycle.
        tg_mock.send_message_id.assert_called_once()
        assert "caught up" in tg_mock.send_message_id.call_args[0][2].lower()
        tg_mock.unpin_message.assert_called_once_with(-100, 7777)
        tg_mock.delete_message.assert_called_once_with(-100, 7777)
        assert slot["msg_ids"] == []
        assert slot["fingerprint"] == ""
        # The freshly-posted caught-up message id is now tracked on the slot.
        assert slot["caught_up_msg_id"] == 8888

    def test_clears_multi_message_batch(self, tg_mock):
        """Multi-message batch deletes every tracked id, unpins only the first."""
        from scheduled.topic_queue_poster import _clear_thread_queue
        slot = {"msg_ids": [7777, 7778, 7779], "fingerprint": "fp"}
        tg_mock.send_message_id.return_value = 8888
        _clear_thread_queue(-100, "40585", slot)
        tg_mock.unpin_message.assert_called_once_with(-100, 7777)
        assert tg_mock.delete_message.call_count == 3
        deleted = [c[0][1] for c in tg_mock.delete_message.call_args_list]
        assert deleted == [7777, 7778, 7779]
        assert slot["msg_ids"] == []

    def test_clears_legacy_slot(self, tg_mock):
        """Legacy slot is migrated to current schema after clear."""
        from scheduled.topic_queue_poster import _clear_thread_queue
        slot = {"msg_id": 7777, "fingerprint": "fp"}
        tg_mock.send_message_id.return_value = 8888
        _clear_thread_queue(-100, "40585", slot)
        tg_mock.delete_message.assert_called_once_with(-100, 7777)
        assert slot["msg_ids"] == []
        assert "msg_id" not in slot

    def test_clear_deletes_previous_caught_up_before_sending_new(self, tg_mock):
        """The 'All caught up!' message itself was previously fire-and-forget,
        so multiple cycles left a permanent trail of them in the topic.
        Now each clear deletes the previous notice before posting its own.
        """
        from scheduled.topic_queue_poster import _clear_thread_queue
        slot = {"msg_ids": [7777], "fingerprint": "fp",
                "caught_up_msg_id": 5555}
        tg_mock.send_message_id.return_value = 8888
        _clear_thread_queue(-100, "40585", slot)
        # Both the queue message and the prior caught-up notice are deleted.
        deleted = [c[0][1] for c in tg_mock.delete_message.call_args_list]
        assert 5555 in deleted
        assert 7777 in deleted
        # And the new caught-up notice's id replaces the old one on the slot.
        assert slot["caught_up_msg_id"] == 8888


class TestPostThreadMultiMessage:
    """The original bug: when a topic queue posts as multiple messages,
    every old message must be deleted on update — not just the first."""

    def test_update_deletes_all_old_messages(self, tg_mock):
        from scheduled.topic_queue_poster import _post_thread_queue
        slot = {"msg_ids": [7777, 7778, 7779], "fingerprint": "stale"}
        entries = [{"name": "A", "time": "2026-04-06 10:00:00",
                    "preview": "p", "link": "", "thread_id": "40585"}]
        tg_mock.send_message_id.return_value = 9999
        tg_mock.delete_message.return_value = True
        _post_thread_queue(-100, "40585", slot, entries, _NOW)
        assert tg_mock.delete_message.call_count == 3
        deleted = [c[0][1] for c in tg_mock.delete_message.call_args_list]
        assert deleted == [7777, 7778, 7779]
        assert slot["msg_ids"] == [9999]


class TestPostDeletesLingeringCaughtUp:
    """Caught-up notices left from a prior clear cycle must be removed
    before a fresh queue post — otherwise the topic stacks them up."""

    def test_caught_up_id_deleted_and_reset_on_post(self, tg_mock):
        from scheduled.topic_queue_poster import _post_thread_queue
        slot = {"msg_ids": [], "fingerprint": "",
                "caught_up_msg_id": 5555}
        entries = [{"name": "A", "time": "2026-04-06 10:00:00",
                    "preview": "p", "link": "", "thread_id": "40585"}]
        tg_mock.send_message_id.return_value = 9999
        tg_mock.delete_message.return_value = True
        _post_thread_queue(-100, "40585", slot, entries, _NOW)
        tg_mock.delete_message.assert_any_call(-100, 5555)
        assert slot["caught_up_msg_id"] is None


class TestDeleteMessage:
    def test_mock_available_and_callable(self):
        import telegram as tg_mod
        assert hasattr(tg_mod, "delete_message")
        assert tg_mod.delete_message(-100, 42) is True
