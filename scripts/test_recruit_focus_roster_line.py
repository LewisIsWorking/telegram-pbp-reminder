"""The recruit advert names the players who are already at the table.

Lewis, 2026-08-29, on a live C00 Riddleport advert: *"These are great but
could we add a 4th line of 'Current Players:' then their telegram @s?"*

The property worth guarding is not "a line appears"
---------------------------------------------------
It is that **the names and the count cannot disagree**. The advert says
``(4/6 players)`` on one line and lists people on the next, and those two
statements come from one roster resolved once. Nothing about that is
visible in the rendered post, so a later change that filtered the name
list (dropping anyone without a username, say) would produce an advert
that is wrong and reads as right.

``test_the_names_match_the_count`` parses both halves back out of the
finished text and compares them, so the divergence fails a test rather
than reaching the group.

⚠️ Two player records really have no username (2 of 41 on 2026-08-30),
one of them a 2026-08-26 recruit, so the fallback path is live code and
is pinned with a can-fail counterpart below.
"""

import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

_NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
_RATIO = re.compile(r"\((\d+)/(\d+) players\)")
_LABEL = "\U0001f465 Current players: "


def _pair(code, pid, target=6):
    return {"name": f"Camp {code}", "code": code, "chat_topic_id": int(pid) + 1,
            "pbp_topic_ids": [int(pid)], "roster_target": target}


def _cfg(*pairs):
    return {"group_id": -100, "gm_queue_topic_id": 146780,
            "bot_topic_id": 137393, "group_username": "Path_Wars",
            "topic_pairs": list(pairs)}


def _state(pid, people):
    """``people``: ``(first_name, username)`` pairs; a blank username is real.

    ``permanent`` is set for the same reason as in ``test_recruit_focus``:
    ``_active_players`` measures recency against the real wall clock, so a
    non-permanent fixture would rot the day the suite runs late enough.
    """
    players = {}
    for i, (first, username) in enumerate(people):
        record = {"user_id": f"{pid}{i}", "first_name": first,
                  "pbp_topic_id": pid, "last_post_time": _NOW.isoformat(),
                  "permanent": True}
        if username:
            record["username"] = username
        players[f"{pid}_{i}"] = record
    return {"players": players}


_RIDDLEPORT = [("Fuzzy", "fuzzystudios"), ("Neg", "MrNegetZ"),
               ("Horia", "Nemesiux"), ("Sas", "Sasuken09")]


def _advert(people, target=6, pid="66154"):
    from scheduled.recruit_focus import build_recruit_message
    text, _pair_chosen = build_recruit_message(
        _cfg(_pair("C00", pid, target)), _state(pid, people))
    return text


class TestTheRenderer:
    """``recruit_roster_line`` on its own, away from the advert."""

    def test_a_username_becomes_a_mention(self):
        from scheduled.recruit_roster_line import mention
        assert mention({"first_name": "Horia", "username": "Nemesiux"}) \
            == "@Nemesiux"

    def test_no_username_falls_back_to_the_first_name(self):
        # ⭐ Live case, not hypothetical: Volf joined C04 on 2026-08-26
        # with no username set. Named plainly, with no @ that would
        # resolve to nobody and no GM-facing "username unknown" warning.
        from scheduled.recruit_roster_line import mention
        assert mention({"first_name": "Volf"}) == "Volf"

    def test_a_stored_at_sign_is_not_doubled(self):
        from scheduled.recruit_roster_line import mention
        assert mention({"username": "@Ravnos1"}) == "@Ravnos1"

    def test_a_record_with_no_name_at_all_still_renders(self):
        # ⭐⭐ Returning "" here would silently shorten the list and make
        # the advert contradict its own count. "?" matches roster.py.
        from scheduled.recruit_roster_line import mention
        assert mention({"user_id": "9"}) == "?"

    def test_nobody_means_no_line(self):
        from scheduled.recruit_roster_line import current_players_line
        assert current_players_line([]) == ""

    def test_the_order_is_stable_and_case_insensitive(self):
        # Fed deliberately out of order: sorting an already sorted list
        # would assert nothing.
        from scheduled.recruit_roster_line import current_players_line
        line = current_players_line([{"username": "zeta"},
                                     {"first_name": "Alpha"},
                                     {"username": "Beta"}])
        assert line == _LABEL + "Alpha, @Beta, @zeta"


class TestInTheAdvert:
    def test_the_players_are_named(self):
        text = _advert(_RIDDLEPORT)
        assert _LABEL + "@fuzzystudios, @MrNegetZ, @Nemesiux, @Sasuken09" \
            in text

    def test_it_is_the_fourth_line(self):
        """Lewis asked for a position, so the position is pinned."""
        lines = _advert(_RIDDLEPORT).split("\n")
        assert lines[3].startswith(_LABEL), (
            f"expected the roster on line 4, directly under the seat "
            f"count it explains; got {lines[3]!r}")
        assert "seats open" in lines[2]

    def test_the_names_match_the_count(self):
        # ⭐⭐ The one that matters. Both halves are parsed back out of
        # the finished post, so this fails if either side is ever
        # filtered, deduplicated or resolved from a second roster call.
        text = _advert(_RIDDLEPORT)
        seated = int(_RATIO.search(text).group(1))
        names = text.split(_LABEL)[1].split("\n")[0].split(", ")
        assert len(names) == seated, (
            f"the advert says {seated} players and names {len(names)}: "
            f"{names}")

    def test_the_count_is_what_the_fixture_seated(self):
        # can-fail counterpart to the test above, which would pass if
        # the regex and the split both found nothing meaningful.
        assert "(4/6 players)" in _advert(_RIDDLEPORT)

    def test_a_player_without_a_username_is_still_counted_and_named(self):
        text = _advert([("Volf", ""), ("Neg", "MrNegetZ")], target=6)
        assert _LABEL + "@MrNegetZ, Volf" in text
        assert "(2/6 players)" in text, (
            "dropping the unnamed player from the list without dropping "
            "them from the count is the exact bug this file exists for")

    def test_the_fixture_really_lacks_a_username(self):
        # ⭐ Without this, a fixture typo that gave Volf a username would
        # make the fallback test above pass while testing the happy path.
        volf = _state("66154", [("Volf", "")])["players"]["66154_0"]
        assert "username" not in volf

    def test_an_empty_campaign_has_no_roster_line_at_all(self):
        # C10 The Junction really does seat zero players today, and it is
        # tiered rather than excluded, so it can win the advert.
        text = _advert([], target=6)
        assert "Current players" not in text
        assert "(0/6 players)" in text, "the advert itself must still appear"

    def test_the_advert_never_contains_a_blank_line(self):
        # ⭐ Added after a mutation SURVIVED: dropping the `if roster_line`
        # guard appends "" for an empty campaign, and the label test above
        # still passed because "" contains no label. The visible defect is
        # a gap in the middle of the post, so that is what is asserted.
        for people in ([], _RIDDLEPORT):
            lines = _advert(people, target=6).split("\n")
            assert "" not in lines, (
                f"blank line in the advert for {len(people)} players: "
                f"{lines}")
