"""Tests for topic_queue_poster — _threads_from_scanned (continued)."""

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
    def test_posts_to_correct_threads(self):
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
             patch("scheduled.topic_queue_poster._save"), \
             patch("scheduled.topic_queue_poster.tg") as mock_tg:
            mock_tg.send_message_id.return_value = 9999
            post_topic_queues(_CFG, scanned, _NOW)
            # Should have sent to both threads
            assert mock_tg.send_message_id.call_count == 2
            sent_threads = {call[0][1] for call in mock_tg.send_message_id.call_args_list}
            assert 40585 in sent_threads
            assert 137075 in sent_threads

    def test_clears_inactive_threads(self):
        from scheduled.topic_queue_poster import post_topic_queues
        cq = {"pid": "40585", "topic_msg_id": None, "topic_fingerprint": "",
              "topic_queues": {"40585": {"msg_id": 1111, "fingerprint": "old"}}}

        with patch("scheduled.topic_queue_poster._all_pids", return_value=["40585"]), \
             patch("scheduled.topic_queue_poster._load", return_value=cq), \
             patch("scheduled.topic_queue_poster._save"), \
             patch("scheduled.topic_queue_poster.tg") as mock_tg:
            post_topic_queues(_CFG, {}, _NOW)
            # Should send caught-up and delete old
            mock_tg.send_message.assert_called_once()
            assert "caught up" in mock_tg.send_message.call_args[0][2].lower()

    def test_no_op_when_no_pins_and_empty(self):
        from scheduled.topic_queue_poster import post_topic_queues
        cq = {"pid": "40585", "topic_msg_id": None, "topic_fingerprint": "",
              "topic_queues": {}}

        with patch("scheduled.topic_queue_poster._all_pids", return_value=["40585"]), \
             patch("scheduled.topic_queue_poster._load", return_value=cq), \
             patch("scheduled.topic_queue_poster._save") as mock_save, \
             patch("scheduled.topic_queue_poster.tg") as mock_tg:
            post_topic_queues(_CFG, {}, _NOW)
            mock_tg.send_message.assert_not_called()
            mock_save.assert_not_called()


class TestDeleteMessage:
    def test_mock_available_and_callable(self):
        import telegram as tg_mod
        assert hasattr(tg_mod, "delete_message")
        assert tg_mod.delete_message(-100, 42) is True
