"""Retiring a campaign leaves its players behind, counted forever.

Removing a pair from ``config.json`` removes the campaign. It does not
remove the rows in ``state["players"]`` that point at its topic, and
nothing else ever will: every cleanup path is keyed by campaign, and the
campaign is gone.

C11 Dark Pockets was retired in #22. Two rows stayed on topic 1242, were
counted by ``/rosterplayers`` as unique players, and printed with a "?"
campaign code. Found 2026-08-25 when Lewis asked how 43 seats were
possible across his campaigns. Two of them were ghosts.

⚠️ The rows are SKIPPED, not deleted. They are history, and a count is
not a good enough reason to destroy history.

⭐ This is the shape worth remembering: **the leftovers of a deleted
parent are invisible precisely because the thing that would notice them
is the parent.** Ask what cleans up after a config entry is removed, and
if the answer is "the code that iterates config", nothing does.
"""

from datetime import datetime, timezone

from commands import roster_players

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)

CONFIG = {
    "topic_pairs": [
        {"code": "C04", "name": "Magni Guard", "pbp_topic_ids": [76799, 144765]},
        {"code": "C06", "name": "Kibwe", "pbp_topic_ids": [25059]},
    ],
    "permanent_user_ids": [],
}


def _seat(topic, uid, name, ago_days=3):
    stamp = (NOW.timestamp() - ago_days * 86400)
    return {"user_id": str(uid), "first_name": name, "pbp_topic_id": str(topic),
            "campaign_name": "whatever",
            "last_post_time": datetime.fromtimestamp(
                stamp, tz=timezone.utc).isoformat()}


def _state(*seats):
    return {"players": {f"{s['pbp_topic_id']}:{s['user_id']}": s
                        for s in seats}}


def _aggregate(state):
    return roster_players._aggregate_by_user(
        state, roster_players._pid_to_code(CONFIG), NOW, CONFIG)


class TestGhostSeats:
    def test_a_row_on_a_retired_topic_is_not_counted(self):
        by_user, _ = _aggregate(_state(_seat(1242, 999, "Ghost")))
        assert by_user == {}

    def test_a_live_row_still_is(self):
        # ⭐ can-fail counterpart. A filter that dropped everything would
        # satisfy the test above and quietly empty the roster.
        by_user, _ = _aggregate(_state(_seat(76799, 1, "Real")))
        assert list(by_user) == ["1"]

    def test_the_ghost_does_not_inflate_the_count_beside_a_real_one(self):
        by_user, _ = _aggregate(_state(_seat(76799, 1, "Real"),
                                       _seat(1242, 999, "Ghost")))
        assert len(by_user) == 1

    def test_a_ghost_is_not_flagged_at_risk_either(self):
        # Being nagged about a campaign that no longer exists is the same
        # bug wearing a louder hat.
        _by_user, at_risk = _aggregate(
            _state(_seat(1242, 999, "Ghost", ago_days=400)))
        assert at_risk == []

    def test_the_second_topic_of_a_two_topic_campaign_is_not_a_ghost(self):
        # ⚠️ C04 has two pbp topics. A filter keyed on only the first
        # would silently delete half a real campaign's roster, which is
        # a far worse bug than the one being fixed.
        by_user, _ = _aggregate(_state(_seat(144765, 7, "SecondTable")))
        assert list(by_user) == ["7"]

    def test_a_row_with_no_user_id_is_still_skipped(self):
        seat = _seat(76799, 1, "Real")
        seat["user_id"] = ""
        by_user, _ = _aggregate(_state(seat))
        assert by_user == {}


class TestAgainstTheRealState:
    def test_no_live_campaign_lost_its_players(self):
        # ⭐⭐ The check that matters, run against the shipped config and
        # the real state file: the fix must remove exactly the ghosts and
        # nothing else. Asserting on a fixture cannot tell the difference
        # between "dropped 2 ghosts" and "dropped 2 ghosts and a table".
        import json
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "config.json"), encoding="utf-8") as fh:
            config = json.load(fh)
        path = os.path.join(root, "data", "state", "players.json")
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)

        mapping = roster_players._pid_to_code(config)
        kept, dropped = set(), set()
        for player in state.get("players", {}).values():
            pid = str(player.get("pbp_topic_id", ""))
            (kept if pid in mapping else dropped).add(pid)

        assert kept, "every topic was dropped, so the mapping is broken"
        codes = {mapping[pid] for pid in kept}
        assert len(codes) >= 5, f"only {codes} survived, expected most campaigns"
        # Ghost topics are allowed to exist. Being counted is what is not.
        assert dropped <= {"1242"}, (
            f"unexpected unconfigured topics in state: {sorted(dropped)}. "
            f"Either a campaign was retired without a note, or the config "
            f"lost a pbp_topic_id it should still have.")
