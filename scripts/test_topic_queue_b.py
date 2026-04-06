"""Tests for telegram.delete_message and queue_reminder integration."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timezone
from unittest.mock import patch


_CFG = {
    "group_id": -1001234567890,
    "topic_pairs": [
        {"name": "Riddleport", "pbp_topic_ids": [40585], "chat_topic_id": 200, "code": "C00"},
        {"name": "Kibwe",      "pbp_topic_ids": [66154], "chat_topic_id": 201, "code": "C06",
         "group_id": -1001234567890},
    ],
}
_NOW = datetime(2026, 4, 6, 13, 0, 0, tzinfo=timezone.utc)
_ENTRIES = [{"name": "Alice", "time": "2026-04-06 10:00:00", "preview": "hi", "link": ""}]


class TestPostTopicQueuesIntegration:
    def test_posts_active_and_clears_inactive(self):
        from scheduled.topic_queue_poster import post_topic_queues
        scanned = {"40585": {"entries": _ENTRIES, "campaign": "Riddleport", "code": "C00"}}
        cq_active   = {"pid": "40585", "topic_msg_id": None,  "topic_fingerprint": ""}
        cq_inactive = {"pid": "66154", "topic_msg_id": 1111,  "topic_fingerprint": "old"}

        with patch("scheduled.topic_queue_poster._all_pids",
                   return_value=["40585", "66154"]), \
             patch("scheduled.topic_queue_poster._load",
                   side_effect=lambda pid: cq_active if pid == "40585" else cq_inactive), \
             patch("scheduled.topic_queue_poster._save"), \
             patch("scheduled.topic_queue_poster.tg") as mock_tg:
            mock_tg.send_message_id.return_value = 9999
            post_topic_queues(_CFG, scanned, _NOW)
            mock_tg.send_message_id.assert_called_once()
            mock_tg.send_message.assert_called_once()
            mock_tg.delete_message.assert_called()

    def test_no_op_when_no_topic_msg_ids(self):
        from scheduled.topic_queue_poster import post_topic_queues
        cq = {"pid": "40585", "topic_msg_id": None, "topic_fingerprint": ""}

        with patch("scheduled.topic_queue_poster._all_pids", return_value=["40585"]), \
             patch("scheduled.topic_queue_poster._load", return_value=cq), \
             patch("scheduled.topic_queue_poster._save") as mock_save, \
             patch("scheduled.topic_queue_poster.tg") as mock_tg:
            post_topic_queues(_CFG, {}, _NOW)
            mock_tg.send_message.assert_not_called()
            mock_save.assert_not_called()


# ── telegram.delete_message ─────────────────────────────────────────────────

class TestDeleteMessage:
    def test_mock_available_and_callable(self):
        import telegram as tg_mod
        assert hasattr(tg_mod, "delete_message"), "delete_message not registered in conftest mock"
        result = tg_mod.delete_message(-100, 42)
        assert result is True


# ── queue_reminder now calls post_topic_queues ──────────────────────────────

class TestQueueReminderCallsTopicQueues:
    def _base_config(self):
        return {
            "group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
            "queue_daily_hours": [], "topic_pairs": [
                {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe", "gm_user_ids": [999]},
            ],
        }

    def _base_state(self):
        return {"last_queue_fingerprint": "OLD", "queue_post_count": 0,
                "last_queue_pin_id": None, "last_queue_daily_slots": []}

    def test_called_with_scanned_when_entries_exist(self):
        from scheduled.queue_reminder import post_queue_reminder
        now = datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc)
        entries = [{"name": "A", "time": "2026-04-06 08:00:00",
                    "preview": "hi", "link": "", "message_id": "1"}]
        scanned = {"100": {"campaign": "Kibwe", "code": "C00", "entries": entries}}
        with patch("scheduled.queue_reminder.scan_transcripts", return_value=scanned), \
             patch("scheduled.queue_reminder.post_topic_queues") as mock_ptq:
            post_queue_reminder(self._base_config(), self._base_state(), now=now)
            mock_ptq.assert_called_once_with(self._base_config(), scanned, now)

    def test_called_when_queue_empty(self):
        from scheduled.queue_reminder import post_queue_reminder
        now = datetime(2026, 4, 6, 10, tzinfo=timezone.utc)
        with patch("scheduled.queue_reminder.scan_transcripts", return_value={}), \
             patch("scheduled.queue_reminder.post_topic_queues") as mock_ptq:
            post_queue_reminder(self._base_config(), self._base_state(), now=now)
            mock_ptq.assert_called_once_with(self._base_config(), {}, now)
