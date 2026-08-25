"""Which untried venue gets suggested first.

Split out of ``test_recruiting_rotation.py`` on 2026-08-25 rather than
appended to it: that file was at 199 of the 200-line limit, and a file
sitting one line under the ceiling is a file nobody can safely touch.

Every untried venue ties on "never posted", so before this the tie fell
through to position in ``recruitment_venues.json`` and ``/recruitads``
showed the first three in the file rather than the three most likely to
work.

⚠️ I first wrote this file claiming a venue appended to the file could
**never** be suggested, and the shipped-catalogue test below refused to
pass. It was right and I was wrong: once a venue is posted to it stops
being untried and drops below the rest, so the untried set drains and
everything is reached in a round or two. The defect is ordering, not
starvation. The overstated version is recorded here because it is the
more tempting story and someone will reach for it again.
"""

from datetime import datetime, timedelta, timezone

from recruiting import catalogue, log, rotation

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)


def _venue(vid, fit="high", cooldown=7):
    return {"id": vid, "name": vid.title(), "kind": "forum",
            "status": "candidate", "cooldown_days": cooldown,
            "cooldown_source": "assumed", "fit": fit, "format": {}}


class TestFitBreaksTies:
    def test_the_better_fit_is_suggested_first(self):
        due = rotation.due_venues({}, NOW, [_venue("meh", fit="medium"),
                                            _venue("good", fit="high")])
        assert [v["id"] for v in due] == ["good", "meh"]

    def test_an_unknown_fit_sorts_last_not_first(self):
        # ⚠️ "unknown" is a real value in the catalogue, used for the two
        # unverified leads. It must not be treated as neutral and slotted
        # ahead of a venue somebody actually assessed.
        due = rotation.due_venues({}, NOW, [_venue("mystery", fit="unknown"),
                                            _venue("meh", fit="medium")])
        assert [v["id"] for v in due] == ["meh", "mystery"]

    def test_a_missing_fit_field_does_not_crash_or_win(self):
        bare = _venue("bare")
        del bare["fit"]
        due = rotation.due_venues({}, NOW, [bare, _venue("good", fit="high")])
        assert [v["id"] for v in due] == ["good", "bare"]


class TestWhatFitMayNotDo:
    def test_fit_cannot_outrank_never_having_been_tried(self):
        # ⭐ The limit that keeps this a search rather than a way of
        # confirming the guess. A venue nobody has tried beats a high-fit
        # one already posted to, because only the untried one can still
        # teach us anything, and `fit` is precisely the guess that
        # posting exists to test.
        state = {}
        log.record_post(state, "proven", NOW - timedelta(days=90))
        due = rotation.due_venues(state, NOW,
                                  [_venue("proven", fit="high"),
                                   _venue("untried", fit="unknown")])
        assert due[0]["id"] == "untried"

    def test_fit_cannot_resurrect_a_cooling_venue(self):
        state = {}
        log.record_post(state, "good", NOW - timedelta(days=1))
        assert rotation.due_venues(state, NOW,
                                   [_venue("good", fit="high")]) == []


class TestAgainstTheShippedCatalogue:
    def test_only_the_best_fits_are_offered_first(self):
        # ⭐⭐ End to end against the shipped file, because the defect was
        # that file order decided the answer. There are four high-fit
        # venues and MAX_SUGGESTIONS is 3, so the assertion is not "which
        # three" but that no lesser fit displaces a better one.
        due = rotation.due_venues({}, NOW, catalogue.load())
        assert [v["fit"] for v in due] == ["high", "high", "high"]

    def test_a_lower_ranked_venue_surfaces_once_the_others_are_used(self):
        # ⭐ The claim the docstring above walks back. Posting to a venue
        # makes it "tried", which sorts it below every untried one, so
        # the queue drains rather than starving anything.
        state = {}
        for vid in ("pf2e-discord-lfg", "paizo-recruitment", "rpg-crossing"):
            log.record_post(state, vid, NOW)
        due = rotation.due_venues(state, NOW, catalogue.load())
        assert "foundry-lfg" in [v["id"] for v in due]

    def test_every_venue_declares_a_fit(self):
        # Not required by the loader, but a venue with no fit sorts last
        # forever, which is a silent way to never try something.
        missing = [v["id"] for v in catalogue.load() if not v.get("fit")]
        assert not missing, f"no fit recorded for {missing}"
