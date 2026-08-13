"""Schedule post renders in local time, gates stay UTC (2026-08-10).

Split out of ``test_schedule_post.py`` on 2026-08-13, which had reached
211 lines. Rendering is its own concern: everything here asks what the
GM sees, and nothing here asks when a job fires.

The distinction is the point. A display bug and a gate bug look
identical in a screenshot, so ``test_gates_are_untouched_by_display``
holds the UTC hour still while the rest of the file moves the clock.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

_MON = datetime(2026, 8, 10, 9, 15, tzinfo=timezone.utc)   # Monday 09:15
_CFG = {"group_id": -100, "bot_topic_id": 137393,
        "queue_daily_hours": [9, 21], "poll_post_hour": 7,
        "diagnostic_hour": 8, "topic_pairs": []}


class TestLocalTimeRendering:
    """Rendered in Belfast time; gates stay UTC (requested 2026-08-10)."""

    def test_summer_hours_shift_to_bst(self):
        from scheduled.schedule_post import build_schedule_text
        text = build_schedule_text(_CFG, {}, _MON)   # 10 Aug -> BST
        assert "09:00 — Daily diagnostic" in text, (
            "08:00 UTC must render as 09:00 BST")
        assert "BST" in text

    def test_winter_hours_stay_gmt(self):
        from scheduled.schedule_post import build_schedule_text
        winter = datetime(2026, 12, 14, 9, 15, tzinfo=timezone.utc)  # Monday
        text = build_schedule_text(_CFG, {}, winter)
        assert "08:00 — Daily diagnostic" in text, (
            "08:00 UTC is 08:00 GMT in winter — no shift")
        assert "GMT" in text

    def test_gates_are_untouched_by_display(self):
        """The schedule table still speaks UTC; only rendering converts."""
        import helpers
        from scheduled.schedule_table import fixed_schedule
        potw = next(r for r in fixed_schedule(_CFG)
                    if "Player of the Week" in r["label"])
        assert potw["hour"] == helpers.POTW_POST_HOUR, (
            "converting the display must not move the gate")

    def test_next_run_is_local(self):
        from scheduled.schedule_post import build_schedule_text
        text = build_schedule_text(_CFG, {}, _MON)   # 09:15 UTC
        assert "Next run: 10:30 BST" in text, "09:30 UTC = 10:30 BST"

    def test_falls_back_to_utc_when_zone_missing(self, monkeypatch):
        """A tz lookup must never take the whole run down."""
        import scheduled.local_time as lt
        monkeypatch.setattr(lt, "_zone", None)
        monkeypatch.setattr(lt, "_zone_loaded", True)
        out = lt.to_local(_MON)
        assert out == _MON
        assert lt.tz_label(out) == "UTC"
