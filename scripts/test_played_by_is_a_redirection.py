"""A character somebody else rolls for is played, not absent.

2026-09-01. Anthony, in the C06 group, explaining why the recruit advert
said 4 when seven characters are at the table:

> *"I mean I guess the fighter/ranger doesn't play much. Right
> @Nemesiux?"* … *"No somebody actually does your rolls for you and all…
> And that somebody is me tragically."*

Measured at that moment: **Horia @Nemesiux, 28.84 days, week 4,
last_warned_week 3**, and ``PLAYER_REMOVE_WEEKS = 4``. He met the removal
condition already; the next hourly run would have swept Lorn out of a
campaign Lorn is currently standing in. The same thing had happened to
**Ji Yun** a week earlier. Their player was removed 2026-08-24 as
Caelum (@Thien_Ming) while Anthony still listed Ji Yun as party.

⭐⭐ **``played_by`` is a REDIRECTION, not an exemption**, and every test
here exists to hold that line. ``permanent`` says *do not measure this
person*. ``played_by`` says *measure them through whoever posts for
them*. A quiet proxy takes the proxied seat down with it, on the same
clock. Anything else inflates the roster in exactly the direction the
recruit advert must not lie.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from commands.roster_members import _ACTIVE_DAYS, _active_players
from players.proxy import effective_post_time, is_proxied, proxy_note

_NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
_PID = "40585"


def _ago(days: float) -> str:
    return (_NOW - timedelta(days=days)).isoformat()


def _seat(name: str, username: str, days: float, **extra) -> dict:
    seat = {"user_id": username, "first_name": name, "username": username,
            "campaign_name": "Kibwe", "pbp_topic_id": _PID,
            "last_post_time": _ago(days), "last_warned_week": 0}
    seat.update(extra)
    return seat


def _state(*seats) -> dict:
    return {"players": {f"{_PID}:{s['username']}": s for s in seats}}


# The real 2026-09-01 pair, names kept so the fixture is recognisable.
def _horia(days=28.84, **kw):
    return _seat("Horia", "Nemesiux", days, **kw)


def _anthony(days=1.55):
    return _seat("Anthony", "MrNegetZ", days)


class TestTheSeatIsCountedThroughItsProxy:
    def test_a_proxied_seat_counts_while_the_proxy_posts(self):
        # ⭐⭐ The bug. Horia at 28.84d is outside the 30d window on his
        # own posting only just, and inside week 4 for removal.
        state = _state(_horia(played_by="MrNegetZ"), _anthony())
        names = {p["first_name"] for p in _active_players(_PID, state, {})}
        assert names == {"Horia", "Anthony"}

    def test_the_effective_time_is_the_proxy_s(self):
        state = _state(_horia(played_by="MrNegetZ"), _anthony())
        seat = state["players"][f"{_PID}:Nemesiux"]
        assert effective_post_time(seat, _PID, state).isoformat() == _ago(1.55)

    def test_without_the_proxy_the_same_seat_is_measured_alone(self):
        # can-fail counterpart: proves the fixture is genuinely near the
        # boundary and the proxy is what moves it.
        state = _state(_horia(), _anthony())
        seat = state["players"][f"{_PID}:Nemesiux"]
        assert effective_post_time(seat, _PID, state).isoformat() == _ago(28.84)


class TestItIsARedirectionNotAnExemption:
    """⭐⭐ The line that separates this from `permanent`."""

    def test_a_quiet_proxy_takes_the_proxied_seat_down_with_it(self):
        # Anthony stops posting for 40 days. BOTH seats go quiet. A
        # feature that kept Horia active here would be `permanent` with
        # extra steps, and would inflate the recruit advert.
        #
        # ⚠️ AMENDED 2026-09-02: Horia's OWN time is now 50d, not the
        # fixture's 28.84d. Resolution takes the LATER of the two since
        # `played_by` began surviving a post, so at 28.84d he was still
        # active on his own account and this asserted the wrong thing.
        # For the proxy to drag him down, he has to be quiet too.
        state = _state(_horia(days=50, played_by="MrNegetZ"),
                       _anthony(days=40))
        assert _active_players(_PID, state, {}) == []

    # ⭐ The other half of this rule (an ACTIVE seat must not be dragged
    # down by a quiet proxy) lives in
    # test_posting_must_not_erase_gm_settings, with the live case that
    # produced it. Not duplicated here.

    def test_the_proxy_itself_is_still_measured_normally(self):
        state = _state(_horia(played_by="MrNegetZ"), _anthony(days=40))
        seat = state["players"][f"{_PID}:MrNegetZ"]
        assert effective_post_time(seat, _PID, state).isoformat() == _ago(40)


class TestABrokenPointerMustNotGrantImmortality:
    """⛔ The failure mode worth breaking a test over."""

    def test_an_unknown_proxy_falls_back_to_the_seat_s_own_time(self):
        # Typo, departed player, renamed account. The seat is measured
        # normally. It must NEVER become "no usable clock, so keep them".
        state = _state(_horia(played_by="SomebodyElse"), _anthony())
        seat = state["players"][f"{_PID}:Nemesiux"]
        assert effective_post_time(seat, _PID, state).isoformat() == _ago(28.84)

    def test_a_seat_with_a_broken_proxy_still_ages_out(self):
        state = _state(_seat("Ghost", "Gone", 400, played_by="Nobody"))
        assert _active_players(_PID, state, {}) == []

    def test_a_proxy_in_a_different_campaign_does_not_count(self):
        # ⚠️ Activity in another game is not evidence this character is
        # being played HERE. The proxy must be on this roster.
        other = _seat("Anthony", "MrNegetZ", 1.0)
        other["pbp_topic_id"] = "107151"
        state = {"players": {f"{_PID}:Nemesiux": _horia(played_by="MrNegetZ"),
                             f"107151:MrNegetZ": other}}
        seat = state["players"][f"{_PID}:Nemesiux"]
        assert effective_post_time(seat, _PID, state).isoformat() == _ago(28.84)

    def test_a_proxy_cycle_terminates(self):
        # One hop only: no recursion, no infinite loop, no exemption.
        # ⚠️ AMENDED 2026-09-02: resolution now takes the LATER of the
        # seat's own time and its proxy's, so a mutual pair both resolve
        # to the more recent of the two (50d). The property that matters
        # is unchanged and asserted last: neither is rescued by the cycle.
        a = _seat("A", "aaa", 50, played_by="bbb")
        b = _seat("B", "bbb", 60, played_by="aaa")
        state = _state(a, b)
        assert effective_post_time(a, _PID, state).isoformat() == _ago(50)
        assert effective_post_time(b, _PID, state).isoformat() == _ago(50)
        assert _active_players(_PID, state, {}) == []


class TestTheRosterSaysWhy:
    def test_a_resolved_proxy_is_named(self):
        state = _state(_horia(played_by="MrNegetZ"), _anthony())
        seat = state["players"][f"{_PID}:Nemesiux"]
        assert proxy_note(seat, _PID, state) == " [played by @MrNegetZ]"

    def test_the_note_reaches_the_posted_roster(self):
        # ⛔ Proven is not reachable. Every other test here calls
        # proxy_note directly, so deleting the call from roster.py's
        # name line survived the mutation harness. This goes through
        # build_roster_campaign, which is what lands in the chat topic
        # after a sweep and is the only version anyone reads.
        from commands.roster import build_roster_campaign
        pair = {"name": "Kibwe", "code": "C06", "chat_topic_id": 21528,
                "pbp_topic_ids": [int(_PID)]}
        state = _state(_horia(played_by="MrNegetZ"), _anthony())
        state["player_history"] = []
        text = build_roster_campaign(pair, {"group_id": -100}, state)
        assert "Horia" in text and "[played by @MrNegetZ]" in text

    def test_an_unresolved_proxy_says_it_is_not_covering_anything(self):
        # ⛔ Silence here would let a GM believe a seat is protected when
        # it is being measured normally and is about to be swept.
        state = _state(_horia(played_by="Ghost"))
        seat = state["players"][f"{_PID}:Nemesiux"]
        note = proxy_note(seat, _PID, state)
        assert "NOT ON THIS ROSTER" in note and "measured normally" in note

    def test_an_ordinary_seat_gets_no_note(self):
        state = _state(_anthony())
        assert proxy_note(state["players"][f"{_PID}:MrNegetZ"], _PID, state) == ""

    def test_is_proxied_reads_the_declaration_not_the_resolution(self):
        # A declared-but-broken proxy is still "proxied" for the purpose
        # of suppressing nudges: the GM said somebody else rolls for
        # them, and that does not stop being true because of a typo.
        assert is_proxied(_horia(played_by="Ghost"))
        assert not is_proxied(_horia())
        assert not is_proxied(_horia(played_by="   "))


class TestPermanentIsUnchanged:
    def test_a_permanent_player_still_counts_with_no_proxy(self):
        # can-fail counterpart for the whole file: the older rule must
        # not have been disturbed by threading a new one through it.
        state = _state(_seat("Perm", "perm", 400, permanent=True))
        assert len(_active_players(_PID, state, {})) == 1

    def test_the_window_is_still_thirty_days(self):
        assert _ACTIVE_DAYS == 30
