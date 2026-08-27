"""Arriving by posting is a join, and must be recorded as one.

Lewis, 2026-08-27: *"C07 is somehow the only campaign with 6/6 players.
Does it really have 6/6 players???"*

It really did. Paul had joined by posting. So had Volf and Alastair in
C04 the day before. **None of the three appear in ``player_history``.**

## Why

``_track_player`` branched three ways and every branch assumed we had
seen the person before:

    if was_removed:               -> on_rejoin, history, "is back!"
    elif old_warn_level >= 2:     -> "back" message
    elif old_player.last_post_time -> comeback check

A first-time poster has ``old_player == {}``, so ``old_warn_level`` is 0
and ``last_post_time`` is None. They fell through **all three**, were
written into ``state["players"]``, and nothing else happened.

``on_join`` existed, was correct, and was called from exactly one place:
``/addplayer``. Every player who arrived the ordinary way, by posting,
was invisible in the history and triggered no roster post.

⚠️ The docstring in ``roster_players.py`` has said since 2026-05-11 that
*"no production code path currently calls them"*. Half of that was fixed
later (``on_rejoin`` and ``on_leave`` are wired), and the note stayed,
which is how the remaining half stayed unnoticed. A partly-fixed comment
reads as a fully-fixed one.

## The test that matters most

``test_an_existing_player_posting_again_logs_nothing``. The obvious fix
is a bare ``else``, and a bare ``else`` would log a join on **every
message from a returning player**, flooding the history and the campaign
topic. The narrow condition is the whole point.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

NOW = datetime(2026, 8, 27, 6, 45, tzinfo=timezone.utc)
CONFIG = {"group_id": -1001, "gm_user_ids": [999], "bot_topic_id": 999,
          "topic_pairs": [{"code": "C07", "name": "Hopeful End-Times",
                           "pbp_topic_ids": [100], "chat_topic_id": 55}]}


def _parsed(uid="U-new", name="Paul", text="Hello all!"):
    return {"user_id": uid, "username": name.lower(), "first_name": name,
            "user_name": name, "user_last_name": "",
            "campaign_name": "Hopeful End-Times", "pid": "100",
            "is_gm": False, "thread_id": "100", "text": text,
            "raw_text": text, "msg_time_iso": NOW.isoformat(),
            "message_id": 42}


def _state(**kw):
    base = {"topics": {}, "warned_absent": {}, "removed_players": {},
            "players": {}, "message_counts": {}, "post_timestamps": {},
            "player_history": []}
    base.update(kw)
    return base


def _track(parsed, state):
    """Run one message through the tracker with Telegram stubbed out."""
    from dispatch.tracking import track_message
    maps = MagicMock()
    maps.to_chat = {"100": 55}
    maps.to_name = {"100": "Hopeful End-Times"}
    sent = []
    # ⚠️ ONE patch, on the telegram module itself. `dispatch.tracking.tg`
    # and `players.history.tg` are the same module object, so patching
    # both means the second silently replaces the first and the capture
    # list stays empty while everything appears to work.
    with patch("dispatch.tracking.helpers") as mh, \
         patch("telegram.send_message",
               side_effect=lambda g, t, m: sent.append(m) or True):
        mh.hours_since.return_value = 5.0
        mh.character_name.return_value = ""
        mh.COMEBACK_THRESHOLD_HOURS = 96
        mh.player_mention.return_value = "@x"
        track_message(parsed, state, CONFIG, {"999"}, maps)
    return sent


def _joins(state):
    return [e for e in state.get("player_history", []) if e["event"] == "join"]


class TestArrivingByPosting:
    def test_a_first_time_poster_is_recorded_as_a_join(self):
        # ⭐⭐ The reported bug. Before the fix this list was empty.
        state = _state()
        _track(_parsed(), state)
        assert len(_joins(state)) == 1

    def test_the_entry_names_who_and_where(self):
        # An entry that cannot be attributed is not much better than none:
        # the roster history renders the name and the campaign.
        state = _state()
        _track(_parsed(uid="U-paul", name="Paul"), state)
        entry = _joins(state)[0]
        assert entry["user_id"] == "U-paul"
        assert entry["name"] == "Paul"
        assert entry["pid"] == "100"
        assert entry["username"] == "paul"

    def test_they_still_land_in_the_roster(self):
        # can-fail counterpart: logging the join must not replace the
        # thing that actually seats them.
        state = _state()
        _track(_parsed(uid="U-paul"), state)
        assert "100:U-paul" in state["players"]

    def test_the_campaign_topic_gets_the_roster_post(self):
        # on_join posts the updated roster, which is the message Lewis
        # reads. Silent arrivals were the visible half of this bug.
        state = _state()
        sent = _track(_parsed(), state)
        assert sent, "no roster post went out for a new player"


class TestItDoesNotFireForEveryoneElse:
    def test_an_existing_player_posting_again_logs_nothing(self):
        # ⭐⭐ The constraint that makes the fix safe. A bare `else` here
        # would log a join on EVERY message from a returning player and
        # spam both the history and the campaign topic.
        state = _state(players={"100:U1": {
            "user_id": "U1", "first_name": "Alice", "username": "alice",
            "campaign_name": "Hopeful End-Times", "pbp_topic_id": "100",
            "last_post_time": "2026-08-20T10:00:00+00:00",
            "last_warned_week": 0}})
        _track(_parsed(uid="U1", name="Alice"), state)
        assert _joins(state) == []

    def test_a_second_message_from_the_new_player_logs_nothing(self):
        # The realistic sequence: they say hello, then say something
        # else. Exactly one join, not two.
        state = _state()
        _track(_parsed(text="Hello all!"), state)
        _track(_parsed(text="Rolling initiative"), state)
        assert len(_joins(state)) == 1

    def test_a_removed_player_returning_is_a_rejoin_not_a_new_join(self):
        # ⚠️ Ordering: was_removed is checked first and must stay first,
        # or a returning player would be logged as brand new and lose
        # the "is back!" message.
        state = _state(removed_players={"100:U1": {
            "username": "alice", "first_name": "Alice",
            "removed_at": "2026-01-01"}})
        _track(_parsed(uid="U1", name="Alice"), state)
        assert len(_joins(state)) == 1
        assert "100:U1" not in state["removed_players"]

    def test_a_command_records_the_join_but_announces_nothing(self):
        # ⚠️ Caught by test_checker_misc_b::test_pick_vote, which broke
        # on the first version of this fix. A stranger typing /pick is
        # SEATED by the tracker regardless, so the history has to record
        # it or history and roster disagree. Announcing it is the part
        # that is wrong: the vote confirmation stopped being the last
        # message sent. Every other announcement here skips commands
        # too, so this now matches.
        state = _state()
        sent = _track(_parsed(text="/pick 2"), state)
        assert len(_joins(state)) == 1, "the seat happened, so log it"
        assert sent == [], "a command must not announce an arrival"

    def test_a_real_post_still_announces(self):
        # can-fail counterpart for the line above.
        state = _state()
        assert _track(_parsed(text="Hello all!"), state)

    def test_the_gm_is_never_logged_as_joining(self):
        # GMs do not reach _track_player at all (track_message skips
        # them), and pinning that here means a future change to the GM
        # filter cannot quietly start announcing the GM as a new player.
        state = _state()
        parsed = _parsed(uid="999", name="Lewis")
        parsed["is_gm"] = True
        _track(parsed, state)
        assert _joins(state) == []
