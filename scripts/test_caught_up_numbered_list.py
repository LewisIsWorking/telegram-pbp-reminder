"""The "All caught up" notice lists its players as a numbered list.

Lewis, 2026-10-12, on a C04 notice that ran four names together on one
line: *"Could this be a numbered list?"*
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from test_per_topic_slim_format import (  # noqa: E402
    _config_with_perms, _player, _state_with)


def test_players_are_a_numbered_list():
    from scheduled.per_topic_caught_up import build_caught_up_text
    state = _state_with(_player("1", "alice"), _player("2", "bob"))
    lines = build_caught_up_text("100", state,
                                 _config_with_perms()).splitlines()
    assert lines[0] == "📋 All caught up. Time for players to post!"
    assert len(lines) == 3, lines
    assert lines[1].startswith("1. ") and lines[2].startswith("2. ")
    assert sorted(l.split("@")[1].rstrip(")") for l in lines[1:]) == [
        "alice", "bob"]
