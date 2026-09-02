"""`/addplayer` over an existing seat refuses; it does not rewrite it.

⛔ My first version of this asserted that `/addplayer` **merges** over
an existing seat, in the same spirit as the 2026-09-02 `_track_player`
fix. It passed, and a mutation restoring the wholesale replace
**survived it**. The reason is the better fact:

``handle_addplayer`` early-returns as soon as any record in the
campaign already carries that username, so **the write is unreachable
for an existing player**. My fixture had two records with the same
username, the refusal fired, and the assertion was inspecting a dict
nothing had touched.

The merge on that writer stays as insurance against the early return
ever changing, but it is not behaviour anything can currently exercise,
so it gets no test pretending otherwise. Per
``never-ignore-coverage-branches``, an unreachable branch is a design
fact worth stating, not a test to fake. What IS reachable, and what
these assert, is the refusal.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

_PRIMARY = "40585"


def _state(**extra):
    seat = {"user_id": "u1", "first_name": "Horia", "username": "Nemesiux",
            "campaign_name": "Kibwe", "pbp_topic_id": _PRIMARY,
            "last_post_time": "2026-09-01T00:00:00+00:00",
            "last_warned_week": 0}
    seat.update(extra)
    return {"players": {f"{_PRIMARY}:u1": seat}, "removed_players": {},
            "characters": {}, "away": {}}


def _add(monkeypatch, state, args="@Nemesiux Horia"):
    import telegram as tg
    from players.management import handle_addplayer
    sent = []
    monkeypatch.setattr(tg, "send_message",
                        lambda g, t, b, **k: sent.append(b) or True)
    handle_addplayer(_PRIMARY, "Kibwe", args,
                     "2026-09-02T12:00:00+00:00", state, -100, 1)
    return sent


class TestAddPlayerRefusesToOverwrite:
    def test_an_existing_seat_is_left_completely_alone(self, monkeypatch):
        # ⚠️ Assert the WHOLE roster, not just the one seat. Dropping the
        # early return does not edit `u1` at all: it writes a SECOND
        # record at `<pid>:pending_Nemesiux`, so a per-seat equality
        # check stays green while the campaign silently gains a
        # duplicate player. The refusal is about the roster, so the
        # assertion is too.
        state = _state(permanent=True, played_by="MrNegetZ")
        before = {k: dict(v) for k, v in state["players"].items()}
        sent = _add(monkeypatch, state)
        assert state["players"] == before, (
            "/addplayer changed the roster instead of refusing")
        assert sent and "already tracked" in sent[0]

    def test_a_genuinely_new_player_is_created(self, monkeypatch):
        # can-fail counterpart: the refusal above must be about the
        # DUPLICATE, not about /addplayer being broken outright.
        #
        # ⚠️ The roster here is deliberately NOT empty. My first version
        # passed `{"players": {}}`, so the duplicate-check loop iterated
        # nothing and mutating its condition to `if True:` SURVIVED. A
        # fixture that supplies no candidates cannot test which
        # candidate is chosen. Nemesiux sits here so the loop runs and
        # the username comparison is the only thing letting Kip through.
        state = _state()
        _add(monkeypatch, state, args="@Kip Kipley")
        assert f"{_PRIMARY}:pending_Kip" in state["players"], (
            "/addplayer refused a username nobody on the roster holds")
        assert f"{_PRIMARY}:u1" in state["players"], (
            "adding a new player disturbed the existing seat")
