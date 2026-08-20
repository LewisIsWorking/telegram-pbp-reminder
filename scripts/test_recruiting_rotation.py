"""Cooldowns, rotation order, and the never/zero distinction.

The rotation exists to post in more places WITHOUT getting thrown out of
any of them, so the tests that matter here are the ones about not posting
too soon, and about telling "never tried" apart from "just used".
"""

from datetime import datetime, timedelta, timezone

import pytest

from recruiting import catalogue, log, rotation

NOW = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)


def _venue(vid, cooldown=7, status="candidate", source="assumed"):
    return {"id": vid, "name": vid.title(), "kind": "forum",
            "status": status, "cooldown_days": cooldown,
            "cooldown_source": source, "format": {}}


class TestDaysSince:
    def test_never_is_none_not_zero(self):
        # ⭐ The distinction the whole rotation rests on. Returning 0.0 for
        # a venue nobody has ever posted to would make it look freshly
        # used and suppress it permanently, which is the exact opposite of
        # what an untried venue deserves.
        assert rotation.days_since(None, NOW) is None

    def test_measures_elapsed_days(self):
        assert rotation.days_since((NOW - timedelta(days=3)).isoformat(),
                                   NOW) == pytest.approx(3.0)

    def test_a_naive_timestamp_is_treated_as_utc(self):
        naive = (NOW - timedelta(days=2)).replace(tzinfo=None).isoformat()
        assert rotation.days_since(naive, NOW) == pytest.approx(2.0)

    def test_garbage_is_none_rather_than_crashing(self):
        assert rotation.days_since("not a date", NOW) is None


class TestIsDue:
    def test_an_untried_venue_is_due(self):
        assert rotation.is_due(_venue("a"), {}, NOW)

    def test_not_due_inside_the_cooldown(self):
        state = {}
        log.record_post(state, "a", NOW - timedelta(days=3))
        assert not rotation.is_due(_venue("a", cooldown=7), state, NOW)

    def test_due_again_once_the_cooldown_has_passed(self):
        state = {}
        log.record_post(state, "a", NOW - timedelta(days=8))
        assert rotation.is_due(_venue("a", cooldown=7), state, NOW)

    def test_exactly_at_the_cooldown_is_due(self):
        state = {}
        log.record_post(state, "a", NOW - timedelta(days=7))
        assert rotation.is_due(_venue("a", cooldown=7), state, NOW)

    def test_the_most_recent_post_wins(self):
        # ⚠️ Two posts to one venue: the OLD one must not make it due.
        state = {}
        log.record_post(state, "a", NOW - timedelta(days=30))
        log.record_post(state, "a", NOW - timedelta(days=1))
        assert not rotation.is_due(_venue("a", cooldown=7), state, NOW)


class TestDueVenues:
    def test_untried_venues_come_first(self):
        state = {}
        log.record_post(state, "old", NOW - timedelta(days=90))
        due = rotation.due_venues(state, NOW,
                                  [_venue("old"), _venue("fresh")])
        assert due[0]["id"] == "fresh"

    def test_then_whichever_waited_longest(self):
        state = {}
        log.record_post(state, "a", NOW - timedelta(days=90))
        log.record_post(state, "b", NOW - timedelta(days=30))
        due = rotation.due_venues(state, NOW, [_venue("b"), _venue("a")])
        assert [v["id"] for v in due] == ["a", "b"]

    def test_rejected_venues_never_appear(self):
        # ⭐ can-fail counterpart: they stay in the catalogue on purpose so
        # the reasoning is preserved, so the filter is what keeps them out.
        due = rotation.due_venues(state={}, now=NOW,
                                  venues=[_venue("no", status="rejected")])
        assert due == []

    def test_capped_so_the_list_stays_actionable(self):
        many = [_venue(f"v{i}") for i in range(9)]
        assert len(rotation.due_venues({}, NOW, many)) == rotation.MAX_SUGGESTIONS

    def test_cooling_venues_are_excluded(self):
        state = {}
        log.record_post(state, "a", NOW - timedelta(days=1))
        assert rotation.due_venues(state, NOW, [_venue("a", cooldown=7)]) == []


class TestWaitingVenues:
    def test_reports_days_remaining_soonest_first(self):
        state = {}
        log.record_post(state, "a", NOW - timedelta(days=1))   # 6 left
        log.record_post(state, "b", NOW - timedelta(days=5))   # 2 left
        rows = rotation.waiting_venues(state, NOW, [_venue("a"), _venue("b")])
        assert [v["id"] for v, _ in rows] == ["b", "a"]
        assert rows[0][1] == pytest.approx(2.0)

    def test_untried_venues_are_not_waiting(self):
        assert rotation.waiting_venues({}, NOW, [_venue("a")]) == []


class TestTheMessageNamesItsOwnArguments:
    def test_every_due_venue_shows_the_id_the_next_command_needs(self):
        # ⭐ The message ends with "/recruitposted <venue-id>". If the ids
        # are not on screen the instruction is unusable without opening
        # the JSON by hand, which is exactly the sort of control that
        # names an action it does not give you the means to perform.
        from commands.recruit_ads import build_recruit_ads
        venues = [_venue("alpha"), _venue("beta")]
        message = build_recruit_ads({}, {}, NOW, venues)
        assert "id: alpha" in message
        assert "id: beta" in message

    def test_an_assumed_cooldown_is_labelled_as_a_guess(self):
        # ⚠️ An operator who believes an assumed 7 days is a real rule
        # will shorten it when impatient, and that is how the one venue
        # that works gets lost.
        from commands.recruit_ads import build_recruit_ads
        message = build_recruit_ads({}, {}, NOW,
                                    [_venue("a", source="assumed")])
        assert "ASSUMED" in message

    def test_a_stated_rule_is_not_labelled_a_guess(self):
        from commands.recruit_ads import build_recruit_ads
        message = build_recruit_ads({}, {}, NOW,
                                    [_venue("a", cooldown=1, source="rule")])
        assert "stated rule" in message
        assert "ASSUMED" not in message


class TestTheRealCatalogue:
    def test_it_loads_and_validates(self):
        # ⭐ The shipped file must satisfy its own validator. Otherwise the
        # rotation raises on the first real invocation, in production.
        venues = catalogue.load()
        assert len(venues) >= 5

    def test_every_assumed_cooldown_respects_the_floor(self):
        for venue in catalogue.load():
            if venue["cooldown_source"] == "assumed":
                assert venue["cooldown_days"] >= catalogue.MIN_ASSUMED_COOLDOWN_DAYS

    def test_the_one_stated_rule_is_recorded_as_such(self):
        # r/lfg states one post per 24h. It is the only short cooldown in
        # the file, and it is short because it is a real rule.
        lfg = catalogue.by_id(catalogue.load(), "r-lfg")
        assert lfg["cooldown_source"] == "rule"
        assert lfg["cooldown_days"] == 1

    def test_something_is_actually_postable(self):
        assert catalogue.postable(catalogue.load())
