"""C11 Dark Pockets is back, for the GM queue only (2026-10-18).

Lewis: *"I want to get reminders when C11's RP topic is the longest waiting
topic."* C11 was retired in #22 because the bot had been removed from its
group. The bot's state kept its last post, 2026-06-29. Re-adding the pair
alone would have read that as 100+ days of silence, and a silent campaign
competes for "Post here next" on hours since its last post, so C11 would
have won the focus on every queue until somebody posted there.

``tracked_since`` is the guard. These tests pin both halves of it (the
silent clock and the transcript floor) and the shape of the live entry.
"""

import json
import os
from datetime import datetime, timezone

from helpers_pkg import tracked_since as ts
from scheduled import queue_focus
from scheduled.queue_silence_rows import latest_last_post

NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
JUNE = "2026-06-29T14:55:57+00:00"
C11 = {"name": "Dark Pockets", "code": "C11", "group_id": -1003496373617,
       "pbp_topic_ids": [1242], "tracked_since": "2026-10-18"}
C04 = {"name": "Magni Guard", "code": "C04", "pbp_topic_ids": [76799]}
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _state(c11_last=JUNE, c04_last="2026-10-18T09:00:00+00:00"):
    return {"topics": {"1242": {"last_message_time": c11_last},
                       "76799": {"last_message_time": c04_last}}}


def _scanned_c04_waiting(time="2026-10-10 09:00:00"):
    return {"76799": {"campaign": "Magni Guard", "code": "C04",
                      "entries": [{"name": "P", "time": time, "preview": "hi"}]}}


class TestTheSilentClock:
    def test_a_june_post_reads_as_the_tracking_day(self):
        last = latest_last_post(_state(), C11)
        assert last == datetime(2026, 10, 18, tzinfo=timezone.utc)

    def test_a_post_after_tracking_is_kept(self):
        last = latest_last_post(_state(c11_last="2026-10-18T10:00:00+00:00"), C11)
        assert last == datetime(2026, 10, 18, 10, tzinfo=timezone.utc)

    def test_without_the_field_nothing_changes(self):
        pair = dict(C11)
        del pair["tracked_since"]
        assert latest_last_post(_state(), pair) == datetime.fromisoformat(JUNE)

    def test_no_recorded_post_stays_no_posts_yet(self):
        assert ts.clamp_last_post(C11, None) is None

    def test_a_naive_timestamp_is_read_as_utc(self):
        assert ts.clamp_last_post(C11, datetime(2026, 6, 1)) == ts.tracked_since(C11)


class TestThePostHereNextFocus:
    def _config(self, pair):
        return {"group_id": -100, "topic_pairs": [C04, pair]}

    def test_stale_june_state_does_not_win_the_focus(self):
        # ⭐ The trap itself. Without the guard C11 is "silent 110d" and an
        # 8-day-old C04 message loses to it on every queue. With it, C11 has
        # been quiet 12h (since tracking began), so the real wait wins.
        row = queue_focus.pick_idle_focus(self._config(C11), _state(),
                                          _scanned_c04_waiting(), {}, NOW)
        assert row is None

    def test_the_same_state_without_the_guard_does_win(self):
        # Proves the test above measures the guard, not some other filter.
        pair = dict(C11)
        del pair["tracked_since"]
        row = queue_focus.pick_idle_focus(self._config(pair), _state(),
                                          _scanned_c04_waiting(), {}, NOW)
        assert row is not None and row.pid == "1242"

    def test_c11_silent_longer_than_the_oldest_wait_still_wins(self):
        # The feature Lewis asked for: once C11 has genuinely gone quiet
        # longer than anything else has waited, it IS "Post here next".
        later = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
        row = queue_focus.pick_idle_focus(
            self._config(C11), _state(c04_last="2026-10-24T09:00:00+00:00"),
            _scanned_c04_waiting("2026-10-24 09:00:00"), {}, later)
        assert row is not None and row.pid == "1242"

    def test_an_unreplied_c11_message_competes_on_age_alone(self):
        scanned = _scanned_c04_waiting("2026-10-18 09:00:00")
        scanned["1242"] = {"campaign": "Dark Pockets", "code": "C11",
                           "entries": [{"name": "Q", "time": "2026-10-18 08:00:00"}]}
        assert queue_focus.pick_focus_pid(scanned, {}) == "1242"


class TestTheTranscriptFloor:
    def test_an_entry_from_before_tracking_is_not_owed(self):
        assert ts.before_tracking(C11, "2026-06-29 14:55:57")

    def test_an_entry_on_the_tracking_day_is(self):
        assert not ts.before_tracking(C11, "2026-10-18 00:00:01")

    def test_a_pair_without_the_field_has_no_floor(self):
        assert not ts.before_tracking(C04, "2020-01-01 00:00:00")

    def test_a_malformed_value_is_no_floor_and_is_reported(self):
        bad = dict(C11, tracked_since="18/10/2026")
        assert not ts.before_tracking(bad, "2020-01-01 00:00:00")
        assert ts.config_issues(bad, "C11")


class TestTheLiveEntry:
    def _pair(self):
        with open(os.path.join(_ROOT, "config.json"), encoding="utf-8") as fh:
            config = json.load(fh)
        pairs = [p for p in config["topic_pairs"] if p.get("code") == "C11"]
        assert len(pairs) == 1, "C11 must be configured exactly once"
        return config, pairs[0]

    def test_it_tracks_the_rp_topic_in_its_own_group(self):
        _, pair = self._pair()
        assert pair["group_id"] == -1003496373617
        assert pair["pbp_topic_ids"] == [1242]
        assert ts.tracked_since(pair) is not None

    def test_it_is_in_the_queue_on_age_not_priority(self):
        # Lewis asked for a reminder when it is the LONGEST waiting. A
        # queue_priority would make it jump the queue instead.
        _, pair = self._pair()
        assert not pair.get("queue_exclude")
        assert "queue_priority" not in pair
        assert not pair.get("queue_always_first")

    def test_nothing_that_posts_into_the_group_or_counts_its_players_is_on(self):
        _, pair = self._pair()
        off = set(pair.get("disabled_features", []))
        assert {"recruitment", "alerts", "smart_alerts", "warnings", "removals",
                "roster", "potw", "pace", "anniversary", "combat",
                "listing"} <= off
        assert not pair.get("linked_polls")
        assert not pair.get("hybrid_live")

    def test_the_shipped_config_validates_clean(self):
        import helpers
        config, _ = self._pair()
        issues = [i for i in helpers.validate_config(config)
                  if "C11" in i or "unknown feature" in i]
        assert not issues, issues


class TestTheCampaignTable:
    def test_the_weekly_table_ages_c11_from_the_tracking_day(self):
        from scheduled.campaign_table import _tracked_last
        assert _tracked_last(C11, JUNE).startswith("2026-10-18T00:00:00")
        assert _tracked_last(C04, JUNE) == JUNE
        assert _tracked_last(C11, None) is None
