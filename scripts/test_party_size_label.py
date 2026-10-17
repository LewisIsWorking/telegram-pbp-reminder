"""Player counts say the standard party size is not a cap (2026-10-12).

A player read Riddleport's "8/6" as "full". The count keeps its numbers and
explains them in brackets.
"""

from datetime import datetime, timedelta, timezone

from helpers_pkg.party_size import party_count
from test_community_roster import _cfg, _pair, _seat, _state


def test_over_the_standard_size_reads_as_players_not_a_cap():
    assert party_count(8, 6) == "8/6 (8 players, standard party size 6)"


def test_one_player_is_singular():
    assert party_count(1, 6) == "1/6 (1 player, standard party size 6)"


def test_the_community_roster_header_carries_the_bracket():
    from scheduled.community_roster_build import build_community_roster
    now = datetime(2020, 1, 5, 12, 0, tzinfo=timezone.utc)
    seat = _seat("Ada", "25059", username="ada")
    seat["last_post_time"] = (now - timedelta(days=2)).isoformat()
    text = build_community_roster(_cfg(_pair("C01", "25059")), _state(seat), now)
    assert "C01: Camp C01 - 1/6 (1 player, standard party size 6)" in text
