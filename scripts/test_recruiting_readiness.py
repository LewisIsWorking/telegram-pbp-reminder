"""Do not advertise a table nobody is posting at.

The failure this prevents is quiet and slow: the advert works, someone
joins a dormant campaign, nothing happens, they leave inside a month, and
the recruitment log records it as the VENUE failing. A good venue then
gets dropped for a table problem, and the drop looks evidence-based.

⭐ The load-bearing test in this file is
``test_a_permanent_player_silent_for_months_is_not_liveness``. Readiness
must NOT go through ``roster_members._active_players``, which counts a
permanent player no matter when they last posted. That behaviour is
correct for "who is enrolled" and wrong for "is anyone posting", and the
two questions are one refactor away from being merged by accident.
"""

from datetime import datetime, timedelta, timezone

from recruiting import readiness

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)
PAIR = {"code": "C04", "name": "Magni Guard", "pbp_topic_ids": [76799, 144765]}


def _seat(topic, ago_days, uid="1"):
    stamp = (NOW - timedelta(days=ago_days)).isoformat() if ago_days is not None else None
    return {"user_id": uid, "first_name": "P", "campaign_name": "Magni Guard",
            "pbp_topic_id": str(topic), "last_post_time": stamp}


def _state(*seats):
    return {"players": {f"{s['pbp_topic_id']}:{s['user_id']}": s
                        for s in seats}}


class TestLiveness:
    def test_a_table_posting_this_week_is_ready(self):
        # ⭐ can-fail counterpart: without this, a warning hard-coded to
        # always fire would pass every other test in the file.
        state = _state(_seat(76799, 2))
        assert not readiness.is_quiet(PAIR, state, NOW)
        assert readiness.warning(PAIR, state, NOW) == ""

    def test_a_table_silent_for_three_weeks_is_quiet(self):
        state = _state(_seat(76799, 21))
        assert readiness.is_quiet(PAIR, state, NOW)
        assert "quiet" in readiness.warning(PAIR, state, NOW)

    def test_exactly_at_the_threshold_is_quiet(self):
        # The boundary is inclusive on purpose: a fortnight with nothing
        # is already the condition being warned about.
        state = _state(_seat(76799, readiness.QUIET_DAYS))
        assert readiness.is_quiet(PAIR, state, NOW)

    def test_a_day_under_the_threshold_is_not(self):
        state = _state(_seat(76799, readiness.QUIET_DAYS - 1))
        assert not readiness.is_quiet(PAIR, state, NOW)

    def test_the_newest_seat_decides(self):
        # ⚠️ One dormant player must not condemn a table where someone
        # else is posting, and one active player is enough to clear it.
        state = _state(_seat(76799, 60, uid="a"), _seat(76799, 1, uid="b"))
        assert not readiness.is_quiet(PAIR, state, NOW)

    def test_a_second_table_counts_as_alive(self):
        # This campaign has two pbp topics. _shortfall looks at [0] only,
        # which is a seat-counting choice; liveness must consider both or
        # a busy second table reads as silence.
        state = _state(_seat(144765, 1))
        assert not readiness.is_quiet(PAIR, state, NOW)

    def test_another_campaigns_seats_do_not_count(self):
        state = _state(_seat(99999, 1))
        assert readiness.is_quiet(PAIR, state, NOW)


