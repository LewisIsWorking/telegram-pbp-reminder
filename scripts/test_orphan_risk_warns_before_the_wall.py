"""Warning before a queue post crosses the 48h delete wall.

Written 2026-09-04. Lewis: *"The GM queue in C05 didn't delete properly"*
- a 2026-08-30 "Unreplied: 2" post still sitting in Grand Explorers.

It was m175998, and it was stranded by a **57.5h gap** between the run
that posted it and the next one that could have replaced it. Three other
threads lost a post in the same window, and 66154 cleared the wall by
twelve minutes. Nothing warned, because nothing was watching the clock.
"""

import json

import pytest

from _test_preflight_helpers import NOW, at
from preflight import orphan_risk


class TestOrphanRisk:
    """The cost the staleness is about to incur. 2026-08-30..09-01 lost
    four queue posts to a 57.5h gap and nothing warned."""

    def _slot(self, hours_ago):
        return {"topic_queues": {"51357": {
            "msg_ids": [175998], "last_posted_at": at(hours_ago)}},
            "pid": "51357"}

    def _dir(self, tmp_path, hours_ago):
        import json
        (tmp_path / "51357.json").write_text(
            json.dumps(self._slot(hours_ago)), encoding="utf-8")
        return str(tmp_path)

    def test_a_fresh_post_is_not_at_risk(self, tmp_path):
        rows = orphan_risk.scan(NOW, self._dir(tmp_path, 2.0))
        assert rows[0]["hours_left"] == pytest.approx(46.0)
        assert orphan_risk.at_risk(rows) == []

    def test_the_real_57_hour_gap_is_reported_past_the_wall(self, tmp_path):
        rows = orphan_risk.scan(NOW, self._dir(tmp_path, 57.5))
        assert rows[0]["hours_left"] == pytest.approx(-9.5)
        assert orphan_risk.at_risk(rows) == rows
        assert "PAST THE WALL" in orphan_risk.summarise(rows)

    def test_the_twelve_minute_near_miss_is_flagged_before_it_happens(self, tmp_path):
        """⭐⭐ 2026-08-28: thread 66154 cleared the wall by 12 minutes and
        nothing said a word. At 47.8h it must be shouting."""
        rows = orphan_risk.scan(NOW, self._dir(tmp_path, 47.8))
        assert orphan_risk.at_risk(rows) == rows

    def test_an_unknown_age_counts_as_at_risk(self, tmp_path):
        """"Cannot tell" about a delete deadline is a reason to look."""
        import json
        (tmp_path / "x.json").write_text(json.dumps(
            {"pid": "1", "topic_queues": {"9": {"msg_ids": [1]}}}),
            encoding="utf-8")
        rows = orphan_risk.scan(NOW, str(tmp_path))
        assert rows[0]["hours_left"] is None
        assert orphan_risk.at_risk(rows) == rows

    def test_an_empty_scan_is_reported_as_suspicious(self):
        """⛔ A summary that goes quiet when the scan breaks is a guard
        that fails silently."""
        assert "suspicious" in orphan_risk.summarise([])

    def test_an_unreadable_directory_does_not_raise(self):
        assert orphan_risk.scan(NOW, "/no/such/dir") == []

    def test_the_wall_matches_the_posters_own_constant(self):
        """⚠️ Two copies of Telegram's 48h wall. Pin them together or one
        will be tuned and the other will not."""
        from scheduled.topic_queue_age import DELETE_WALL
        assert orphan_risk.DELETE_WALL == DELETE_WALL
