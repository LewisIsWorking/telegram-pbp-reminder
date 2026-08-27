"""The three arrivals that predate the fix stay in the history.

Volf, Alastair Tan and Paul Rowan all joined on 2026-08-26 by posting,
the day before ``_track_player`` learned to record that. They were seated
correctly and left no ``player_history`` entry, so the roster history
Lewis reads showed nothing at all for the busiest recruitment day the
campaigns have had.

⭐ **The timestamps are derived, not invented.** Each one is that
player's first message in the campaign transcript
(``data/pbp_logs/<campaign>/2026-08.md``), which is real evidence of when
they arrived. ``last_post_time`` in state would have been wrong: it is
their MOST RECENT post, not their first, and using it would have dated
every arrival to whenever the backfill happened to run.

Split from ``test_new_player_join_is_recorded.py`` on 2026-08-27, which
had reached 201 of the 200-line limit. It is a different kind of test in
any case: that file proves behaviour against a fixture, this one asserts
against the shipped state file.
"""

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# name -> (campaign topic id, first post in the transcript)
BACKFILLED = {
    "Volf": ("76799", "2026-08-26T04:11:35+00:00"),
    "Alastair Tan": ("76799", "2026-08-26T06:16:35+00:00"),
    "Paul Rowan": ("52083", "2026-08-26T14:29:12+00:00"),
}


def _history() -> list:
    path = os.path.join(_ROOT, "data", "state", "players.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle).get("player_history", [])


def _joins() -> list:
    return [e for e in _history() if e.get("event") == "join"]


class TestTheBackfillSurvives:
    def test_the_history_is_not_empty(self):
        # ⭐ Without this, a state reset that wiped player_history would
        # make every assertion below vacuous against an empty list.
        assert len(_joins()) > 5

    def test_all_three_arrivals_are_present(self):
        names = {e["name"] for e in _joins()}
        missing = sorted(set(BACKFILLED) - names)
        assert not missing, f"backfilled joins lost from history: {missing}"

    def test_each_is_dated_from_its_first_transcript_post(self):
        # ⚠️ Not "some time on the 26th". The exact instant, because the
        # whole point of deriving them was to avoid inventing a number
        # that would then look like evidence.
        for name, (_pid, at) in BACKFILLED.items():
            entry = next(e for e in _joins() if e["name"] == name)
            assert entry["at"] == at, f"{name} dated {entry['at']}, expected {at}"

    def test_each_is_attached_to_the_right_campaign(self):
        for name, (pid, _at) in BACKFILLED.items():
            entry = next(e for e in _joins() if e["name"] == name)
            assert entry["pid"] == pid

    def test_none_of_them_got_a_duplicate(self):
        # The backfill refused to run twice by design, and a later
        # re-run of the same script must not be able to double them.
        for name in BACKFILLED:
            matches = [e for e in _joins() if e["name"] == name]
            assert len(matches) == 1, f"{name} has {len(matches)} join entries"


class TestTheyAreStillSeated:
    def test_every_backfilled_join_matches_a_real_seat(self):
        # ⭐⭐ A history entry for somebody who is not on the roster would
        # be worse than no entry: it reads as evidence. This ties the
        # backfill back to the seats it was derived from.
        path = os.path.join(_ROOT, "data", "state", "players.json")
        with open(path, encoding="utf-8") as handle:
            players = json.load(handle).get("players", {})
        for name, (pid, _at) in BACKFILLED.items():
            entry = next(e for e in _joins() if e["name"] == name)
            key = f"{pid}:{entry['user_id']}"
            assert key in players, (
                f"{name} has a join event but no seat at {key}; either the "
                f"backfill invented them or they have since left, in which "
                f"case a leave event should exist too")