class TestTheAbsentCases:
    def test_no_seats_at_all_is_quiet_not_fine(self):
        # ⭐⭐ None is "no player has ever posted", which is emphatically
        # not "0 days ago". Treating the absent case as healthy would
        # silence the warning exactly when it is most deserved: an empty
        # table being advertised to strangers.
        assert readiness.days_since_a_player_posted(PAIR, {}, NOW) is None
        assert readiness.is_quiet(PAIR, {}, NOW)
        assert "ever posted" in readiness.warning(PAIR, {}, NOW)

    def test_a_seat_that_never_posted_is_ignored_not_counted_as_now(self):
        state = _state(_seat(76799, None))
        assert readiness.days_since_a_player_posted(PAIR, state, NOW) is None

    def test_a_garbage_timestamp_is_skipped_rather_than_crashing(self):
        seat = _seat(76799, 1)
        seat["last_post_time"] = "not a date"
        assert readiness.days_since_a_player_posted(PAIR, _state(seat), NOW) is None

    def test_a_naive_timestamp_is_read_as_utc(self):
        seat = _seat(76799, 3)
        seat["last_post_time"] = (NOW - timedelta(days=3)).replace(
            tzinfo=None).isoformat()
        measured = readiness.days_since_a_player_posted(PAIR, _state(seat), NOW)
        assert 2.9 < measured < 3.1

    def test_a_future_timestamp_does_not_go_negative(self):
        state = _state(_seat(76799, -5))
        assert readiness.days_since_a_player_posted(PAIR, state, NOW) == 0.0


class TestPermanenceIsNotLiveness:
    def test_a_permanent_player_silent_for_months_is_not_liveness(self):
        # ⭐⭐ The real case, 2026-08-25. C04 read as "3/6 players" while
        # its three seats were silent 21, 24 and 56 days, because the
        # 56-day one is flagged permanent and _active_players counts
        # permanent players unconditionally. That flag answers "is this
        # person a member"; it cannot answer "is this table moving".
        # If this test ever fails because someone routed readiness
        # through _active_players, the fix is to route it back.
        seat = _seat(76799, 56)
        seat["permanent"] = True
        state = _state(seat)
        assert readiness.is_quiet(PAIR, state, NOW)


class TestTheWarningReachesTheMessage:
    def _venue(self, vid):
        return {"id": vid, "name": vid.title(), "kind": "forum",
                "status": "candidate", "cooldown_days": 7,
                "cooldown_source": "assumed", "format": {}}

    def _build(self, monkeypatch, state):
        from commands import recruit_ads
        monkeypatch.setattr(recruit_ads, "_focus_pair", lambda c, s: PAIR)
        return recruit_ads.build_recruit_ads({}, state, NOW,
                                             [self._venue("paizo")])

    def test_a_quiet_table_warns_in_the_message(self, monkeypatch):
        # ⭐ Proven reachable, not merely correct: a readiness module
        # nothing calls is the same bug in a nicer shape.
        message = self._build(monkeypatch, _state(_seat(76799, 30)))
        assert "⚠️" in message and "quiet" in message

    def test_a_live_table_says_nothing_about_being_quiet(self, monkeypatch):
        message = self._build(monkeypatch, _state(_seat(76799, 1)))
        assert "quiet" not in message

    def test_the_warning_comes_before_the_venues(self, monkeypatch):
        # A caution printed under the venue list and the "post now"
        # instruction is read second, if at all.
        message = self._build(monkeypatch, _state(_seat(76799, 30)))
        assert message.index("quiet") < message.index("Paizo")

    def test_the_campaign_is_still_named(self, monkeypatch):
        message = self._build(monkeypatch, _state(_seat(76799, 1)))
        assert "C04: Magni Guard" in message


class TestTheShippedCatalogue:
    def test_foundry_is_a_venue_because_these_games_run_on_foundry(self):
        # ⚠️ Was rejected on 2026-08-20 by generalising Roll20's "must
        # play on Roll20" rule to Foundry. These campaigns DO run on
        # Foundry, so the generalisation was wrong. Pinned so the
        # rejection is not quietly reinstated.
        from recruiting import catalogue
        venue = catalogue.by_id(catalogue.load(), "foundry-lfg")
        assert venue and venue["status"] != "rejected"
        assert venue in catalogue.postable(catalogue.load())

    def test_roll20_stays_rejected(self):
        # can-fail counterpart: the correction above is specific to
        # Foundry and must not have re-opened the venue whose rules
        # genuinely exclude this game.
        from recruiting import catalogue
        venue = catalogue.by_id(catalogue.load(), "roll20-lfg")
        assert venue["status"] == "rejected"
