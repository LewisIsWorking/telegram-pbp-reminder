"""The GM queue says when it will next be checked.

Lewis, 2026-09-15: "It would be great to see a live countdown clock until the
next queue check." A Telegram message cannot tick, so the queue shows the
time of the next scheduled check under "Checked", and the in-place refresh
keeps it current on every run.

⛔ The time is only as right as ``CHECK_MINUTES`` is. It restates the crons in
pbp-reminder.yml, which have moved before (PR #75, :00/:30 to :13/:43), so
the last tests read the workflow itself.
"""

from datetime import datetime, timezone

from scheduled.queue_refresh import CHECK_MINUTES, next_check, next_check_line
# ⚠️ The module, not the class: a Test class imported by name is collected
# again here, and every one of its tests would run twice.
import test_queue_refreshes_in_place as refresh_tests
from test_schedule_conditions_match_the_crons import _doc, declared_crons


def _utc(hour, minute, second=0, day=15):
    return datetime(2026, 9, day, hour, minute, second, tzinfo=timezone.utc)


def test_a_run_after_the_top_cron_points_at_half_past():
    assert next_check(_utc(17, 15)) == _utc(17, 43)


def test_a_run_after_the_half_past_cron_points_at_the_next_hour():
    assert next_check(_utc(17, 44)) == _utc(18, 13)


def test_a_run_inside_the_cron_minute_points_at_the_one_after():
    """A cron run that starts on time must not name itself as next."""
    assert next_check(_utc(17, 13, 0)) == _utc(17, 43)
    assert next_check(_utc(17, 43, 59)) == _utc(18, 13)


def test_a_run_just_before_a_cron_points_at_that_cron():
    assert next_check(_utc(17, 12, 30)) == _utc(17, 13)


def test_the_next_check_crosses_midnight():
    assert next_check(_utc(23, 50)) == _utc(0, 13, day=16)


def test_the_line_reads_in_local_time():
    assert next_check_line(_utc(17, 15)) == "⏭ Next check ~18:43 BST"


def test_next_check_matches_the_crons():
    """⛔⛔ Moving a cron without moving CHECK_MINUTES shows the wrong time."""
    minutes = set()
    for cron in declared_crons(_doc()):
        minute, hour = cron.split()[:2]
        assert hour == "*", f"{cron!r} is not hourly; next_check assumes it is"
        minutes.add(int(minute))
    assert minutes == set(CHECK_MINUTES), (minutes, CHECK_MINUTES)


def test_posted_and_refreshed_heads_carry_the_next_check():
    """Through post_queue_reminder, on both the repost and the refresh."""
    real = refresh_tests.TestThroughTheRealQueuePost()
    state = real._fresh()
    t1 = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
    posted, _edits = real._run(state, t1)
    head = posted.call_args.args[3][0]
    assert "🕒 Checked 11:00 BST\n⏭ Next check ~11:13 BST" in head, head
    _posted, edits = real._run(state, t1.replace(minute=20))
    heads = [c.args[2] for c in edits.call_args_list if "GM Queue" in c.args[2]]
    assert heads and "⏭ Next check ~11:43 BST" in heads[0], heads
