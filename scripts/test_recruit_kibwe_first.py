"""Kibwe recruits first whenever it is under 6 players (Lewis, 2026-10-08).

*"If Kibwe falls under 6 players, it has priority recruitment."*

Done with the existing tier cascade rather than a new flag: C06 sits in
tier -1, below the normal queue, so while it is short it is the only
eligible campaign, and once it has 6 it drops out and the cascade carries
on as before. Its own ``roster_target`` of 6 pins the threshold, so the
shared ladder raising everyone else's target does not move Kibwe's.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from test_recruit_focus import _cfg, _pair, _state  # noqa: E402

_CONFIG = os.path.join(os.path.dirname(__file__), "..", "config.json")


def _cfg_with_kibwe():
    kibwe = _pair("C06", "500", target=6)
    kibwe["recruit_tier"] = -1
    c01 = _pair("C01", "100", target=6)
    c10 = _pair("C10", "200", target=6)
    c10["recruit_tier"] = 1
    return _cfg(kibwe, c01, c10)


def test_kibwe_under_six_beats_a_bigger_gap_elsewhere():
    from scheduled.recruit_focus import pick_recruit_pair
    state = _state(**{"500": 5, "100": 1, "200": 0})
    assert pick_recruit_pair(_cfg_with_kibwe(), state)["code"] == "C06"


def test_kibwe_at_six_steps_aside():
    from scheduled.recruit_focus import pick_recruit_pair
    state = _state(**{"500": 6, "100": 1, "200": 0})
    assert pick_recruit_pair(_cfg_with_kibwe(), state)["code"] == "C01"


def test_kibwe_advert_does_not_claim_the_others_are_full():
    """Tier -1 is truthy; the reserve wording is for tiers above 0 only."""
    from scheduled.recruit_focus import build_recruit_message
    text, pair = build_recruit_message(_cfg_with_kibwe(),
                                       _state(**{"500": 5, "100": 1, "200": 0}))
    assert pair["code"] == "C06"
    assert "Now open for new players" not in text


def test_real_config_puts_kibwe_first_at_six():
    with open(_CONFIG, encoding="utf-8") as fh:
        config = json.load(fh)
    kibwe = next(p for p in config["topic_pairs"] if p.get("code") == "C06")
    others = [p.get("recruit_tier", 0) for p in config["topic_pairs"]
              if p.get("code") != "C06"]
    assert kibwe["roster_target"] == 6
    assert kibwe["recruit_tier"] < min(others)
