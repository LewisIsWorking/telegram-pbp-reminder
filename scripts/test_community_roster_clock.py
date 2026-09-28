"""The community roster judges "active" by its own date (2026-09-28).

Split out of test_community_roster.py, which is at the 200-line limit.
"""

from datetime import datetime, timedelta, timezone

from test_community_roster import _cfg, _pair, _seat, _state


class TestTheReportKeepsOneClock:
    """⛔ 2026-09-28: these tests went red on their own, a month after being
    written. Each campaign's "active" list read the REAL clock while the
    header used the report's ``now``, so fixtures dated 2026-08-30 aged past
    the 30 day window. The fixture here is from 2020, so the old code fails
    it every day from now on."""

    def test_active_is_judged_as_of_the_report_date(self):
        from commands.roster_members import _active_players
        from scheduled.community_roster_build import build_community_roster
        old_now = datetime(2020, 1, 5, 12, 0, tzinfo=timezone.utc)
        seat = _seat("Ada", "25059", username="ada")
        seat["last_post_time"] = (old_now - timedelta(days=2)).isoformat()
        state = _state(seat)
        assert len(_active_players("25059", state, {}, now=old_now)) == 1
        text = build_community_roster(_cfg(_pair("C01", "25059")), state, old_now)
        assert "C01: Camp C01 - 1/6" in text and "@ada" in text
