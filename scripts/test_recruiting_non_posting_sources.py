"""A player can arrive from somewhere you cannot post an advert.

Lewis, 2026-08-27: *"Volf and Alastair Tan are from the PF2e Discord,
Paul is my IRL friend."*

Two of those go straight into the log. The third had nowhere to go.

⛔ Crediting Paul to ``UNKNOWN_VENUE`` would have been a **lie**. Unknown
means "we asked and did not find out", and it exists so that missing
attribution stays visible. Lewis told us exactly where Paul came from.

⭐ **So the catalogue now separates two questions one field was
answering:**

    creditable()   somewhere a player can have come FROM
    postable()     somewhere an advert can GO

Every source was both, right up until one was not. ``rotates: false``
marks the difference, and defaults to true so no existing venue changes.

## Why bother recording it at all

The personal network is historically the highest-converting source for
any small game and the one nobody writes down. Leaving it out does not
make the venue comparison neutral, it makes it **wrong**: the advertised
venues get measured against a total that silently excludes a share of
the real arrivals.
"""

import pytest

from recruiting import catalogue, log


def _venue(vid, rotates=None, **kw):
    v = {"id": vid, "name": vid.title(), "kind": "forum",
         "status": "candidate", "cooldown_days": 7,
         "cooldown_source": "assumed", "fit": "high", "format": {}}
    if rotates is not None:
        v["rotates"] = rotates
    v.update(kw)
    return v


def _write(tmp_path, *venues):
    import json
    path = tmp_path / "v.json"
    path.write_text(json.dumps({"venues": list(venues)}), encoding="utf-8")
    return str(path)


class TestTheTwoQuestions:
    def test_a_non_rotating_source_is_creditable(self):
        venues = [_venue("friends", rotates=False)]
        assert [v["id"] for v in catalogue.creditable(venues)] == ["friends"]

    def test_but_never_postable(self):
        venues = [_venue("friends", rotates=False)]
        assert catalogue.postable(venues) == []

    def test_an_ordinary_venue_is_both(self):
        # ⭐ can-fail counterpart. A filter that excluded everything
        # would satisfy the test above and empty the rotation.
        venues = [_venue("paizo")]
        assert catalogue.postable(venues) and catalogue.creditable(venues)

    def test_absent_rotates_means_true(self):
        # Every venue in the file predates the field. Defaulting to
        # False would have silently emptied the whole rotation.
        assert catalogue.rotates(_venue("paizo"))

    def test_rejected_is_neither(self):
        venues = [_venue("no", status="rejected")]
        assert catalogue.creditable(venues) == []
        assert catalogue.postable(venues) == []

    def test_it_stays_out_of_the_rotation_end_to_end(self):
        # ⭐⭐ Proven through due_venues, not just the filter: a source
        # you cannot post to appearing under "Due now" would send Lewis
        # to advertise at his own friends.
        from datetime import datetime, timezone
        from recruiting import rotation
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        due = rotation.due_venues({}, now, [_venue("friends", rotates=False)])
        assert due == []


class TestTheCatalogueAcceptsIt:
    def test_a_non_rotating_source_needs_no_cooldown(self, tmp_path):
        # A cooldown on something you cannot post to is meaningless, and
        # demanding one only invites a made-up number.
        bare = {"id": "friends", "name": "Friends", "kind": "personal",
                "status": "active", "rotates": False}
        assert catalogue.load(_write(tmp_path, bare))

    def test_a_rotating_venue_still_must_have_one(self, tmp_path):
        # can-fail counterpart: the exemption must not leak.
        bare = {"id": "paizo", "name": "Paizo", "kind": "forum",
                "status": "candidate"}
        with pytest.raises(catalogue.CatalogueError, match="cooldown_days"):
            catalogue.load(_write(tmp_path, bare))

    def test_rotates_must_be_a_boolean(self, tmp_path):
        # ⚠️ "false" as a string is truthy, so a typo would silently put
        # a non-postable source back into the rotation.
        bad = _venue("friends", rotates="false")
        with pytest.raises(catalogue.CatalogueError, match="rotates"):
            catalogue.load(_write(tmp_path, bad))

    def test_the_assumed_floor_still_applies_to_rotating_venues(self, tmp_path):
        bad = _venue("x", cooldown_days=1, cooldown_source="assumed")
        with pytest.raises(catalogue.CatalogueError, match="floor"):
            catalogue.load(_write(tmp_path, bad))


