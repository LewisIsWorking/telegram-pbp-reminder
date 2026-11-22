"""The GM's own session poll vote is named as the GM, never an unknown voter (2026-11-22).

The bot posted "Unknown voter in C01 poll: uid 1698524397" and listed the GM's vote by raw uid.
"""

from unittest.mock import patch

from dispatch.poll_notify import _voter_mention, capture_unknown_voter, identify_unknown_voter
from dispatch.poll_tally import _uid_mention

GM = "1698524397"


def _config(**extra):
    return {"gm_user_ids": [int(GM)], "gm_username": "PathWars",
            "topic_pairs": [{"code": "C01", "poll_user_ids": [111], "poll_user_names": {}}], **extra}


def test_the_gm_vote_is_named_as_the_gm_in_the_vote_line_and_the_tally():
    assert _voter_mention(GM, "Path", _config(), {"players": {}}) == "@PathWars"
    assert _uid_mention(GM, _config(), {"players": {}}) == "@PathWars"


def test_gm_user_id_alone_is_enough():
    config = {"gm_user_id": int(GM), "topic_pairs": []}
    assert _uid_mention(GM, config, {"players": {}}) == "@PathWars"


def test_the_gm_is_never_captured_or_alerted_as_an_unknown_voter():
    state = {}
    with patch("dispatch.poll_notify.tg.send_message") as send:
        capture_unknown_voter(GM, "C01", _config(), state, [1])
    assert state.get("poll_unknown_voters", {}).get("C01", []) == []
    send.assert_not_called()


def test_a_real_unknown_player_is_still_captured():
    state = {}
    with patch("dispatch.poll_notify.tg.send_message"), \
         patch("dispatch.poll_notify.route", return_value=(-1, 2)):
        capture_unknown_voter("555", "C01", _config(), state, [0])
    assert state["poll_unknown_voters"]["C01"] == ["555"]


def test_a_gm_captured_before_the_fix_is_dropped_quietly_when_they_post():
    state = {"poll_unknown_voters": {"C01": [GM, "555"]}}
    with patch("dispatch.poll_notify.tg.send_message") as send:
        identify_unknown_voter(GM, "PathWars", "Path", "C01", _config(), state)
    assert state["poll_unknown_voters"]["C01"] == ["555"]
    assert GM not in state.get("poll_identified_voters", {}), "the GM must never be promoted into a player slot"
    send.assert_not_called()
