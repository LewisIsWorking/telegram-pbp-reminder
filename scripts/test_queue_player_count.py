"""Player counts on the GM queue's campaign lines (2026-10-20).

Lewis: "Can we add campaign player counts to the GM queue?" The target is
always 6; more than 6 is good and carries no warning.

Every test pins ``now`` to 2020. Posts are dated relative to it, so code
that read the real clock instead would see every player as inactive and
fail here at once, rather than going red a month from now.
"""

from datetime import datetime, timedelta, timezone

from scheduled.queue_player_count import player_count_tag, QUEUE_TARGET

NOW = datetime(2020, 3, 10, 12, 0, tzinfo=timezone.utc)
PID = "25059"


def _pair(**extra):
    return {"code": "C06", "name": "Kibwe", "pbp_topic_ids": [int(PID)],
            "chat_topic_ids": [1], **extra}


def _cfg(pair=None, **extra):
    return {"topic_pairs": [pair or _pair()], "group_id": -100, **extra}


def _seat(n, days_ago=1, **extra):
    return {"user_id": str(1000 + n), "first_name": f"P{n}",
            "pbp_topic_id": PID,
            "last_post_time": (NOW - timedelta(days=days_ago)).isoformat(),
            **extra}


def _state(*seats):
    return {"players": {f"{PID}:{s['user_id']}": s for s in seats}}


def _posted(ago):
    """The campaign's last RP post, ``ago`` before NOW."""
    return {"topics": {PID: {"last_message_time": (NOW - ago).isoformat()}}}


def _tag(n, cfg=None, extra_seats=()):
    cfg = cfg or _cfg()
    state = _state(*[_seat(i) for i in range(n)], *extra_seats)
    return player_count_tag(cfg, state, cfg["topic_pairs"][0], NOW)


class TestTheTag:
    def test_the_target_is_six(self):
        assert QUEUE_TARGET == 6

    def test_below_target_warns(self):
        assert _tag(4) == " 👥 4/6 ⚠️"

    def test_at_target_is_plain(self):
        assert _tag(6) == " 👥 6/6"

    def test_above_target_is_good_not_a_warning(self):
        assert _tag(7) == " 👥 7/6"

    def test_a_per_campaign_roster_target_is_ignored(self):
        """Lewis: always 6, whatever the campaign's own roster_target says."""
        assert _tag(6, _cfg(_pair(roster_target=8))) == " 👥 6/6"

    def test_a_campaign_that_never_recruits_gets_no_target(self):
        cfg = _cfg(_pair(disabled_features=["recruitment"]))
        assert _tag(2, cfg) == " 👥 2"

    def test_an_explicit_recruit_tier_still_has_a_target(self):
        cfg = _cfg(_pair(disabled_features=["recruitment"], recruit_tier=1))
        assert _tag(2, cfg) == " 👥 2/6 ⚠️"

    def test_inactive_players_do_not_count(self):
        """Judged against the injected ``now``: 31 days back is out."""
        assert _tag(3, extra_seats=[_seat(9, days_ago=31)]) == " 👥 3/6 ⚠️"

    def test_permanent_players_are_shown_but_do_not_fill_the_target(self):
        perm = _seat(9, days_ago=90, permanent=True)
        assert _tag(5, extra_seats=[perm]) == " 👥 5/6 +1p ⚠️"

    def test_other_campaigns_players_are_not_counted(self):
        stray = _seat(9)
        stray["pbp_topic_id"] = "999"
        assert _tag(1, extra_seats=[stray]) == " 👥 1/6 ⚠️"

    def test_no_pair_means_no_tag(self):
        assert player_count_tag(_cfg(), _state(), None, NOW) == ""


class TestTheQueueShowsIt:
    def test_the_campaign_header_carries_the_count(self):
        from scheduled.queue_render import build_body_lines
        entry = {"name": "P0", "preview": "hi", "time": "2020-03-10 10:00:00"}
        scanned = {PID: {"campaign": "Kibwe", "code": "C06",
                         "entries": [entry]}}
        lines = build_body_lines(_cfg(), _state(_seat(0), _seat(1)), scanned,
                                 [PID], set(), {}, NOW)
        assert lines[0].startswith("━━ C06: Kibwe (1) 👥 2/6 ⚠️ ━━"), lines[0]

    def test_caught_up_and_silent_rows_carry_the_count(self):
        from scheduled.queue_silence import caught_up_campaigns, silent_campaigns
        recent = _posted(timedelta(hours=5))
        state = {**_state(*[_seat(i) for i in range(6)]), **recent}
        line = caught_up_campaigns(_cfg(), state, {}, NOW)[0]
        assert "C06: Kibwe 👥 6/6 - " in line, line
        quiet = _posted(timedelta(days=9))
        state = {**_state(*[_seat(i, days_ago=9) for i in range(3)]), **quiet}
        line = silent_campaigns(_cfg(), state, {}, NOW)[0]
        assert "C06: Kibwe 👥 3/6 ⚠️ - " in line, line

    def test_a_count_change_does_not_change_the_fingerprint(self):
        """A count change must not repost the queue: it is shown by the next
        in-place refresh. Silence ids are the only state the fingerprint
        reads besides the scan."""
        from scheduled.queue_silence import silent_ids, silent_rows
        quiet = _posted(timedelta(days=9))
        few = {**_state(_seat(0, days_ago=9)), **quiet}
        many = {**_state(*[_seat(i, days_ago=9) for i in range(7)]), **quiet}
        assert (silent_ids(silent_rows(_cfg(), few, {}, NOW))
                == silent_ids(silent_rows(_cfg(), many, {}, NOW)) == [PID])
