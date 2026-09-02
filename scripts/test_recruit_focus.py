"""'Recruit for this next' focus post (2026-08-15).

Sibling to the queue focus message: that one names the campaign most in
need of a reply, this one the campaign most in need of players.

What is worth guarding here, and why
------------------------------------
The selection rule is the interesting part, and the exclusion is the part
most likely to rot. **C08 Theria has ``recruitment`` in
``disabled_features`` and would win on shortfall almost every day** — it
has the emptiest roster in the group. A version of this feature that
forgot the feature flag would look completely correct in testing against
a synthetic config and would name the one campaign Lewis has explicitly
switched off, every day, forever.

The lifecycle half is guarded elsewhere and deliberately not duplicated:
``test_state_keys_are_declared`` proves both state keys survive a save,
and ``test_bot_sent_scan_covers_state`` proves the message id reaches the
bot-sent registry so the delete is permitted. Those are the two things
that broke the schedule post; they are checked mechanically rather than
re-asserted by hand here.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

_NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
_GROUP = -100


def _pair(code, pid, target=None, emoji="", disabled=None):
    p = {"name": f"Camp {code}", "code": code, "chat_topic_id": int(pid) + 1,
         "pbp_topic_ids": [int(pid)]}
    if target is not None:
        p["roster_target"] = target
    if emoji:
        p["emoji"] = emoji
    if disabled:
        p["disabled_features"] = disabled
    return p


def _cfg(*pairs):
    return {"group_id": _GROUP, "gm_queue_topic_id": 146780,
            "bot_topic_id": 137393, "group_username": "Path_Wars",
            "topic_pairs": list(pairs)}


def _state(**counts):
    """counts: pid -> number of active players.

    Mirrors the real record shape read by ``commands.roster._active_players``:
    membership is ``pbp_topic_id`` (a single pid, not a list) and recency is
    ``last_post_time``. ``permanent`` is set so the count does not depend on
    a wall-clock cutoff — ``_active_players`` measures recency against the
    real ``datetime.now``, not the ``now`` passed into the job, so a
    non-permanent fixture would rot the day this test is run late enough.
    """
    players = {}
    for pid, n in counts.items():
        for i in range(n):
            players[f"{pid}_{i}"] = {
                "user_id": f"{pid}{i}", "full_name": f"P{i}",
                "pbp_topic_id": pid, "last_post_time": _NOW.isoformat(),
                "permanent": True,
            }
    return {"players": players}


class TestSelection:
    def test_picks_the_biggest_shortfall(self):
        from scheduled.recruit_focus import pick_recruit_pair
        cfg = _cfg(_pair("C01", "100", target=6), _pair("C02", "200", target=6))
        pair = pick_recruit_pair(cfg, _state(**{"100": 5, "200": 2}))
        assert pair["code"] == "C02", "4 missing beats 1 missing"

    def test_tie_breaks_on_the_lower_fill_ratio(self):
        """Same gap of one: 1-of-2 is emptier than 5-of-6."""
        from scheduled.recruit_focus import pick_recruit_pair
        cfg = _cfg(_pair("C01", "100", target=6), _pair("C02", "200", target=2))
        pair = pick_recruit_pair(cfg, _state(**{"100": 5, "200": 1}))
        assert pair["code"] == "C02"

    def test_full_campaigns_are_never_picked(self):
        from scheduled.recruit_focus import pick_recruit_pair
        cfg = _cfg(_pair("C01", "100", target=6))
        assert pick_recruit_pair(cfg, _state(**{"100": 6})) is None

    def test_over_target_is_not_a_negative_shortfall(self):
        from scheduled.recruit_focus import pick_recruit_pair
        cfg = _cfg(_pair("C01", "100", target=4))
        assert pick_recruit_pair(cfg, _state(**{"100": 7})) is None


class TestRecruitmentDisabledIsExcluded:
    """The exclusion most likely to be forgotten, and the costliest.

    C08 Theria really does carry disabled_features ["warnings",
    "recruitment"] in the live config, and really does have the emptiest
    roster. Without the flag check it wins every day.
    """

    def test_a_disabled_campaign_never_wins(self):
        from scheduled.recruit_focus import pick_recruit_pair
        cfg = _cfg(_pair("C08", "107151", target=6,
                         disabled=["warnings", "recruitment"]),
                   _pair("C01", "100", target=6))
        pair = pick_recruit_pair(cfg, _state(**{"107151": 0, "100": 5}))
        assert pair["code"] == "C01", (
            "C08 has a shortfall of 6 to C01's 1, but recruitment is "
            "switched off for it")

    def test_disabled_and_alone_means_no_message(self):
        from scheduled.recruit_focus import pick_recruit_pair
        cfg = _cfg(_pair("C08", "107151", target=6,
                         disabled=["recruitment"]))
        assert pick_recruit_pair(cfg, _state(**{"107151": 0})) is None

    def test_disabled_campaigns_are_not_counted_in_the_total(self):
        """The '<n> campaigns currently short' line must agree."""
        from scheduled.recruit_focus import build_recruit_message
        cfg = _cfg(_pair("C08", "107151", target=6, disabled=["recruitment"]),
                   _pair("C01", "100", target=6))
        text, _chosen = build_recruit_message(cfg, _state(**{"107151": 0, "100": 5}))
        assert "only campaign currently below target" in text


class TestMessage:
    def _text(self):
        from scheduled.recruit_focus import build_recruit_message
        cfg = _cfg(_pair("C05", "51357", target=6, emoji="🔭"),
                   _pair("C01", "100", target=6))
        return build_recruit_message(cfg, _state(**{"51357": 2, "100": 5}))[0]

    def test_names_the_campaign_with_its_emoji(self):
        assert "🧭 This table has room: 🔭 C05: Camp C05" in self._text()

    def test_states_seats_and_the_ratio(self):
        assert "4 seats open (2/6 players)." in self._text()

    def test_one_seat_is_singular(self):
        from scheduled.recruit_focus import build_recruit_message
        cfg = _cfg(_pair("C01", "100", target=6))
        text, _chosen = build_recruit_message(cfg, _state(**{"100": 5}))
        assert "1 seat open" in text and "1 seats" not in text

    def test_links_to_the_chat_topic_not_the_pbp_topic(self):
        # ⛔ Lewis, 2026-09-02, on the live C01 advert: "why does this not
        # link to DF chat?" It linked to 25059, the in-character thread.
        # The line answers "Know someone?", so it is the link you forward
        # to a prospective player, and it dropped them somewhere they
        # cannot ask to join without posting OOC in the middle of a
        # scene. _pair() sets chat_topic_id to pid + 1.
        text = self._text()
        assert "🔗 https://t.me/Path_Wars/51358" in text
        assert "https://t.me/Path_Wars/51357" not in text, (
            "still linking to the in-character pbp topic")

    def test_the_real_c01_advert_links_to_df_chat(self):
        # The live numbers from the message Lewis pasted, so the case is
        # recognisable rather than abstract: C01 pbp 25059, chat 21514.
        from scheduled.recruit_focus import build_recruit_message
        cfg = _cfg({"name": "Doomsday Funtime", "code": "C01",
                    "chat_topic_id": 21514, "pbp_topic_ids": [25059, 22566],
                    "roster_target": 6})
        text, _ = build_recruit_message(cfg, _state(**{"25059": 3}))
        assert "🔗 https://t.me/Path_Wars/21514" in text
        assert "25059" not in text

    def test_a_private_group_gets_no_link_line_rather_than_a_fake_one(self):
        # Private groups have no t.me/<name> form. Omitting the line is
        # the honest outcome; a half-built URL would look clickable.
        from scheduled.recruit_link import recruit_link
        pair = {"chat_topic_id": 21514, "pbp_topic_ids": [25059]}
        assert recruit_link(pair, {}) == ""
        assert recruit_link(pair, {"group_username": "Path_Wars"}) == (
            "🔗 https://t.me/Path_Wars/21514")

    def test_a_campaign_with_no_chat_topic_still_gets_a_link(self):
        # can-fail counterpart: the fallback must not silently drop the
        # link entirely. A recruit advert with no way to reach the
        # campaign is worse than one pointing at the wrong thread.
        from scheduled.recruit_focus import build_recruit_message
        cfg = _cfg({"name": "Camp C01", "code": "C01",
                    "pbp_topic_ids": [100], "roster_target": 6})
        text, _ = build_recruit_message(cfg, _state(**{"100": 5}))
        assert "🔗 https://t.me/Path_Wars/100" in text

    def test_counts_the_other_short_campaigns(self):
        assert "biggest gap of 2 campaigns" in self._text()
        assert "Know someone?" in self._text(), (
            "the post is read by players now; give them the action")

    def test_empty_when_nothing_is_short(self):
        from scheduled.recruit_focus import build_recruit_message
        cfg = _cfg(_pair("C01", "100", target=6))
        assert build_recruit_message(cfg, _state(**{"100": 6})) == ("", None)
