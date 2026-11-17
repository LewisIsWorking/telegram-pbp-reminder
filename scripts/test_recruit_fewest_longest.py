"""Recruit pick: "fewest players, for longest" (Lewis, 2026-11-17).

Largest shortfall still wins. A tie now goes to the campaign that has sat
at its current player count the longest, read from ``recruit_count_since``.
Before this the tiebreak was the fill ratio, and with every target at 6 the
ratio never separated anyone, so the pick quietly fell to config order.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from test_recruit_focus import _cfg, _pair, _state  # noqa: E402

_NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def _since(state, pid, count, days_ago):
    state.setdefault("recruit_count_since", {})[pid] = {
        "count": count, "since": (_NOW - timedelta(days=days_ago)).isoformat()}
    return state


def _two():
    return _cfg(_pair("C01", "100", target=6), _pair("C02", "200", target=6))


def test_tie_goes_to_the_campaign_stuck_longer():
    from scheduled.recruit_focus import pick_recruit_pair
    state = _state(**{"100": 4, "200": 4})
    _since(state, "100", 4, 3)
    _since(state, "200", 4, 30)
    assert pick_recruit_pair(_two(), state, now=_NOW)["code"] == "C02", (
        "C02 has been at 4 players for 30 days, C01 for 3; config order "
        "must not decide this")


def test_tie_with_no_record_falls_back_to_config_order():
    from scheduled.recruit_focus import pick_recruit_pair
    state = _state(**{"100": 4, "200": 4})
    assert pick_recruit_pair(_two(), state, now=_NOW)["code"] == "C01"


def test_unknown_campaign_is_seeded_now_not_back_dated():
    from scheduled.recruit_focus import pick_recruit_pair
    state = _state(**{"100": 4, "200": 4})
    _since(state, "100", 4, 1)
    assert pick_recruit_pair(_two(), state, now=_NOW)["code"] == "C01", (
        "C01 has waited a day; C02 has no record, so its clock starts now")
    assert state["recruit_count_since"]["200"] == {
        "count": 4, "since": _NOW.isoformat()}


def test_a_count_change_resets_the_clock():
    from scheduled.recruit_focus import pick_recruit_pair
    state = _state(**{"100": 4, "200": 4})
    _since(state, "100", 4, 3)
    _since(state, "200", 5, 30)  # was 5 for 30 days, has just dropped to 4
    assert pick_recruit_pair(_two(), state, now=_NOW)["code"] == "C01"
    assert state["recruit_count_since"]["200"] == {
        "count": 4, "since": _NOW.isoformat()}


def test_an_unchanged_count_keeps_its_clock():
    from scheduled.recruit_focus import pick_recruit_pair
    state = _state(**{"100": 4, "200": 4})
    _since(state, "200", 4, 30)
    before = dict(state["recruit_count_since"]["200"])
    pick_recruit_pair(_two(), state, now=_NOW)
    pick_recruit_pair(_two(), state, now=_NOW + timedelta(days=1))
    assert state["recruit_count_since"]["200"] == before


def test_shortfall_still_beats_time():
    from scheduled.recruit_focus import pick_recruit_pair
    state = _state(**{"100": 3, "200": 5})
    _since(state, "100", 3, 1)
    _since(state, "200", 5, 300)
    assert pick_recruit_pair(_two(), state, now=_NOW)["code"] == "C01"


def test_fill_ratio_breaks_a_tie_on_time():
    from scheduled.recruit_focus import pick_recruit_pair
    cfg = _cfg(_pair("C01", "100", target=6), _pair("C02", "200", target=2))
    state = _state(**{"100": 5, "200": 1})
    assert pick_recruit_pair(cfg, state, now=_NOW)["code"] == "C02"


def test_tiers_still_hold_against_time():
    from scheduled.recruit_focus import pick_recruit_pair
    tiered = _pair("C10", "300", target=6, disabled=["recruitment"])
    tiered["recruit_tier"] = 1
    cfg = _cfg(_pair("C01", "100", target=6), tiered)
    state = _state(**{"100": 5, "300": 5})
    _since(state, "100", 5, 1)
    _since(state, "300", 5, 300)
    assert pick_recruit_pair(cfg, state, now=_NOW)["code"] == "C01", (
        "C10 has waited far longer, but tier 0 is not full")


def test_later_tier_banks_its_time_while_it_waits():
    """Tracked while queued, so its wait counts once its tier opens."""
    from scheduled.recruit_focus import pick_recruit_pair
    tiered = _pair("C10", "300", target=6)
    tiered["recruit_tier"] = 1
    cfg = _cfg(_pair("C01", "100", target=6), tiered)
    state = _state(**{"100": 5, "300": 2})
    pick_recruit_pair(cfg, state, now=_NOW)
    assert state["recruit_count_since"]["300"]["count"] == 2


def test_never_recruiting_campaign_is_not_tracked():
    from scheduled.recruit_focus import pick_recruit_pair
    cfg = _cfg(_pair("C01", "100", target=6),
               _pair("C08", "400", target=6, disabled=["recruitment"]))
    state = _state(**{"100": 5, "400": 0})
    pick_recruit_pair(cfg, state, now=_NOW)
    assert "400" not in state["recruit_count_since"]


def test_state_key_is_declared():
    from state_schema import DEFAULT_STATE, PARTITIONS
    assert any("recruit_count_since" in keys for keys in PARTITIONS.values())
    assert DEFAULT_STATE["recruit_count_since"] == {}
