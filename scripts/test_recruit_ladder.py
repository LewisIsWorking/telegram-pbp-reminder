"""The recruiting ladder: once everyone clears a rung, the bar moves up.

COVERS  ``roster_members.effective_target`` and RECRUIT_LADDER.
MISSES  whether 8 is the right second rung. That is Lewis's call, not a
        fact a test can settle.
PROVEN  by ``test_the_ladder_can_fail``.

Split from ``test_recruit_mirror.py`` on 2026-08-18 at 238 lines. That
file owns WHERE the advert goes and how long each copy lives; this one
owns WHAT NUMBER every campaign is being measured against. Two questions
that happened to arrive in the same request.

⚠️ The ladder returns the rung to AIM FOR, not the rung already reached.
With every campaign on 6 the answer is 8 - that is the whole point, and
the first implementation got it backwards.
"""
import pytest

from commands.roster_members import RECRUIT_LADDER, effective_target


def _ladder_cfg(*counts):
    return {"topic_pairs": [
        {"code": f"C{i}", "pbp_topic_ids": [100 + i]} for i in range(len(counts))]}


def _ladder_state(*counts):
    players = {}
    for i, n in enumerate(counts):
        for j in range(n):
            players[f"{i}-{j}"] = {"pbp_topic_id": str(100 + i),
                                   "permanent": True}
    return {"players": players}


@pytest.mark.parametrize("counts,expected", [
    ((0, 0), 6),        # nothing near the bar
    ((6, 5), 6),        # one short campaign holds it
    ((6, 6), 8),        # everyone cleared 6 -> aim for 8
    ((8, 8), 8),        # top of the ladder, stays there
    ((9, 8), 8),        # overshooting does not invent a rung
    ((6, 0), 6),        # ⚠️ a campaign at ZERO must not raise the bar
])
def test_the_bar_rises_only_when_everyone_clears_it(counts, expected):
    assert effective_target(_ladder_cfg(*counts), _ladder_state(*counts)) == expected


def test_a_campaign_that_never_recruits_neither_blocks_nor_satisfies():
    cfg = _ladder_cfg(6, 6)
    cfg["topic_pairs"].append({"code": "C08", "pbp_topic_ids": [999],
                               "disabled_features": ["recruitment"]})
    assert effective_target(cfg, _ladder_state(6, 6)) == 8


def test_an_explicit_roster_target_opts_that_pair_out():
    cfg = _ladder_cfg(6, 6)
    cfg["topic_pairs"][0]["roster_target"] = 4
    assert effective_target(cfg, _ladder_state(6, 6)) == 8


def test_the_ladder_can_fail():
    """One campaign one short must hold the whole bar at 6. If this ever
    returns 8, the ladder has stopped checking every campaign."""
    assert effective_target(_ladder_cfg(6, 5), _ladder_state(6, 5)) == 6
    assert RECRUIT_LADDER[0] == 6 and RECRUIT_LADDER[-1] == 8
