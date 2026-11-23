"""A player waiting on a silent GM still counts on the roster (2026-11-23).

C05 read 0/6 with all four players back, because the roster counted only
posts in the last 30 days while the sweep had stopped counting GM silences.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from commands.roster_members import _active_players  # noqa: E402

_NOW = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
_PID = "51357"


def _ago(days):
    return (_NOW - timedelta(days=days)).isoformat()


def _state(silences):
    return {"players": {f"{_PID}:7": {"user_id": "7", "first_name": "Ryo", "pbp_topic_id": _PID,
                                      "last_post_time": _ago(40)}},
            "post_timestamps": {}, "gm_silences": {_PID: silences}}


_CONFIG = {"gm_user_ids": [999], "topic_pairs": [{"name": "Grand Explorers", "code": "C05",
                                                  "pbp_topic_ids": [int(_PID)]}]}


def test_a_player_quiet_40_days_with_no_gm_silence_does_not_count():
    # ⭐ Can-fail counterpart: the GM posted yesterday and had no long gap.
    assert _active_players(_PID, _state({"last": _ago(1), "gaps": []}), _CONFIG, now=_NOW) == []


def test_the_same_player_counts_while_the_gm_was_the_silent_one():
    state = _state({"last": _ago(13), "gaps": [[_ago(39), _ago(13)]]})
    assert len(_active_players(_PID, state, _CONFIG, now=_NOW)) == 1
