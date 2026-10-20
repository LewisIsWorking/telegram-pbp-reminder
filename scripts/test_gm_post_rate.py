"""The GM posting rate and queue clearing rate on the GM queue post.

Lewis, 2026-10-20: "It would be good if the bot posted to the GM queue topic
about MY post number per day (the rate of clearing the queue) kinda thing."

Every test pins ``now``. The data is built relative to it, so nothing here
goes red when the real calendar moves on.
"""

from datetime import datetime, timedelta, timezone

from scheduled import gm_post_rate as rate

LEWIS = "1698524397"
OTHER_GM = "6144366145"
PLAYER = "555"
# 12:00 UTC on a BST day is 13:00 in London.
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def _cfg():
    return {"gm_user_ids": [int(LEWIS)]}


def _ts(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).isoformat()


def _state(by_user, pid="25059"):
    return {"post_timestamps": {pid: by_user}}


class TestPostsPerDay:
    def test_today_and_yesterday_are_london_days(self):
        # 12:30 UTC yesterday-ish: 23.5h ago is 12:30 UTC on 10-19.
        state = _state({LEWIS: [_ts(1), _ts(2), _ts(23.5)]})
        line = rate.posts_line(_cfg(), state, NOW)
        assert "2 today" in line and "1 yesterday" in line, line

    def test_the_boundary_is_london_midnight_not_utc(self):
        """23:30 UTC on 10-19 is 00:30 BST on 10-20: today, not yesterday."""
        late = datetime(2026, 10, 19, 23, 30, tzinfo=timezone.utc).isoformat()
        line = rate.posts_line(_cfg(), _state({LEWIS: [late]}), NOW)
        assert "1 today" in line and "0 yesterday" in line, line

    def test_only_the_global_gm_counts(self):
        """Theria has its own GM; the post is about Lewis's rate."""
        state = _state({LEWIS: [_ts(1)], OTHER_GM: [_ts(1)], PLAYER: [_ts(1)]})
        assert "1 today" in rate.posts_line(_cfg(), state, NOW)

    def test_every_campaign_counts(self):
        state = {"post_timestamps": {"1": {LEWIS: [_ts(1)]},
                                     "2": {LEWIS: [_ts(2)]}}}
        assert "2 today" in rate.posts_line(_cfg(), state, NOW)

    def test_average_is_over_seven_complete_days(self):
        """14 posts across the 7 days before today is 2.0/day. Today's posts
        and anything 8+ days back are left out."""
        stamps = [_ts(24 * d) for d in range(1, 8) for _ in (0, 1)]
        stamps += [_ts(1)] * 5 + [_ts(24 * 9)] * 5
        line = rate.posts_line(_cfg(), _state({LEWIS: stamps}), NOW)
        assert "2.0/day (7d)" in line, line

    def test_no_posts_reads_zero(self):
        assert rate.posts_line(_cfg(), {}, NOW) == (
            "✍️ GM posts: 0 today | 0 yesterday | 0.0/day (7d)")


class TestQueueSnapshots:
    def test_each_run_records_the_unreplied_count(self):
        state = {}
        rate.record_queue_size(state, {"1": {"entries": [{}, {}]},
                                       "2": {"entries": [{}]}}, NOW)
        assert state[rate.LOG_KEY] == [[NOW.isoformat(), 3]]

    def test_samples_past_48h_are_dropped(self):
        state = {rate.LOG_KEY: [[_ts(49), 9], [_ts(30), 7]]}
        rate.record_queue_size(state, {}, NOW)
        assert state[rate.LOG_KEY] == [[_ts(30), 7], [NOW.isoformat(), 0]]

    def test_compares_with_the_newest_sample_at_least_24h_old(self):
        state = {rate.LOG_KEY: [[_ts(30), 20], [_ts(24.5), 17], [_ts(3), 1]]}
        assert rate.queue_size_then(state, NOW) == 17

    def test_nothing_old_enough_means_no_comparison(self):
        state = {rate.LOG_KEY: [[_ts(5), 17]]}
        assert rate.queue_change_line(state, 12, NOW) is None

    def test_a_sample_too_stale_is_not_used(self):
        """With runs missed, a 40h-old reading is not "yesterday"."""
        state = {rate.LOG_KEY: [[_ts(40), 17]]}
        assert rate.queue_size_then(state, NOW) is None


class TestQueueChangeLine:
    def test_shrinking(self):
        state = {rate.LOG_KEY: [[_ts(24), 17]]}
        assert rate.queue_change_line(state, 12, NOW) == (
            "📉 Queue 17 -> 12 since yesterday (5 fewer)")

    def test_growing(self):
        state = {rate.LOG_KEY: [[_ts(24), 12]]}
        assert rate.queue_change_line(state, 17, NOW) == (
            "📈 Queue 12 -> 17 since yesterday (5 more)")

    def test_unchanged(self):
        state = {rate.LOG_KEY: [[_ts(24), 4]]}
        assert rate.queue_change_line(state, 4, NOW) == (
            "➖ Queue 4, same as yesterday")

    def test_rate_lines_skip_the_queue_line_without_history(self):
        assert len(rate.rate_lines(_cfg(), {}, 3, NOW)) == 1


class TestOnTheQueuePost:
    def test_the_posted_queue_carries_both_lines(self):
        from unittest.mock import patch
        from scheduled import queue_reminder
        from test_core_scheduled import _qr_config

        config = _qr_config()
        config["gm_user_ids"] = [int(LEWIS)]
        state = {"post_timestamps": {"25059": {LEWIS: [_ts(1)]}},
                 rate.LOG_KEY: [[_ts(24), 5]]}
        scanned = {"25059": {"campaign": "Doomsday", "code": "C01",
                             "entries": [{"time": "2026-10-20 10:00:00",
                                          "user": "Pat", "text": "hi",
                                          "message_id": 7}]}}
        sent = []
        with patch.object(queue_reminder, "scan_transcripts", return_value=scanned), \
             patch.object(queue_reminder, "drop_deleted", side_effect=lambda c, s, sc, n: sc), \
             patch.object(queue_reminder, "post_topic_queues"), \
             patch.object(queue_reminder, "send_focus_dm", return_value=False), \
             patch.object(queue_reminder, "post_and_persist",
                          side_effect=lambda st, g, t, msgs, **k: (sent.extend(msgs), (True, 1))[1]):
            queue_reminder.post_queue_reminder(config, state, now=NOW)

        head = sent[0]
        assert "✍️ GM posts: 1 today" in head, head
        assert "📉 Queue 5 -> 1 since yesterday (4 fewer)" in head, head
        assert state[rate.LOG_KEY][-1] == [NOW.isoformat(), 1]
