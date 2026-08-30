"""One GM per campaign, and the GM does not also hold a seat in it.

Lewis, 2026-08-30, when Anthony took over C08 Theria from Link: *"Each
campaign only has 1 GM."* Stated as a rule, so it is written down as one.

Why a pair-level list is easy to get wrong
------------------------------------------
``gm_ids_for_campaign`` **replaces** the global list when a pair has its
own, it does not merge. That is the same shape as the GitHub branch
protection ``PUT`` that cost an afternoon on 2026-08-27: an API that
looks additive and is not. C08 is the only campaign with its own list,
and the consequence is that the global GM has no GM rights there at all,
which is correct and is not obvious from reading the config.

``test_a_pair_level_list_replaces_rather_than_merges`` pins that
semantic, because "fixing" it into a merge would silently hand every
campaign's GM rights to everyone in the global list.

The second invariant, and why it is not cosmetic
-------------------------------------------------
``track_message`` skips ``_track_player`` for anyone in ``gm_ids``, so a
GM never accrues a player record by posting. A GM who nonetheless has one
is a leftover from before they were GM, and it is not inert: it occupies
a seat in the roster count, appears in the recruit advert's player list,
and shows up in the weekly community roster as a quiet seat.

C08 was in exactly that state until 2026-08-30. Link GM'd it and held a
seat in it, silent 180 days, so Theria read one seat larger than it was.
"""

import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(__file__))

_ROOT = pathlib.Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _config() -> dict:
    return json.loads((_ROOT / "config.json").read_text(encoding="utf-8"))


def _players() -> dict:
    path = _ROOT / "data" / "state" / "players.json"
    return json.loads(path.read_text(encoding="utf-8")).get("players", {})


def _pairs() -> list:
    return _config().get("topic_pairs", [])


class TestTheScanWorks:
    def test_there_are_campaigns_to_check(self):
        # ⭐ Without this, a config that failed to load would make every
        # assertion below pass against an empty list.
        assert len(_pairs()) >= 5, "config parsed too few campaigns to trust"

    def test_at_least_one_pair_has_its_own_gm_list(self):
        # ⭐ The override case is the one worth guarding, so if it ever
        # stops existing this file has quietly stopped testing anything.
        assert [p for p in _pairs() if "gm_user_ids" in p], (
            "no campaign overrides the GM list any more; either delete "
            "this file or it is now checking nothing")


class TestExactlyOneGM:
    def test_every_campaign_resolves_to_a_single_gm(self):
        import helpers
        offenders = {}
        for pair in _pairs():
            pid = str(pair["pbp_topic_ids"][0])
            gms = helpers.gm_ids_for_campaign(_config(), pid)
            if len(gms) != 1:
                offenders[pair.get("code", pid)] = sorted(gms)
        assert not offenders, (
            f"Lewis, 2026-08-30: 'Each campaign only has 1 GM.' These "
            f"resolve to a different number: {offenders}")

    def test_the_global_list_is_a_single_gm_too(self):
        # It is the fallback for every campaign without its own, so a
        # second entry there is a second GM for eight campaigns at once.
        assert len(_config().get("gm_user_ids", [])) == 1


class TestTheOverrideReplaces:
    def test_a_pair_level_list_replaces_rather_than_merges(self):
        # ⛔ The trap. If this is ever "fixed" into a union, the global
        # GM silently regains rights in every campaign that deliberately
        # named somebody else.
        import helpers
        cfg = {"gm_user_ids": [111],
               "topic_pairs": [{"code": "CX", "pbp_topic_ids": [900],
                                "gm_user_ids": [222]}]}
        assert helpers.gm_ids_for_campaign(cfg, "900") == {"222"}

    def test_a_pair_without_its_own_list_inherits_the_global_one(self):
        # can-fail counterpart: without this, a function that returned
        # the pair list unconditionally would pass the test above.
        import helpers
        cfg = {"gm_user_ids": [111],
               "topic_pairs": [{"code": "CX", "pbp_topic_ids": [900]}]}
        assert helpers.gm_ids_for_campaign(cfg, "900") == {"111"}


class TestAGMDoesNotAlsoHoldASeat:
    def test_no_campaigns_gm_is_in_its_own_roster(self):
        # ⭐⭐ Would have FAILED before 2026-08-30: Link GM'd C08 Theria
        # and held a seat in it, silent 180 days, so the campaign read one
        # seat larger than it was in /roster, in the recruit advert and in
        # the weekly community roster.
        import helpers
        config, players = _config(), _players()
        clashes = {}
        for pair in _pairs():
            pid = str(pair["pbp_topic_ids"][0])
            gms = helpers.gm_ids_for_campaign(config, pid)
            seated = {str(p.get("user_id")) for p in players.values()
                      if str(p.get("pbp_topic_id")) == pid}
            both = gms & seated
            if both:
                clashes[pair.get("code", pid)] = sorted(both)
        assert not clashes, (
            f"these campaigns' GMs also hold a player seat in them: "
            f"{clashes}. A GM never accrues a record by posting "
            f"(track_message skips them), so this is a leftover from "
            f"before they were GM, and it pads the roster count. Remove "
            f"the seat, or the GM is the wrong person.")

    def test_the_roster_is_readable_at_all(self):
        # ⭐ can-fail counterpart. An unreadable or empty players file
        # would make the clash scan pass by comparing against nothing.
        assert len(_players()) > 10, "players.json looks empty or unreadable"
