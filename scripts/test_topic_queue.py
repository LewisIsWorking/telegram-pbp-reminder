"""Tests for commands/topic_queue_format.py and scheduled/topic_queue_poster.py."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


# ── topic_queue_format ──────────────────────────────────────────────────────

class TestBuildTopicFingerprint:
    def test_empty_list(self):
        from commands.topic_queue_format import build_topic_fingerprint
        assert build_topic_fingerprint([]) == "empty"

    def test_single_entry(self):
        from commands.topic_queue_format import build_topic_fingerprint
        assert build_topic_fingerprint([{"time": "2026-04-06 10:00:00"}]) == "2026-04-06 10:00:00"

    def test_multiple_entries(self):
        from commands.topic_queue_format import build_topic_fingerprint
        entries = [{"time": "2026-04-05 09:00:00"}, {"time": "2026-04-06 10:00:00"}]
        assert build_topic_fingerprint(entries) == "2026-04-05 09:00:00|2026-04-06 10:00:00"


class TestEntryHours:
    _NOW = datetime(2026, 4, 6, 13, 0, 0, tzinfo=timezone.utc)

    def test_valid_time(self):
        from commands.topic_queue_format import _entry_hours
        assert abs(_entry_hours({"time": "2026-04-06 11:00:00"}, self._NOW) - 2.0) < 0.01

    def test_missing_time_key(self):
        from commands.topic_queue_format import _entry_hours
        assert _entry_hours({}, self._NOW) == 0.0

    def test_invalid_time_format(self):
        from commands.topic_queue_format import _entry_hours
        assert _entry_hours({"time": "not-a-date"}, self._NOW) == 0.0


class TestFormatTopicQueue:
    _NOW = datetime(2026, 4, 6, 13, 0, 0, tzinfo=timezone.utc)

    def _e(self, name="A", t="2026-04-06 12:00:00", preview="text", link=""):
        return {"name": name, "time": t, "preview": preview, "link": link}

    def test_header_shows_count(self):
        from commands.topic_queue_format import format_topic_queue
        result = format_topic_queue([self._e()], self._NOW)
        assert "📋 Unreplied: 1" in result

    def test_entry_with_link(self):
        from commands.topic_queue_format import format_topic_queue
        e = self._e(link="https://t.me/Path_Wars/100/42")
        result = format_topic_queue([e], self._NOW)
        assert "🔗 https://t.me/Path_Wars/100/42" in result

    def test_entry_without_link(self):
        from commands.topic_queue_format import format_topic_queue
        result = format_topic_queue([self._e()], self._NOW)
        assert "🔗" not in result

    def test_multiple_entries_numbered(self):
        from commands.topic_queue_format import format_topic_queue
        entries = [self._e("Alice"), self._e("Bob", "2026-04-05 09:00:00")]
        result = format_topic_queue(entries, self._NOW)
        assert "📋 Unreplied: 2" in result and "01" in result and "02" in result

    def test_missing_time_falls_back_to_new_icon(self):
        from commands.topic_queue_format import format_topic_queue
        result = format_topic_queue([{"name": "C", "preview": "x", "link": ""}], self._NOW)
        assert "C" in result and "🆕" in result

    def test_age_legend_present(self):
        from commands.topic_queue_format import format_topic_queue
        result = format_topic_queue([self._e()], self._NOW)
        assert "Age:" in result and "🆕<1h" in result


# ── topic_queue_poster — helpers ────────────────────────────────────────────

_CFG = {
    "group_id": -1001234567890,
    "topic_pairs": [
        {"name": "Riddleport", "pbp_topic_ids": [40585], "chat_topic_id": 200, "code": "C00"},
        {"name": "Kibwe",      "pbp_topic_ids": [40585, 137075], "chat_topic_id": 201,
         "code": "C06", "group_id": -1001234567890},
    ],
}
_NOW = datetime(2026, 4, 6, 13, 0, 0, tzinfo=timezone.utc)
_ENTRIES = [{"name": "Alice", "time": "2026-04-06 10:00:00",
             "preview": "hi", "link": "", "thread_id": "40585"}]


class TestGroupIdFor:
    def test_falls_back_to_global(self):
        from scheduled.topic_queue_poster import _group_id_for
        assert _group_id_for(_CFG, "40585") == -1001234567890

    def test_uses_pair_group_id(self):
        from scheduled.topic_queue_poster import _group_id_for
        cfg = {"group_id": -999, "topic_pairs": [
            {"name": "X", "pbp_topic_ids": [100], "chat_topic_id": 200,
             "code": "CX", "group_id": -1001234567890},
        ]}
        assert _group_id_for(cfg, "100") == -1001234567890


class TestMigrateLegacy:
    def test_deletes_old_msg_id(self):
        from scheduled.topic_queue_poster import _migrate_legacy
        cq = {"topic_msg_id": 7777, "topic_fingerprint": "fp"}
        with patch("scheduled.topic_queue_poster.tg") as mock_tg:
            _migrate_legacy(cq, -100)
            mock_tg.delete_message.assert_called_once_with(-100, 7777)
            assert cq["topic_msg_id"] is None
            assert cq["topic_fingerprint"] == ""

    def test_no_op_when_none(self):
        from scheduled.topic_queue_poster import _migrate_legacy
        cq = {"topic_msg_id": None}
        with patch("scheduled.topic_queue_poster.tg") as mock_tg:
            _migrate_legacy(cq, -100)
            mock_tg.delete_message.assert_not_called()


class TestPostThreadQueue:
    def test_new_post(self):
        from scheduled.topic_queue_poster import _post_thread_queue
        slot = {"msg_id": None, "fingerprint": ""}
        with patch("scheduled.topic_queue_poster.tg") as mock_tg:
            mock_tg.send_message_id.return_value = 9999
            _post_thread_queue(-100, "40585", slot, _ENTRIES, _NOW)
            mock_tg.send_message_id.assert_called_once()
            mock_tg.pin_message.assert_called_once_with(-100, 9999, disable_notification=False)
            assert slot["msg_id"] == 9999

    def test_skip_when_unchanged(self):
        from scheduled.topic_queue_poster import _post_thread_queue
        slot = {"msg_id": 8888, "fingerprint": "2026-04-06 10:00:00"}
        with patch("scheduled.topic_queue_poster.tg") as mock_tg:
            _post_thread_queue(-100, "40585", slot, _ENTRIES, _NOW)
            mock_tg.send_message_id.assert_not_called()

    def test_update_deletes_old(self):
        from scheduled.topic_queue_poster import _post_thread_queue
        slot = {"msg_id": 7777, "fingerprint": "stale"}
        with patch("scheduled.topic_queue_poster.tg") as mock_tg:
            mock_tg.send_message_id.return_value = 9999
            _post_thread_queue(-100, "40585", slot, _ENTRIES, _NOW)
            mock_tg.delete_message.assert_called_once_with(-100, 7777)
            assert slot["msg_id"] == 9999

    def test_no_state_update_when_send_fails(self):
        from scheduled.topic_queue_poster import _post_thread_queue
        slot = {"msg_id": None, "fingerprint": ""}
        with patch("scheduled.topic_queue_poster.tg") as mock_tg:
            mock_tg.send_message_id.return_value = None
            _post_thread_queue(-100, "40585", slot, _ENTRIES, _NOW)
            mock_tg.pin_message.assert_not_called()
            assert slot["msg_id"] is None


class TestClearThreadQueue:
    def test_clears_with_msg(self):
        from scheduled.topic_queue_poster import _clear_thread_queue
        slot = {"msg_id": 7777, "fingerprint": "fp"}

