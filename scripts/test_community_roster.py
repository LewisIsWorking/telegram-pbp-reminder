"""The weekly community roster post (2026-08-30).

Lewis, after "44 active players" turned out to be 19: *"You should be
able to give me the accurate figure more often, maybe once a week the bot
could post the full community roster."*

What is worth guarding
----------------------
**The quiet list must be the complement of the active list, not a second
opinion about it.** ``_active_players`` counts a permanent player through
any amount of silence, on purpose (the L20 rule). A quiet list that
re-tested ``last_post_time`` for itself would print that same person
under both "active" and "quiet 200d" in one post, which is exactly the
kind of self-contradiction this whole post exists to prevent.
``test_a_permanent_player_is_never_listed_as_quiet`` pins it.

The lifecycle half is thin on purpose: this post deletes nothing and
holds no message id, so the only state is a timestamp, and the only way
it can misbehave is by firing every hour.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

_NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
_GROUP = -100
_QUEUE_TOPIC = 146780


def _pair(code, pid, target=6, emoji="", disabled=None):
    pair = {"name": f"Camp {code}", "code": code, "roster_target": target,
            "pbp_topic_ids": [int(pid)], "chat_topic_id": int(pid) + 1}
    if emoji:
        pair["emoji"] = emoji
    if disabled:
        pair["disabled_features"] = disabled
    return pair


def _cfg(*pairs, **extra):
    cfg = {"group_id": _GROUP, "gm_queue_topic_id": _QUEUE_TOPIC,
           "bot_topic_id": 137393, "group_username": "Path_Wars",
           "topic_pairs": list(pairs)}
    cfg.update(extra)
    return cfg


def _seat(name, pid, days_ago=1, username=None, permanent=False):
    record = {"user_id": f"u{name}", "first_name": name,
              "pbp_topic_id": str(pid),
              "last_post_time": (_NOW - timedelta(days=days_ago)).isoformat()}
    if username:
        record["username"] = username
    if permanent:
        record["permanent"] = True
    return record


def _state(*seats):
    return {"players": {f"r{i}": s for i, s in enumerate(seats)}}


def _text(cfg, state, now=_NOW):
    from scheduled.community_roster_build import build_community_roster
    return build_community_roster(cfg, state, now)


class TestTheHeadlineShowsItsWorking:
    def _built(self):
        cfg = _cfg(_pair("C01", "100"), _pair("C02", "200"))
        state = _state(_seat("Ann", 100, username="ann"),
                       _seat("Ann", 200, username="ann"),
                       _seat("Bo", 100, username="bo", days_ago=90))
        return _text(cfg, state)

    def test_people_and_seats_are_both_reported(self):
        # ⭐ The whole reason for the post. Two people, three seats, and
        # quoting either number alone is what caused the confusion.
        text = self._built()
        assert "2 people hold 3 seats" in text

    def test_active_is_reported_separately_from_enrolled(self):
        assert "1 people (2 seats) have posted in the last 30 days" \
            in self._built()

    def test_the_window_is_stated_in_the_post(self):
        # ⭐⭐ A figure that does not name its basis gets read as whichever
        # basis flatters. The post says so in words, in itself.
        assert '"Active" means posted within 30 days' in self._built()


class TestEachCampaign:
    def test_players_are_named_with_their_usernames(self):
        text = _text(_cfg(_pair("C01", "100", emoji="🎲")),
                     _state(_seat("Ann", 100, username="ann"),
                            _seat("Bo", 100, username="bo")))
        assert "🎲 C01: Camp C01 - 2/6" in text
        assert "@ann, @bo" in text

    def test_a_player_with_no_username_is_still_named(self):
        text = _text(_cfg(_pair("C01", "100")), _state(_seat("Volf", 100)))
        assert "Volf" in text and "@Volf" not in text

    def test_an_empty_campaign_says_so(self):
        # C10 The Junction really is at zero. An empty line under a
        # heading reads as a rendering failure.
        assert "(nobody seated)" in _text(_cfg(_pair("C10", "900")), _state())

    def test_silent_seats_are_listed_with_how_long(self):
        text = _text(_cfg(_pair("C08", "107151")),
                     _state(_seat("Ann", 107151, username="ann"),
                            _seat("Old", 107151, username="old",
                                  days_ago=180)))
        assert "💤 @old 180d" in text
        assert "1/6" in text, "the silent seat must not pad the active count"

    def test_the_longest_silence_is_listed_first(self):
        text = _text(_cfg(_pair("C08", "107151")),
                     _state(_seat("Mid", 107151, username="mid",
                                  days_ago=100),
                            _seat("Old", 107151, username="old",
                                  days_ago=180)))
        assert text.index("@old") < text.index("@mid")


class TestQuietIsTheComplementOfActive:
    def test_a_permanent_player_is_never_listed_as_quiet(self):
        # ⭐⭐ The one that matters. _active_players counts a permanent
        # player through any silence (the L20 rule), so a quiet list that
        # re-tested last_post_time would print the same person as both
        # active and quiet-200d in a single post.
        text = _text(_cfg(_pair("C01", "100")),
                     _state(_seat("Perm", 100, username="perm",
                                  days_ago=200, permanent=True)))
        assert "@perm" in text
        assert "💤" not in text, (
            "a permanent player counts as active, so nothing should be "
            "listed as quiet")
        assert "1/6" in text

    def test_an_active_player_beside_a_permanent_one_is_not_called_quiet(self):
        # ⭐⭐ Added after a mutation SURVIVED. Replacing the subtraction
        # with `not p.get("permanent")` passed every test above, because
        # each fixture held ONE seat. With two, the mutation prints the
        # active player in the names line AND in the 💤 line of the same
        # block: one post, two contradictory claims about one person.
        text = _text(_cfg(_pair("C01", "100")),
                     _state(_seat("Live", 100, username="live", days_ago=2),
                            _seat("Perm", 100, username="perm",
                                  days_ago=200, permanent=True)))
        assert "@live, @perm" in text
        assert "💤" not in text, (
            "both seats count as active, so nothing is quiet; anything "
            "listed here is also listed above it")
        assert "2/6" in text

    def test_the_same_fixture_without_permanent_IS_quiet(self):
        # ⭐ can-fail counterpart. Without this the test above would pass
        # against a build that simply never emits a quiet line.
        text = _text(_cfg(_pair("C01", "100")),
                     _state(_seat("Perm", 100, username="perm",
                                  days_ago=200)))
        assert "💤 @perm 200d" in text and "0/6" in text


class TestOrphanRows:
    def test_rows_in_no_current_campaign_are_named_separately(self):
        # C11 Dark Pockets retired and left two roster rows behind. They
        # inflate every enrolment count, so the post names them rather
        # than letting them hide inside a total.
        text = _text(_cfg(_pair("C01", "100")),
                     _state(_seat("Ann", 100, username="ann"),
                            _seat("Luke", 1242, username="Luke_Skillen")))
        assert "In no current campaign: @Luke_Skillen" in text
        assert "1 people hold 1 seats" in text, (
            "an orphan row is not a seat in any campaign")

    def test_no_orphans_means_no_line(self):
        text = _text(_cfg(_pair("C01", "100")),
                     _state(_seat("Ann", 100, username="ann")))
        assert "In no current campaign" not in text
