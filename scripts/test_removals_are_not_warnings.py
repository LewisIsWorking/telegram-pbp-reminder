"""Nagging a player and sweeping a dead seat are different acts.

Lewis, 2026-08-30, looking at five C08 Theria seats silent 110 to 176
days: *"Well if people have been gone from 08 for 100 days, they should
have been kicked as players."*

They should have been. One flag named ``warnings`` gated both the 1, 2
and 3 week nudges (messages to a player) and the 4 week removal (roster
hygiene). C08 disabled ``warnings`` because it is another GM's table and
the bot should not nag their players, and that silently switched off the
sweep too. Five dead seats accumulated, and Theria read larger than it
was in ``/roster``, in the recruit advert and in the weekly community
roster.

⛔ The comment on the removal block said *"ALWAYS fires, even when GM is
bottleneck"*. True of the condition it was written about, false of the
function, because a ``continue`` thirty lines earlier meant the block was
never reached. A docblock can state a rule the predicate does not
enforce; that is the third time in this repo.

The four combinations are all meaningful, which is the argument for two
flags rather than one:

===========  ==========  ============================================
``warnings`` ``removals``
===========  ==========  ============================================
on           on          the default
**off**      **on**      **somebody else's table: stay quiet, stay tidy**
on           off         warn, but never act on it
off          off         use ``paused_campaigns`` instead, it says why
===========  ==========  ============================================
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

_NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
_GROUP = -100
_PID = "107151"
_CHAT = 107141


def _cfg(*disabled):
    pair = {"name": "Theria", "code": "C08", "chat_topic_id": _CHAT,
            "pbp_topic_ids": [int(_PID)]}
    if disabled:
        pair["disabled_features"] = list(disabled)
    return {"group_id": _GROUP, "bot_topic_id": 137393,
            "gm_user_ids": [999], "topic_pairs": [pair]}


def _state(days_ago=200, permanent=False, **extra):
    player = {"user_id": "u1", "first_name": "Quiet", "username": "quiet",
              "campaign_name": "Theria", "pbp_topic_id": _PID,
              "last_post_time": (_NOW - timedelta(days=days_ago)).isoformat(),
              "last_warned_week": 0}
    if permanent:
        player["permanent"] = True
    state = {"players": {f"{_PID}:u1": player}, "removed_players": {},
             "topics": {}, "last_alerts": {}}
    state.update(extra)
    return state


def _run(monkeypatch, config, state):
    import telegram as tg
    from scheduled.alerts import check_player_activity
    sent = []
    monkeypatch.setattr(tg, "send_message",
                        lambda g, t, b, **k: sent.append((t, b)) or True)
    check_player_activity(config, state, now=_NOW)
    return sent


def _removed(state):
    return not state["players"]


class TestSomebodyElsesTable:
    """warnings off, removals on. The combination C08 needed."""

    def test_a_seat_silent_for_months_is_swept(self, monkeypatch):
        # ⭐⭐ The bug. Before 2026-08-30 this returned with the seat
        # still in place, because one `continue` covered both halves.
        state = _state(days_ago=176)
        _run(monkeypatch, _cfg("warnings"), state)
        assert _removed(state)

    def test_the_player_is_never_nagged(self, monkeypatch):
        # can-fail counterpart: the fix must not have simply re-enabled
        # warnings. A seat one week quiet gets nothing at all.
        state = _state(days_ago=8)
        sent = _run(monkeypatch, _cfg("warnings"), state)
        assert sent == []
        assert not _removed(state)


class TestTheOtherThreeCombinations:
    def test_both_enabled_still_sweeps(self, monkeypatch):
        state = _state(days_ago=176)
        _run(monkeypatch, _cfg(), state)
        assert _removed(state), "the default behaviour must be unchanged"

    def test_removals_off_keeps_the_seat(self, monkeypatch):
        state = _state(days_ago=176)
        sent = _run(monkeypatch, _cfg("removals"), state)
        assert not _removed(state)
        assert sent == [], "past four weeks, so no warning either"

    def test_removals_off_still_warns_at_one_week(self, monkeypatch):
        # ⭐ Proves the two flags are independent in both directions.
        state = _state(days_ago=8)
        sent = _run(monkeypatch, _cfg("removals"), state)
        assert sent and "hasn't posted" in sent[0][1]

    def test_both_off_does_nothing(self, monkeypatch):
        state = _state(days_ago=176)
        sent = _run(monkeypatch, _cfg("warnings", "removals"), state)
        assert not _removed(state) and sent == []


class TestWhatStillProtectsAPlayer:
    def test_a_paused_campaign_is_left_alone(self, monkeypatch):
        # ⭐ Pausing is a statement about the table, so it outranks both
        # flags. This is the switch for a hiatus, not disabled_features.
        state = _state(days_ago=176, paused_campaigns={_PID: "hiatus"})
        sent = _run(monkeypatch, _cfg(), state)
        assert not _removed(state) and sent == []

    def test_a_permanent_player_is_never_swept(self, monkeypatch):
        # The L20 rule, unchanged by the split.
        state = _state(days_ago=400, permanent=True)
        _run(monkeypatch, _cfg(), state)
        assert not _removed(state)

    def test_an_away_player_is_never_swept(self, monkeypatch):
        # ⚠️ `away` is keyed FLAT as "pid:user_id", not nested by pid.
        # The first version of this fixture nested it, the player was
        # swept, and the test failed rather than quietly passing. Worth
        # recording: a fixture built from a guessed shape is a test of
        # the guess.
        state = _state(days_ago=176)
        state["away"] = {f"{_PID}:u1": {
            "until": (_NOW + timedelta(days=30)).isoformat()}}
        _run(monkeypatch, _cfg(), state)
        assert not _removed(state)


class TestTheFeatureNameIsValid:
    def test_removals_is_an_accepted_feature(self):
        # ⭐ Without this, `disabled_features: ["removals"]` would work
        # AND emit "unknown feature 'removals'" on every run.
        import helpers
        issues = helpers.validate_config(_cfg("removals"))
        assert not [i for i in issues if "unknown feature" in i], issues

    def test_smart_alerts_is_too(self):
        # Pre-existing gap found while adding the above: the name is used
        # by scheduled/smart_alerts.py and was missing from the list.
        import helpers
        issues = helpers.validate_config(_cfg("smart_alerts"))
        assert not [i for i in issues if "unknown feature" in i], issues

    def test_a_typo_is_still_rejected(self):
        # can-fail counterpart. Without this, a validator that accepted
        # everything would pass both tests above.
        import helpers
        issues = helpers.validate_config(_cfg("removalz"))
        assert [i for i in issues if "unknown feature" in i], issues
