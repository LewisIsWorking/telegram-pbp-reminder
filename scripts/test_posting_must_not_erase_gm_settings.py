"""A player posting must not delete what a GM set about them.

Found 2026-09-02 while reading the live Kibwe log. Horia had
``played_by: MrNegetZ`` set on 09-01; he posted on 09-02 and the field
was **gone**.

⛔⛔ `_track_player` did `state["players"][key] = {...}`, a wholesale
replace of the record with the eight fields the bot observes. Everything
else on it was discarded on the player's next message.

**`/setpermanent` was the real casualty, and nobody noticed for months.**
Measured against live state:

```
records with permanent=True in state: 0
config permanent_user_ids:            []
field names across ALL 40-odd records:
  campaign_name, first_name, last_name, last_post_time,
  last_warned_week, pbp_topic_id, user_id, username
```

Exactly the eight the writer produces, and nothing else. Meanwhile
``roster_members._active_players`` carries a long, carefully argued
docstring about the permanent rule (L20, *"Lewis explicitly flagged this
design on 2026-05-10"*) and a warning not to add a recency check to it.
**The rule is elaborately documented and could not survive one post.**

⭐ A record is two things with two owners: what the bot OBSERVES, which
must always win, and what a human DECIDED, which the bot has no business
touching. The write path conflated them.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

_PID = "40585"


def _parsed(**over):
    base = {"pid": _PID, "user_id": "u1", "user_name": "Horia",
            "user_last_name": "", "username": "Nemesiux",
            "campaign_name": "Kibwe", "text": "a post",
            "msg_time_iso": datetime.now(timezone.utc).isoformat(),
            "message_id": 1}
    base.update(over)
    return base


def _track(state, monkeypatch, **over):
    import telegram as tg
    from dispatch.tracking import _track_player
    from helpers import build_topic_maps
    monkeypatch.setattr(tg, "send_message", lambda *a, **k: True)
    config = {"group_id": -100, "topic_pairs": [
        {"name": "Kibwe", "code": "C06", "chat_topic_id": 1,
         "pbp_topic_ids": [int(_PID)]}]}
    _track_player(_parsed(**over), state, config, set(),
                  build_topic_maps(config))
    return state["players"][f"{_PID}:u1"]


def _seat(**extra):
    seat = {"user_id": "u1", "first_name": "Horia", "last_name": "",
            "username": "Nemesiux", "campaign_name": "Kibwe",
            "pbp_topic_id": _PID, "last_warned_week": 3,
            "last_post_time": (datetime.now(timezone.utc)
                               - timedelta(days=29)).isoformat()}
    seat.update(extra)
    return {"players": {f"{_PID}:u1": seat}, "removed_players": {},
            "away": {}, "player_history": []}


class TestWhatTheGmDecidedSurvives:
    def test_permanent_survives_a_post(self, monkeypatch):
        # ⭐⭐ The months-old bug. /setpermanent was undone by the very
        # next message from the player it protected.
        rec = _track(_seat(permanent=True), monkeypatch)
        assert rec.get("permanent") is True, (
            "posting erased /setpermanent; the permanent rule cannot take "
            "effect for anyone who ever posts")

    def test_played_by_survives_a_post(self, monkeypatch):
        rec = _track(_seat(played_by="MrNegetZ"), monkeypatch)
        assert rec.get("played_by") == "MrNegetZ"

    def test_an_unknown_future_field_survives_too(self, monkeypatch):
        # The fix must be general. A merge protects fields nobody has
        # written yet; an allow-list would have to be remembered.
        rec = _track(_seat(some_future_flag="keep me"), monkeypatch)
        assert rec.get("some_future_flag") == "keep me"


class TestWhatTheBotObservesStillWins:
    def test_the_post_time_is_updated(self, monkeypatch):
        # ⚠️ Assert against NOW, not against another fixture's stamp. The
        # first version compared two separately-built `_seat()` records,
        # whose 29-day-old timestamps differ by microseconds in the
        # WRONG direction, so a mutation that kept the old value still
        # satisfied `rec > before`. Two nearly-equal values cannot test
        # which one was chosen.
        rec = _track(_seat(), monkeypatch)
        age = datetime.now(timezone.utc) - datetime.fromisoformat(
            rec["last_post_time"])
        assert age < timedelta(minutes=1), (
            f"last_post_time is {age} old; posting must stamp it now")

    def test_the_warning_level_is_cleared_by_posting(self, monkeypatch):
        # can-fail counterpart: a merge must not preserve EVERYTHING, or
        # a player at week 3 would stay one post from removal forever.
        rec = _track(_seat(), monkeypatch)
        assert rec["last_warned_week"] == 0

    def test_a_renamed_player_takes_the_new_name(self, monkeypatch):
        rec = _track(_seat(), monkeypatch, user_name="Horia C",
                     username="NemesiuxNew")
        assert rec["first_name"] == "Horia C"
        assert rec["username"] == "NemesiuxNew"


class TestAProxyNeverMakesAnActivePlayerLookQuiet:
    """⭐⭐ The consequence of the fix above, and it is live.

    Horia was proxied by Anthony on 09-01 and posted himself on 09-02.
    Once ``played_by`` survives a post, returning the proxy's time
    blindly would measure an ACTIVE player against somebody else's
    silence and sweep him for it.
    """

    def _state(self, own_days, proxy_days):
        now = datetime.now(timezone.utc)
        def seat(name, user, days, **extra):
            d = {"user_id": user, "first_name": name, "username": user,
                 "campaign_name": "Kibwe", "pbp_topic_id": _PID,
                 "last_post_time": (now - timedelta(days=days)).isoformat(),
                 "last_warned_week": 0}
            d.update(extra)
            return d
        return {"players": {
            f"{_PID}:a": seat("Horia", "Nemesiux", own_days,
                              played_by="MrNegetZ"),
            f"{_PID}:b": seat("Anthony", "MrNegetZ", proxy_days)}}

    def _age(self, state):
        from players.proxy import effective_post_time
        seat = state["players"][f"{_PID}:a"]
        eff = effective_post_time(seat, _PID, state)
        return (datetime.now(timezone.utc) - eff).days

    def test_an_active_seat_is_not_dragged_down_by_a_quiet_proxy(self):
        assert self._age(self._state(own_days=0, proxy_days=40)) == 0

    def test_a_quiet_seat_is_still_carried_by_an_active_proxy(self):
        assert self._age(self._state(own_days=40, proxy_days=0)) == 0

    def test_both_quiet_stays_quiet(self):
        # ⛔ The redirection-not-exemption rule, unchanged. If neither is
        # posting the seat is swept exactly as before.
        assert self._age(self._state(own_days=40, proxy_days=50)) == 40

    def test_a_proxy_with_no_usable_time_falls_back_to_the_seat(self):
        # ⛔ A proxy record that exists but carries a broken timestamp
        # must not erase the seat's own clock. Returning None there makes
        # the seat unmeasurable, which reads as "not active" and sweeps a
        # player who is posting.
        from players.proxy import effective_post_time
        state = self._state(own_days=1, proxy_days=99)
        state["players"][f"{_PID}:b"]["last_post_time"] = "not-a-date"
        eff = effective_post_time(state["players"][f"{_PID}:a"], _PID, state)
        assert eff is not None, "a broken proxy timestamp erased the seat"
        assert (datetime.now(timezone.utc) - eff).days == 1
