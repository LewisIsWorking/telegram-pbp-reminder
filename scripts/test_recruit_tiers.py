"""Recruit tiers — reserve campaigns wait their turn (2026-08-15).

Asked for after the hard exclusion landed: *"Could C10 pop up but only if
every other campaign has at least 6 players? C08 could also popup but only
if C10 is full."*

So the rule is a strict cascade, not a filter:

    tier 0   the normal queue
    tier 1   C10 — eligible only once every tier-0 campaign is full
    tier 2   C08 — eligible only once C10 is full as well

Precedence is the part worth guarding
-------------------------------------
An explicit ``recruit_tier`` **must** beat ``disabled_features``. C10 and
C08 both still carry ``recruitment`` in ``disabled_features``, deliberately
— that flag keeps the fortnightly ``check_recruitment_needs`` nag switched
off for them, which is behaviour Lewis did not ask to change. If the
disabled check ran first, both tiered campaigns would be unreachable and
the feature would look correct while never firing.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from test_recruit_focus import _cfg, _pair, _state  # noqa: E402


def _tiered(code, pid, tier, target=6, disabled=None):
    p = _pair(code, pid, target=target, disabled=disabled)
    p["recruit_tier"] = tier
    return p


class TestTierResolution:
    def test_default_is_tier_zero(self):
        from scheduled.recruit_focus import recruit_tier
        cfg = _cfg(_pair("C01", "100"))
        assert recruit_tier(cfg["topic_pairs"][0], cfg) == 0

    def test_recruitment_disabled_means_never(self):
        from scheduled.recruit_focus import recruit_tier
        cfg = _cfg(_pair("C01", "100", disabled=["recruitment"]))
        assert recruit_tier(cfg["topic_pairs"][0], cfg) is None

    def test_explicit_tier_beats_disabled_features(self):
        """The live config for C10 and C08 is exactly this shape."""
        from scheduled.recruit_focus import recruit_tier
        cfg = _cfg(_tiered("C10", "100", 1, disabled=["recruitment"]))
        assert recruit_tier(cfg["topic_pairs"][0], cfg) == 1, (
            "an explicit tier must win, or the tiered campaign can never "
            "become eligible")


class TestCascade:
    _CFG = None

    def _cfg3(self):
        return _cfg(_pair("C01", "100", target=6),
                    _tiered("C10", "200", 1, disabled=["recruitment"]),
                    _tiered("C08", "300", 2, target=4,
                            disabled=["warnings", "recruitment"]))

    def test_tier_one_waits_while_tier_zero_is_short(self):
        from scheduled.recruit_focus import pick_recruit_pair
        state = _state(**{"100": 5, "200": 0, "300": 0})
        assert pick_recruit_pair(self._cfg3(), state)["code"] == "C01", (
            "C10 has a bigger gap but tier 0 is not full yet")

    def test_tier_one_becomes_eligible_once_tier_zero_is_full(self):
        from scheduled.recruit_focus import pick_recruit_pair
        state = _state(**{"100": 6, "200": 0, "300": 0})
        assert pick_recruit_pair(self._cfg3(), state)["code"] == "C10"

    def test_tier_two_waits_for_tier_one(self):
        from scheduled.recruit_focus import pick_recruit_pair
        state = _state(**{"100": 6, "200": 5, "300": 0})
        assert pick_recruit_pair(self._cfg3(), state)["code"] == "C10", (
            "C10 still has a seat, so C08 stays queued")

    def test_tier_two_becomes_eligible_once_tier_one_is_full(self):
        from scheduled.recruit_focus import pick_recruit_pair
        state = _state(**{"100": 6, "200": 6, "300": 0})
        assert pick_recruit_pair(self._cfg3(), state)["code"] == "C08"

    def test_everything_full_posts_nothing(self):
        from scheduled.recruit_focus import pick_recruit_pair
        state = _state(**{"100": 6, "200": 6, "300": 4})
        assert pick_recruit_pair(self._cfg3(), state) is None

    def test_one_short_tier_zero_campaign_holds_the_whole_queue(self):
        """Even a single open seat in tier 0 outranks an empty reserve."""
        from scheduled.recruit_focus import pick_recruit_pair
        cfg = _cfg(_pair("C01", "100", target=6), _pair("C02", "150", target=6),
                   _tiered("C10", "200", 1))
        state = _state(**{"100": 6, "150": 5, "200": 0})
        assert pick_recruit_pair(cfg, state)["code"] == "C02"


class TestMessage:
    def test_reserve_campaigns_say_so(self):
        from scheduled.recruit_focus import build_recruit_message
        cfg = _cfg(_pair("C01", "100", target=6),
                   _tiered("C10", "200", 1, disabled=["recruitment"]))
        text, _ = build_recruit_message(cfg, _state(**{"100": 6, "200": 0}))
        assert "Now open for new players" in text
        # Reworded 2026-08-17 for a player audience: "tier" is internal
        # scheduling and the number means nothing to a reader who is
        # being invited to join. Asserting its ABSENCE, because the
        # jargon creeping back is the regression worth catching.
        assert "tier" not in text.lower()
        assert "the campaigns ahead of it are full" in text

    def test_normal_campaigns_do_not(self):
        from scheduled.recruit_focus import build_recruit_message
        cfg = _cfg(_pair("C01", "100", target=6))
        text, _ = build_recruit_message(cfg, _state(**{"100": 5}))
        assert "Now open for new players" not in text

    def test_count_covers_the_eligible_tier_only(self):
        """Two short tier-0 campaigns, one queued reserve: the count is 2."""
        from scheduled.recruit_focus import build_recruit_message
        cfg = _cfg(_pair("C01", "100", target=6), _pair("C02", "150", target=6),
                   _tiered("C10", "200", 1))
        text, _ = build_recruit_message(cfg, _state(**{"100": 5, "150": 4,
                                                    "200": 0}))
        assert "2 campaigns currently recruiting" in text, text
