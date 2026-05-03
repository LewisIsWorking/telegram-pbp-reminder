"""Tests for the v4.45.0 idempotency fix and all-time-total helper.

Covers:
- queue_io.mark_replied returns bool and gates reply_log on dedup
- commands.queue_stats.record_reply defensive same-msg_id dedup
- commands.queue_stats.get_alltime_clears reads per-campaign reply_log
- dispatch.gm_reply.record_gm_reply end-to-end behaviour
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timezone
from unittest.mock import patch


# ── queue_io.mark_replied ────────────────────────────────────────────────

class TestMarkRepliedReturnBool:
    def test_returns_true_on_new(self, tmp_path, monkeypatch):
        from commands import queue_io
        monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
        log_entry = {"msg_id": "42", "via": "reply"}
        result = queue_io.mark_replied("100", "msg:42",
                                       "2026-03-01 10:00:00", log_entry)
        assert result is True
        cq = queue_io.load("100")
        assert cq["reply_log"] == [log_entry]
        assert "msg:42" in cq["replied"]

    def test_returns_false_on_duplicate(self, tmp_path, monkeypatch):
        from commands import queue_io
        monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
        log_entry = {"msg_id": "42", "via": "reply"}
        queue_io.mark_replied("100", "msg:42", None, log_entry)
        # Second call with same mid_key — must dedup.
        result = queue_io.mark_replied("100", "msg:42", None,
                                       {"msg_id": "42", "via": "reply",
                                        "extra": "would-be-dup"})
        assert result is False
        cq = queue_io.load("100")
        assert len(cq["reply_log"]) == 1  # not duplicated
        assert cq["reply_log"][0] == log_entry  # original preserved

    def test_empty_mid_key_returns_false_no_append(self, tmp_path, monkeypatch):
        from commands import queue_io
        monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
        result = queue_io.mark_replied("100", "", None, {"msg_id": "0"})
        assert result is False
        cq = queue_io.load("100")
        assert cq["reply_log"] == []


# ── queue_stats.record_reply defensive dedup ─────────────────────────────

class TestRecordReplyDefensiveDedup:
    def test_appends_when_archive_empty(self):
        from commands.queue_stats import record_reply
        state = {}
        result = record_reply("100", state, "preview", "Alice",
                              now=datetime(2026, 5, 3, tzinfo=timezone.utc),
                              msg_id="42")
        assert result is True
        assert len(state["queue_archive"]) == 1
        assert len(state["queue_history"]["100"]) == 1

    def test_skips_when_same_pid_and_msg_id_at_tail(self):
        from commands.queue_stats import record_reply
        state = {"queue_archive": [
            {"pid": "100", "msg_id": "42", "time": "x", "player": "A", "preview": ""}
        ], "queue_history": {"100": ["x"]}}
        result = record_reply("100", state, "p", "A",
                              now=datetime(2026, 5, 3, tzinfo=timezone.utc),
                              msg_id="42")
        assert result is False
        assert len(state["queue_archive"]) == 1  # unchanged
        assert len(state["queue_history"]["100"]) == 1

    def test_appends_when_msg_id_differs(self):
        from commands.queue_stats import record_reply
        state = {"queue_archive": [
            {"pid": "100", "msg_id": "42", "time": "x", "player": "A", "preview": ""}
        ], "queue_history": {"100": ["x"]}}
        result = record_reply("100", state, "p", "A",
                              now=datetime(2026, 5, 3, tzinfo=timezone.utc),
                              msg_id="43")
        assert result is True
        assert len(state["queue_archive"]) == 2

    def test_appends_when_pid_differs(self):
        from commands.queue_stats import record_reply
        state = {"queue_archive": [
            {"pid": "100", "msg_id": "42", "time": "x", "player": "A", "preview": ""}
        ], "queue_history": {"100": ["x"]}}
        result = record_reply("200", state, "p", "A",
                              now=datetime(2026, 5, 3, tzinfo=timezone.utc),
                              msg_id="42")
        assert result is True
        assert len(state["queue_archive"]) == 2

    def test_no_msg_id_skips_dedup_check(self):
        """Old call sites without msg_id behave as before — always append."""
        from commands.queue_stats import record_reply
        state = {}
        for _ in range(3):
            record_reply("100", state, "p", "A",
                         now=datetime(2026, 5, 3, tzinfo=timezone.utc))
        assert len(state["queue_archive"]) == 3


# ── queue_stats.get_alltime_clears ───────────────────────────────────────

class TestGetAlltimeClears:
    def test_sums_default_filter(self, tmp_path, monkeypatch):
        from commands import queue_io
        from commands.queue_stats import get_alltime_clears
        monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
        queue_io.save("100", {"pid": "100", "reply_log": [
            {"via": "reply"}, {"via": "markdone"},
            {"via": "manual"}, {"via": "dedup"},  # excluded
            {"via": "archive-pre-w11"},  # excluded
        ]})
        queue_io.save("200", {"pid": "200", "reply_log": [
            {"via": "reply"}, {"via": "reply"},
        ]})
        assert get_alltime_clears() == 5  # 3 + 2

    def test_custom_filter(self, tmp_path, monkeypatch):
        from commands import queue_io
        from commands.queue_stats import get_alltime_clears
        monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
        queue_io.save("100", {"pid": "100", "reply_log": [
            {"via": "reply"}, {"via": "markdone"}, {"via": "manual"},
        ]})
        assert get_alltime_clears(filter_via={"reply"}) == 1
        assert get_alltime_clears(filter_via={"reply", "manual"}) == 2

    def test_zero_when_no_files(self, tmp_path, monkeypatch):
        from commands import queue_io
        from commands.queue_stats import get_alltime_clears
        monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
        assert get_alltime_clears() == 0

    def test_handles_entries_without_via(self, tmp_path, monkeypatch):
        from commands import queue_io
        from commands.queue_stats import get_alltime_clears
        monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
        queue_io.save("100", {"pid": "100", "reply_log": [
            {"player": "A"}, {"via": "reply"},
        ]})
        assert get_alltime_clears() == 1


# ── dispatch.gm_reply.record_gm_reply ────────────────────────────────────

class TestRecordGmReply:
    _PARSED = {
        "msg_time_iso": "2026-05-03T13:00:00+00:00",
    }

    def _cq_with_unreplied(self, msg_id):
        return {"pid": "100",
                "unreplied": [{
                    "message_id": msg_id,
                    "thread_id": "100",
                    "user_id": "U1",
                    "user_name": "Alice",
                    "time": "2026-05-03T12:00:00+00:00",
                    "preview": "Hello",
                }],
                "replied": [], "reply_log": []}

    def test_first_call_records_reply(self, tmp_path, monkeypatch):
        from commands import queue_io
        from dispatch import gm_reply
        monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
        queue_io.save("100", self._cq_with_unreplied(42))
        state = {}
        result = gm_reply.record_gm_reply(self._PARSED, state, "100", 42)
        assert result is True
        cq = queue_io.load("100")
        assert "msg:42" in cq["replied"]
        assert len(cq["reply_log"]) == 1
        assert state["queue_history"]["100"] == [
            cq["reply_log"][0]["t"]] or len(state["queue_history"]["100"]) == 1
        assert len(state["queue_archive"]) == 1

    def test_duplicate_call_is_noop(self, tmp_path, monkeypatch):
        from commands import queue_io
        from dispatch import gm_reply
        monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
        queue_io.save("100", self._cq_with_unreplied(42))
        state = {}
        gm_reply.record_gm_reply(self._PARSED, state, "100", 42)
        result = gm_reply.record_gm_reply(self._PARSED, state, "100", 42)
        assert result is False
        cq = queue_io.load("100")
        assert len(cq["reply_log"]) == 1  # not duplicated
        assert len(state["queue_archive"]) == 1
        assert len(state["queue_history"]["100"]) == 1
