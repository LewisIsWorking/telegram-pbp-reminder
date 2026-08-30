"""Taking a seat off a roster: one path, and one announcement.

``players/retire.retire_seat`` was extracted on 2026-08-30 from two
copies of the same twelve lines, in ``scheduled/alerts`` (the 4 week
sweep) and ``players/management.handle_kick`` (the GM command). They
agreed on the important parts and differed on ``kicked``, which is the
shape that drifts.

The announcement bug this found
------------------------------
``on_leave`` posts an updated roster to the campaign's chat topic on
every event. That is right for one removal and wrong for five: sweeping
C08 Theria's backlog would have put **five** near-identical rosters into
another GM's table in a single run, four of them intermediate states
nobody needs.

Found by dry-running the sweep against the real roster before merging,
not by reading the code. Ten messages where five were expected.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

_NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
_GROUP = -100


def _pair(code, pid, chat):
    return {"name": f"Camp {code}", "code": code, "chat_topic_id": chat,
            "pbp_topic_ids": [int(pid)]}


def _cfg(*pairs):
    return {"group_id": _GROUP, "bot_topic_id": 137393, "gm_user_ids": [999],
            "topic_pairs": list(pairs)}


def _seat(uid, pid, campaign, days_ago=200):
    return {"user_id": uid, "first_name": f"P{uid}", "username": f"u{uid}",
            "campaign_name": campaign, "pbp_topic_id": pid,
            "last_post_time": (_NOW - timedelta(days=days_ago)).isoformat(),
            "last_warned_week": 0}


def _state(*seats):
    return {"players": {f"{s['pbp_topic_id']}:{s['user_id']}": s
                        for s in seats},
            "removed_players": {}, "topics": {}, "last_alerts": {}}


class TestTheThreeThingsThatMustHappenTogether:
    def _retired(self, **kwargs):
        from players.retire import retire_seat
        state = _state(_seat("1", "100", "Camp"))
        retire_seat("100:1", state, None, now=_NOW, **kwargs)
        return state

    def test_the_seat_leaves_the_roster(self):
        assert self._retired()["players"] == {}

    def test_the_leave_is_recorded_in_history(self):
        # Without it, /roster shows a player vanishing with no event to
        # explain when or why.
        history = self._retired()["player_history"]
        assert history[-1]["event"] == "leave"
        assert history[-1]["pid"] == "100"

    def test_removed_players_gains_an_entry(self):
        # ⭐ Without it, _track_player reads their next message as a
        # FIRST join rather than a rejoin, so the history says they
        # arrived twice and never left.
        entry = self._retired()["removed_players"]["100:1"]
        assert entry["username"] == "u1"
        assert entry["campaign_name"] == "Camp"

    def test_an_inactivity_sweep_is_not_marked_as_a_kick(self):
        # Nobody decided this. The two are different facts.
        assert "kicked" not in self._retired()["removed_players"]["100:1"]

    def test_a_gm_kick_is(self):
        assert self._retired(kicked=True)["removed_players"]["100:1"]["kicked"]


class TestOneRosterPostPerSweep:
    def _sweep(self, monkeypatch, config, state):
        import telegram as tg
        from scheduled.alerts import check_player_activity
        posts = []
        monkeypatch.setattr(tg, "send_message",
                            lambda g, t, b, **k: posts.append((t, b)) or True)
        check_player_activity(config, state, now=_NOW)
        return [p for p in posts if p[1].startswith("\U0001f4cb")]

    def test_five_removals_in_one_campaign_post_one_roster(self, monkeypatch):
        # ⭐⭐ The bug the dry run found. Five was the real C08 backlog.
        config = _cfg(_pair("C08", "100", 101))
        state = _state(*[_seat(str(i), "100", "Camp C08") for i in range(5)])
        assert len(self._sweep(monkeypatch, config, state)) == 1
        assert state["players"] == {}, "all five still have to go"

    def test_two_campaigns_swept_post_one_roster_each(self, monkeypatch):
        # can-fail counterpart: a fix that posted exactly one roster ever
        # would pass the test above and lose a campaign's announcement.
        config = _cfg(_pair("C08", "100", 101), _pair("C09", "200", 201))
        state = _state(_seat("1", "100", "Camp C08"),
                       _seat("2", "100", "Camp C08"),
                       _seat("3", "200", "Camp C09"))
        assert len(self._sweep(monkeypatch, config, state)) == 2

    def test_no_removals_post_no_roster(self, monkeypatch):
        config = _cfg(_pair("C08", "100", 101))
        state = _state(_seat("1", "100", "Camp C08", days_ago=2))
        assert self._sweep(monkeypatch, config, state) == []


class TestTheKickCommandUsesTheSamePath:
    def test_a_kick_records_history_and_removed_players(self, monkeypatch):
        # ⭐ The duplication that was extracted. If /kick drifts back to
        # its own copy, one of these three stops happening silently.
        import telegram as tg
        from players.management import handle_kick
        monkeypatch.setattr(tg, "send_message", lambda *a, **k: True)
        state = _state(_seat("1", "100", "Camp"))
        handle_kick("100", "Camp", "u1", state, _GROUP, 101,
                    _cfg(_pair("C08", "100", 101)))
        assert state["players"] == {}
        assert state["player_history"][-1]["event"] == "leave"
        assert state["removed_players"]["100:1"]["kicked"] is True

    def test_an_unknown_name_removes_nobody(self, monkeypatch):
        # can-fail counterpart for the matching, not the retiring.
        import telegram as tg
        from players.management import handle_kick
        monkeypatch.setattr(tg, "send_message", lambda *a, **k: True)
        state = _state(_seat("1", "100", "Camp"))
        handle_kick("100", "Camp", "nobody", state, _GROUP, 101, _cfg())
        assert len(state["players"]) == 1
