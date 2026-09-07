"""Who each POTW message is addressed to, and what the roundup says.

Lewis, 2026-09-07, on the two messages the W37 award produced: *"Could
these go to the campaign specific chat"* and *"we could say when a
player has a streak in that 2nd message, if that happens."*

⭐ The two messages are addressed to different people, and that is the
whole distinction:

  the AWARD    names one campaign's player, offers them a boon to claim.
               It belongs where their table reads.
  the ROUNDUP  answers "who won this week" across every campaign at
               once, which is why it exists at all. Sending it to a
               campaign topic would post N copies of a list that is
               only useful whole.

⛔ This is the third time the ``bot_topic or chat_topic_id`` idiom has
been applied one send too far - anniversaries went the same way on
2026-09-04. The idiom is right for operator-facing output and wrong for
anything addressed to a table, and only the destination assertion
catches it: every earlier POTW test checked that a message was sent and
what it said, never where it went.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from scheduled.potw_roundup import (MIN_STREAK, build_roundup_text,
                                    post_potw_roundup, streak_note)

NOW = datetime(2026, 9, 7, 10, 30, tzinfo=timezone.utc)
BOT_TOPIC = 300
CHAT_TOPIC = 200


def _winner(uid="42", posts=6, gap=8.1, name="Anthony"):
    return {"user_id": uid, "first_name": name, "username": "MrNegetZ",
            "post_count": posts, "avg_gap_hours": gap}


def _awarded(pid="52083", campaign="Hopeful End-Times", **kw):
    return [{"campaign": campaign, "pid": pid, "winner": _winner(**kw)}]


class TestTheAwardGoesToTheTable:
    """⭐ Asserts the DESTINATION. The gap that let this ship."""

    def _send(self, monkeypatch):
        from scheduled import potw
        sent = []
        monkeypatch.setattr(potw.tg, "send_message_id",
                            lambda gid, tid, text, **k: sent.append((tid, text)) or 999)
        return sent

    def test_the_award_is_not_sent_to_the_bot_topic(self, monkeypatch):
        """Reading the source is the honest check here: the award send
        must not consult bot_topic at all."""
        import inspect

        from scheduled import potw
        source = inspect.getsource(potw.player_of_the_week)
        award = [line for line in source.splitlines()
                 if "send_message_id" in line and not line.strip().startswith("#")]
        assert award, "could not find the award send"
        assert "bot_topic" not in "".join(award), (
            "the POTW award is routed to the bot topic again; it is "
            "addressed to one campaign's player")

    def test_the_streak_call_targets_the_campaign_too(self):
        import inspect

        from scheduled import potw
        source = inspect.getsource(potw.player_of_the_week)
        call = source[source.index("announce_streaks(config"):]
        assert "bot_topic" not in call[:200]


class TestTheRoundupStaysCrossCampaign:
    """⛔ Can-fail counterpart to the above, and the reason "these" was
    not simply applied to both messages. The roundup summarises every
    campaign; per-campaign delivery would post N copies of a list whose
    only value is being whole."""

    @patch("scheduled.potw_roundup.tg.send_message", return_value=True)
    def test_it_still_goes_to_the_bot_topic(self, mock_send):
        config = {"group_id": -100, "bot_topic_id": BOT_TOPIC}
        post_potw_roundup(config, {"potw_history": []}, _awarded(), now=NOW)
        assert mock_send.call_args[0][1] == BOT_TOPIC

    @patch("scheduled.potw_roundup.tg.send_message", return_value=True)
    def test_one_post_however_many_campaigns_won(self, mock_send):
        awarded = _awarded() + [
            {"campaign": "Metal City", "pid": "107171",
             "winner": _winner(uid="7", name="Sam")}]
        post_potw_roundup({"group_id": -100, "bot_topic_id": BOT_TOPIC},
                          {"potw_history": []}, awarded, now=NOW)
        assert mock_send.call_count == 1


class TestTheStreakNote:
    def test_a_run_of_wins_is_mentioned(self):
        assert streak_note(2) == " · 🔥 2-week streak"

    def test_a_single_win_is_not_called_a_streak(self):
        """⭐ Can-fail counterpart. "1-week streak" on every winner every
        week is noise, and noise is what gets the line ignored."""
        assert streak_note(1) == ""
        assert streak_note(0) == ""

    @pytest.mark.parametrize("streak", [4, 6, 7, 9])
    def test_it_reads_between_the_celebration_milestones(self, streak):
        """⚠️ Looser than potw_streaks.CAMPAIGN_MILESTONES (2, 3, 5, 10)
        on purpose. Lewis asked for "when a player HAS a streak", which
        is a different question from "is it worth a fanfare"."""
        assert f"{streak}-week streak" in streak_note(streak)

    def test_the_line_carries_it_next_to_the_stats(self):
        text = build_roundup_text(_awarded(), NOW, {"52083": 3})
        assert "avg gap 8.1h · 🔥 3-week streak" in text

    def test_a_winner_with_no_streak_reads_exactly_as_before(self):
        text = build_roundup_text(_awarded(), NOW, {"52083": 1})
        assert "avg gap 8.1h" in text and "streak" not in text


class TestTheRoundupNeverBreaksTheAward:
    """⛔ The roundup runs AFTER the awards have already been posted. If
    it raises, the awards are out and the week is marked done, so the
    failure is invisible and unrecoverable."""

    @patch("scheduled.potw_roundup.tg.send_message", return_value=True)
    def test_a_winner_without_a_user_id_still_posts(self, mock_send):
        awarded = [{"campaign": "C", "pid": "1",
                    "winner": {"post_count": 6, "avg_gap_hours": 8.1,
                               "first_name": "X"}}]
        post_potw_roundup({"group_id": -100, "bot_topic_id": BOT_TOPIC},
                          {"potw_history": []}, awarded, now=NOW)
        assert mock_send.called

    def test_streaks_may_be_omitted_entirely(self):
        assert "streak" not in build_roundup_text(_awarded(), NOW)
        assert "streak" not in build_roundup_text(_awarded(), NOW, None)


class TestTheStreakCountIsReal:
    """⚠️ Counted from potw_history AFTER this week's win is appended,
    so it includes the win being announced. Computed before, every
    streak would read one short."""

    def _history(self, weeks, pid="52083", uid="42"):
        return [{"campaign_pid": pid, "user_id": uid, "year": 2026,
                 "week": f"W{w}"} for w in weeks]

    @patch("scheduled.potw_roundup.tg.send_message", return_value=True)
    def test_three_consecutive_weeks_reads_as_three(self, mock_send):
        state = {"potw_history": self._history([35, 36, 37])}
        post_potw_roundup({"group_id": -100, "bot_topic_id": BOT_TOPIC},
                          state, _awarded(), now=NOW)
        assert "3-week streak" in mock_send.call_args[0][2]

    @patch("scheduled.potw_roundup.tg.send_message", return_value=True)
    def test_a_gap_in_the_weeks_breaks_it(self, mock_send):
        """⭐ Can-fail counterpart: wins are not simply counted."""
        state = {"potw_history": self._history([33, 35, 37])}
        post_potw_roundup({"group_id": -100, "bot_topic_id": BOT_TOPIC},
                          state, _awarded(), now=NOW)
        assert "streak" not in mock_send.call_args[0][2]

    def test_the_threshold_is_the_one_the_renderer_uses(self):
        assert MIN_STREAK == 2
