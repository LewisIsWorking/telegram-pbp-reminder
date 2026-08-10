"""Self-replacing schedule/timer post (2026-08-10).

Requested: "a daily schedule post and/or a timer post that says when it
will fire next ... deleted when the next schedule and/or timer is posted."

Built as ONE message rather than two: an accurate "next fire" timer has
to refresh every run anyway (the cron ticks twice an hour), and since the
post replaces its predecessor, refreshing costs no clutter. One message
means one lifecycle and one thing to delete.

The guards that matter here are the ones that would silently rot:

* the post must not claim a time the job does not actually use, so the
  table reads its hours from the same config keys / helpers constants the
  jobs read;
* it must be silent, or it pings 48 times a day;
* it must never leave the topic with no schedule at all.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

_MON = datetime(2026, 8, 10, 9, 15, tzinfo=timezone.utc)   # Monday 09:15
_THU = datetime(2026, 8, 13, 6, 5, tzinfo=timezone.utc)    # Thursday 06:05
_CFG = {"group_id": -100, "bot_topic_id": 137393,
        "queue_daily_hours": [9, 21], "poll_post_hour": 7,
        "diagnostic_hour": 8, "topic_pairs": []}


class TestNextTick:
    def test_before_half_past_goes_to_thirty(self):
        from scheduled.schedule_post import next_tick
        assert next_tick(_MON).strftime("%H:%M") == "09:30"

    def test_after_half_past_rolls_to_next_hour(self):
        from scheduled.schedule_post import next_tick
        now = datetime(2026, 8, 10, 9, 45, tzinfo=timezone.utc)
        assert next_tick(now).strftime("%H:%M") == "10:00"

    def test_last_half_hour_of_day_rolls_over_midnight(self):
        from scheduled.schedule_post import next_tick
        now = datetime(2026, 8, 10, 23, 45, tzinfo=timezone.utc)
        nxt = next_tick(now)
        assert nxt.strftime("%H:%M") == "00:00" and nxt.day == 11


class TestScheduleMatchesRealGates:
    """The post must not advertise a time the job does not use."""

    def test_potw_row_tracks_the_helpers_constants(self):
        import helpers
        from scheduled.schedule_table import fixed_schedule
        rows = fixed_schedule(_CFG)
        potw = next(r for r in rows if "Player of the Week" in r["label"])
        assert potw["day"] == helpers.POTW_WEEKDAY
        assert potw["hour"] == helpers.POTW_POST_HOUR

    def test_queue_hours_come_from_config(self):
        from scheduled.schedule_table import fixed_schedule
        hours = sorted(r["hour"] for r in fixed_schedule(_CFG)
                       if "GM queue" in r["label"])
        assert hours == [9, 21]

    def test_legacy_single_queue_hour_still_works(self):
        from scheduled.schedule_table import fixed_schedule
        cfg = {k: v for k, v in _CFG.items() if k != "queue_daily_hours"}
        cfg["queue_daily_hour"] = 11
        hours = [r["hour"] for r in fixed_schedule(cfg)
                 if "GM queue" in r["label"]]
        assert hours == [11]

    def test_poll_hour_comes_from_config(self):
        from scheduled.schedule_table import fixed_schedule
        row = next(r for r in fixed_schedule(_CFG) if "Session poll +" in r["label"])
        assert row["hour"] == 7 and row["day"] == 6


class TestTodaysItems:
    def test_marks_past_hours_done(self):
        """Keyed by hour, not label — 'GM queue digest' appears twice."""
        from scheduled.schedule_table import todays_items
        items = todays_items(_CFG, _MON)   # Monday 09:15
        done_at = {i["hour"]: i["done"] for i in items}
        assert done_at[8] is True,  "08:00 diagnostic already fired"
        assert done_at[9] is True,  "09:00 already fired"
        assert done_at[21] is False, "21:00 queue digest still to come"

    def test_sorted_by_hour(self):
        from scheduled.schedule_table import todays_items
        hours = [i["hour"] for i in todays_items(_CFG, _MON)]
        assert hours == sorted(hours)

    def test_only_todays_weekday_jobs(self):
        from scheduled.schedule_table import todays_items
        labels = [i["label"] for i in todays_items(_CFG, _THU)]
        assert any("POTW standings" in l for l in labels), "Thursday"
        assert not any("Player of the Week" in l for l in labels), "that's Monday"


class TestBody:
    def test_contains_timer_and_todays_schedule(self):
        from scheduled.schedule_post import build_schedule_text
        text = build_schedule_text(_CFG, {}, _MON)
        # Rendered in Belfast time: 09:30 UTC is 10:30 BST in August.
        assert "Next run: 10:30 BST" in text
        assert "in 15 min" in text
        assert "Player of the Week" in text

    def test_interval_jobs_show_next_due(self):
        from scheduled.schedule_post import build_schedule_text
        state = {"last_leaderboard": (_MON - timedelta(days=1)).isoformat()}
        text = build_schedule_text(_CFG, state, _MON)
        assert "Leaderboard" in text
        assert "Interval jobs" in text

    def test_per_campaign_interval_uses_earliest(self):
        """last_roster is a dict of pid -> iso; the oldest is what's due."""
        from scheduled.schedule_post import _interval_lines
        state = {"last_roster": {
            "1": (_MON - timedelta(days=10)).isoformat(),
            "2": (_MON - timedelta(hours=1)).isoformat()}}
        line = [l for l in _interval_lines(state, _MON) if "Roster" in l][0]
        assert "due now" in line, "the 10-day-old campaign is overdue"

    def test_unrun_job_reads_due_now(self):
        from scheduled.schedule_post import _interval_lines
        assert any("due now" in l for l in _interval_lines({}, _MON))


class TestPosting:
    def test_is_silent(self, tg_mock):
        """48 refreshes a day must not be 48 notifications."""
        from scheduled.schedule_post import post_schedule
        tg_mock.send_message_id.return_value = 500
        post_schedule(_CFG, {}, now=_MON)
        assert tg_mock.send_message_id.call_args.kwargs.get("silent") is True

    def test_deletes_the_previous_post(self, tg_mock):
        from scheduled.schedule_post import post_schedule
        tg_mock.send_message_id.return_value = 501
        state = {"schedule_post_msg_id": 500}
        post_schedule(_CFG, state, now=_MON)
        deleted = [c.args[1] for c in tg_mock.delete_message.call_args_list]
        assert 500 in deleted
        assert state["schedule_post_msg_id"] == 501

    def test_send_failure_keeps_the_old_post(self, tg_mock):
        """Never leave the topic with no schedule at all."""
        from scheduled.schedule_post import post_schedule
        tg_mock.send_message_id.return_value = None
        state = {"schedule_post_msg_id": 500}
        post_schedule(_CFG, state, now=_MON)
        assert not tg_mock.delete_message.called
        assert state["schedule_post_msg_id"] == 500

    def test_no_bot_topic_is_a_noop(self, tg_mock):
        from scheduled.schedule_post import post_schedule
        post_schedule({"group_id": -100}, {}, now=_MON)
        assert not tg_mock.send_message_id.called

    def test_can_be_disabled(self, tg_mock):
        from scheduled.schedule_post import post_schedule
        cfg = {**_CFG, "schedule_post_enabled": False}
        post_schedule(cfg, {}, now=_MON)
        assert not tg_mock.send_message_id.called


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
