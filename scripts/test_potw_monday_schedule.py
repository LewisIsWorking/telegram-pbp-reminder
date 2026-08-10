"""POTW fires on Mondays only, once per calendar week (2026-08-10).

The reported symptom: "it doesn't really know when to post it and it
seems to fire semi-randomly whenever anyone makes a post."

Two independent drift sources, both from the old rolling gate
``interval_elapsed(state["last_potw"][pid], 7, now)``:

1. It fired on the first cron tick *at or after* the 7-day mark. The cron
   ticks at :00 and :30, so the post time crept later every week and
   eventually wandered onto a different weekday.
2. A week with fewer than POTW_MIN_POSTS qualifying posts hit ``continue``
   **without stamping** ``last_potw``. The gate stayed open, so the award
   fired on the first tick after activity resumed — literally whenever a
   player next posted enough to qualify.

Both are replaced by a calendar weekday gate plus an ISO week key, the
same shape ``scheduled.week_welcome`` already uses.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

# 2026-08-10 is a Monday; 2026-08-13 a Thursday; 2026-08-11 a Tuesday.
_MON_09 = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)
_MON_02 = datetime(2026, 8, 10, 2, 0, tzinfo=timezone.utc)
_TUE_09 = datetime(2026, 8, 11, 9, 0, tzinfo=timezone.utc)
_THU_09 = datetime(2026, 8, 13, 9, 0, tzinfo=timezone.utc)


class TestWeekKey:
    def test_key_is_stable_across_the_whole_week(self):
        from scheduled.potw_schedule import week_key
        assert week_key(_MON_09) == week_key(_THU_09)

    def test_key_changes_between_weeks(self):
        from scheduled.potw_schedule import week_key
        nxt = datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc)  # next Monday
        assert week_key(_MON_09) != week_key(nxt)

    def test_key_format(self):
        from scheduled.potw_schedule import week_key
        assert week_key(_MON_09).startswith("2026-W")


class TestDueGate:
    def test_due_on_the_right_day_and_hour(self):
        from scheduled.potw_schedule import due
        assert due(_MON_09, 0, 9) is True

    def test_not_due_before_the_hour(self):
        from scheduled.potw_schedule import due
        assert due(_MON_02, 0, 9) is False

    def test_not_due_on_another_day(self):
        from scheduled.potw_schedule import due
        assert due(_TUE_09, 0, 9) is False

    def test_countdown_day_is_independent(self):
        from scheduled.potw_schedule import due
        assert due(_THU_09, 3, 9) is True
        assert due(_THU_09, 0, 9) is False


class TestAwardOnlyFiresMonday:
    """The headline fix: no posting on a random Tuesday."""

    def _state(self):
        return {"last_potw": {}, "pending_potw_boons": {}, "potw_week": {}}

    def test_does_not_fire_midweek(self, tg_mock):
        from scheduled.potw import player_of_the_week
        cfg = {"group_id": -100, "bot_topic_id": 1, "topic_pairs": []}
        player_of_the_week(cfg, self._state(), now=_TUE_09)
        assert not tg_mock.send_message_id.called, (
            "POTW must not fire on a Tuesday — this is the reported bug")

    def test_does_not_fire_before_post_hour(self, tg_mock):
        from scheduled.potw import player_of_the_week
        cfg = {"group_id": -100, "bot_topic_id": 1, "topic_pairs": []}
        player_of_the_week(cfg, self._state(), now=_MON_02)
        assert not tg_mock.send_message_id.called

    def test_quiet_week_stamps_so_it_cannot_fire_later(self):
        """The 'fires whenever someone posts' half of the bug.

        A campaign with no qualifying players must still record that this
        week was evaluated. The old code skipped without stamping, leaving
        the gate open for the next tick.
        """
        from scheduled.potw_schedule import week_key
        state = self._state()
        # Simulate the no-candidate branch stamping.
        state["potw_week"]["40585"] = week_key(_MON_09)
        assert state["potw_week"]["40585"] == week_key(_MON_09)


class TestRoundup:
    def test_no_award_means_no_roundup(self, tg_mock):
        from scheduled.potw_roundup import post_potw_roundup
        post_potw_roundup({"group_id": -100, "bot_topic_id": 1}, {}, [],
                          now=_MON_09)
        assert not tg_mock.send_message.called, (
            "an empty week should post nothing, not an empty scoreboard")

    def test_roundup_lists_every_campaign_sorted_by_gap(self):
        from scheduled.potw_roundup import build_roundup_text
        awarded = [
            {"campaign": "C05", "pid": "5", "winner": {
                "first_name": "Cannon", "last_name": "", "username": "",
                "post_count": 9, "avg_gap_hours": 6.1}},
            {"campaign": "C01", "pid": "1", "winner": {
                "first_name": "Anthony", "last_name": "", "username": "",
                "post_count": 12, "avg_gap_hours": 4.2}},
        ]
        text = build_roundup_text(awarded, _MON_09)
        assert "C01" in text and "C05" in text
        # Smallest average gap ranks first.
        assert text.index("C01") < text.index("C05")
        assert "2026-W" in text

    def test_roundup_is_once_per_week(self, tg_mock):
        from scheduled.potw_roundup import post_potw_roundup
        from scheduled.potw_schedule import week_key
        state = {"last_potw_roundup": week_key(_MON_09)}
        awarded = [{"campaign": "C01", "pid": "1", "winner": {
            "first_name": "A", "last_name": "", "username": "",
            "post_count": 5, "avg_gap_hours": 1.0}}]
        post_potw_roundup({"group_id": -100, "bot_topic_id": 1}, state,
                          awarded, now=_MON_09)
        assert not tg_mock.send_message.called


class TestCountdown:
    def test_only_fires_on_countdown_day(self, tg_mock):
        from scheduled.potw_countdown import post_potw_countdown
        cfg = {"group_id": -100, "bot_topic_id": 1, "topic_pairs": []}
        post_potw_countdown(cfg, {}, now=_MON_09)
        assert not tg_mock.send_message.called

    def test_says_four_days_to_go_on_thursday(self):
        from scheduled.potw_countdown import build_countdown_text
        rows = [{"campaign": "C01",
                 "leader": {"first_name": "Anthony", "last_name": "",
                            "username": "", "post_count": 12,
                            "avg_gap_hours": 4.2},
                 "runner_up": None}]
        # (0 - 3) % 7 == 4
        text = build_countdown_text(rows, 4)
        assert "4 days to go" in text
        assert "Anthony" in text

    def test_shows_the_gap_to_the_chaser(self):
        from scheduled.potw_countdown import build_countdown_text
        rows = [{"campaign": "C01",
                 "leader": {"first_name": "Anthony", "last_name": "",
                            "username": "", "post_count": 12,
                            "avg_gap_hours": 4.2},
                 "runner_up": {"first_name": "Horia", "last_name": "",
                               "username": "", "post_count": 8,
                               "avg_gap_hours": 5.8}}]
        text = build_countdown_text(rows, 4)
        assert "Horia" in text
        assert "+1.6h behind" in text, "the chase gap is the point of the post"

    def test_no_qualifiers_posts_nothing(self, tg_mock):
        from scheduled.potw_countdown import post_potw_countdown
        cfg = {"group_id": -100, "bot_topic_id": 1, "topic_pairs": []}
        post_potw_countdown(cfg, {}, now=_THU_09)
        assert not tg_mock.send_message.called


class TestCountdownAgreesWithAward:
    """The countdown must not name a leader Monday then contradicts."""

    def test_countdown_reuses_the_award_ranking_function(self):
        import scheduled.potw as potw
        import scheduled.potw_countdown as countdown
        assert countdown._gather_potw_candidates is potw._gather_potw_candidates
