"""The GM queue reposts when the queue changes, not when an hour passes.

Lewis, 2026-09-13: "Isn't the queue only meant to repost if the queue
changes?" It was meant to. It was not doing it.

⛔⛔ The change fingerprint appended the rendered silent-campaign lines, and
each line carries its age ("no posts for 13d 20h"). The age ticks every hour,
so the fingerprint changed every hour, so the queue reposted every hour.
Measured from committed state history: **12 of 13 consecutive reposts were
only an age ticking.** One was a real change.

These tests drive the REAL post_queue_reminder with the REAL silent-section
rendering, and fake only the idle rows, as a function of the clock. Patching
silent_campaigns itself would have faked away the very code that was wrong.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from _test_queue_post_fakes import edit_ok, faithful_post_and_persist
from scheduled.queue_silence_rows import IdleRow

T0 = datetime(2026, 9, 13, 10, 0, tzinfo=timezone.utc)

# No queue_daily_hours, so no daily slot is ever due. Every post in these
# tests has to be earned by a change, which is the property under test.
CONFIG = {"group_id": -1001, "bot_topic_id": 999,
          "topic_pairs": [{"pbp_topic_ids": [146645], "code": "C10",
                           "name": "The Junction"},
                          {"pbp_topic_ids": [25059], "code": "C01",
                           "name": "Doomsday Funtime"}]}


def _row(pid, label, days_at_t0, now):
    """A silent campaign whose age advances with the clock, as it really does."""
    days = days_at_t0 + (now - T0).total_seconds() / 86400
    hours = int(days * 24)
    return IdleRow(pair={}, pid=pid, days=days, icon="🟤", prefix="",
                   label=label, age=f"{hours // 24}d {hours % 24}h",
                   link="", ever_posted=True)


def _idle(silent):
    """Build a fake idle_campaigns: ``silent`` is {pid: (label, days_at_t0)}."""
    def fake(config, state, scanned, now):
        return [_row(pid, label, d, now) for pid, (label, d) in silent.items()]
    return fake


def _post(state, now, silent, scanned=None):
    """Run one queue pass. Returns how many times the queue was REPOSTED.

    ⚠️ Since 2026-09-13 an unchanged queue is edited in place rather than
    left alone, so the post fake must record its batch the way the real one
    does, or every unchanged run finds nothing to edit and reposts. See
    _test_queue_post_fakes.
    """
    with patch("scheduled.queue_silence.idle_campaigns", _idle(silent)), \
         patch("scheduled.queue_reminder.scan_transcripts",
               return_value=scanned or {}), \
         patch("scheduled.queue_reminder.post_topic_queues"), \
         patch("scheduled.queue_reminder.send_focus_dm", return_value=False), \
         patch("scheduled.queue_reminder.post_and_persist",
               side_effect=faithful_post_and_persist) as posted, \
         patch("scheduled.queue_reminder.tg.edit_message", side_effect=edit_ok), \
         patch("scheduled.queue_caught_up.post_and_persist",
               return_value=(True, 1)):
        from scheduled.queue_reminder import post_queue_reminder
        post_queue_reminder(CONFIG, state, now=now)
    return posted.call_count


SILENT = {"146645": ("The Junction", 13.8), "25059": ("Doomsday Funtime", 6.7)}


class TestTheBug:
    def test_an_hour_passing_does_not_repost_the_queue(self):
        """⛔⛔ THE BUG. Nothing about the queue changed; only its ages did."""
        state = {"queue_post_count": 0, "last_queue_daily_slots": []}
        assert _post(state, T0, SILENT) == 1, "first pass should post"
        assert _post(state, T0 + timedelta(hours=1), SILENT) == 0

    def test_a_whole_day_of_hourly_passes_posts_once(self):
        """The measured shape: 24 runs, and the queue only changed once."""
        state = {"queue_post_count": 0, "last_queue_daily_slots": []}
        posts = sum(_post(state, T0 + timedelta(hours=h), SILENT)
                    for h in range(24))
        assert posts == 1

    def test_reordering_campaigns_in_config_is_not_a_queue_change(self):
        """Why silent_campaign_ids sorts. idle_campaigns walks topic_pairs in
        config order, which is stable run to run, so in normal operation an
        unsorted list would behave identically. It stops being identical the
        moment someone reorders topic_pairs in config.json: the same silent
        campaigns, a different sequence, and a repost for nothing."""
        state = {"queue_post_count": 0, "last_queue_daily_slots": []}
        _post(state, T0, SILENT)
        reordered = dict(reversed(list(SILENT.items())))
        assert _post(state, T0 + timedelta(hours=1), reordered) == 0

    def test_crossing_an_age_band_is_still_not_a_queue_change(self):
        """Jumping several days moves ages across display bands too. The set
        of silent campaigns is unchanged, so there is still nothing to post."""
        state = {"queue_post_count": 0, "last_queue_daily_slots": []}
        _post(state, T0, SILENT)
        assert _post(state, T0 + timedelta(days=4), SILENT) == 0


class TestRealChangesStillRepost:
    """⭐ Can-fail counterparts. Without these, a fingerprint that never
    changes at all would pass every test above."""

    def test_a_campaign_going_silent_reposts(self):
        state = {"queue_post_count": 0, "last_queue_daily_slots": []}
        _post(state, T0, {"146645": ("The Junction", 13.8)})
        assert _post(state, T0 + timedelta(hours=1), SILENT) == 1

    def test_a_campaign_leaving_silence_reposts(self):
        state = {"queue_post_count": 0, "last_queue_daily_slots": []}
        _post(state, T0, SILENT)
        still_silent = {"146645": ("The Junction", 13.8)}
        assert _post(state, T0 + timedelta(hours=1), still_silent) == 1

    def test_a_new_unreplied_message_reposts(self):
        state = {"queue_post_count": 0, "last_queue_daily_slots": []}
        waiting = {"76799": {"campaign": "Magni Guard", "code": "C04",
                             "entries": [{"name": "Alastair Tan",
                                          "time": "2026-09-13 09:00:00",
                                          "preview": "x", "link": ""}]}}
        _post(state, T0, SILENT)
        assert _post(state, T0 + timedelta(hours=1), SILENT, waiting) == 1
