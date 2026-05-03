"""Tests for commands/markdone_audit.py â€” markdone clears mirror into queue_history."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timezone
from unittest.mock import patch


_NOW = datetime(2026, 5, 3, 14, 0, 0, tzinfo=timezone.utc)


class TestRecordClear:
    def test_appends_to_reply_log(self):
        from commands.markdone_audit import record_clear
        cq = {}
        state = {}
        with patch("commands.queue_stats.record_reply", return_value=True):
            record_clear(cq, "40585", state,
                         mid_str="12345", thread_id="40585",
                         player_name="Alice", preview="hi", now=_NOW)
        assert len(cq["reply_log"]) == 1
        e = cq["reply_log"][0]
        assert e["via"] == "markdone"
        assert e["pid"] == "40585"
        assert e["msg_id"] == "12345"
        assert e["player"] == "Alice"

    def test_truncates_preview_to_80_chars(self):
        from commands.markdone_audit import record_clear
        cq = {}
        long_preview = "x" * 200
        with patch("commands.queue_stats.record_reply", return_value=True):
            record_clear(cq, "40585", {},
                         mid_str="1", thread_id="40585",
                         player_name="A", preview=long_preview, now=_NOW)
        assert len(cq["reply_log"][0]["preview"]) == 80

    def test_calls_record_reply_for_today_counter(self):
        """Markdone clears must mirror into queue_history so they show
        in the daily Y today counter, not just the all-time figure."""
        from commands.markdone_audit import record_clear
        with patch("commands.queue_stats.record_reply") as mock_rr:
            mock_rr.return_value = True
            record_clear({}, "40585", {},
                         mid_str="42", thread_id="40585",
                         player_name="Bob", preview="ok", now=_NOW)
            mock_rr.assert_called_once()
            kwargs = mock_rr.call_args.kwargs
            args = mock_rr.call_args.args
            # signature: record_reply(pid, state, preview, player, *, now, msg_id)
            assert args[0] == "40585"
            assert args[2] == "ok"
            assert args[3] == "Bob"
            assert kwargs["msg_id"] == "42"

    def test_preserves_existing_reply_log_entries(self):
        from commands.markdone_audit import record_clear
        cq = {"reply_log": [{"via": "reply", "msg_id": "0"}]}
        with patch("commands.queue_stats.record_reply", return_value=True):
            record_clear(cq, "40585", {},
                         mid_str="1", thread_id="40585",
                         player_name="A", preview="b", now=_NOW)
        assert len(cq["reply_log"]) == 2
        assert cq["reply_log"][0]["via"] == "reply"
        assert cq["reply_log"][1]["via"] == "markdone"


class TestMarkdoneTodayCounterParity:
    """Integration-ish: a /markdone clear should bump state.queue_history
    so the today counter agrees with the all-time counter on what counts."""

    def test_markdone_clear_writes_queue_history(self):
        from commands.markdone_audit import record_clear
        state = {}
        cq = {}
        # Use real record_reply so we exercise the full mirroring path.
        record_clear(cq, "40585", state,
                     mid_str="55", thread_id="40585",
                     player_name="Carol", preview="x", now=_NOW)
        # queue_history is the source for the daily today counter.
        history = state.get("queue_history", {})
        assert "40585" in history
        assert len(history["40585"]) == 1