class TestTheRealCredits:
    def _state(self):
        import json
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "data", "state", "trackers.json"),
                  encoding="utf-8") as handle:
            return json.load(handle)

    def test_the_two_discord_arrivals_are_credited_there(self):
        state = self._state()
        names = {j["player"] for j in log.joins_for(state, "pf2e-discord-lfg")}
        assert {"Volf", "Alastair Tan"} <= names

    def test_paul_is_credited_to_the_personal_network(self):
        state = self._state()
        names = {j["player"] for j in log.joins_for(state, "personal-network")}
        assert "Paul Rowan" in names

    def test_nothing_is_unattributed(self):
        # ⭐ The quality signal. Lewis answered for all three, so a
        # non-zero count here means something was recorded as a guess.
        assert log.unattributed(self._state()) == 0

    def test_paul_is_not_credited_to_a_venue_that_earned_it(self):
        # ⛔ The failure this whole file prevents: two real Discord
        # arrivals plus one friend would read as three, and the Discord
        # advert would look 50% better than it was.
        state = self._state()
        discord = {j["player"] for j in log.joins_for(state, "pf2e-discord-lfg")}
        assert "Paul Rowan" not in discord

    def test_every_credited_venue_exists_in_the_catalogue(self):
        # ⭐⭐ Added after a mutation SURVIVED: renaming personal-network
        # in the catalogue left Paul's credit pointing at an id nothing
        # defines. yield_table iterates the CATALOGUE, so such a credit
        # vanishes from the comparison entirely and the arithmetic
        # silently stops adding up. Same shape as the ghost seats left
        # behind by a retired campaign.
        state = self._state()
        known = {v["id"] for v in catalogue.load()} | {log.UNKNOWN_VENUE}
        credited = {j["venue"] for j in log.get_log(state)["joins"]}
        orphans = sorted(credited - known)
        assert not orphans, (
            f"players credited to venues the catalogue does not define: "
            f"{orphans}. They are invisible in /recruityield.")

    def test_every_posted_venue_exists_too(self):
        state = self._state()
        known = {v["id"] for v in catalogue.load()}
        posted = set(log.get_log(state)["posts"])
        orphans = sorted(posted - known)
        assert not orphans, f"posts recorded against unknown venues: {orphans}"

    def test_the_personal_network_shows_in_the_yield_table(self):
        # Stored is not shown. It must reach the comparison, or the
        # advertised venues are measured against an incomplete total.
        from commands.recruit_ads import build_recruit_yield
        assert "Personal network" in build_recruit_yield(self._state())

    def test_it_reports_the_player_rather_than_never_posted(self):
        # ⭐⭐ The first render said "Personal network: never posted"
        # while Paul was the only arrival credited to it. Literally true
        # and exactly backwards: the branch keyed on posts, and a source
        # with no posts by definition looked like a source with no
        # results. Reaching the table is not the same as being counted.
        from commands.recruit_ads import build_recruit_yield
        line = next(l for l in build_recruit_yield(self._state()).splitlines()
                    if "Personal network" in l)
        assert "never posted" not in line
        assert "1 player" in line

    def test_a_real_venue_with_no_posts_still_says_never_posted(self):
        # can-fail counterpart: the new branch must not swallow the
        # never/zero distinction that the rest of the table rests on.
        from commands.recruit_ads import build_recruit_yield
        line = next(l for l in build_recruit_yield(self._state()).splitlines()
                    if "Paizo" in l)
        assert "never posted" in line
