"""The leaderboard must report exactly the window it posts at.

Lewis, 2026-08-19, pointing at "📬 GM Queue: 64 replies cleared this week":
*"This is only meant to be weekly."*

The count was right. The **cadence** was not. `LEADERBOARD_INTERVAL_DAYS`
was 3 while the reporting window was 7, so every report re-counted four
days of the previous one, and "MVP of the Week" (with its hero point
prize) was handed out roughly twice a week. Anthony had reached MVP x15.

Nothing caught it because nothing could: the four lines that build the
queue-clearance section each carried `# pragma: no cover`, so the block
was invisible to the coverage report and had no test at all.

⭐ The invariant here is more general than one constant. A rolling report
has exactly one correct cadence: **report the window you post at.**

    INTERVAL < WINDOW  overlap. Activity is counted more than once, and
                       any prize attached to the report is over-awarded.
    INTERVAL > WINDOW  gap. Activity between reports is never counted at
                       all, and simply vanishes.

Only equality double-counts nothing and drops nothing.
"""

from datetime import datetime, timedelta, timezone

import helpers
from commands.queue_stats import get_week_clears
from scheduled.leaderboard import _format_leaderboard

NOW = datetime(2026, 8, 19, 20, 31, tzinfo=timezone.utc)


def _stats(**over):
    """One campaign row, with every key ``_format_leaderboard`` reads.

    Mirrors what ``_gather_leaderboard_stats`` produces. Kept complete
    rather than minimal: a missing key raises KeyError deep inside the
    formatter, which reads as a test bug rather than as the contract
    change it usually is.
    """
    base = {"name": "Hopeful End-Times", "code": "C07", "player_7d": 20,
            "total_7d": 28, "gm_7d": 8, "trend_icon": "📈",
            "avg_gap_str": "4.0h", "last_post_str": "today",
            "player_avg_gap": 5.7, "player_avg_gap_str": "5.7h",
            "days_since_last": 0, "top_players": []}
    base.update(over)
    return base


class TestTheCadenceMatchesTheWindow:
    def test_interval_equals_window(self):
        # ⭐⭐ THE GUARD. Had this existed, the 3 vs 7 mismatch could not
        # have shipped, and it is the whole bug in one line.
        assert helpers.LEADERBOARD_INTERVAL_DAYS == helpers.LEADERBOARD_WINDOW_DAYS

    def test_and_that_shared_value_is_a_week(self):
        # Separate from the equality above on purpose: 3 == 3 would satisfy
        # that test while still contradicting every "week" word in the
        # message. This pins the value the wording promises.
        assert helpers.LEADERBOARD_INTERVAL_DAYS == 7


class TestTheHeaderMatchesTheWindow:
    def test_the_reported_range_spans_the_window(self):
        message = _format_leaderboard([_stats()], {}, NOW)
        expected_from = helpers.fmt_date(
            NOW - timedelta(days=helpers.LEADERBOARD_WINDOW_DAYS))
        assert expected_from in message.splitlines()[0]
        assert helpers.fmt_date(NOW) in message.splitlines()[0]

    def test_it_still_calls_itself_weekly(self):
        # If the window ever stops being 7, this test fails and forces the
        # wording to be revisited rather than left quietly lying.
        assert helpers.LEADERBOARD_WINDOW_DAYS == 7
        assert "Weekly Campaign Leaderboard" in _format_leaderboard(
            [_stats()], {}, NOW)


class TestQueueClearanceSection:
    """Covers the four lines that were `pragma: no cover` until 2026-08-19."""

    def _state(self, *timestamps):
        return {"queue_history": {"52083": list(timestamps)}}

    def test_reports_clears_inside_the_window(self):
        state = self._state((NOW - timedelta(days=1)).isoformat(),
                            (NOW - timedelta(days=6)).isoformat())
        assert "📬 GM Queue: 2 replies cleared this week." in _format_leaderboard(
            [_stats()], {}, NOW, None, state)

    def test_ignores_clears_older_than_the_window(self):
        # ⭐ The can-fail counterpart. Without it, a function that counted
        # everything ever would pass the test above.
        state = self._state((NOW - timedelta(days=1)).isoformat(),
                            (NOW - timedelta(days=30)).isoformat())
        assert "1 replies cleared" in _format_leaderboard(
            [_stats()], {}, NOW, None, state)

    def test_measures_from_the_message_instant_not_the_wall_clock(self):
        # ⚠️ get_week_clears defaults `now` to datetime.now(), so left to
        # default the line would measure a different window to the header
        # above it.
        #
        # ⭐ The instant is deliberately YEARS in the past. My first
        # attempt used NOW minus 10 days, which sat outside BOTH the
        # message window and the real one, so it passed whichever clock
        # was used and proved nothing. The mutation harness caught that.
        # A clear inside the message's window can only also be inside the
        # wall clock's window if the suite runs within a week of that
        # instant, so putting it far back makes the two windows disjoint
        # and the test discriminating forever.
        old_now = datetime(2024, 1, 15, 12, tzinfo=timezone.utc)
        state = self._state((old_now - timedelta(days=1)).isoformat())
        assert "1 replies cleared" in _format_leaderboard(
            [_stats()], {}, old_now, None, state)

    def test_the_section_is_omitted_when_nothing_was_cleared(self):
        assert "GM Queue:" not in _format_leaderboard(
            [_stats()], {}, NOW, None, {"queue_history": {}})

    def test_no_section_at_all_without_state(self):
        assert "GM Queue:" not in _format_leaderboard([_stats()], {}, NOW)


class TestGetWeekClearsDirectly:
    def test_counts_only_the_last_seven_days(self):
        history = {"queue_history": {"a": [
            (NOW - timedelta(days=d)).isoformat() for d in (0, 3, 6, 8, 40)]}}
        assert get_week_clears(history, NOW) == 3

    def test_sums_across_campaigns(self):
        history = {"queue_history": {
            "a": [(NOW - timedelta(hours=1)).isoformat()],
            "b": [(NOW - timedelta(hours=2)).isoformat()],
        }}
        assert get_week_clears(history, NOW) == 2

    def test_empty_state_is_zero(self):
        assert get_week_clears({}, NOW) == 0
