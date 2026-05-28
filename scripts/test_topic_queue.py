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

    def _full(self, entries, now=None):
        from commands.topic_queue_format import format_topic_queue
        return "\n".join(format_topic_queue(entries, now or self._NOW))

    def test_header_shows_count(self):
        assert "📋 Unreplied: 1" in self._full([self._e()])

    def test_entry_with_link(self):
        e = self._e(link="https://t.me/Path_Wars/100/42")
        out = self._full([e])
        assert "https://t.me/Path_Wars/100/42" in out
        assert "🔗" not in out  # slim format dropped the prefix

    def test_entry_without_link(self):
        # Slim format never had 🔗; check that link section is omitted entirely.
        out = self._full([self._e()])
        assert "t.me/" not in out

    def test_multiple_entries_no_numbered_prefix(self):
        # Slim format drops 01/02 numbering — ↗ prefix is the cue.
        entries = [self._e("Alice"), self._e("Bob", "2026-04-05 09:00:00")]
        result = self._full(entries)
        assert "📋 Unreplied: 2" in result
        assert "↗ Alice" in result and "↗ Bob" in result
        assert "01" not in result and "02" not in result

    def test_missing_time_falls_back_to_new_icon(self):
        result = self._full([{"name": "C", "preview": "x", "link": ""}])
        assert "C" in result and "🆕" in result

    def test_age_legend_removed(self):
        # Lewis 2026-05-19: legend was the main meta-brick (L27).
        result = self._full([self._e()])
        assert "Age:" not in result
        assert "🆕<1h" not in result

    def test_returns_list(self):
        from commands.topic_queue_format import format_topic_queue
        result = format_topic_queue([self._e()], self._NOW)
        assert isinstance(result, list) and len(result) >= 1

    def test_splits_long_message(self):
        from commands.topic_queue_format import format_topic_queue
        # Slim per-line is ~50 chars; need many entries to overflow
        # _MAX_MSG (3900). 500 is comfortable headroom.
        entry = self._e(link="https://t.me/Path_Wars/100/42",
                        name="Reasonably_Long_Player_Name")
        result = format_topic_queue([entry] * 500, self._NOW)
        assert len(result) > 1
        assert all(len(chunk) <= 4096 for chunk in result)


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
    def test_new_post(self, tg_mock):
        from scheduled.topic_queue_poster import _post_thread_queue
        slot = {"msg_ids": [], "fingerprint": ""}
        tg_mock.send_message_id.return_value = 9999
        _post_thread_queue(-100, "40585", slot, _ENTRIES, _NOW)
        assert tg_mock.send_message_id.call_count >= 1  # ≥1 chunks
        tg_mock.pin_message.assert_called_once_with(-100, 9999, disable_notification=False)
        assert slot["msg_ids"] == [9999]

    def test_skip_when_unchanged(self, tg_mock):
        from scheduled.topic_queue_poster import _post_thread_queue
        # Fresh last_posted_at (1h before _NOW) → unchanged AND within
        # the 48h delete window, so the re-post is safely skipped.
        slot = {"msg_ids": [8888], "fingerprint": "2026-04-06 10:00:00",
                "last_posted_at": "2026-04-06T12:00:00+00:00"}
        _post_thread_queue(-100, "40585", slot, _ENTRIES, _NOW)
        tg_mock.send_message_id.assert_not_called()

    def test_legacy_slot_reposts_to_acquire_timestamp(self, tg_mock):
        """A legacy slot (singular msg_id, no last_posted_at) has unknown
        age. Since we can't confirm the tracked message is still within
        Telegram's 48h delete window, we refuse to skip and re-post once
        — which migrates the slot to the current schema and stamps a
        last_posted_at so future cycles can age-check it. See L28."""
        from scheduled.topic_queue_poster import _post_thread_queue
        slot = {"msg_id": 8888, "fingerprint": "2026-04-06 10:00:00"}
        tg_mock.send_message_id.return_value = 9999
        tg_mock.delete_message.return_value = True
        _post_thread_queue(-100, "40585", slot, _ENTRIES, _NOW)
        tg_mock.send_message_id.assert_called()
        assert slot["msg_ids"] == [9999]
        assert "msg_id" not in slot  # migrated to current schema
        assert slot.get("last_posted_at")  # now age-checkable

    def test_update_deletes_old(self, tg_mock):
        from scheduled.topic_queue_poster import _post_thread_queue
        slot = {"msg_ids": [7777], "fingerprint": "stale"}
        tg_mock.send_message_id.return_value = 9999
        tg_mock.delete_message.return_value = True
        _post_thread_queue(-100, "40585", slot, _ENTRIES, _NOW)
        tg_mock.delete_message.assert_called_once_with(-100, 7777)
        assert slot["msg_ids"] == [9999]

    def test_update_legacy_slot_migrates(self, tg_mock):
        """Legacy slot with singular msg_id is rewritten as msg_ids on update."""
        from scheduled.topic_queue_poster import _post_thread_queue
        slot = {"msg_id": 7777, "fingerprint": "stale"}
        tg_mock.send_message_id.return_value = 9999
        tg_mock.delete_message.return_value = True
        _post_thread_queue(-100, "40585", slot, _ENTRIES, _NOW)
        tg_mock.delete_message.assert_called_once_with(-100, 7777)
        assert slot["msg_ids"] == [9999]
        assert "msg_id" not in slot

    def test_no_state_update_when_send_fails(self, tg_mock):
        from scheduled.topic_queue_poster import _post_thread_queue
        slot = {"msg_ids": [], "fingerprint": ""}
        tg_mock.send_message_id.return_value = None
        _post_thread_queue(-100, "40585", slot, _ENTRIES, _NOW)
        tg_mock.pin_message.assert_not_called()
        assert slot["msg_ids"] == []

